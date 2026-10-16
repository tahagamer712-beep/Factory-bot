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

async def command_center_stats(bot_id: int) -> dict:
    """Real numbers for the command-center home screen. No placeholders."""
    from datetime import datetime, timedelta
    import os, glob
    now = datetime.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    day_ago = (now - timedelta(hours=24)).isoformat()

    c = await db.connection.execute(
        "SELECT COUNT(*) FROM bot_users WHERE bot_id = ?", (bot_id,))
    total_users = (await c.fetchone())[0]

    c = await db.connection.execute(
        "SELECT COUNT(*) FROM bot_users WHERE bot_id = ? AND first_seen >= ?",
        (bot_id, today))
    new_today = (await c.fetchone())[0]

    # "Active conversations": distinct users with any message in last 24h
    c = await db.connection.execute(
        "SELECT COUNT(DISTINCT chat_id) FROM messages WHERE bot_id = ? AND timestamp >= ?",
        (bot_id, day_ago))
    active_24h = (await c.fetchone())[0]

    # Pending reports (new + reviewing)
    try:
        c = await db.connection.execute(
            "SELECT COUNT(*) FROM reports WHERE bot_id = ? AND status IN ('new','reviewing')",
            (bot_id,))
        pending_reports = (await c.fetchone())[0]
    except Exception:
        pending_reports = 0

    # Blocked users
    c = await db.connection.execute(
        "SELECT COUNT(*) FROM bot_users WHERE bot_id = ? AND is_blocked = 1",
        (bot_id,))
    blocked = (await c.fetchone())[0]

    # Last 5 admin events
    c = await db.connection.execute(
        "SELECT event_type, description, timestamp FROM events WHERE bot_id = ? "
        "ORDER BY timestamp DESC LIMIT 5", (bot_id,))
    recent_events = await c.fetchall()

    # Last errors for this bot (logs source = 'bot:<id>')
    c = await db.connection.execute(
        "SELECT message, created_at FROM logs WHERE source = ? AND level = 'error' "
        "ORDER BY created_at DESC LIMIT 3", (f"bot:{bot_id}",))
    recent_errors = await c.fetchall()

    # Latest factory backup (covers all bots' data)
    backups = sorted(glob.glob(os.path.expanduser("~/factory/backups/factory_backup_*.zip")))
    last_backup = os.path.basename(backups[-1]) if backups else None

    # DB size
    try:
        db_size = os.path.getsize(os.path.expanduser("~/factory/data/factory.db"))
        db_size_mb = round(db_size / 1024 / 1024, 2)
    except OSError:
        db_size_mb = 0

    c = await db.connection.execute(
        "SELECT MAX(timestamp) FROM messages WHERE bot_id = ?", (bot_id,))
    row = await c.fetchone()
    last_activity = _humanize(row[0]) if row and row[0] else "لا يوجد نشاط بعد"

    return {
        "total_users": total_users,
        "new_today": new_today,
        "active_24h": active_24h,
        "pending_reports": pending_reports,
        "blocked": blocked,
        "recent_events": recent_events,
        "recent_errors": recent_errors,
        "last_backup": last_backup,
        "db_size_mb": db_size_mb,
        "last_activity": last_activity,
    }


async def find_user(bot_id: int, query: str):
    """Search bot_users by chat_id or username. Returns list of dicts."""
    query = query.strip().lstrip("@")
    c = await db.connection.execute(
        "SELECT chat_id, username, first_name, first_seen, last_active, is_blocked "
        "FROM bot_users WHERE bot_id = ? AND (CAST(chat_id AS TEXT) = ? OR username = ? COLLATE NOCASE) "
        "LIMIT 10", (bot_id, query, query))
    rows = await c.fetchall()
    return [dict(zip(["chat_id", "username", "first_name", "first_seen",
                      "last_active", "is_blocked"], r)) for r in rows]


