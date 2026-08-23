#!/usr/bin/env python3
"""
Test Phase 2: Async Long Polling
"""

import asyncio
from db import db
from bot_registry import bot_registry
from offset_manager import offset_manager
from poller import poller_supervisor
from dispatcher import dispatcher
from telegram_adapter import telegram_pool

async def test_phase2():
    print("🧪 Phase 2 Testing: Async Long Polling")
    print("=" * 50)
    
    # Initialize
    await db.init()
    await bot_registry.load_bots()
    await offset_manager.load_offsets()
    
    # Add test bot if not exists
    print("\n✓ Test 1: Add Test Bot")
    bot_id = 123456789
    token = "1234567890:ABCDEFghijklmn"  # REPLACE WITH REAL TOKEN
    
    existing_bot = bot_registry.get_bot(bot_id)
    if not existing_bot:
        success = await bot_registry.register_bot(bot_id, token, 111, "@TestBot")
        if success:
            print("  ✅ Test bot registered")
        else:
            print("  ⚠️ Could not register (may already exist)")
    else:
        print(f"  ✅ Bot already exists: @{existing_bot['username']}")
    
    # Test Telegram adapter
    print("\n✓ Test 2: Telegram Adapter")
    try:
        adapter = await telegram_pool.get_adapter(token)
        me = await adapter.get_me()
        
        if me.get("ok"):
            bot_info = me.get("result", {})
            print(f"  ✅ Bot info retrieved: @{bot_info.get('username')}")
        else:
            print(f"  ❌ Error: {me.get('description', 'Unknown error')}")
            print("  ⚠️ Check if token is valid")
    except Exception as e:
        print(f"  ❌ Error: {e}")
    
    # Test poller creation
    print("\n✓ Test 3: Create Poller")
    poller_supervisor.on_update = dispatcher.dispatch
    await poller_supervisor.add_poller(bot_id, token)
    print(f"  ✅ Poller created")
    
    # Test offset manager
    print("\n✓ Test 4: Offset Manager")
    offset = offset_manager.get_offset(bot_id)
    print(f"  ✅ Current offset: {offset}")
    
    # Test polling (5 seconds only)
    print("\n✓ Test 5: Test Polling (5 seconds)")
    print("  🔄 Starting poller (send a message to your bot to test)...")
    
    # Run poller for 5 seconds only
    poller = poller_supervisor.pollers.get(bot_id)
    if poller:
        async def run_for_5s():
            try:
                await asyncio.wait_for(poller.start(), timeout=5)
            except asyncio.TimeoutError:
                await poller.stop()
                print("  ✅ Test completed")
        
        await run_for_5s()
    
    # Final status
    print("\n" + "=" * 50)
    print("✅ Phase 2 Tests Complete!")
    print("=" * 50)
    
    await telegram_pool.close_all()
    await db.close()

if __name__ == "__main__":
    print("\n⚠️ IMPORTANT: Replace token in test with real bot token from BotFather\n")
    
    asyncio.run(test_phase2())
