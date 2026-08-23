import asyncio
import sys
from concurrent.futures import ThreadPoolExecutor
from db import db
from bot_registry import bot_registry
from offset_manager import offset_manager
from poller import poller_supervisor
from dispatcher import dispatcher
from telegram_adapter import telegram_pool
from priority_queue import job_queue
from broadcast_engine import broadcast_engine
import scheduler

# telegram_adapter.py runs HTTP calls (including long-polling getUpdates,
# which blocks its thread for up to ~40s) via asyncio.to_thread(), since we
# use stdlib urllib.request instead of a truly-async HTTP client - this
# keeps `pip install` from ever needing to build/download anything (see
# telegram_adapter.py's module docstring for why). The trade-off is that
# each concurrently-polled bot needs its own OS thread for the duration of
# its poll. Python's default executor caps out around 32 threads, which
# would bottleneck well before 100 bots, so we size it explicitly here.
MAX_CONCURRENT_BOTS = 200

async def _health_monitor():
    """Periodic status log so silent failures are visible instead of
    just disappearing into the console scrollback."""
    while True:
        await asyncio.sleep(60)
        try:
            q = job_queue.get_status()
            p = poller_supervisor.get_status()
            offline = [bid for bid, info in p.items() if not info["running"]]
            print(f"💓 health: queue={q['total_queued']} queued/"
                  f"{q['active_jobs']} active | pollers={len(p)} total, "
                  f"{len(offline)} offline {offline if offline else ''}")
        except Exception as e:
            print(f"⚠️ health_monitor error: {type(e).__name__}: {e}")

async def main():
    """Main entry point - Phases 1-6"""
    print("🏭 NEXA Factory Engine - Starting")
    print("=" * 50)
    
    # Must be set before any polling/HTTP work starts (see comment above).
    asyncio.get_event_loop().set_default_executor(
        ThreadPoolExecutor(max_workers=MAX_CONCURRENT_BOTS)
    )
    
    # Phase 1: Initialize database
    await db.init()
    
    # Phase 1: Load registered bots
    await bot_registry.load_bots()
    
    # Auto-register the master factory bot from .env if configured and
    # not already in the database (first run only - after that it's just
    # a normal row in `bots`).
    from config import FACTORY_BOT_TOKEN, FACTORY_BOT_ID
    if FACTORY_BOT_ID is not None and not bot_registry.get_bot(FACTORY_BOT_ID):
        from telegram_adapter import TelegramAdapter
        temp = TelegramAdapter(FACTORY_BOT_TOKEN, timeout=10)
        await temp.init()
        info = await temp.get_me()
        await temp.close()
        if info.get("ok"):
            uname = info["result"].get("username", str(FACTORY_BOT_ID))
            # owner_id: the factory bot has no single "owner" in the
            # normal admin-panel sense (it's driven entirely by
            # factory_bot.py, dispatcher routes it away from admin_panel
            # before owner_id is ever consulted) - self-owned satisfies
            # the "must be a positive int" validation in db.add_bot.
            await bot_registry.register_bot(FACTORY_BOT_ID, FACTORY_BOT_TOKEN, owner_id=FACTORY_BOT_ID, username=uname)
            print(f"🏭 Factory bot registered: @{uname}")
        else:
            print(f"❌ FACTORY_BOT_TOKEN is set but invalid: {info}")

    # Keep Telegram's slash-command menu aligned with the public/admin
    # permissions before pollers start receiving updates.
    from command_menu import sync_all_commands
    await sync_all_commands()
    
    # Phase 2: Load offsets
    await offset_manager.load_offsets()
    
    if bot_registry.count() == 0:
        print("⚠️ No bots registered yet")
        print("\nTo add a bot:")
        print("  1. Go to @BotFather on Telegram")
        print("  2. Create a new bot and get the token")
        print("  3. Register it using:")
        print("     await bot_registry.register_bot(bot_id, token, owner_id, username)")
    else:
        print(f"✅ {bot_registry.count()} bot(s) loaded:")
        for bot in bot_registry.list_bots():
            print(f"   - Bot #{bot['bot_id']}: @{bot['username']}")
    
    print("\n🏭 NEXA Factory - Status:")
    print("   ✅ Phase 1: Database + Registry")
    print("   ✅ Phase 2: Long Polling (async)")
    print("   ✅ Phase 3: Priority Queue + Rate Limiting")
    print("   ✅ Phase 4: Message Handlers + Subscriptions")
    print("   ✅ Phase 5: Broadcast Engine (streaming)")
    print("   ✅ Phase 6: Backup System (Excel)")
    print("=" * 50)
    
    # Set dispatcher callback for poller
    poller_supervisor.on_update = dispatcher.dispatch
    
    # Create pollers for all registered bots
    for bot in bot_registry.list_bots():
        await poller_supervisor.add_poller(bot['bot_id'], bot['token'])
    
    # Resume any broadcast that was mid-flight when the process last died
    await broadcast_engine.resume_pending_broadcasts()
    
    print("\n🚀 Starting all services...")
    
    # Start workers, pollers, and health monitoring concurrently.
    # job_queue.start_workers() and poller_supervisor.start_all() each run
    # their own internal watchdog and restart their sub-tasks on crash, so
    # under normal operation these three coroutines never return - if they
    # do, it's an unrecovered fault and we treat it as fatal rather than
    # silently swallowing it.
    tasks = [
        asyncio.create_task(job_queue.start_workers()),
        asyncio.create_task(poller_supervisor.start_all()),
        asyncio.create_task(_health_monitor()),
        asyncio.create_task(scheduler.run_forever()),
    ]
    
    try:
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        
        for task in done:
            exc = task.exception()
            if exc:
                print(f"🔴 Fatal: a core service crashed: {type(exc).__name__}: {exc}")
                try:
                    await db.add_log("error", "engine", f"Fatal: core service crashed: {type(exc).__name__}: {exc}")
                except Exception:
                    pass  # DB itself may be the thing that's down - don't mask the original error
            else:
                print(f"🔴 Fatal: a core service exited unexpectedly")
        
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        
        raise RuntimeError("core service exited - see log above")
    
    except KeyboardInterrupt:
        print("\n⏹️ Shutting down gracefully...")
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await job_queue.stop_workers()
        await poller_supervisor.stop_all()
        await telegram_pool.close_all()
        await db.close()
        print("✅ Goodbye!")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        print(f"❌ Fatal error: {type(e).__name__}: {e}")
        sys.exit(1)
