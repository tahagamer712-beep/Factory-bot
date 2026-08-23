# 🏭 NEXA Factory - API Reference

## Table of Contents
1. [Database](#database)
2. [Bot Registry](#bot-registry)
3. [Polling](#polling)
4. [Message Handling](#message-handling)
5. [Broadcasting](#broadcasting)
6. [Backup](#backup)

---

## Database

### Initialize
```python
from db import db

await db.init()  # Initialize with WAL
await db.close()  # Graceful shutdown
```

### Add Bot
```python
success = await db.add_bot(
    bot_id=123456789,
    token="1234567890:ABCD...",
    owner_id=111222333,
    username="MyBot"
)
```

### User Management
```python
# Add/update user
await db.add_user(
    bot_id=123456789,
    chat_id=999888777,
    username="@username",
    first_name="FirstName"
)

# Get user count
cursor = await db.connection.execute(
    "SELECT COUNT(*) FROM bot_users WHERE bot_id = ?",
    (bot_id,)
)
count = (await cursor.fetchone())[0]
```

### Message Management
```python
# Save message
await db.add_message(
    bot_id=123456789,
    chat_id=999888777,
    message_id=123,
    text="Message text",
    is_incoming=True
)

# Get recent messages
cursor = await db.connection.execute(
    "SELECT * FROM messages WHERE bot_id = ? ORDER BY timestamp DESC LIMIT 10",
    (bot_id,)
)
messages = await cursor.fetchall()
```

### Offset Management
```python
# Get offset (don't re-process updates)
offset = await db.get_offset(bot_id)

# Update offset after processing
await db.update_offset(bot_id, update_id, last_offset)
```

### Cleanup
```python
# Remove old messages (auto runs hourly)
await db.cleanup_old_data()
```

---

## Bot Registry

### Register Bot
```python
from bot_registry import bot_registry

await bot_registry.load_bots()

success = await bot_registry.register_bot(
    bot_id=123456789,
    token="1234567890:ABCD...",
    owner_id=111222333,
    username="MyBot"
)
```

### Get Bot Info
```python
# Single bot
bot = bot_registry.get_bot(bot_id=123456789)
# → {"bot_id": 123456789, "token": "...", "username": "MyBot"}

# Get token
token = bot_registry.get_token(123456789)

# All bots
bot_list = bot_registry.list_bots()

# Count
total = bot_registry.count()
```

### Remove Bot
```python
await bot_registry.unregister_bot(bot_id=123456789)
```

---

## Polling

### Start Polling
```python
from poller import poller_supervisor
from dispatcher import dispatcher

# Set dispatcher callback
poller_supervisor.on_update = dispatcher.dispatch

# Add bots to polling
await poller_supervisor.add_poller(
    bot_id=123456789,
    token="1234567890:ABCD..."
)

# Start (runs forever)
await poller_supervisor.start_all()
```

### Poller Status
```python
status = poller_supervisor.get_status()
# → {bot_id: {"running": bool, "last_poll": timestamp, "failed_attempts": int}}
```

### Stop Polling
```python
await poller_supervisor.stop_all()
```

---

## Message Handling

### Handle Message
```python
from message_handler import message_handler

message = {
    "message_id": 1,
    "chat": {"id": 999888777},
    "from": {"id": 999888777, "first_name": "User", "username": "user"},
    "text": "Hello bot"
}

await message_handler.handle_message(bot_id=123456789, message=message)
```

### Commands
Automatic commands:
- `/start` - Welcome message
- `/help` - Help message
- `/stats` - Bot statistics

### Auto-Replies
```python
from auto_reply_manager import auto_reply_manager

# Add auto-reply
await auto_reply_manager.add_auto_reply(
    bot_id=123456789,
    keyword=r"السلام|أهلا|مرحبا",  # Regex pattern
    reply="وعليكم السلام ورحمة الله وبركاته ❤️"
)

# Get all
replies = await auto_reply_manager.get_auto_replies(bot_id=123456789)

# Enable/disable
await auto_reply_manager.toggle_auto_reply(
    bot_id=123456789,
    keyword=r"السلام|...",
    active=False
)

# Remove
await auto_reply_manager.remove_auto_reply(
    bot_id=123456789,
    keyword=r"السلام|..."
)
```

### Subscriptions
```python
from subscription_handler import subscription_handler

# Add mandatory subscription
await subscription_handler.add_subscription(
    bot_id=123456789,
    channel_id="@MyChannel",
    mandatory=True
)

# Check if user subscribed
is_member = await subscription_handler.check_subscription(
    bot_id=123456789,
    chat_id=999888777
)

# Get all subscriptions
subs = await subscription_handler.get_subscriptions(bot_id=123456789)
# → [{"channel_id": "@MyChannel", "is_mandatory": True, "active": True}]

# Remove subscription
await subscription_handler.remove_subscription(
    bot_id=123456789,
    channel_id="@MyChannel"
)
```

---

## Message Sending

### Send Message
```python
from message_sender import message_sender

result = await message_sender.send_message(
    bot_id=123456789,
    chat_id=999888777,
    text="Hello user! 👋",
    parse_mode="HTML"  # or "Markdown"
)
```

### With Rate Limiting
```python
# Automatic rate limiting (30 msg/s per bot)
await message_sender.send_message(bot_id, chat_id, text)

# Check rate limiter status
from rate_limiter import rate_limiter_pool

status = rate_limiter_pool.get_status()
# → {bot_id: {"rate": X/s, "queued_requests": N, "retry_after": timestamp}}
```

---

## Broadcasting

### Start Broadcast
```python
from broadcast_engine import broadcast_engine

broadcast_id = await broadcast_engine.start_broadcast(
    bot_id=123456789,
    text="🔔 Important announcement! 📢",
    batch_size=1000  # Users per batch
)
```

### Check Status
```python
status = await broadcast_engine.get_broadcast_status(broadcast_id)
# → {
#     "id": 1,
#     "status": "processing" | "completed" | "cancelled",
#     "stats": {"sent": 95000, "failed": 5000, "blocked": 0, "success_rate": 95.0},
#     "created_at": "...",
#     "completed_at": "..."
# }
```

### Cancel Broadcast
```python
await broadcast_engine.cancel_broadcast(broadcast_id)
```

---

## Job Queue

### Add Job
```python
from priority_queue import job_queue, JobPriority

job = await job_queue.add_job(
    job_id="unique_id",
    priority=JobPriority.HIGH,  # or NORMAL, LOW
    handler=some_async_function,
    arg1="value1",
    arg2="value2"
)
```

### Priorities
- **CRITICAL** (0) - System critical operations
- **HIGH** (1) - User messages, commands
- **NORMAL** (2) - Regular operations
- **LOW** (3) - Broadcasts, backups

### Queue Status
```python
status = job_queue.get_status()
# → {
#     "total_queued": 10,
#     "active_jobs": 2,
#     "completed_jobs": 100,
#     "queue_sizes": {"CRITICAL": 0, "HIGH": 3, "NORMAL": 2, "LOW": 5}
# }
```

### Active Jobs
```python
active = job_queue.get_active_jobs()
completed = job_queue.get_completed_jobs(limit=10)
```

---

## Backup

### Create Backup
```python
from backup import backup_manager

backup_path = await backup_manager.create_backup()
# → "/home/factory/backups/factory_backup_2026_08_14_140000.xlsx"
```

### Restore Backup
```python
success = await backup_manager.restore_from_backup(backup_path)
```

### List Backups
```python
backups = await backup_manager.list_backups()
# → [
#     {"name": "factory_backup_2026_08_14_140000.xlsx", "size_mb": 5.2, "created": datetime},
#     ...
# ]
```

---

## Common Patterns

### Start Engine
```python
import asyncio
from main import main

asyncio.run(main())
```

### Add Bot & Start
```python
async def setup():
    from db import db
    from bot_registry import bot_registry
    
    await db.init()
    await bot_registry.load_bots()
    
    # Register new bot
    await bot_registry.register_bot(
        bot_id=123456789,
        token="1234567890:ABCD...",
        owner_id=111222333,
        username="MyBot"
    )
    
    # Now run main.py
```

### Monitor Bots
```python
async def monitor():
    while True:
        # Check queue
        status = job_queue.get_status()
        print(f"Queue: {status['total_queued']} jobs")
        
        # Check pollers
        poller_status = poller_supervisor.get_status()
        for bot_id, info in poller_status.items():
            print(f"Bot #{bot_id}: {'🟢 online' if info['running'] else '🔴 offline'}")
        
        await asyncio.sleep(60)
```

---

## Error Handling

### Rate Limiting (429)
```python
# Automatic retry on 429
# If needed, check status:
status = rate_limiter_pool.get_status()
if status[bot_id]["retry_after"] > time.time():
    print("Still rate limited, waiting...")
```

### Message Sending Failures
```python
result = await message_sender.send_message(bot_id, chat_id, text)

if result is None:
    print("Message failed - user may be blocked or rate limited")
```

### Polling Failures
```python
# Pollers auto-recover with exponential backoff
# If poller dies after 5 failures, restart from supervisor:
await poller_supervisor.remove_poller(bot_id)
await poller_supervisor.add_poller(bot_id, token)
```

---

See `QUICK_START.md` for beginner examples.
