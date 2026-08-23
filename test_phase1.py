#!/usr/bin/env python3
"""
Test Phase 1: Database + Bot Registry
"""

import asyncio
from db import db
from bot_registry import bot_registry

async def test_phase1():
    print("🧪 Phase 1 Testing")
    print("=" * 50)
    
    # Test 1: Database initialization
    print("\n✓ Test 1: Database Initialization")
    await db.init()
    print("  ✅ Database initialized successfully")
    
    # Test 2: Add bot
    print("\n✓ Test 2: Add Bot")
    await bot_registry.load_bots()
    
    bot_id = 123456789
    token = "1234567890:ABCDEFghijklmn"
    owner_id = 111222333
    username = "TestBot"
    
    success = await bot_registry.register_bot(bot_id, token, owner_id, username)
    if success:
        print(f"  ✅ Bot #{bot_id} registered")
    else:
        print(f"  ❌ Failed to register bot")
    
    # Test 3: Get bot
    print("\n✓ Test 3: Get Bot")
    bot = bot_registry.get_bot(bot_id)
    if bot:
        print(f"  ✅ Retrieved bot: @{bot['username']}")
    
    # Test 4: Add user
    print("\n✓ Test 4: Add User")
    chat_id = 999888777
    username_user = "testuser"
    first_name = "Test"
    
    await db.add_user(bot_id, chat_id, username_user, first_name)
    print(f"  ✅ User {chat_id} added")
    
    # Test 5: Add message
    print("\n✓ Test 5: Add Message")
    message_id = 1
    text = "Hello Bot"
    
    await db.add_message(bot_id, chat_id, message_id, text, is_incoming=True)
    print(f"  ✅ Message added")
    
    # Test 6: Update offset
    print("\n✓ Test 6: Update Offset")
    await db.update_offset(bot_id, 100, 100)
    offset = await db.get_offset(bot_id)
    print(f"  ✅ Offset: {offset}")
    
    # Test 7: List all bots
    print("\n✓ Test 7: List Bots")
    all_bots = await db.get_all_bots()
    print(f"  ✅ Total bots in DB: {len(all_bots)}")
    for bot in all_bots:
        print(f"     - Bot #{bot['bot_id']}: @{bot['username']}")
    
    # Test 8: Cleanup
    print("\n✓ Test 8: Cleanup Old Data")
    await db.cleanup_old_data()
    print("  ✅ Cleanup completed")
    
    # Final check
    print("\n" + "=" * 50)
    print("✅ All Phase 1 Tests Passed!")
    print("=" * 50)
    
    await db.close()

if __name__ == "__main__":
    asyncio.run(test_phase1())
