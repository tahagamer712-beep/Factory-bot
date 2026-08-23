#!/usr/bin/env python3
"""
Test Phase 4: Message Handlers
"""

import asyncio
from db import db
from bot_registry import bot_registry
from offset_manager import offset_manager
from message_handler import message_handler
from subscription_handler import subscription_handler
from auto_reply_manager import auto_reply_manager
from priority_queue import job_queue

async def test_phase4():
    print("🧪 Phase 4 Testing: Message Handlers")
    print("=" * 50)
    
    # Initialize
    await db.init()
    await bot_registry.load_bots()
    await offset_manager.load_offsets()
    
    # Start queue workers in background
    workers_task = asyncio.create_task(job_queue.start_workers())
    await asyncio.sleep(0.5)
    
    # Get first bot for testing
    bots = bot_registry.list_bots()
    if not bots:
        print("⚠️ No bots registered. Please register a bot first.")
        await job_queue.stop_workers()
        await db.close()
        return
    
    bot_id = bots[0]['bot_id']
    print(f"✅ Using bot #{bot_id} for testing\n")
    
    # Test 1: Add auto-replies
    print("✓ Test 1: Auto-Reply Manager")
    await auto_reply_manager.add_auto_reply(
        bot_id,
        r"السلام|أهلا|مرحبا",
        "وعليكم السلام ورحمة الله وبركاته ❤️"
    )
    await auto_reply_manager.add_auto_reply(
        bot_id,
        r"شكرا|thank you|thanks",
        "أهلاً وسهلاً 😊"
    )
    
    replies = await auto_reply_manager.get_auto_replies(bot_id)
    print(f"  ✅ {len(replies)} auto-reply(ies) added")
    
    # Test 2: Add subscriptions
    print("\n✓ Test 2: Subscription Handler")
    await subscription_handler.add_subscription(bot_id, "@MyChannel", mandatory=True)
    await subscription_handler.add_subscription(bot_id, "@MyGroup", mandatory=False)
    
    subs = await subscription_handler.get_subscriptions(bot_id)
    print(f"  ✅ {len(subs)} subscription(s) added")
    for sub in subs:
        status = "mandatory" if sub['is_mandatory'] else "optional"
        print(f"     - {sub['channel_id']} ({status})")
    
    # Test 3: Simulate incoming message
    print("\n✓ Test 3: Handle Incoming Message")
    
    test_message = {
        "message_id": 1,
        "date": 1234567890,
        "chat": {"id": 999888777, "type": "private"},
        "from": {
            "id": 999888777,
            "is_bot": False,
            "first_name": "TestUser",
            "username": "testuser"
        },
        "text": "السلام عليكم"
    }
    
    print("  Simulating message: 'السلام عليكم'")
    await message_handler.handle_message(bot_id, test_message)
    print("  ✅ Message processed")
    
    # Test 4: Test command
    print("\n✓ Test 4: Handle Command")
    
    test_command = {
        "message_id": 2,
        "date": 1234567891,
        "chat": {"id": 999888777, "type": "private"},
        "from": {
            "id": 999888777,
            "is_bot": False,
            "first_name": "TestUser",
            "username": "testuser"
        },
        "text": "/start"
    }
    
    print("  Simulating command: '/start'")
    await message_handler.handle_message(bot_id, test_command)
    print("  ✅ Command processed (job queued)")
    
    # Test 5: Check queue status
    print("\n✓ Test 5: Queue Status")
    status = job_queue.get_status()
    print(f"  ✅ Queue status:")
    print(f"     - Total queued: {status['total_queued']}")
    print(f"     - Active jobs: {status['active_jobs']}")
    print(f"     - Completed: {status['completed_jobs']}")
    print(f"     - By priority: {status['queue_sizes']}")
    
    # Wait for jobs to complete
    print("\n  Waiting for jobs to complete...")
    await asyncio.sleep(3)
    
    # Test 6: Check database
    print("\n✓ Test 6: Database Verification")
    
    cursor = await db.connection.execute(
        "SELECT COUNT(*) FROM messages WHERE bot_id = ?",
        (bot_id,)
    )
    msg_count = (await cursor.fetchone())[0]
    print(f"  ✅ Messages in database: {msg_count}")
    
    cursor = await db.connection.execute(
        "SELECT COUNT(*) FROM events WHERE bot_id = ? AND event_type = 'message'",
        (bot_id,)
    )
    event_count = (await cursor.fetchone())[0]
    print(f"  ✅ Events logged: {event_count}")
    
    # Test 7: Toggle auto-reply
    print("\n✓ Test 7: Toggle Auto-Reply")
    await auto_reply_manager.toggle_auto_reply(bot_id, r"السلام|أهلا|مرحبا", False)
    print("  ✅ Auto-reply disabled")
    
    # Stop workers
    await job_queue.stop_workers()
    
    print("\n" + "=" * 50)
    print("✅ Phase 4 Tests Complete!")
    print("=" * 50)
    
    await db.close()

if __name__ == "__main__":
    asyncio.run(test_phase4())
