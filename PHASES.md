# 🏭 NEXA Factory Phases

## Phase 1: Engine Base ✅
**Database + Bot Registry**

### Files:
- `config.py` - Configuration and paths
- `db.py` - SQLite async database (WAL optimized)
- `bot_registry.py` - Bot registration and management
- `test_phase1.py` - Test database and registry

### What it does:
```
Database (SQLite)
├── bots table (bot ID, token, owner)
├── bot_users table (users per bot)
├── messages table (chat history)
├── subscriptions, blocks, offsets
├── queue_jobs (background work)
└── events (activity log)

Bot Registry
├── Load all registered bots
├── Store bot info in memory
├── Add/remove bots
└── Provide token lookup
```

### Tested Operations:
- ✅ Database initialization with WAL
- ✅ Create tables with proper indexes
- ✅ Add bot to registry
- ✅ Store/retrieve user data
- ✅ Track message history
- ✅ Update offsets

---

## Phase 2: Async Long Polling ✅
**Concurrent update retrieval from Telegram**

### Files:
- `telegram_adapter.py` - HTTP wrapper for Telegram API
- `offset_manager.py` - Track last update per bot
- `poller.py` - Async long polling supervisor
- `dispatcher.py` - Route updates to handlers
- `test_phase2.py` - Test long polling

### What it does:
```
100 Bots (async tasks)
    ↓
Async Supervisor (1 event loop)
    ↓
Long Polling (30s timeout per bot)
    ↓
Telegram API (concurrent, non-blocking)
    ↓
Update Router
    ↓
Database (save messages, users, events)
```

### Key Features:
- **Concurrent Polling**: All bots poll Telegram simultaneously
- **Non-blocking**: Uses pure async/await, no threads
- **Long Polling**: 30-second timeout = fewer API calls
- **Offset Tracking**: Never process same message twice
- **Error Recovery**: Exponential backoff on failures
- **Message Storage**: Auto-save incoming messages

### Telegram Update Types:
- `message` - Chat messages
- `callback_query` - Button presses
- `my_chat_member` - User blocked/unblocked

---

## Phase 3: Priority Queue + Rate Limiting ✅
**Manage job execution with priorities and rate limits**

### Files:
- `priority_queue.py` - Multi-priority job queue
- `rate_limiter.py` - Per-bot rate limiting
- `message_sender.py` - Send messages with rate limiting
- `test_phase3.py` - Test queue and limits

### What it does:
```
Jobs arrive
    ↓
Priority Assignment
    ├─ CRITICAL (0)
    ├─ HIGH (1) ← User messages
    ├─ NORMAL (2)
    └─ LOW (3) ← Broadcasts
    ↓
Job Queue
    ↓
Worker Pool (4 workers default)
    ↓
Rate Limiter (30 msg/s per bot)
    ├─ Track requests
    ├─ Handle 429 errors
    └─ Auto-retry
    ↓
Execute Job
    ↓
Save Result/Error
```

### Features:
- **Priority Execution**: HIGH priority processed before LOW
- **Worker Pool**: Configurable number of concurrent workers
- **Rate Limiting**: 30 messages/second per bot (Telegram limit)
- **429 Handling**: Auto-retry with backoff on rate limit
- **Job Tracking**: Monitor job status, timing, results
- **Backpressure**: Prevent resource exhaustion

### Job Priorities:
| Priority | Use Case | Examples |
|----------|----------|----------|
| CRITICAL | System | Health checks, errors |
| HIGH | Users | Incoming messages, commands |
| NORMAL | Regular | User updates, subscriptions |
| LOW | Background | Broadcasts, backups, analytics |

---

## Phase 4: Message Handlers ✅
**Process incoming messages with business logic**

### Files:
- `message_handler.py` - Handle commands, auto-replies
- `subscription_handler.py` - Check mandatory subscriptions
- `auto_reply_manager.py` - Manage keyword-based replies
- `test_phase4.py` - Test message handlers

### Features:
- **Commands**: /start, /help, /stats
- **Auto-Replies**: Regex-based keyword matching
- **Subscriptions**: Check mandatory channel membership
- **User Tracking**: Track who blocked the bot
- **Job Queueing**: Process with HIGH priority