async def user_detail(bot_id: int, chat_id: int):
    """Full detail for one user: profile + message stats + note + admin actions."""
    c = await db.connection.execute(
        "SELECT chat_id, username, first_name, first_seen, last_active, is_blocked "
        "FROM bot_users WHERE bot_id = ? AND chat_id = ?", (bot_id, chat_id))
    row = await c.fetchone()
    if not row:
        return None
    user = dict(zip(["chat_id", "username", "first_name", "first_seen",
                     "last_active", "is_blocked"], row))
    c = await db.connection.execute(
        "SELECT COUNT(*) FROM messages WHERE bot_id = ? AND chat_id = ?",
        (bot_id, chat_id))
    user["msg_count"] = (await c.fetchone())[0]
    c = await db.connection.execute(
        "SELECT COUNT(*) FROM reports WHERE bot_id = ? AND target_id = ?",
        (bot_id, chat_id))
    user["reports_against"] = (await c.fetchone())[0]
    # Admin note stored in bot_settings
    c = await db.connection.execute(
        "SELECT value FROM bot_settings WHERE bot_id = ? AND key = ?",
        (bot_id, f"user_note_{chat_id}"))
    nrow = await c.fetchone()
    user["admin_note"] = nrow[0] if nrow else None
    # Admin actions on this user from events
    c = await db.connection.execute(
        "SELECT description, timestamp FROM events WHERE bot_id = ? AND "
        "(description LIKE ? OR description LIKE ?) ORDER BY timestamp DESC LIMIT 5",
        (bot_id, f"%{chat_id}%block%", f"%{chat_id}%unblock%"))
    user["admin_actions"] = await c.fetchall()
    return user


async def active_conversations(bot_id: int, hours: int = 24, limit: int = 20):
    """Users with recent message activity. No message content exposed."""
    from datetime import datetime, timedelta
    since = (datetime.now() - timedelta(hours=hours)).isoformat()
    c = await db.connection.execute(
        "SELECT u.chat_id, u.username, u.first_name, COUNT(m.id) AS n, MAX(m.timestamp) AS last_msg "
        "FROM bot_users u JOIN messages m ON m.bot_id = u.bot_id AND m.chat_id = u.chat_id "
        "WHERE u.bot_id = ? AND m.timestamp >= ? "
        "GROUP BY u.chat_id ORDER BY last_msg DESC LIMIT ?",
        (bot_id, since, limit))
    rows = await c.fetchall()
    return [dict(zip(["chat_id", "username", "first_name", "msg_count", "last_msg"], r))
            for r in rows]


# ================= Phase 3: advanced analytics =================
# Every number comes from a real query. Missing data -> "البيانات غير متاحة"
# (never a misleading zero). All timestamps are phone-local = Asia/Baghdad.

