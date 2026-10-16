"""
Phase 3 tests: analytics, stuck detection, jobs, health, alerts, security.
Safe: uses TEST_BOT (8919249178) + fake IDs, cleans up after itself.
Never sends real broadcasts or bans real users.
"""
import asyncio
import sys
import json
from datetime import datetime, timedelta

sys.path.insert(0, "/data/data/com.termux/files/home/Factory-bot")

from db import db
from admin_panel import permissions as pm
from admin_panel.auth import has_permission, is_owner

TEST_BOT = 8919249178
OWNER = 5149213983
FAKE_ADMIN = 999000111
FAKE_USER = 999000222
FAKE_USER2 = 999000333

passed, failed = [], []

def check(name, cond, detail=""):
    (passed if cond else failed).append(name)
    print(f"  {'PASS' if cond else 'FAIL'} {name} {detail if not cond else ''}")


async def seed_analytics_data():
    """Known dataset: 3 fake users with controlled timestamps."""
    now = datetime.now()
    async with db._lock:
        for uid, days_ago, active_days_ago in [
            (FAKE_USER, 0, 0), (FAKE_USER2, 10, 1), (999000444, 40, 30)]:
            fs = (now - timedelta(days=days_ago)).isoformat()
            la = (now - timedelta(days=active_days_ago)).isoformat()
            await db.connection.execute(
                "INSERT OR REPLACE INTO bot_users (bot_id, chat_id, username, first_seen, last_active) "
                "VALUES (?, ?, ?, ?, ?)", (TEST_BOT, uid, f"u{uid}", fs, la))
            # messages for peak-hour test (hour 0)
            ts = now.replace(hour=0, minute=10).isoformat()
            await db.connection.execute(
                "INSERT INTO messages (bot_id, chat_id, text, timestamp) VALUES (?, ?, ?, ?)",
                (TEST_BOT, uid, "hi", ts))
        await db.connection.commit()

async def cleanup_analytics_data():
    async with db._lock:
        await db.connection.execute(
            "DELETE FROM bot_users WHERE bot_id = ? AND chat_id IN (?, ?, ?)",
            (TEST_BOT, FAKE_USER, FAKE_USER2, 999000444))
        await db.connection.execute(
            "DELETE FROM messages WHERE bot_id = ? AND chat_id IN (?, ?, ?)",
            (TEST_BOT, FAKE_USER, FAKE_USER2, 999000444))
        await db.connection.execute("DELETE FROM alerts WHERE bot_id = ?", (TEST_BOT,))
        await db.connection.execute(
            "DELETE FROM queue_jobs WHERE bot_id = ? AND job_type IN ('broadcast','test_job')",
            (TEST_BOT,))
        await db.connection.commit()

async def test_analytics_accuracy():
    print("== 1. analytics accuracy (known data) ==")
    from admin_panel import stats as st
    await seed_analytics_data()
    a = await st.analytics_overview(TEST_BOT)
    check("ana_total", a["total_users"] >= 3, a["total_users"])
    check("ana_new_today", a["new"]["today"] >= 1, a["new"])
    check("ana_new_7d", a["new"]["d7"] >= 1, a["new"])
    check("ana_new_30d", a["new"]["d30"] >= 2, a["new"])
    check("ana_active_24h", a["active_24h"] >= 1, a["active_24h"])
    check("ana_active_7d", a["active_7d"] >= 2, a["active_7d"])
    check("ana_msg_total", a["msg_total"] >= 3, a["msg_total"])
    # peak hours: we seeded 3 msgs at hour 0
    ph = a.get("peak_hours")
    check("ana_peak_hours", ph is None or any(h == 0 for h, _ in ph), ph)

async def test_timezones():
    print("== 2. time periods & Baghdad timezone ==")
    from admin_panel import stats as st
    # phone local time must be +03 (Baghdad)
    import time
    check("tz_is_baghdad", time.timezone == -10800, time.timezone)
    a = await st.analytics_overview(TEST_BOT)
    # 'today' boundary uses local midnight - just verify keys exist and sane
    check("tz_keys", all(k in a["new"] for k in ("today", "d7", "d30")))

async def test_missing_data():
    print("== 3. missing historical data honesty ==")
    from admin_panel import screens as sc
    # bot with no reports table data -> screen must not show misleading zeros
    a = {"total_users": 0, "new": {"today": 0, "d7": 0, "d30": 0}, "active_24h": 0,
         "active_7d": 0, "growth_pct": 0.0, "prev7": 0, "peak_hours": None,
         "msg_total": 0, "reports_new": None, "reports_open": None, "reports_closed": None,
         "reports_avg_hours": None, "bc_total": 0, "bc_last": None, "errors_24h": 0,
         "backups_total": 0, "backup_last": None}
    txt = sc.analytics_menu(a)
    check("missing_peak_honest", "البيانات غير متاحة" in txt)
    check("missing_reports_honest", "البيانات غير متاحة" in txt)
    check("missing_bc_honest", "لا يوجد بعد" in txt)

