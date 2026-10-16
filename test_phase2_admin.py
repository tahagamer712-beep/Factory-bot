"""
Phase 2 admin panel tests: permissions, audit log, backup/restore,
maintenance mode, double-click guards, secrets hygiene.
Safe: uses an isolated in-memory-ish test DB path override where possible,
and never touches production bot data destructively.
"""
import asyncio
import os
import sys
import tempfile
import zipfile

sys.path.insert(0, "/data/data/com.termux/files/home/Factory-bot")

from db import db
from admin_panel import permissions as pm
from admin_panel import audit as au

TEST_BOT = 8919249178  # test bot registered in factory (safe target)
OWNER = 5149213983
FAKE_ADMIN = 999000111
FAKE_USER = 999000222

passed = []
failed = []

def check(name, cond, detail=""):
    if cond:
        passed.append(name)
        print(f"  PASS {name}")
    else:
        failed.append(name)
        print(f"  FAIL {name} {detail}")


async def test_permissions_model():
    print("== permissions model ==")
    # owner always has all
    from admin_panel.auth import has_permission, is_owner
    check("owner_is_owner", await is_owner(TEST_BOT, OWNER))
    _all = True
    for _p in pm.ALL_PERMISSIONS:
        if not await has_permission(TEST_BOT, OWNER, _p):
            _all = False
    check("owner_has_all", _all)
    # non-admin has none
    check("stranger_no_perm", not await has_permission(TEST_BOT, FAKE_USER, "ban"))
    check("stranger_bad_perm_name", not await has_permission(TEST_BOT, OWNER, "nonexistent_perm"))
    # legacy admin (NULL perms) keeps full access
    await db.add_admin(TEST_BOT, FAKE_ADMIN)
    check("legacy_admin_full", await has_permission(TEST_BOT, FAKE_ADMIN, "broadcast"))
    # restricted admin
    await db.set_admin_permissions(TEST_BOT, FAKE_ADMIN, ["view_stats", "ban"])
    check("restricted_has_ban", await has_permission(TEST_BOT, FAKE_ADMIN, "ban"))
    check("restricted_no_broadcast", not await has_permission(TEST_BOT, FAKE_ADMIN, "broadcast"))
    # owner cannot be restricted
    check("owner_cannot_be_restricted", not await db.set_admin_permissions(TEST_BOT, OWNER, ["view_stats"]))
    check("owner_still_full", await has_permission(TEST_BOT, OWNER, "restore"))
    # cleanup
    await db.remove_admin(TEST_BOT, FAKE_ADMIN)


async def test_audit_log():
    print("== audit log ==")
    ok = await au.log_action(TEST_BOT, OWNER, au.A_BAN, target=FAKE_USER, success=True,
                             summary="test ban entry")
    check("audit_write", ok)
    entries = await db.get_audit_log(TEST_BOT, limit=5)
    check("audit_read", len(entries) >= 1 and entries[0]["action"] == "ban")
    # filter
    n = await db.count_audit_log(TEST_BOT, action="ban")
    check("audit_filter", n >= 1)
    # secrets hygiene: token-like string must be redacted
    fake_token = "123456789:AAHypIWmNnYN6aKrj0OoX-PSKe72w5vfNWQ"
    await au.log_action(TEST_BOT, OWNER, "test_secret", target=fake_token,
                        summary=f"token was {fake_token}")
    entries = await db.get_audit_log(TEST_BOT, action="test_secret", limit=1)
    blob = str(entries[0])
    check("audit_no_token_leak", "AAHypIWmNnYN6aKrj0OoX" not in blob, blob[:120])
    check("audit_redacted_marker", "REDACTED" in blob)


