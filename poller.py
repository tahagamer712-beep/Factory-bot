import asyncio
from typing import Callable, Optional, List
from telegram_adapter import telegram_pool
from offset_manager import offset_manager
from bot_registry import bot_registry
from config import LONG_POLL_TIMEOUT
import time

class BotPoller:
    """
    Single bot long poller
    Each bot gets its own async task
    """
    
    def __init__(self, bot_id: int, token: str, on_update: Callable):
        self.bot_id = bot_id
        self.token = token
        self.on_update = on_update  # Callback when update arrives
        self.is_running = False
        self.should_run = False  # intent flag - stays True across transient failures
        self.last_poll_time = 0
        self.failed_attempts = 0
        self.max_backoff = 300  # 5 minutes cap - never give up entirely
    
    async def start(self):
        """Start polling for this bot. Retries forever on failure (capped backoff)."""
        self.is_running = True
        self.should_run = True
        print(f"🟢 Poller started for bot #{self.bot_id}")
        
        while self.should_run:
            try:
                await self._poll_once()
                self.failed_attempts = 0  # Reset on success
            
            except asyncio.CancelledError:
                raise
            except (ConnectionError, TimeoutError, OSError) as e:
                # Network-level issues (e.g. wifi drop) - keep retrying, never give up
                self.failed_attempts += 1
                wait_time = min(2 ** self.failed_attempts, self.max_backoff)
                print(f"🌐 Bot #{self.bot_id}: network issue ({e}) - retry in {wait_time}s")
                await asyncio.sleep(wait_time)
            except Exception as e:
                # Unexpected error - log with type, keep retrying with capped backoff
                self.failed_attempts += 1
                wait_time = min(2 ** self.failed_attempts, self.max_backoff)
                print(f"❌ Poll error for bot #{self.bot_id}: {type(e).__name__}: {e} "
                      f"(attempt {self.failed_attempts}, retry in {wait_time}s)")
                if self.failed_attempts in (1, 5, 10) or self.failed_attempts % 20 == 0:
                    # Log to DB too (not every single retry - just enough
                    # to be visible in the factory admin panel without
                    # flooding the logs table)
                    from db import db
                    await db.add_log("error", f"bot:{self.bot_id}",
                                      f"Poll error ({self.failed_attempts} attempts): {type(e).__name__}: {e}")
                await asyncio.sleep(wait_time)
        
        self.is_running = False
    
    async def _poll_once(self):
        """Single poll iteration"""
        adapter = await telegram_pool.get_adapter(self.token)
        offset = offset_manager.get_offset(self.bot_id)
        
        # Get updates (long polling, non-blocking)
        result = await adapter.get_updates(
            offset=offset,
            timeout=LONG_POLL_TIMEOUT,
            limit=100
        )
        
        self.last_poll_time = time.time()
        
        if result.get("ok"):
            updates = result.get("result", [])
            
            if updates:
                print(f"📨 Bot #{self.bot_id}: {len(updates)} update(s)")
                
                # Process each update. If dispatch fails for one, we stop advancing
                # the offset past it so it gets redelivered on next poll instead of
                # being silently dropped.
                for update in updates:
                    update_id = update.get("update_id")
                    
                    try:
                        await self.on_update(self.bot_id, update)
                    except Exception as e:
                        print(f"❌ Bot #{self.bot_id}: handler failed on update {update_id}: "
                              f"{type(e).__name__}: {e}")
                        break
                    
                    await offset_manager.update_offset(self.bot_id, update_id)
        
        elif "timeout" in str(result.get("error", "")):
            # Timeout is normal in long polling - not a failure
            pass
        else:
            # Real API error (bad token, etc) - surface it as an exception so the
            # retry/backoff loop above handles it instead of silently looping.
            raise RuntimeError(f"getUpdates failed: {result.get('error', 'unknown error')}")
    
    async def stop(self):
        """Stop polling"""
        self.should_run = False
        print(f"⏹️ Poller stopped for bot #{self.bot_id}")


class PollerSupervisor:
    """
    Manages all bot pollers
    Runs them concurrently with asyncio
    """
    
    def __init__(self, on_update: Callable):
        self.pollers = {}  # bot_id -> BotPoller
        self.tasks = {}    # bot_id -> asyncio.Task
        self.on_update = on_update
        self.is_running = False
    
    async def add_poller(self, bot_id: int, token: str):
        """Add new bot to polling"""
        if bot_id not in self.pollers:
            poller = BotPoller(bot_id, token, self.on_update)
            self.pollers[bot_id] = poller
            print(f"✅ Poller created for bot #{bot_id}")
    
    async def add_and_start_poller(self, bot_id: int, token: str):
        """Register AND immediately start polling a bot at runtime - used
        when the factory bot registers a brand-new bot, so it goes live
        without needing to restart the whole process."""
        await self.add_poller(bot_id, token)
        if bot_id not in self.tasks or self.tasks[bot_id].done():
            self.tasks[bot_id] = asyncio.create_task(self.pollers[bot_id].start())
            print(f"🚀 Poller live for bot #{bot_id} (hot-added)")
    
    async def remove_poller(self, bot_id: int):
        """Remove bot from polling"""
        if bot_id in self.pollers:
            await self.pollers[bot_id].stop()
            task = self.tasks.pop(bot_id, None)
            if task and not task.done():
                task.cancel()
            del self.pollers[bot_id]
            print(f"✅ Poller removed for bot #{bot_id}")
    
    async def start_all(self):
        """Start all pollers concurrently, with a watchdog that restarts
        any poller task that dies unexpectedly (crash, not explicit stop)."""
        self.is_running = True
        print(f"\n🚀 Starting {len(self.pollers)} poller(s) concurrently")
        
        for bot_id, poller in self.pollers.items():
            self.tasks[bot_id] = asyncio.create_task(poller.start())
        
        # Watchdog loop: since BotPoller.start() itself retries forever on
        # transient errors, a task only *completes* if should_run was set
        # False (explicit stop) or an unhandled crash escaped the poller's
        # own try/except. In the latter case, restart it.
        while self.is_running:
            await asyncio.sleep(10)
            for bot_id, task in list(self.tasks.items()):
                if task.done() and self.is_running:
                    poller = self.pollers.get(bot_id)
                    if poller and poller.should_run:
                        exc = task.exception() if not task.cancelled() else None
                        print(f"🔁 Bot #{bot_id}: poller task died unexpectedly "
                              f"({exc}) - restarting")
                        from db import db
                        await db.add_log("error", f"bot:{bot_id}", f"Poller task crashed and restarted: {exc}")
                        self.tasks[bot_id] = asyncio.create_task(poller.start())
    
    async def stop_all(self):
        """Stop all pollers"""
        self.is_running = False
        print("\n⏹️ Stopping all pollers...")
        
        for poller in self.pollers.values():
            await poller.stop()
        
        for task in self.tasks.values():
            if not task.done():
                task.cancel()
        await asyncio.gather(*self.tasks.values(), return_exceptions=True)
    
    def get_status(self) -> dict:
        """Get status of all pollers"""
        status = {}
        for bot_id, poller in self.pollers.items():
            status[bot_id] = {
                "running": poller.is_running,
                "last_poll": poller.last_poll_time,
                "failed_attempts": poller.failed_attempts
            }
        return status

# Global instance
poller_supervisor = PollerSupervisor(on_update=None)  # on_update set in main.py
