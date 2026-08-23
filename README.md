# 🏭 NEXA Factory - Multi-Bot Engine

Telegram bot factory for Termux - Create and manage multiple bots from one engine.

## 📱 Requirements

- Termux
- Python 3.11+
- pip

## ⚙️ Installation

```bash
# Create factory directory
mkdir -p ~/factory
cd ~/factory

# Copy all files here

# Install dependencies
pip install -r requirements-termux.txt
```

## 🚀 Quick Start

```bash
# Run the engine
python main.py
```

## 📝 Adding Your First Bot

```python
# In Python shell or add to script:
import asyncio
from bot_registry import bot_registry
from db import db

async def add_bot():
    await db.init()
    await bot_registry.load_bots()
    
    # Replace with your actual bot ID and token
    bot_id = 123456789  # Get from BotFather
    token = "1234567890:ABCDEFghijklmn"  # Get from BotFather
    owner_id = 111222333  # Your Telegram ID
    username = "@MyAwesomeBot"
    
    success = await bot_registry.register_bot(bot_id, token, owner_id, username)
    print(f"Bot registered: {success}")
    
    await db.close()

asyncio.run(add_bot())
```

## 📂 File Structure

```
~/factory/
├── Core Engine
│  ├── config.py                 # Configuration & paths
│  ├── main.py                   # Entry point (all phases)
│  ├── db.py                     # SQLite + async
│  └── bot_registry.py           # Bot management
│
├── Phase 2: Polling
│  ├── telegram_adapter.py       # Telegram API wrapper (httpx)
│  ├── offset_manager.py         # Update tracking
│  ├── poller.py                 # Async long polling
│  └── dispatcher.py             # Route updates
│
├── Phase 3: Queue & Rate Limiting
│  ├── priority_queue.py         # Job queue (HIGH/LOW priority)
│  ├── rate_limiter.py           # Per-bot rate limiter
│  └── message_sender.py         # Send with rate limiting
│
├── Phase 4: Message Handlers
│  ├── message_handler.py        # Process messages/commands
│  ├── subscription_handler.py   # Mandatory subscriptions
│  └── auto_reply_manager.py     # Keyword auto-replies
│
├── Phase 5: Broadcast
│  └── broadcast_engine.py       # Stream broadcast (no RAM overload)
│
├── Phase 6: Backup
│  └── backup.py                 # Excel export/import
│
├── Testing
│  ├── test_phase1.py            # Database tests
│  ├── test_phase2.py            # Polling tests
│  ├── test_phase3.py            # Queue & rate limit tests
│  ├── test_phase4.py            # Handler tests
│  └── test_phase5_6.py          # Broadcast & backup tests
│
├── Documentation
│  ├── README.md                 # This file
│  ├── PHASES.md                 # Detailed phase breakdown
│  └── QUICK_START.md            # Getting started guide
│
├── Data
│  ├── data/
│  │  └── factory.db             # SQLite database
│  ├── backups/                  # Backup files
│  └── logs/                     # Log files
│
└── Configuration
   ├── requirements-termux.txt   # Python dependencies
   ├── .env.example              # Environment variables
   └── install.sh                # Installation script
```

## 🗄️ Database

SQLite database with WAL mode for better performance on Termux.

**Tables:**
- `bots` - Bot information
- `bot_users` - Users per bot
- `messages` - Message history
- `subscriptions` - Channel subscriptions
- `blocks` - Blocked users
- `offsets` - Long polling offsets
- `queue_jobs` - Background jobs
- `events` - Event logs

## 🔧 Configuration

Copy `.env.example` to `.env` and edit:

```bash
cp .env.example .env
```

### Available Settings

- `LOG_LEVEL` - Logging level (INFO, DEBUG, WARNING)
- `MAX_WORKERS` - Number of concurrent workers (default: 4)
- `LONG_POLL_TIMEOUT` - Polling timeout in seconds (default: 30)
- `BATCH_SIZE` - Batch processing size (default: 100)
- `MEMORY_THRESHOLD_MB` - Alert threshold for memory usage (default: 300)

## 📊 Backup & Export

Database can be exported to Excel with all data:

```python
from backup import export_to_excel
await export_to_excel()  # Creates backup.xlsx
```

## 🐛 Debugging

Enable debug logging:

```bash
LOG_LEVEL=DEBUG python main.py
```

## 📞 Support

For issues on Termux, check:
- Internet connection
- Storage permissions
- Python version compatibility

## 🚀 Phase 2: Async Long Polling

**New Files:**
- `telegram_adapter.py` - Lightweight Telegram API wrapper
- `offset_manager.py` - Track last update for each bot
- `poller.py` - Async long polling supervisor
- `dispatcher.py` - Route updates to handlers
- `test_phase2.py` - Test long polling

**Features:**
- Concurrent polling of multiple bots
- No blocking, pure async with asyncio
- Long polling (30s timeout) = fewer requests
- Automatic offset tracking
- Error recovery with exponential backoff
- Message/update storage in SQLite

**How It Works:**

```
100 Bots
   ↓
Poller Supervisor (1 event loop)
   ↓
100 Async Tasks (concurrent, non-blocking)
   ↓
Telegram API (long poll each bot)
   ↓
Update Router/Dispatcher
   ↓
Database (save messages, users, events)
```

## 📦 Phase 3: Priority Queue + Rate Limiting

**New Files:**
- `priority_queue.py` - Multi-priority job queue with workers
- `rate_limiter.py` - Per-bot rate limiting (30 msg/s)
- `message_sender.py` - Send messages with rate limiting
- `test_phase3.py` - Test queue and rate limiting

**Features:**
- HIGH priority: User messages, commands (processed first)
- LOW priority: Broadcasts, backups (background)
- Configurable worker pool (default: 4 workers)
- Per-bot rate limiting (default: 30 msgs/sec)
- Automatic 429 error handling
- Queue status monitoring

**How It Works:**

```
HIGH Priority Queue    LOW Priority Queue
    (user messages)        (broadcasts)
        ↓                        ↓
        └────┬────────────────┬──┘
             ↓
        Worker Pool (4 workers)
             ↓
        Execute Job
             ↓
        Rate Limiter (30/s per bot)
             ↓
        Send to Telegram
```

---

**Phase 1** ✅
**Phase 2** ✅
**Phase 3** ✅
Next: Phase 4 - Message Handlers
