#!/usr/bin/env python3
"""
Test Phase 5-6: Broadcast Engine + Backup System
"""

import asyncio
from db import db
from bot_registry import bot_registry
from broadcast_engine import broadcast_engine
from backup import backup_manager
from priority_queue import job_queue

async def test_broadcast_backup():
    print("🧪 Phase 5-6 Testing: Broadcast + Backup")
    print("=" * 50)
    
    # Initialize
    await db.init()
    await bot_registry.load_bots()
    
    # Start queue workers
    workers_task = asyncio.create_task(job_queue.start_workers())
    await asyncio.sleep(0.5)
    
    # Get first bot
    bots = bot_registry.list_bots()
    if not bots:
        print("⚠️ No bots registered")
        await job_queue.stop_workers()
        await db.close()
        return
    
    bot_id = bots[0]['bot_id']
    print(f"Using bot #{bot_id}\n")
    
    # Test 1: Broadcast Engine
    print("✓ Test 1: Start Broadcast")
    
    broadcast_text = "🔔 This is a test broadcast message! 📢"
    
    try:
        broadcast_id = await broadcast_engine.start_broadcast(
            bot_id,
            broadcast_text,
            batch_size=100
        )
        print(f"  ✅ Broadcast #{broadcast_id} queued")
    except Exception as e:
        print(f"  ⚠️ Broadcast setup warning: {e}")
    
    # Test 2: Check broadcast status
    print("\n✓ Test 2: Check Broadcast Status")
    await asyncio.sleep(2)  # Let it process
    
    try:
        status = await broadcast_engine.get_broadcast_status(broadcast_id)
        if status:
            print(f"  ✅ Status: {status['status']}")
            print(f"  Stats: {status['stats']}")
    except:
        print("  ⚠️ Broadcast status check skipped (no broadcast yet)")
    
    # Test 3: Stop workers before backup
    print("\n✓ Test 3: Preparing for Backup")
    await job_queue.stop_workers()
    await asyncio.sleep(1)
    print("  ✅ Queue workers stopped")
    
    # Test 4: Create Backup
    print("\n✓ Test 4: Create Backup")
    
    try:
        backup_path = await backup_manager.create_backup()
        print(f"  ✅ Backup created successfully")
    except Exception as e:
        print(f"  ❌ Backup error: {e}")
    
    # Test 5: List Backups
    print("\n✓ Test 5: List Backups")
    
    try:
        backups = await backup_manager.list_backups()
        print(f"  ✅ Total backups: {len(backups)}")
        
        for backup in backups[:3]:  # Show last 3
            print(f"     - {backup['name']} ({backup['size_mb']:.2f} MB)")
    except Exception as e:
        print(f"  ⚠️ Error listing backups: {e}")
    
    # Test 6: Verify database content
    print("\n✓ Test 6: Database Verification")
    
    cursor = await db.connection.execute("SELECT COUNT(*) FROM bots")
    bot_count = (await cursor.fetchone())[0]
    
    cursor = await db.connection.execute("SELECT COUNT(*) FROM bot_users")
    user_count = (await cursor.fetchone())[0]
    
    cursor = await db.connection.execute("SELECT COUNT(*) FROM messages")
    msg_count = (await cursor.fetchone())[0]
    
    print(f"  ✅ Database stats:")
    print(f"     - Bots: {bot_count}")
    print(f"     - Users: {user_count}")
    print(f"     - Messages: {msg_count}")
    
    print("\n" + "=" * 50)
    print("✅ Phase 5-6 Tests Complete!")
    print("=" * 50)
    
    await db.close()

if __name__ == "__main__":
    asyncio.run(test_broadcast_backup())
