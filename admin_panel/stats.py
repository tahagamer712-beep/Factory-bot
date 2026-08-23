"""Real stats computed from the actual database - no placeholder numbers."""

from datetime import datetime, timedelta
from db import db


def _humanize(ts_str: str) -> str:
    try:
        ts = datetime.fromisoformat(ts_str)
    except (ValueError, TypeError):
        return ts_str or "—"
    delta = datetime.now() - ts
    if delta < timedelta(minutes=1):
        return "الآن"
    if delta < timedelta(hours=1):
        return f"قبل {int(delta.total_seconds() // 60)} دقيقة"
    if delta < timedelta(days=1):
        return f"قبل {int(delta.total_seconds() // 3600)} ساعة"
    return f"قبل {delta.days} يوم"


async def today_stats(bot_id: int) -> dict:
    since = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    
    cursor = await db.connection.execute(
        "SELECT COUNT(*) FROM bot_users WHERE bot_id = ?", (bot_id,))
    total_users = (await cursor.fetchone())[0]
    
    cursor = await db.connection.execute(
        "SELECT COUNT(*) FROM bot_users WHERE bot_id = ? AND first_seen >= ?", (bot_id, since))
    new_users = (await cursor.fetchone())[0]
    
    cursor = await db.connection.execute(
        "SELECT COUNT(*) FROM messages WHERE bot_id = ? AND timestamp >= ?", (bot_id, since))
    messages = (await cursor.fetchone())[0]
    
    cursor = await db.connection.execute(
        "SELECT COUNT(DISTINCT chat_id) FROM messages WHERE bot_id = ? AND timestamp >= ?", (bot_id, since))
    sessions = (await cursor.fetchone())[0]
    
    cursor = await db.connection.execute(
        "SELECT MAX(timestamp) FROM messages WHERE bot_id = ?", (bot_id,))
    row = await cursor.fetchone()
    last_activity = _humanize(row[0]) if row and row[0] else "لا يوجد نشاط بعد"
    
    return {
        "total_users": total_users,
        "new_users": new_users,
        "messages": messages,
        "sessions": sessions,
        # Response-time tracking isn't implemented anywhere in the engine
        # yet, so this is honestly 0 rather than a made-up number.
        "avg_response_ms": 0,
        "last_activity": last_activity,
    }


async def users_stats(bot_id: int) -> dict:
    since = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    week_ago = (datetime.now() - timedelta(days=7)).isoformat()
    
    cursor = await db.connection.execute(
        "SELECT COUNT(*) FROM bot_users WHERE bot_id = ?", (bot_id,))
    total = (await cursor.fetchone())[0]
    
    cursor = await db.connection.execute(
        "SELECT COUNT(*) FROM bot_users WHERE bot_id = ? AND is_blocked = 1", (bot_id,))
    blocked = (await cursor.fetchone())[0]
    
    cursor = await db.connection.execute(
        "SELECT COUNT(*) FROM bot_users WHERE bot_id = ? AND last_active >= ?", (bot_id, week_ago))
    active_7d = (await cursor.fetchone())[0]
    
    cursor = await db.connection.execute(
        "SELECT COUNT(*) FROM bot_users WHERE bot_id = ? AND first_seen >= ?", (bot_id, since))
    today = (await cursor.fetchone())[0]
    
    return {"total": total, "blocked": blocked, "active_7d": active_7d, "today": today}


async def get_blocked_users(bot_id: int, limit: int = 500, offset: int = 0) -> list:
    cursor = await db.connection.execute(
        "SELECT chat_id FROM bot_users WHERE bot_id = ? AND is_blocked = 1 LIMIT ? OFFSET ?",
        (bot_id, limit, offset)
    )
    return [row[0] for row in await cursor.fetchall()]


async def get_recent_events(bot_id: int, limit: int = 15) -> list:
    cursor = await db.connection.execute(
        "SELECT event_type, description, timestamp FROM events WHERE bot_id = ? ORDER BY timestamp DESC LIMIT ?",
        (bot_id, limit)
    )
    return await cursor.fetchall()