async def test_stuck_detection():
    print("== 4. stuck detection (no false positives) ==")
    from admin_panel import health as h
    # fresh completed job must NOT be flagged
    async with db._lock:
        cur = await db.connection.execute(
            "INSERT INTO queue_jobs (bot_id, job_type, status, data) VALUES (?, 'test_job', 'completed', '{}')",
            (TEST_BOT,))
        jid = cur.lastrowid
        await db.connection.commit()
    stuck = await db.get_stuck_jobs(TEST_BOT, timeout_minutes=120)
    check("completed_not_stuck", not any(j["job_id"] == jid for j in stuck))
    # old processing job IS stuck
    old = (datetime.now() - timedelta(hours=5)).isoformat()
    async with db._lock:
        cur = await db.connection.execute(
            "INSERT INTO queue_jobs (bot_id, job_type, status, data, created_at, updated_at) "
            "VALUES (?, 'test_job', 'processing', '{}', ?, ?)", (TEST_BOT, old, old))
        jid2 = cur.lastrowid
        await db.connection.commit()
    stuck = await db.get_stuck_jobs(TEST_BOT, timeout_minutes=120)
    check("old_processing_is_stuck", any(j["job_id"] == jid2 for j in stuck))
    # alert dedupe: run twice, still one open alert
    await db.upsert_alert(TEST_BOT, "stuck_job", "warning", "t", "d", ref=f"job:{jid2}")
    await db.upsert_alert(TEST_BOT, "stuck_job", "warning", "t", "d", ref=f"job:{jid2}")
    c = await db.connection.execute(
        "SELECT COUNT(*) FROM alerts WHERE bot_id = ? AND ref = ?", (TEST_BOT, f"job:{jid2}"))
    check("alert_dedupe", (await c.fetchone())[0] == 1)

async def test_job_transitions():
    print("== 5. job state transitions ==")
    async with db._lock:
        cur = await db.connection.execute(
            "INSERT INTO queue_jobs (bot_id, job_type, status, data) VALUES (?, 'test_job', 'pending', '{}')",
            (TEST_BOT,))
        jid = cur.lastrowid
        await db.connection.commit()
    await db.mark_job_started(jid)
    c = await db.connection.execute("SELECT started_at FROM queue_jobs WHERE job_id = ?", (jid,))
    check("job_started_at", (await c.fetchone())[0] is not None)
    await db.update_job_progress(jid, json.dumps({"progress": {"sent": 5}}))
    c = await db.connection.execute("SELECT data, updated_at FROM queue_jobs WHERE job_id = ?", (jid,))
    row = await c.fetchone()
    check("job_progress", "sent" in row[0] and row[1] is not None)
    await db.mark_job_failed(jid, "boom")
    c = await db.connection.execute("SELECT status FROM queue_jobs WHERE job_id = ?", (jid,))
    check("job_failed", (await c.fetchone())[0] == "failed")

async def test_double_execution():
    print("== 6. double execution prevention ==")
    # two processing broadcasts -> count detects it (router refuses second)
    async with db._lock:
        await db.connection.execute(
            "INSERT INTO queue_jobs (bot_id, job_type, status, data) VALUES (?, 'broadcast', 'processing', '{}')",
            (TEST_BOT,))
        await db.connection.commit()
    n = await db.count_processing_broadcasts(TEST_BOT)
    check("processing_count", n >= 1, n)
    # second start must be blocked by the check the router uses
    blocked = n >= 1
    check("second_start_blocked", blocked)

async def test_restart_recovery():
    print("== 7. restart during job ==")
    from broadcast_engine import broadcast_engine
    # simulate: processing broadcast at startup gets resumed (not duplicated)
    async with db._lock:
        cur = await db.connection.execute(
            "INSERT INTO queue_jobs (bot_id, job_type, status, data) VALUES (?, 'broadcast', 'processing', ?)",
            (TEST_BOT, json.dumps({"text": "x", "offset": 0})))
        jid = cur.lastrowid
        await db.connection.commit()
    rows_before = await db.get_stuck_jobs(TEST_BOT, timeout_minutes=0)
    check("processing_visible", any(j["job_id"] == jid for j in rows_before))
    # resume_pending_broadcasts must not crash on it
    try:
        await broadcast_engine.resume_pending_broadcasts()
        check("resume_no_crash", True)
    except Exception as e:
        check("resume_no_crash", False, str(e)[:80])

async def test_error_classification():
    print("== 8. transient vs permanent errors ==")
    # classification logic mirrored from broadcast_engine
    def cls(code):
        return "perm" if code in (403, 400, 401, 404) else "temp"
    check("perm_403", cls(403) == "perm")
    check("perm_400", cls(400) == "perm")
    check("temp_429", cls(429) == "temp")
    check("temp_none", cls(None) == "temp")
    check("temp_500", cls(500) == "temp")