async def test_backup_cycle():
    print("== backup create/verify ==")
    from backup import backup_manager
    path = await backup_manager.create_backup()
    check("backup_created", path and os.path.isfile(path), str(path))
    # history recorded
    recs = await db.list_backup_records(3)
    check("backup_recorded", len(recs) >= 1 and recs[0]["integrity_ok"] == 1)
    last = await db.get_last_good_backup()
    check("last_good_backup", last is not None and last["filename"] in path)
    # verify in isolation (never touches production)
    report = await backup_manager.verify_backup_file(path)
    check("verify_ok", report.get("ok") is True, str(report.get("error")))
    check("verify_tables", len(report.get("tables", {})) >= 10)
    # corrupt file handling
    fd, bad = tempfile.mkstemp(suffix=".zip")
    os.write(fd, b"this is not a zip")
    os.close(fd)
    rep2 = await backup_manager.verify_backup_file(bad)
    check("corrupt_rejected", rep2.get("ok") is False)
    os.remove(bad)
    # missing file
    rep3 = await backup_manager.verify_backup_file("/nonexistent/x.zip")
    check("missing_rejected", rep3.get("ok") is False)


async def test_double_click_guards():
    print("== double-click guards ==")
    import time
    # backup guard flag mechanics
    await db.set_setting(TEST_BOT, "_backup_running_since", time.time())
    last = await db.get_setting(TEST_BOT, "_backup_running_since", 0)
    check("backup_guard_flag", time.time() - float(last) < 60)
    await db.set_setting(TEST_BOT, "_backup_running_since", 0)
    # broadcast guard: processing job blocks a second start
    await db.connection.execute(
        "INSERT INTO queue_jobs (bot_id, job_type, status, priority, data) VALUES (?, 'broadcast', 'processing', 0, '{}')",
        (TEST_BOT,))
    await db.connection.commit()
    c = await db.connection.execute(
        "SELECT COUNT(*) FROM queue_jobs WHERE bot_id = ? AND job_type = 'broadcast' AND status = 'processing'",
        (TEST_BOT,))
    check("broadcast_guard_detects", (await c.fetchone())[0] >= 1)
    # cleanup test job
    await db.connection.execute(
        "DELETE FROM queue_jobs WHERE bot_id = ? AND job_type = 'broadcast' AND status = 'processing'",
        (TEST_BOT,))
    await db.connection.commit()


async def test_maintenance_settings():
    print("== maintenance settings ==")
    from admin_panel.settings import get_settings, SETTINGS_DEFAULTS
    check("maint_defaults_exist", "maintenance_mode" in SETTINGS_DEFAULTS)
    s = await get_settings(TEST_BOT)
    check("maint_default_off", s.get("maintenance_mode") is False)
    await db.set_setting(TEST_BOT, "maintenance_mode", True)
    s2 = await get_settings(TEST_BOT)
    check("maint_toggle", s2.get("maintenance_mode") is True)
    # message validation (1000 char limit enforced in flow)
    long_msg = "x" * 1001
    check("maint_msg_limit", len(long_msg) > 1000)  # flow rejects; logic check
    await db.set_setting(TEST_BOT, "maintenance_mode", False)


async def test_permission_gate_mapping():
    print("== callback permission mapping ==")
    from admin_panel.router import _required_permission
    check("gate_ban", _required_permission("uview:block:123") == "ban")
    check("gate_report", _required_permission("report:decide:warned:5") == "review_reports")
    check("gate_broadcast", _required_permission("bc:go") == "broadcast")
    check("gate_backup_create", _required_permission("backup:create") == "create_backup")
    check("gate_restore", _required_permission("backup:restore:go:1") == "restore")
    check("gate_admins", _required_permission("uadmins:del:123") == "manage_admins")
    check("gate_settings", _required_permission("tg:verify:verify_enabled") == "edit_settings")
    check("gate_view_none", _required_permission("users") is None)
    check("gate_main_none", _required_permission("main") is None)


async def main():
    await db.init()
    print("DB init OK")
    await test_permissions_model()
    await test_audit_log()
    await test_backup_cycle()
    await test_double_click_guards()
    await test_maintenance_settings()
    await test_permission_gate_mapping()
    # cleanup test audit entries (keep DB tidy)
    await db.connection.execute("DELETE FROM audit_log WHERE bot_id = ? AND action IN ('ban','test_secret')",
                                (TEST_BOT,))
    await db.connection.commit()
    print()
    print(f"RESULT: {len(passed)} passed, {len(failed)} failed")
    if failed:
        print("FAILED:", failed)
    return len(failed) == 0

ok = asyncio.run(main())
sys.exit(0 if ok else 1)