### What it does:
```
Message arrives
    ↓
Check subscriptions
    ├─ If missing → show prompt
    └─ If valid → continue
    ↓
Process message
    ├─ Command (/start, /help)
    ├─ Auto-reply (keyword match)
    └─ Default response
    ↓
Queue reply
    ↓
Send with rate limiting
```

---

## Phase 5: Broadcast Engine ✅
**Send messages to many users efficiently**

### Files:
- `broadcast_engine.py` - Streaming batch broadcast
- `test_phase5_6.py` - Test broadcasting

### Features:
- **Streaming**: Process users in batches (no RAM overload)
- **Rate Limited**: Respects Telegram 30 msg/s limit
- **Background**: LOW priority processing
- **Statistics**: Track sent/failed/blocked
- **Traceable**: Broadcast ID for tracking

### How it works:
```
Start broadcast
    ↓
Queue as LOW priority job
    ↓
Stream users from DB (batch_size=1000)
    ├─ Batch 1 (1000 users)
    ├─ Batch 2 (1000 users)
    └─ Batch N (remaining)
    ↓
Send with rate limiting
    ↓
Update statistics
    ↓
Complete & save results
```

### Example:
```python
# Start broadcast to 100k users
broadcast_id = await broadcast_engine.start_broadcast(
    bot_id=123456789,
    text="مرحباً! هذي إذاعة جماعية",
    batch_size=1000
)

# Check status
status = await broadcast_engine.get_broadcast_status(broadcast_id)
print(status)  # {sent: 95000, failed: 5000, blocked: 0}
```

---

## Phase 6: Backup System ✅
**Export/import database as Excel**

### Files:
- `backup.py` - Excel backup/restore
- `test_phase5_6.py` - Test backup

### Features:
- **Full Export**: All tables to Excel
- **Multi-Sheet**: One sheet per table
- **Formatted**: Headers with styling
- **Restore**: Import from Excel back to DB
- **Timestamped**: `factory_backup_YYYYMMDD_HHMMSS.xlsx`

### What's backed up:
```
factory_backup_2026_08_14_140000.xlsx

Sheet 1: SUMMARY
├─ Backup date
├─ Total bots
├─ Total users
└─ Total messages

Sheet 2: BOTS
├─ bot_id, token, owner_id, username, created_at

Sheet 3: USERS
├─ chat_id, username, first_name, last_active, is_blocked

Sheet 4: MESSAGES
├─ message_id, chat_id, text, timestamp

Sheet 5: SUBSCRIPTIONS
├─ channel_id, is_mandatory, active

Sheet 6: BLOCKS
├─ user_id, reason, blocked_date

Sheet 7: OFFSETS
├─ bot_id, last_offset, last_update_id

Sheet 8: JOBS
├─ job_type, status, data, created_at

Sheet 9: EVENTS
├─ event_type, description, timestamp

Sheet 10: AUTO_REPLIES
└─ keyword, reply, active
```

### Example:
```python
# Create backup
backup_path = await backup_manager.create_backup()
# → "factory_backup_2026_08_14_140000.xlsx"

# Restore from backup
await backup_manager.restore_from_backup(backup_path)

# List all backups
backups = await backup_manager.list_backups()
```

---

## Phase 7: Dashboards ⏳
**Admin interfaces**

### Planned Files:
- `factory_dashboard.py` - Master admin panel
- `bot_owner_dashboard.py` - Per-bot control panel

### Features:
- Real-time stats
- Bot management
- User management
- Broadcast controls
- Settings adjustment

---

## Current Status

```
✅ Phase 1: Database + Registry (COMPLETE)
✅ Phase 2: Long Polling (COMPLETE)
✅ Phase 3: Queue + Rate Limiting (COMPLETE)
✅ Phase 4: Message Handlers (COMPLETE)
✅ Phase 5: Broadcast Engine (COMPLETE)
✅ Phase 6: Backup System (COMPLETE)
⏳ Phase 7: Dashboards (Web UI)

READY FOR PRODUCTION! 🚀
```

---

## Running Tests

```bash
cd ~/factory

# Phase 1
python test_phase1.py

# Phase 2
python test_phase2.py

# Phase 3
python test_phase3.py

# Phase 4 (when ready)
python test_phase4.py
```

---

## Main Engine

```bash
python main.py
```

This runs Phases 1-3 together:
- Database loaded
- Bots registered
- Pollers started (concurrent)
- Queue workers started
- Ready to receive updates
