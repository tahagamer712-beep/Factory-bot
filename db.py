import asqlite
import asyncio
import json
from datetime import datetime, timedelta
from config import DATABASE_PATH, MESSAGE_RETENTION_DAYS
from typing import List, Dict, Optional, Any

class Database:
    def __init__(self):
        self.db_path = str(DATABASE_PATH)
        self.connection = None
        # Guards multi-statement operations on the single shared connection
        # so polling/broadcast/backup can't interleave writes mid-transaction.
        self._lock = asyncio.Lock()
    
    async def init(self):
        """Initialize database with WAL and optimizations"""
        self.connection = await asqlite.connect(self.db_path)
        
        await self.connection.execute("PRAGMA journal_mode=WAL")
        await self.connection.execute("PRAGMA foreign_keys=ON")
        await self.connection.execute("PRAGMA synchronous=NORMAL")
        await self.connection.execute("PRAGMA temp_store=MEMORY")
        await self.connection.execute("PRAGMA mmap_size=30000000")
        await self.connection.execute("PRAGMA busy_timeout=30000")
        
        await self._create_tables()
        await self.connection.commit()
        print("✅ Database initialized")
    
    async def _create_tables(self):
        """Create all required tables"""
        
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS bots (
                bot_id INTEGER PRIMARY KEY,
                token TEXT UNIQUE NOT NULL,
                owner_id INTEGER NOT NULL,
                username TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                settings TEXT DEFAULT '{}'
            )
        """)
        
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS bot_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                username TEXT,
                first_name TEXT,
                language TEXT DEFAULT 'en',
                chat_type TEXT DEFAULT 'private',
                last_bot_message_id INTEGER,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_blocked BOOLEAN DEFAULT 0,
                metadata TEXT DEFAULT '{}',
                FOREIGN KEY (bot_id) REFERENCES bots(bot_id) ON DELETE CASCADE,
                UNIQUE(bot_id, chat_id)
            )
        """)
        
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                message_id INTEGER,
                text TEXT,
                message_type TEXT DEFAULT 'text',
                is_incoming BOOLEAN DEFAULT 1,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT DEFAULT '{}',
                FOREIGN KEY (bot_id) REFERENCES bots(bot_id) ON DELETE CASCADE
            )
        """)
        
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_id INTEGER NOT NULL,
                channel_id TEXT NOT NULL,
                is_mandatory BOOLEAN DEFAULT 1,
                active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (bot_id) REFERENCES bots(bot_id) ON DELETE CASCADE,
                UNIQUE(bot_id, channel_id)
            )
        """)
        
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS blocks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                reason TEXT,
                blocked_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (bot_id) REFERENCES bots(bot_id) ON DELETE CASCADE
            )
        """)
        
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS offsets (
                bot_id INTEGER PRIMARY KEY,
                last_offset INTEGER DEFAULT 0,
                last_update_id INTEGER DEFAULT 0,
                last_checked TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (bot_id) REFERENCES bots(bot_id) ON DELETE CASCADE
            )
        """)
        
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS queue_jobs (
                job_id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_id INTEGER NOT NULL,
                job_type TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                priority INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                data TEXT DEFAULT '{}',
                FOREIGN KEY (bot_id) REFERENCES bots(bot_id) ON DELETE CASCADE
            )
        """)
        
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                description TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT DEFAULT '{}',
                FOREIGN KEY (bot_id) REFERENCES bots(bot_id) ON DELETE CASCADE
            )
        """)
        
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS auto_replies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_id INTEGER NOT NULL,
                keyword TEXT NOT NULL,
                reply TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                active BOOLEAN DEFAULT 1,
                FOREIGN KEY (bot_id) REFERENCES bots(bot_id) ON DELETE CASCADE,
                UNIQUE(bot_id, keyword)
            )
        """)
        
        # Generic per-bot settings store: every toggle/value in the admin
        # panel (verification method, auto-delete duration, notification
        # flags, welcome message text, etc) lives here as bot_id+key -> a
        # JSON-encoded value, so new panel screens don't need a new table
        # each time.
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS bot_settings (
                bot_id INTEGER NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (bot_id, key),
                FOREIGN KEY (bot_id) REFERENCES bots(bot_id) ON DELETE CASCADE
            )
        """)
        
        # Additional admins beyond the bot's owner (owner is always an
        # implicit admin - see admin_panel/auth.py)
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS bot_admins (
                bot_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (bot_id, user_id),
                FOREIGN KEY (bot_id) REFERENCES bots(bot_id) ON DELETE CASCADE
            )
        """)
        
        # Tracks "the admin panel is waiting for a text reply from this
        # admin" (e.g. after pressing "broadcast", the next message they
        # send is the broadcast text, not a random chat message). Keyed by
        # the admin's own chat_id since one admin can only be in one flow
        # at a time.
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS conversation_state (
                chat_id INTEGER PRIMARY KEY,
                bot_id INTEGER NOT NULL,
                state TEXT NOT NULL,
                context TEXT DEFAULT '{}',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (bot_id) REFERENCES bots(bot_id) ON DELETE CASCADE
            )
        """)
        
        # Auto-delete: every bot message eligible for deletion gets a row
        # here when sent; scheduler.py sweeps due rows and actually calls
        # Telegram's deleteMessage.
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS scheduled_deletions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                delete_at TIMESTAMP NOT NULL,
                FOREIGN KEY (bot_id) REFERENCES bots(bot_id) ON DELETE CASCADE
            )
        """)
        
        # Inactivity reminders: which (bot, chat, stage) combos have
        # already been reminded (so we don't re-send every sweep), and so
        # scheduler.py can also detect "they came back" for the reward
        # feature. `stage` is the index into the admin's configured
        # reminders list, since a bot can have several reminders at
        # different day-offsets (e.g. stage 0 = after 7 days, stage 1 =
        # after 14 days).
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS inactivity_reminders (
                bot_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                stage INTEGER NOT NULL DEFAULT 0,
                reminded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (bot_id, chat_id, stage),
                FOREIGN KEY (bot_id) REFERENCES bots(bot_id) ON DELETE CASCADE
            )
        """)
        
        # Verification gate: who has passed it (any enabled method)
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS verified_users (
                bot_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                verified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (bot_id, chat_id),
                FOREIGN KEY (bot_id) REFERENCES bots(bot_id) ON DELETE CASCADE
            )
        """)
        
        # Message forwarding: maps a message forwarded into the admin's
        # chat back to its original sender, so a reply (or /r1../r20) in
        # the admin's chat can be routed back to the right user.
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS forwarded_messages (
                bot_id INTEGER NOT NULL,
                admin_chat_id INTEGER NOT NULL,
                forwarded_message_id INTEGER NOT NULL,
                origin_chat_id INTEGER NOT NULL,
                origin_message_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (bot_id, admin_chat_id, forwarded_message_id),
                FOREIGN KEY (bot_id) REFERENCES bots(bot_id) ON DELETE CASCADE
            )
        """)
        
        # Migration: add columns to bot_users that may not exist if this
        # database was created before they were introduced. CREATE TABLE
        # IF NOT EXISTS above only helps brand-new databases.
        await self._ensure_column("bot_users", "chat_type", "TEXT DEFAULT 'private'")
        await self._ensure_column("bot_users", "last_bot_message_id", "INTEGER")
        
        # ---- Factory admin panel tables (separate from any single bot) ----
        
        # System-wide log: errors/warnings worth reviewing later, since
        # print() output disappears once the terminal/session is gone.
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                level TEXT NOT NULL,
                source TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Factory-level admins (distinct from a single bot's admins/owner).
        # The factory bot's own owner_id (self-owned, see main.py) is
        # always an implicit "owner"-role admin on top of this table.
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS factory_admins (
                user_id INTEGER PRIMARY KEY,
                role TEXT NOT NULL DEFAULT 'support',
                permissions TEXT NOT NULL DEFAULT '[]',
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # People who've messaged the factory bot itself (separate from any
        # created bot's own bot_users - needed to target announcements).
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS factory_users (
                chat_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_blocked BOOLEAN DEFAULT 0
            )
        """)
        
        # Factory-wide blocks on a *person* (by Telegram user_id), with
        # independent flags for what exactly they're blocked from -
        # matches the "حظر من استخدام المصنع / من إنشاء بوتات / إيقاف
        # بوتاته الحالية" checkboxes.
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS factory_blocks (
                user_id INTEGER PRIMARY KEY,
                block_factory_use BOOLEAN DEFAULT 0,
                block_bot_creation BOOLEAN DEFAULT 0,
                bots_disabled BOOLEAN DEFAULT 0,
                reason TEXT DEFAULT '',
                blocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_messages_bot_id ON messages(bot_id)",
            "CREATE INDEX IF NOT EXISTS idx_messages_chat_id ON messages(chat_id)",
            "CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_bot_users_bot_id ON bot_users(bot_id)",
            "CREATE INDEX IF NOT EXISTS idx_blocks_bot_id ON blocks(bot_id)",
            "CREATE INDEX IF NOT EXISTS idx_offsets_bot_id ON offsets(bot_id)",
            "CREATE INDEX IF NOT EXISTS idx_queue_bot_id ON queue_jobs(bot_id)",
            "CREATE INDEX IF NOT EXISTS idx_queue_status ON queue_jobs(status)",
            "CREATE INDEX IF NOT EXISTS idx_scheduled_del_time ON scheduled_deletions(delete_at)",
            "CREATE INDEX IF NOT EXISTS idx_bot_users_last_active ON bot_users(last_active)",
            "CREATE INDEX IF NOT EXISTS idx_logs_created_at ON logs(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_logs_level ON logs(level)",
            "CREATE INDEX IF NOT EXISTS idx_factory_users_active ON factory_users(last_active)",
        ]
        
        for idx in indexes:
            await self.connection.execute(idx)
    
    async def _ensure_column(self, table: str, column: str, coltype: str):
        """Add `column` to `table` if it doesn't already exist - lets
        existing databases pick up new columns without a full migration
        tool. Safe to call every startup."""
        cursor = await self.connection.execute(f"PRAGMA table_info({table})")
        existing = {row[1] for row in await cursor.fetchall()}
        if column not in existing:
            await self.connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")
    
    async def add_bot(self, bot_id: int, token: str, owner_id: int, username: str) -> bool:
        """Add new bot to database"""
        # --- input validation ---
        if not isinstance(bot_id, int) or bot_id <= 0:
            print("❌ Error adding bot: invalid bot_id")
            return False
        if not token or not isinstance(token, str) or ":" not in token:
            print("❌ Error adding bot: invalid token format")
            return False
        if not isinstance(owner_id, int) or owner_id <= 0:
            print("❌ Error adding bot: invalid owner_id")
            return False
        username = (username or "")[:64]
        
        async with self._lock:
            try:
                await self.connection.execute("BEGIN")
                await self.connection.execute(
                    "INSERT INTO bots (bot_id, token, owner_id, username) VALUES (?, ?, ?, ?)",
                    (bot_id, token, owner_id, username)
                )
                
                await self.connection.execute(
                    "INSERT INTO offsets (bot_id, last_offset, last_update_id) VALUES (?, 0, 0)",
                    (bot_id,)
                )
                
                await self.connection.commit()
                print(f"✅ Bot #{bot_id} added")
                return True
            except Exception as e:
                await self.connection.rollback()
                print(f"❌ Error adding bot: {e}")
                return False
    
    async def get_all_bots(self) -> List[Dict]:
        """Get all bots"""
        cursor = await self.connection.execute("SELECT * FROM bots")
        rows = await cursor.fetchall()
        columns = [description[0] for description in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    
    async def get_bot(self, bot_id: int) -> Optional[Dict]:
        """Get specific bot"""
        cursor = await self.connection.execute(
            "SELECT * FROM bots WHERE bot_id = ?", (bot_id,)
        )
        row = await cursor.fetchone()
        if row:
            columns = [description[0] for description in cursor.description]
            return dict(zip(columns, row))
        return None
    
    async def delete_bot(self, bot_id: int) -> bool:
        """Delete bot and all related data"""
        async with self._lock:
            try:
                await self.connection.execute("DELETE FROM bots WHERE bot_id = ?", (bot_id,))
                await self.connection.commit()
                return True
            except Exception as e:
                await self.connection.rollback()
                print(f"❌ Error deleting bot: {e}")
                return False
    
    async def get_offset(self, bot_id: int) -> int:
        """Get last offset for bot"""
        cursor = await self.connection.execute(
            "SELECT last_offset FROM offsets WHERE bot_id = ?", (bot_id,)
        )
        row = await cursor.fetchone()
        return row[0] if row else 0
    
    async def update_offset(self, bot_id: int, offset: int, update_id: int):
        """Update offset for bot. DB is the single source of truth."""
        async with self._lock:
            try:
                await self.connection.execute(
                    "UPDATE offsets SET last_offset = ?, last_update_id = ?, last_checked = CURRENT_TIMESTAMP WHERE bot_id = ?",
                    (offset, update_id, bot_id)
                )
                await self.connection.commit()
            except Exception as e:
                await self.connection.rollback()
                print(f"❌ Error updating offset for bot #{bot_id}: {e}")
                raise
    
    async def add_user(self, bot_id: int, chat_id: int, username: str, first_name: str,
                       chat_type: str = "private") -> bool:
        """Add or update user (atomic - both statements commit together or not at all).
        Returns True if this chat_id is new for this bot (first time ever
        seen) - used to trigger the "new user joined" admin notification."""
        if not isinstance(bot_id, int) or not isinstance(chat_id, int):
            print("❌ Error adding user: invalid bot_id/chat_id")
            return False
        username = (username or "")[:64]
        first_name = (first_name or "")[:128]
        chat_type = (chat_type or "private")[:32]
        
        async with self._lock:
            try:
                await self.connection.execute("BEGIN")
                cursor = await self.connection.execute(
                    """INSERT OR IGNORE INTO bot_users (bot_id, chat_id, username, first_name, chat_type)
                       VALUES (?, ?, ?, ?, ?)""",
                    (bot_id, chat_id, username, first_name, chat_type)
                )
                is_new = cursor.rowcount > 0
                
                await self.connection.execute(
                    "UPDATE bot_users SET last_active = CURRENT_TIMESTAMP WHERE bot_id = ? AND chat_id = ?",
                    (bot_id, chat_id)
                )
                
                await self.connection.commit()
                return is_new
            except Exception as e:
                await self.connection.rollback()
                print(f"❌ Error adding user: {e}")
                return False
    
    async def add_message(self, bot_id: int, chat_id: int, message_id: int, text: str, is_incoming: bool = True):
        """Add message"""
        if not isinstance(bot_id, int) or not isinstance(chat_id, int):
            print("❌ Error adding message: invalid bot_id/chat_id")
            return
        # cap text length to avoid unbounded rows
        text = (text or "")[:4096]
        
        async with self._lock:
            try:
                await self.connection.execute(
                    """INSERT INTO messages (bot_id, chat_id, message_id, text, is_incoming)
                       VALUES (?, ?, ?, ?, ?)""",
                    (bot_id, chat_id, message_id, text, is_incoming)
                )
                await self.connection.commit()
            except Exception as e:
                await self.connection.rollback()
                print(f"❌ Error adding message: {e}")
    
    async def cleanup_old_data(self):
        """Remove old messages and logs"""
        retention_date = (datetime.now() - timedelta(days=MESSAGE_RETENTION_DAYS)).isoformat()
        
        async with self._lock:
            try:
                await self.connection.execute(
                    "DELETE FROM messages WHERE timestamp < ?", (retention_date,)
                )
                await self.connection.execute(
                    "DELETE FROM events WHERE timestamp < ?", (retention_date,)
                )
                await self.connection.execute(
                    "DELETE FROM queue_jobs WHERE status = 'completed' AND completed_at < ?", (retention_date,)
                )
                await self.connection.commit()
                print(f"✅ Cleanup completed")
            except Exception as e:
                await self.connection.rollback()
                print(f"❌ Error during cleanup: {e}")
    
    # ---- bot_settings: generic per-bot key/value store for the admin panel ----
    
    async def get_setting(self, bot_id: int, key: str, default: Any = None) -> Any:
        """Read one setting, JSON-decoded. Returns `default` if unset."""
        cursor = await self.connection.execute(
            "SELECT value FROM bot_settings WHERE bot_id = ? AND key = ?", (bot_id, key)
        )
        row = await cursor.fetchone()
        if not row:
            return default
        try:
            return json.loads(row[0])
        except (json.JSONDecodeError, TypeError):
            return default
    
    async def get_settings(self, bot_id: int, keys: List[str], defaults: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Read several settings at once (one query instead of N)."""
        defaults = defaults or {}
        if not keys:
            return {}
        placeholders = ", ".join(["?"] * len(keys))
        cursor = await self.connection.execute(
            f"SELECT key, value FROM bot_settings WHERE bot_id = ? AND key IN ({placeholders})",
            (bot_id, *keys)
        )
        rows = await cursor.fetchall()
        result = {k: defaults.get(k) for k in keys}
        for key, value in rows:
            try:
                result[key] = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                pass
        return result
    
    async def set_setting(self, bot_id: int, key: str, value: Any):
        """Write one setting (JSON-encoded)."""
        payload = json.dumps(value, ensure_ascii=False)
        async with self._lock:
            try:
                await self.connection.execute(
                    """INSERT INTO bot_settings (bot_id, key, value, updated_at)
                       VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                       ON CONFLICT(bot_id, key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP""",
                    (bot_id, key, payload)
                )
                await self.connection.commit()
            except Exception as e:
                await self.connection.rollback()
                print(f"❌ Error saving setting {key} for bot #{bot_id}: {e}")
    
    async def toggle_setting(self, bot_id: int, key: str, default: bool = False) -> bool:
        """Flip a boolean setting and return its new value."""
        current = await self.get_setting(bot_id, key, default)
        new_value = not bool(current)
        await self.set_setting(bot_id, key, new_value)
        return new_value
    
    # ---- bot_admins: additional admins beyond the bot owner ----
    
    async def is_admin(self, bot_id: int, user_id: int, owner_id: Optional[int] = None) -> bool:
        """True if user_id is the bot's owner or a registered extra admin."""
        if owner_id is not None and user_id == owner_id:
            return True
        cursor = await self.connection.execute(
            "SELECT 1 FROM bot_admins WHERE bot_id = ? AND user_id = ?", (bot_id, user_id)
        )
        return (await cursor.fetchone()) is not None
    
    async def add_admin(self, bot_id: int, user_id: int) -> bool:
        async with self._lock:
            try:
                await self.connection.execute(
                    "INSERT OR IGNORE INTO bot_admins (bot_id, user_id) VALUES (?, ?)",
                    (bot_id, user_id)
                )
                await self.connection.commit()
                return True
            except Exception as e:
                await self.connection.rollback()
                print(f"❌ Error adding admin: {e}")
                return False
    
    async def remove_admin(self, bot_id: int, user_id: int) -> bool:
        async with self._lock:
            try:
                await self.connection.execute(
                    "DELETE FROM bot_admins WHERE bot_id = ? AND user_id = ?", (bot_id, user_id)
                )
                await self.connection.commit()
                return True
            except Exception as e:
                await self.connection.rollback()
                print(f"❌ Error removing admin: {e}")
                return False
    
    async def list_admins(self, bot_id: int) -> List[int]:
        cursor = await self.connection.execute(
            "SELECT user_id FROM bot_admins WHERE bot_id = ?", (bot_id,)
        )
        return [row[0] for row in await cursor.fetchall()]
    
    # ---- conversation_state: "waiting for a text reply" flows in the admin panel ----
    
    async def set_conversation_state(self, chat_id: int, bot_id: int, state: str, context: Optional[Dict[str, Any]] = None):
        payload = json.dumps(context or {}, ensure_ascii=False)
        async with self._lock:
            try:
                await self.connection.execute(
                    """INSERT INTO conversation_state (chat_id, bot_id, state, context, updated_at)
                       VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                       ON CONFLICT(chat_id) DO UPDATE SET
                           bot_id = excluded.bot_id, state = excluded.state,
                           context = excluded.context, updated_at = CURRENT_TIMESTAMP""",
                    (chat_id, bot_id, state, payload)
                )
                await self.connection.commit()
            except Exception as e:
                await self.connection.rollback()
                print(f"❌ Error setting conversation state: {e}")
    
    async def get_conversation_state(self, chat_id: int) -> Optional[Dict[str, Any]]:
        cursor = await self.connection.execute(
            "SELECT bot_id, state, context FROM conversation_state WHERE chat_id = ?", (chat_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return None
        try:
            context = json.loads(row[2]) if row[2] else {}
        except (json.JSONDecodeError, TypeError):
            context = {}
        return {"bot_id": row[0], "state": row[1], "context": context}
    
    async def clear_conversation_state(self, chat_id: int):
        async with self._lock:
            try:
                await self.connection.execute(
                    "DELETE FROM conversation_state WHERE chat_id = ?", (chat_id,)
                )
                await self.connection.commit()
            except Exception as e:
                await self.connection.rollback()
                print(f"❌ Error clearing conversation state: {e}")
    
    # ---- scheduled_deletions: auto-delete-after-N-minutes bookkeeping ----
    
    async def add_scheduled_deletion(self, bot_id: int, chat_id: int, message_id: int, delete_at_iso: str):
        async with self._lock:
            try:
                await self.connection.execute(
                    "INSERT INTO scheduled_deletions (bot_id, chat_id, message_id, delete_at) VALUES (?, ?, ?, ?)",
                    (bot_id, chat_id, message_id, delete_at_iso)
                )
                await self.connection.commit()
            except Exception as e:
                await self.connection.rollback()
                print(f"❌ Error scheduling deletion: {e}")
    
    async def pop_due_scheduled_deletions(self, limit: int = 200) -> List[tuple]:
        """Atomically fetch and remove every deletion whose time has come.
        Removing them up front (rather than after the actual Telegram
        call) means a delete that fails doesn't get retried forever - see
        scheduler.py for why that's the right tradeoff here."""
        now = datetime.now().isoformat()
        async with self._lock:
            try:
                await self.connection.execute("BEGIN")
                cursor = await self.connection.execute(
                    "SELECT id, bot_id, chat_id, message_id FROM scheduled_deletions WHERE delete_at <= ? LIMIT ?",
                    (now, limit)
                )
                rows = await cursor.fetchall()
                if rows:
                    ids = [r[0] for r in rows]
                    placeholders = ",".join(["?"] * len(ids))
                    await self.connection.execute(
                        f"DELETE FROM scheduled_deletions WHERE id IN ({placeholders})", ids
                    )
                await self.connection.commit()
                return [(r[1], r[2], r[3]) for r in rows]
            except Exception as e:
                await self.connection.rollback()
                print(f"❌ Error popping due deletions: {e}")
                return []
    
    # ---- inactivity_reminders (per-stage: a bot can have several
    # reminders at different day-offsets, each tracked independently) ----
    
    async def mark_reminded(self, bot_id: int, chat_id: int, stage: int = 0):
        async with self._lock:
            try:
                await self.connection.execute(
                    """INSERT INTO inactivity_reminders (bot_id, chat_id, stage, reminded_at)
                       VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                       ON CONFLICT(bot_id, chat_id, stage) DO UPDATE SET reminded_at = CURRENT_TIMESTAMP""",
                    (bot_id, chat_id, stage)
                )
                await self.connection.commit()
            except Exception as e:
                await self.connection.rollback()
                print(f"❌ Error marking reminded: {e}")
    
    async def was_reminded(self, bot_id: int, chat_id: int, stage: int = 0) -> bool:
        cursor = await self.connection.execute(
            "SELECT 1 FROM inactivity_reminders WHERE bot_id = ? AND chat_id = ? AND stage = ?",
            (bot_id, chat_id, stage)
        )
        return (await cursor.fetchone()) is not None
    
    async def has_any_reminder(self, bot_id: int, chat_id: int) -> bool:
        """True if this user has been sent at least one reminder stage -
        used to detect "they came back" regardless of which stage."""
        cursor = await self.connection.execute(
            "SELECT 1 FROM inactivity_reminders WHERE bot_id = ? AND chat_id = ? LIMIT 1",
            (bot_id, chat_id)
        )
        return (await cursor.fetchone()) is not None
    
    async def clear_reminded(self, bot_id: int, chat_id: int):
        """Clear every stage for this user (e.g. they came back)."""
        async with self._lock:
            try:
                await self.connection.execute(
                    "DELETE FROM inactivity_reminders WHERE bot_id = ? AND chat_id = ?", (bot_id, chat_id)
                )
                await self.connection.commit()
            except Exception as e:
                await self.connection.rollback()
                print(f"❌ Error clearing reminded flag: {e}")
    
    async def clear_all_reminded(self, bot_id: int):
        async with self._lock:
            try:
                await self.connection.execute(
                    "DELETE FROM inactivity_reminders WHERE bot_id = ?", (bot_id,)
                )
                await self.connection.commit()
            except Exception as e:
                await self.connection.rollback()
                print(f"❌ Error clearing reminded flags: {e}")
    
    async def get_inactive_candidates(self, bot_id: int, cutoff_iso: str, stage: int = 0, limit: int = 200) -> List[int]:
        """Users who've been inactive since cutoff, aren't blocked, and
        haven't already received this specific reminder stage."""
        cursor = await self.connection.execute(
            """SELECT bu.chat_id FROM bot_users bu
               LEFT JOIN inactivity_reminders ir
                 ON ir.bot_id = bu.bot_id AND ir.chat_id = bu.chat_id AND ir.stage = ?
               WHERE bu.bot_id = ? AND bu.is_blocked = 0
                 AND bu.last_active < ? AND ir.chat_id IS NULL
               LIMIT ?""",
            (stage, bot_id, cutoff_iso, limit)
        )
        return [row[0] for row in await cursor.fetchall()]
    
    async def count_inactive_candidates(self, bot_id: int, cutoff_iso: str, stage: int = 0) -> int:
        cursor = await self.connection.execute(
            """SELECT COUNT(*) FROM bot_users bu
               LEFT JOIN inactivity_reminders ir
                 ON ir.bot_id = bu.bot_id AND ir.chat_id = bu.chat_id AND ir.stage = ?
               WHERE bu.bot_id = ? AND bu.is_blocked = 0
                 AND bu.last_active < ? AND ir.chat_id IS NULL""",
            (stage, bot_id, cutoff_iso)
        )
        return (await cursor.fetchone())[0]
    
    # ---- verified_users (membership verification gate) ----
    
    async def mark_verified(self, bot_id: int, chat_id: int):
        async with self._lock:
            try:
                await self.connection.execute(
                    "INSERT OR IGNORE INTO verified_users (bot_id, chat_id) VALUES (?, ?)",
                    (bot_id, chat_id)
                )
                await self.connection.commit()
            except Exception as e:
                await self.connection.rollback()
                print(f"❌ Error marking verified: {e}")
    
    async def is_verified(self, bot_id: int, chat_id: int) -> bool:
        cursor = await self.connection.execute(
            "SELECT 1 FROM verified_users WHERE bot_id = ? AND chat_id = ?", (bot_id, chat_id)
        )
        return (await cursor.fetchone()) is not None
    
    async def count_verified(self, bot_id: int) -> int:
        cursor = await self.connection.execute(
            "SELECT COUNT(*) FROM verified_users WHERE bot_id = ?", (bot_id,)
        )
        return (await cursor.fetchone())[0]
    
    # ---- forwarded_messages (user <-> admin routing) ----
    
    async def add_forwarded_mapping(self, bot_id: int, admin_chat_id: int, forwarded_message_id: int,
                                     origin_chat_id: int, origin_message_id: Optional[int]):
        async with self._lock:
            try:
                await self.connection.execute(
                    """INSERT OR REPLACE INTO forwarded_messages
                       (bot_id, admin_chat_id, forwarded_message_id, origin_chat_id, origin_message_id)
                       VALUES (?, ?, ?, ?, ?)""",
                    (bot_id, admin_chat_id, forwarded_message_id, origin_chat_id, origin_message_id)
                )
                await self.connection.commit()
            except Exception as e:
                await self.connection.rollback()
                print(f"❌ Error saving forwarded mapping: {e}")
    
    async def get_forwarded_origin(self, bot_id: int, admin_chat_id: int, forwarded_message_id: int) -> Optional[int]:
        cursor = await self.connection.execute(
            """SELECT origin_chat_id FROM forwarded_messages
               WHERE bot_id = ? AND admin_chat_id = ? AND forwarded_message_id = ?""",
            (bot_id, admin_chat_id, forwarded_message_id)
        )
        row = await cursor.fetchone()
        return row[0] if row else None
    
    # ---- last bot message per chat (for "delete between messages") ----
    
    async def set_last_bot_message(self, bot_id: int, chat_id: int, message_id: int) -> Optional[int]:
        """Records the new last message id and returns the PREVIOUS one
        (so the caller can delete it), atomically."""
        async with self._lock:
            try:
                cursor = await self.connection.execute(
                    "SELECT last_bot_message_id FROM bot_users WHERE bot_id = ? AND chat_id = ?",
                    (bot_id, chat_id)
                )
                row = await cursor.fetchone()
                previous = row[0] if row else None
                await self.connection.execute(
                    "UPDATE bot_users SET last_bot_message_id = ? WHERE bot_id = ? AND chat_id = ?",
                    (message_id, bot_id, chat_id)
                )
                await self.connection.commit()
                return previous
            except Exception as e:
                await self.connection.rollback()
                print(f"❌ Error updating last bot message: {e}")
                return None
    
    # ---- factory dashboard helpers: bots + owners with aggregated stats ----
    
    async def list_all_bots(self, search: str = "", limit: int = 20, offset: int = 0) -> List[dict]:
        query = "SELECT bot_id, username, owner_id, created_at FROM bots"
        params: tuple = ()
        if search:
            query += " WHERE username LIKE ? OR CAST(bot_id AS TEXT) LIKE ?"
            params = (f"%{search}%", f"%{search}%")
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params = params + (limit, offset)
        cursor = await self.connection.execute(query, params)
        rows = await cursor.fetchall()
        return [{"bot_id": r[0], "username": r[1], "owner_id": r[2], "created_at": r[3]} for r in rows]
    
    async def count_all_bots(self) -> int:
        cursor = await self.connection.execute("SELECT COUNT(*) FROM bots")
        return (await cursor.fetchone())[0]
    
    async def get_bot_full_info(self, bot_id: int) -> Optional[dict]:
        cursor = await self.connection.execute(
            "SELECT bot_id, token, username, owner_id, created_at FROM bots WHERE bot_id = ?", (bot_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return None
        cursor = await self.connection.execute("SELECT COUNT(*) FROM bot_users WHERE bot_id = ?", (bot_id,))
        user_count = (await cursor.fetchone())[0]
        cursor = await self.connection.execute("SELECT COUNT(*) FROM messages WHERE bot_id = ?", (bot_id,))
        msg_count = (await cursor.fetchone())[0]
        cursor = await self.connection.execute(
            "SELECT COUNT(*) FROM queue_jobs WHERE bot_id = ? AND job_type = 'broadcast'", (bot_id,)
        )
        broadcast_count = (await cursor.fetchone())[0]
        return {
            "bot_id": row[0], "token": row[1], "username": row[2], "owner_id": row[3], "created_at": row[4],
            "user_count": user_count, "msg_count": msg_count, "broadcast_count": broadcast_count,
        }
    
    async def list_owners(self, search: str = "", limit: int = 20, offset: int = 0) -> List[dict]:
        query = """
            SELECT owner_id, COUNT(*) as bot_count, MIN(created_at) as first_bot
            FROM bots GROUP BY owner_id
        """
        cursor = await self.connection.execute(query)
        rows = await cursor.fetchall()
        result = [{"owner_id": r[0], "bot_count": r[1], "first_bot_at": r[2]} for r in rows]
        if search:
            result = [r for r in result if search in str(r["owner_id"])]
        return result[offset:offset + limit]
    
    async def count_owners(self) -> int:
        cursor = await self.connection.execute("SELECT COUNT(DISTINCT owner_id) FROM bots")
        return (await cursor.fetchone())[0]
    
    async def get_owner_info(self, owner_id: int) -> dict:
        cursor = await self.connection.execute(
            "SELECT bot_id, username FROM bots WHERE owner_id = ?", (owner_id,)
        )
        bots = [{"bot_id": r[0], "username": r[1]} for r in await cursor.fetchall()]
        total_users = 0
        for b in bots:
            cursor = await self.connection.execute(
                "SELECT COUNT(*) FROM bot_users WHERE bot_id = ?", (b["bot_id"],)
            )
            total_users += (await cursor.fetchone())[0]
        return {"owner_id": owner_id, "bots": bots, "total_users": total_users}
    
    async def factory_wide_stats(self) -> dict:
        total_bots = await self.count_all_bots()
        total_owners = await self.count_owners()
        cursor = await self.connection.execute("SELECT COUNT(*) FROM bot_users")
        total_users = (await cursor.fetchone())[0]
        since = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        cursor = await self.connection.execute("SELECT COUNT(*) FROM messages WHERE timestamp >= ?", (since,))
        messages_today = (await cursor.fetchone())[0]
        cursor = await self.connection.execute(
            "SELECT COUNT(*) FROM queue_jobs WHERE job_type = 'broadcast' AND created_at >= ?", (since,)
        )
        broadcasts_today = (await cursor.fetchone())[0]
        cursor = await self.connection.execute("SELECT COUNT(*) FROM bot_users WHERE is_blocked = 1")
        total_blocks = (await cursor.fetchone())[0]
        return {
            "total_bots": total_bots, "total_owners": total_owners, "total_users": total_users,
            "messages_today": messages_today, "broadcasts_today": broadcasts_today, "total_blocks": total_blocks,
        }
    
    async def get_bots_with_setting(self, key: str, value: Any) -> List[int]:
        """Bots that currently have setting `key` equal to `value` - used
        by the scheduler to only wake up bots with a feature enabled."""
        payload = json.dumps(value)
        cursor = await self.connection.execute(
            "SELECT bot_id FROM bot_settings WHERE key = ? AND value = ?", (key, payload)
        )
        return [row[0] for row in await cursor.fetchall()]
    
    # ---- logs (factory-wide, not tied to any single bot) ----
    
    async def add_log(self, level: str, source: str, message: str):
        """level: 'error' | 'warning' | 'info'. Never raises - logging
        must never be the thing that crashes the caller."""
        try:
            await self.connection.execute(
                "INSERT INTO logs (level, source, message) VALUES (?, ?, ?)",
                (level, source, message[:2000])
            )
            await self.connection.commit()
        except Exception as e:
            print(f"⚠️ Failed to write log entry: {e}")
    
    async def get_logs(self, level: Optional[str] = None, limit: int = 30) -> List[tuple]:
        if level:
            cursor = await self.connection.execute(
                "SELECT level, source, message, created_at FROM logs WHERE level = ? ORDER BY id DESC LIMIT ?",
                (level, limit)
            )
        else:
            cursor = await self.connection.execute(
                "SELECT level, source, message, created_at FROM logs ORDER BY id DESC LIMIT ?", (limit,)
            )
        return await cursor.fetchall()
    
    async def cleanup_old_logs(self, days: int = 7):
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        async with self._lock:
            try:
                await self.connection.execute("DELETE FROM logs WHERE created_at < ?", (cutoff,))
                await self.connection.commit()
            except Exception as e:
                await self.connection.rollback()
                print(f"❌ Error cleaning up logs: {e}")
    
    # ---- factory_admins (role-based, separate from any single bot's admins) ----
    
    async def get_factory_admin(self, user_id: int) -> Optional[dict]:
        cursor = await self.connection.execute(
            "SELECT role, permissions FROM factory_admins WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return None
        try:
            perms = json.loads(row[1])
        except (json.JSONDecodeError, TypeError):
            perms = []
        return {"role": row[0], "permissions": perms}
    
    async def set_factory_admin(self, user_id: int, role: str, permissions: List[str]):
        async with self._lock:
            try:
                await self.connection.execute(
                    """INSERT INTO factory_admins (user_id, role, permissions)
                       VALUES (?, ?, ?)
                       ON CONFLICT(user_id) DO UPDATE SET role = excluded.role, permissions = excluded.permissions""",
                    (user_id, role, json.dumps(permissions))
                )
                await self.connection.commit()
            except Exception as e:
                await self.connection.rollback()
                print(f"❌ Error setting factory admin: {e}")
    
    async def remove_factory_admin(self, user_id: int):
        async with self._lock:
            try:
                await self.connection.execute("DELETE FROM factory_admins WHERE user_id = ?", (user_id,))
                await self.connection.commit()
            except Exception as e:
                await self.connection.rollback()
                print(f"❌ Error removing factory admin: {e}")
    
    async def list_factory_admins(self) -> List[dict]:
        cursor = await self.connection.execute("SELECT user_id, role, permissions FROM factory_admins")
        rows = await cursor.fetchall()
        result = []
        for uid, role, perms in rows:
            try:
                perms_list = json.loads(perms)
            except (json.JSONDecodeError, TypeError):
                perms_list = []
            result.append({"user_id": uid, "role": role, "permissions": perms_list})
        return result
    
    # ---- factory_users (people who've messaged the factory bot itself) ----
    
    async def add_factory_user(self, chat_id: int, username: str, first_name: str) -> bool:
        """Same pattern as add_user() but for the factory bot's own
        audience. Returns True if this is a first-time contact."""
        username = (username or "")[:64]
        first_name = (first_name or "")[:128]
        async with self._lock:
            try:
                await self.connection.execute("BEGIN")
                cursor = await self.connection.execute(
                    "INSERT OR IGNORE INTO factory_users (chat_id, username, first_name) VALUES (?, ?, ?)",
                    (chat_id, username, first_name)
                )
                is_new = cursor.rowcount > 0
                await self.connection.execute(
                    "UPDATE factory_users SET last_active = CURRENT_TIMESTAMP WHERE chat_id = ?", (chat_id,)
                )
                await self.connection.commit()
                return is_new
            except Exception as e:
                await self.connection.rollback()
                print(f"❌ Error adding factory user: {e}")
                return False
    
    async def get_factory_user_ids(self, audience: str = "all") -> List[int]:
        """audience: all | owners | new_today | active_7d | inactive_30d"""
        base = "SELECT DISTINCT fu.chat_id FROM factory_users fu"
        where = "WHERE fu.is_blocked = 0"
        params: tuple = ()
        
        if audience == "owners":
            base += " JOIN bots b ON b.owner_id = fu.chat_id"
        elif audience == "new_today":
            since = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
            where += " AND fu.first_seen >= ?"
            params = (since,)
        elif audience == "active_7d":
            since = (datetime.now() - timedelta(days=7)).isoformat()
            where += " AND fu.last_active >= ?"
            params = (since,)
        elif audience == "inactive_30d":
            since = (datetime.now() - timedelta(days=30)).isoformat()
            where += " AND fu.last_active < ?"
            params = (since,)
        
        cursor = await self.connection.execute(f"{base} {where}", params)
        return [row[0] for row in await cursor.fetchall()]
    
    async def factory_stats(self) -> dict:
        cursor = await self.connection.execute("SELECT COUNT(*) FROM factory_users")
        total = (await cursor.fetchone())[0]
        since = (datetime.now() - timedelta(days=1)).isoformat()
        cursor = await self.connection.execute(
            "SELECT COUNT(*) FROM factory_users WHERE last_active >= ?", (since,)
        )
        active_today = (await cursor.fetchone())[0]
        return {"total": total, "active_today": active_today}
    
    # ---- factory_blocks (block a person from the factory / bot creation / their existing bots) ----
    
    async def set_factory_block(self, user_id: int, block_factory_use: bool, block_bot_creation: bool,
                                 bots_disabled: bool, reason: str = ""):
        async with self._lock:
            try:
                await self.connection.execute(
                    """INSERT INTO factory_blocks (user_id, block_factory_use, block_bot_creation, bots_disabled, reason)
                       VALUES (?, ?, ?, ?, ?)
                       ON CONFLICT(user_id) DO UPDATE SET
                           block_factory_use = excluded.block_factory_use,
                           block_bot_creation = excluded.block_bot_creation,
                           bots_disabled = excluded.bots_disabled,
                           reason = excluded.reason""",
                    (user_id, block_factory_use, block_bot_creation, bots_disabled, reason)
                )
                await self.connection.commit()
            except Exception as e:
                await self.connection.rollback()
                print(f"❌ Error setting factory block: {e}")
    
    async def clear_factory_block(self, user_id: int):
        async with self._lock:
            try:
                await self.connection.execute("DELETE FROM factory_blocks WHERE user_id = ?", (user_id,))
                await self.connection.commit()
            except Exception as e:
                await self.connection.rollback()
                print(f"❌ Error clearing factory block: {e}")
    
    async def get_factory_block(self, user_id: int) -> Optional[dict]:
        cursor = await self.connection.execute(
            "SELECT block_factory_use, block_bot_creation, bots_disabled, reason FROM factory_blocks WHERE user_id = ?",
            (user_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return {"block_factory_use": bool(row[0]), "block_bot_creation": bool(row[1]),
                "bots_disabled": bool(row[2]), "reason": row[3]}
    
    async def list_factory_blocks(self) -> List[dict]:
        cursor = await self.connection.execute(
            "SELECT user_id, block_factory_use, block_bot_creation, bots_disabled, reason FROM factory_blocks"
        )
        rows = await cursor.fetchall()
        return [
            {"user_id": r[0], "block_factory_use": bool(r[1]), "block_bot_creation": bool(r[2]),
             "bots_disabled": bool(r[3]), "reason": r[4]}
            for r in rows
        ]
    
    async def close(self):
        """Close database connection"""
        if self.connection:
            await self.connection.close()
            print("✅ Database closed")

# Global instance
db = Database()