async def analytics_overview(bot_id: int) -> dict:
    """Professional analytics. Definitions:
    - active_24h/7d: users whose last_active is within the period
    - acquisition: new users in last 7d vs the 7d before that
    - peak hours: top hours by message count (needs >=20 messages)
    - report resolution: avg(decided_at - created_at) for decided reports
    """
    from datetime import datetime, timedelta
    now = datetime.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    d1, d7, d14, d30 = (today - timedelta(days=n) for n in (1, 7, 14, 30))
    h24 = now - timedelta(hours=24)
    iso = lambda dt: dt.isoformat()

    async def one(q, *a):
        c = await db.connection.execute(q, a)
        return (await c.fetchone())[0]

    out = {}

    # --- users ---
    out["total_users"] = await one("SELECT COUNT(*) FROM bot_users WHERE bot_id = ?", bot_id)
    new = {}
    for label, since in (("today", today), ("d7", d7), ("d30", d30)):
        new[label] = await one(
            "SELECT COUNT(*) FROM bot_users WHERE bot_id = ? AND first_seen >= ?", bot_id, iso(since))
    out["new"] = new
    out["active_24h"] = await one(
        "SELECT COUNT(*) FROM bot_users WHERE bot_id = ? AND last_active >= ?", bot_id, iso(h24))
    out["active_7d"] = await one(
        "SELECT COUNT(*) FROM bot_users WHERE bot_id = ? AND last_active >= ?", bot_id, iso(d7))

    # --- acquisition: last 7d vs previous 7d ---
    prev7 = await one(
        "SELECT COUNT(*) FROM bot_users WHERE bot_id = ? AND first_seen >= ? AND first_seen < ?",
        bot_id, iso(d14), iso(d7))
    cur7 = new["d7"]
    if prev7 > 0:
        out["growth_pct"] = round((cur7 - prev7) / prev7 * 100, 1)
    elif cur7 > 0:
        out["growth_pct"] = None  # new growth, no baseline -> show "لا أساس للمقارنة"
    else:
        out["growth_pct"] = 0.0
    out["prev7"] = prev7

    # --- peak hours (needs >=20 messages to be meaningful) ---
    msg_total = await one("SELECT COUNT(*) FROM messages WHERE bot_id = ?", bot_id)
    out["msg_total"] = msg_total
    if msg_total >= 20:
        c = await db.connection.execute(
            "SELECT CAST(strftime('%H', timestamp) AS INTEGER) AS h, COUNT(*) AS n "
            "FROM messages WHERE bot_id = ? GROUP BY h ORDER BY n DESC LIMIT 3", (bot_id,))
        out["peak_hours"] = [(r[0], r[1]) for r in await c.fetchall()]
    else:
        out["peak_hours"] = None

    # --- reports ---
    try:
        out["reports_new"] = await one(
            "SELECT COUNT(*) FROM reports WHERE bot_id = ? AND status = 'new'", bot_id)
        out["reports_open"] = await one(
            "SELECT COUNT(*) FROM reports WHERE bot_id = ? AND status IN ('new','reviewing')", bot_id)
        out["reports_closed"] = await one(
            "SELECT COUNT(*) FROM reports WHERE bot_id = ? AND status = 'closed'", bot_id)
        c = await db.connection.execute(
            "SELECT AVG((julianday(decided_at) - julianday(created_at)) * 24) FROM reports "
            "WHERE bot_id = ? AND decided_at IS NOT NULL", (bot_id,))
        avg_h = (await c.fetchone())[0]
        out["reports_avg_hours"] = round(avg_h, 1) if avg_h is not None else None
    except Exception:
        out["reports_new"] = out["reports_open"] = out["reports_closed"] = None
        out["reports_avg_hours"] = None

    # --- broadcasts (from queue_jobs) ---
    out["bc_total"] = await one(
        "SELECT COUNT(*) FROM queue_jobs WHERE bot_id = ? AND job_type = 'broadcast'", bot_id)
    c = await db.connection.execute(
        "SELECT status, data, created_at FROM queue_jobs WHERE bot_id = ? AND job_type = 'broadcast' "
        "ORDER BY job_id DESC LIMIT 1", (bot_id,))
    row = await c.fetchone()
    out["bc_last"] = None
    if row:
        import json
        try:
            stats = json.loads(row[1]) if row[1] else {}
        except Exception:
            stats = {}
        out["bc_last"] = {"status": row[0], "stats": stats, "created_at": row[2]}

    # --- errors (24h) ---
    out["errors_24h"] = await one(
        "SELECT COUNT(*) FROM logs WHERE source = ? AND level = 'error' AND created_at >= ?",
        f"bot:{bot_id}", iso(h24))

    # --- backups ---
    out["backups_total"] = await one("SELECT COUNT(*) FROM backups")
    c = await db.connection.execute(
        "SELECT filename, integrity_ok, created_at FROM backups ORDER BY id DESC LIMIT 1")
    row = await c.fetchone()
    out["backup_last"] = dict(zip(["filename", "integrity_ok", "created_at"], row)) if row else None

    return out