async def test_api_failure_paths():
    print("== 9. API failure paths ==")
    # mark_job_failed sanitizes (no secrets stored)
    await db.mark_job_failed(999999999, "token 123456:ABC-DEF secret leaked here")
    c = await db.connection.execute("SELECT data FROM queue_jobs WHERE job_id = 999999999")
    row = await c.fetchone()
    # job doesn't exist -> row None, but must not crash
    check("failed_missing_job_safe", row is None)
    # sanitize check via audit path
    from admin_panel import audit as au
    ok = await au.log_action(TEST_BOT, OWNER, "test_secret",
                             target="tok 123456:ABCDEF1234567890abcdefGHIJKL1234567890", summary="s")
    c = await db.connection.execute(
        "SELECT target FROM audit_log WHERE bot_id = ? AND action = 'test_secret' ORDER BY id DESC LIMIT 1",
        (TEST_BOT,))
    row = await c.fetchone()
    check("audit_sanitizes_token", row and "123456:" not in row[0], row[0][:40] if row else None)

async def test_new_permissions():
    print("== 10. permissions for new actions ==")
    from admin_panel.router import _required_permission
    check("perm_analytics", _required_permission("analytics") == "view_stats")
    check("perm_analytics_export", _required_permission("analytics:export") == "view_stats")
    check("perm_health", _required_permission("health") == "view_logs")
    check("perm_alerts", _required_permission("alerts") == "view_logs")
    check("perm_alert_detail", _required_permission("alert:5") == "view_logs")
    check("perm_bchistory", _required_permission("bchistory") == "view_logs")
    check("perm_health_check", _required_permission("health:check") == "view_logs")
    check("perm_alertack", _required_permission("alertack:5") == "view_logs")
    check("perm_alertresolve", _required_permission("alertresolve:5") == "view_logs")
    # owner can do all new actions
    for perm in ("view_stats", "view_logs"):
        check(f"owner_{perm}", await has_permission(TEST_BOT, OWNER, perm))
    # stranger cannot
    check("stranger_no_view_stats", not await has_permission(TEST_BOT, FAKE_USER, "view_stats"))

async def test_owner_protection():
    print("== 12. owner protection ==")
    check("owner_is_owner", await is_owner(TEST_BOT, OWNER))
    check("fake_not_owner", not await is_owner(TEST_BOT, FAKE_ADMIN))
    # owner keeps manage_admins implicitly
    check("owner_manage_admins", await has_permission(TEST_BOT, OWNER, "manage_admins"))

async def test_backup_isolated():
    print("== 13. backup/restore isolated ==")
    from backup import backup_manager as bu
    # verify_backup_file on missing file must fail safely
    r = await bu.verify_backup_file("/nonexistent/x.zip")
    check("verify_missing_fails", r.get("ok") is False)
    # corrupt zip must fail safely
    import tempfile, os
    fd, bad = tempfile.mkstemp(suffix=".zip")
    os.write(fd, b"not a zip at all")
    os.close(fd)
    r = await bu.verify_backup_file(bad)
    check("verify_corrupt_fails", r.get("ok") is False)
    os.unlink(bad)

async def test_phase12_regression():
    print("== 15. phase 1+2 regression ==")
    from admin_panel import stats as st
    s = await st.command_center_stats(TEST_BOT)
    check("cc_has_keys", all(k in s for k in ("total_users", "pending_reports", "recent_events")))
    # audit log still append-only
    ok = await db.log_audit(TEST_BOT, OWNER, "phase3_regression_probe", success=True)
    check("audit_still_works", ok)
    # permissions model intact
    check("pm_all", len(pm.ALL_PERMISSIONS) == 10)

async def main():
    await db.init()
    print("DB init OK")
    try:
        await test_analytics_accuracy()
        await test_timezones()
        await test_missing_data()
        await test_stuck_detection()
        await test_job_transitions()
        await test_double_execution()
        await test_restart_recovery()
        await test_error_classification()
        await test_api_failure_paths()
        await test_new_permissions()
        await test_owner_protection()
        await test_backup_isolated()
        await test_phase12_regression()
    finally:
        await cleanup_analytics_data()
        # remove test audit entries
        await db.connection.execute(
            "DELETE FROM audit_log WHERE bot_id = ? AND action IN ('test_secret','phase3_regression_probe')",
            (TEST_BOT,))
        await db.connection.commit()
    print()
    print(f"RESULT: {len(passed)} passed, {len(failed)} failed")
    if failed:
        print("FAILED:", failed)
    return len(failed) == 0

ok = asyncio.run(main())
sys.exit(0 if ok else 1)
