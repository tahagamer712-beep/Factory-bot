# 🚀 Quick Start Guide

## Installation (Termux)

```bash
# 1. Clone/download files to ~/factory
mkdir -p ~/factory
cd ~/factory
# Copy all .py files here

# 2. Install dependencies
bash install.sh

# 3. Verify installation
python test_phase1.py
```

## Adding Your First Bot

### Step 1: Create Bot on Telegram

```
1. Open @BotFather on Telegram
2. Send: /start
3. Send: /newbot
4. Give it a name: "My Awesome Bot"
5. Give it a username: "my_awesome_bot_xyz"
6. Copy the token: 1234567890:ABCDEFghijklmnOPQRSTUV...
```

### Step 2: Register Bot

Create `add_bot.py`:

```python
import asyncio
from db import db
from bot_registry import bot_registry

async def add_my_bot():
    # Initialize
    await db.init()
    await bot_registry.load_bots()
    
    # Add your bot
    bot_id = 123456789          # From BotFather
    token = "1234567890:ABCD..."  # From BotFather
    owner_id = 111222333       # Your Telegram ID
    username = "my_awesome_bot_xyz"
    
    success = await bot_registry.register_bot(bot_id, token, owner_id, username)
    
    if success:
        print(f"✅ Bot @{username} registered!")
    else:
        print("❌ Failed to register bot")
    
    await db.close()

asyncio.run(add_my_bot())
```

Run it:
```bash
python add_bot.py
```

### Step 3: Start Engine

```bash
python main.py
```

You should see:
```
🏭 NEXA Factory Engine - Starting
==================================================
✅ 1 bot(s) loaded
   - Bot #123456789: @my_awesome_bot_xyz

🏭 Engine ready (Phase 1: Base complete)
🚀 Phase 2: Long Polling active
📦 Phase 3: Priority Queue + Rate Limiter active
==================================================
```

### Step 4: Test Bot

Send a message to your bot on Telegram. You should see in console:

```
💬 Bot #123456789 | User 999888777: Hello!
```

## File Structure

```
~/factory/
├── config.py              # Configuration
├── db.py                  # Database
├── bot_registry.py        # Bot management
├── telegram_adapter.py    # Telegram API wrapper
├── offset_manager.py      # Update tracking
├── poller.py             # Long polling
├── dispatcher.py         # Update routing
├── priority_queue.py     # Job queue
├── rate_limiter.py       # Rate limiting
├── message_sender.py     # Send messages
├── main.py               # Main engine
├── requirements-termux.txt
├── .env.example
├── README.md
├── PHASES.md             # Phase documentation
├── QUICK_START.md        # This file
├── data/
│   └── factory.db        # SQLite database
├── backups/              # Backup files
└── logs/                 # Log files
```

## Common Commands

### Check Bot Status

```python
from bot_registry import bot_registry
import asyncio
from db import db

async def check():
    await db.init()
    await bot_registry.load_bots()
    
    for bot in bot_registry.list_bots():
        print(f"Bot #{bot['bot_id']}: @{bot['username']}")
    
    await db.close()

asyncio.run(check())
```

### List All Users

```python
import asyncio
import sqlite3

def list_users():
    conn = sqlite3.connect('data/factory.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT bot_id, COUNT(*) as users FROM bot_users GROUP BY bot_id")
    for bot_id, count in cursor.fetchall():
        print(f"Bot #{bot_id}: {count} users")
    
    conn.close()

list_users()
```

### View Messages

```python
import sqlite3

def get_messages(bot_id, limit=10):
    conn = sqlite3.connect('data/factory.db')
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT timestamp, chat_id, text FROM messages WHERE bot_id = ? ORDER BY timestamp DESC LIMIT ?",
        (bot_id, limit)
    )
    
    for ts, chat_id, text in cursor.fetchall():
        print(f"[{ts}] User {chat_id}: {text}")
    
    conn.close()

get_messages(123456789)
```

## Troubleshooting

### Bot doesn't receive messages

```
1. Check token is correct
2. Make sure bot is running: python main.py
3. Check internet connection
4. Send /start to bot and wait 30 seconds
```

### High memory usage

```
1. Check message retention: MESSAGE_RETENTION_DAYS in .env
2. Run cleanup: db.cleanup_old_data()
3. Check queue size: job_queue.get_status()
4. Reduce MAX_WORKERS if needed
```

### Database errors

```
1. Check if factory.db is locked
2. Close other Python processes
3. Backup database: cp data/factory.db data/factory.db.backup
4. Remove factory.db and restart (recreates fresh)
```

### Rate limiting issues

```
1. Check rate limiter status:
   rate_limiter_pool.get_status()
2. If 429 errors, wait retry_after seconds
3. Reduce message sending rate
```

## Next Steps

1. **Phase 4**: Add message handlers (auto-replies, commands)
2. **Phase 5**: Implement broadcasting
3. **Phase 6**: Add backup/restore to Excel
4. **Phase 7**: Build dashboards

See `PHASES.md` for details.

## Support

For issues on Termux:
- Check Python version: `python --version`
- Check storage space: `storage`
- Check network: `ping 1.1.1.1`
- Check logs: `tail -f logs/factory.log`

---

**Happy Bot Building! 🚀**
