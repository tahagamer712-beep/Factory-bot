# -*- coding: utf-8 -*-
"""Phase 3: health checks + stuck-state detection + alert management.

Evidence-based only: an issue is raised only when DB state proves it.
Thresholds are configurable per-bot via bot_settings.
Alerts are deduped by (bot_id, alert_type, ref) - re-detection refreshes
last_seen instead of spamming a new row.
"""

from datetime import datetime, timedelta
from db import db

# alert_type constants
T_STUCK_BROADCAST = "stuck_broadcast"
T_STUCK_JOB = "stuck_job"
T_STALE_REPORT = "stale_report"
T_BACKUP_FAILED = "backup_failed"
T_REPEATED_ERRORS = "repeated_errors"
T_POLLER_DOWN = "poller_down"

DEFAULTS = {
    "alert_broadcast_timeout_min": 120,
    "alert_job_timeout_min": 120,
    "alert_report_stale_hours": 48,
    "alert_error_repeat_count": 5,
    "alert_error_repeat_hours": 1,
}


async def _threshold(bot_id: int, key: str) -> int:
    try:
        return int(await db.get_setting(bot_id, key, DEFAULTS[key]))
    except (ValueError, TypeError):
        return DEFAULTS[key]


async def run_health_checks(bot_id: int) -> list:
    """Run all checks, upsert alerts, return list of (alert_type, severity, title)."""
    found = []
    found += await _check_stuck_broadcasts(bot_id)
    found += await _check_stuck_jobs(bot_id)
    found += await _check_stale_reports(bot_id)
    found += await _check_backup_failures(bot_id)
    found += await _check_repeated_errors(bot_id)
    found += await _check_poller(bot_id)
    return found


async def _check_stuck_broadcasts(bot_id: int) -> list:
    timeout = await _threshold(bot_id, "alert_broadcast_timeout_min")
    stuck = await db.get_stuck_jobs(bot_id, timeout_minutes=timeout)
    out = []
    for j in stuck:
        if "broadcast" not in (j.get("job_type") or ""):
            continue
        aid = await db.upsert_alert(
            bot_id, T_STUCK_BROADCAST, "critical",
            f"إذاعة عالقة #{j['job_id']}",
            f"بدأت {j.get('started_at') or j.get('created_at')} ولم تتحدث منذ "
            f"{j.get('updated_at') or j.get('started_at')}. تحقق من السجلات قبل الإلغاء.",
            ref=f"job:{j['job_id']}")
        out.append((T_STUCK_BROADCAST, "critical", aid))
    return out


async def _check_stuck_jobs(bot_id: int) -> list:
    timeout = await _threshold(bot_id, "alert_job_timeout_min")
    stuck = await db.get_stuck_jobs(bot_id, timeout_minutes=timeout)
    out = []
    for j in stuck:
        if "broadcast" in (j.get("job_type") or ""):
            continue
        aid = await db.upsert_alert(
            bot_id, T_STUCK_JOB, "warning",
            f"مهمة عالقة #{j['job_id']} ({j.get('job_type')})",
            f"في حالة processing منذ {j.get('started_at') or j.get('created_at')} "
            f"دون تحديث. قد تحتاج مراجعة يدوية.",
            ref=f"job:{j['job_id']}")
        out.append((T_STUCK_JOB, "warning", aid))
    return out


async def _check_stale_reports(bot_id: int) -> list:
    hours = await _threshold(bot_id, "alert_report_stale_hours")
    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
    try:
        c = await db.connection.execute(
            "SELECT id, created_at FROM reports WHERE bot_id = ? AND status IN ('new','reviewing') "
            "AND created_at < ?", (bot_id, cutoff))
        rows = await c.fetchall()
    except Exception:
        return []
    out = []
    for rid, created in rows:
        aid = await db.upsert_alert(
            bot_id, T_STALE_REPORT, "warning",
            f"بلاغ #{rid} معلق منذ {created[:16]}",
            f"تجاوز حد المراجعة ({hours} ساعة). راجعه من شاشة البلاغات.",
            ref=f"report:{rid}")
        out.append((T_STALE_REPORT, "warning", aid))
    return out


async def _check_backup_failures(bot_id: int) -> list:
    c = await db.connection.execute(
        "SELECT id, filename, created_at FROM backups WHERE integrity_ok = 0 "
        "ORDER BY id DESC LIMIT 3")
    rows = await c.fetchall()
    out = []
    for bid, fn, ts in rows:
        aid = await db.upsert_alert(
            bot_id, T_BACKUP_FAILED, "critical",
            f"فشل نسخة احتياطية: {fn}",
            f"أُنشئت {ts} لكن فحص السلامة فشل. لا تعتمد عليها للاستعادة.",
            ref=f"backup:{bid}")
        out.append((T_BACKUP_FAILED, "critical", aid))
    return out


async def _check_repeated_errors(bot_id: int) -> list:
    count_th = await _threshold(bot_id, "alert_error_repeat_count")
    hours = await _threshold(bot_id, "alert_error_repeat_hours")
    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
    c = await db.connection.execute(
        "SELECT substr(message, 1, 60) AS m, COUNT(*) AS n, MAX(created_at) AS last_t "
        "FROM logs WHERE source = ? AND level = 'error' AND created_at >= ? "
        "GROUP BY m HAVING n >= ? ORDER BY n DESC LIMIT 3",
        (f"bot:{bot_id}", cutoff, count_th))
    rows = await c.fetchall()
    out = []
    for msg, n, last_t in rows:
        aid = await db.upsert_alert(
            bot_id, T_REPEATED_ERRORS, "warning",
            f"خطأ متكرر ({n} مرات): {(msg or '')[:50]}",
            f"تكرر {n} مرات خلال {hours} ساعة. آخر ظهور: {last_t}. "
            f"لن يُرسل تنبيه جديد لهذه الحادثة.",
            ref=f"err:{hash(msg) % 10**8}")
        out.append((T_REPEATED_ERRORS, "warning", aid))
    return out


async def _check_poller(bot_id: int) -> list:
    try:
        from poller import poller_supervisor as _sup
        # Zero pollers globally = standalone/test context, not a live factory:
        # cannot verify -> Unknown, never a false critical alert.
        if not getattr(_sup, "pollers", None):
            return []
        p = _sup.pollers.get(bot_id)
        running = bool(p and getattr(p, "is_running", False))
    except Exception:
        return []  # cannot verify -> Unknown, not an alert
    if not running:
        aid = await db.upsert_alert(
            bot_id, T_POLLER_DOWN, "critical",
            "الـpolling متوقف لهذا البوت",
            "لا يوجد poller حي مسجل لهذا البوت. أعد تشغيل المصنع.",
            ref="poller")
        return [(T_POLLER_DOWN, "critical", aid)]
    return []


def classify_health(open_alerts: dict, poller_status: str, db_integrity: str) -> str:
    """healthy / warning / critical / unknown - honest, never claims healthy blindly."""
    if db_integrity not in ("ok",):
        return "critical"
    if poller_status in ("غير معروف", "لا يوجد poller"):
        return "unknown"
    if open_alerts.get("critical", 0) > 0:
        return "critical"
    if open_alerts.get("warning", 0) > 0:
        return "warning"
    if poller_status == "متوقف":
        return "critical"
    return "healthy"


HEALTH_LABEL = {
    "healthy": "🟢 سليم",
    "warning": "🟡 تحذير",
    "critical": "🔴 حرج",
    "unknown": "⚪ غير معروف",
}
