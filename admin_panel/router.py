"""Routes admin-panel callback_query presses (and the initial /start) to
the right screen. `send_screen()` is the shared "render this screen" entry
point used both for fresh sends (admin's /start) and in-place edits
(button presses)."""

from db import db
from bot_registry import bot_registry
from telegram_adapter import telegram_pool
from message_sender import message_sender
from . import keyboards as kb
from . import screens as sc
from . import stats as st
from .settings import get_settings, CONTENT_EDIT_KEYS

DEFAULT_WELCOME = "👋 أهلاً بك! تفضل استخدم البوت."


async def _ack(bot_id: int, callback_id: str, text: str = None, alert: bool = False):
    bot = bot_registry.get_bot(bot_id)
    if not bot:
        return
    adapter = await telegram_pool.get_adapter(bot["token"])
    await adapter.answer_callback_query(callback_id, text=text, show_alert=alert)


async def send_screen(bot_id: int, chat_id: int, screen: str, message_id: int = None, param: str = None):
    text, markup = await _build_screen(bot_id, chat_id, screen, param)
    if text is None:
        return
    if message_id is not None:
        result = await message_sender.edit_message(bot_id, chat_id, message_id, text, reply_markup=markup)
        if result is not None:
            return
    await message_sender.send_message(bot_id, chat_id, text, reply_markup=markup, is_admin_flow=True)


async def _report_counts(bot_id: int) -> dict:
    out = {"new": 0, "reviewing": 0, "closed": 0}
    try:
        c = await db.connection.execute(
            "SELECT status, COUNT(*) FROM reports WHERE bot_id = ? GROUP BY status", (bot_id,))
        for status, n in await c.fetchall():
            if status in out:
                out[status] = n
    except Exception:
        pass
    return out


async def _report_list(bot_id: int, status: str, limit: int = 15) -> list:
    try:
        c = await db.connection.execute(
            "SELECT id, reporter_id, target_id, reason, status, created_at FROM reports "
            "WHERE bot_id = ? AND status = ? ORDER BY created_at DESC LIMIT ?",
            (bot_id, status, limit))
        cols = ["id", "reporter_id", "target_id", "reason", "status", "created_at"]
        return [dict(zip(cols, r)) for r in await c.fetchall()]
    except Exception:
        return []


async def _report_get(bot_id: int, rid: int):
    try:
        c = await db.connection.execute(
            "SELECT id, reporter_id, target_id, reason, status, decision, created_at "
            "FROM reports WHERE bot_id = ? AND id = ?", (bot_id, rid))
        row = await c.fetchone()
        if row:
            cols = ["id", "reporter_id", "target_id", "reason", "status", "decision", "created_at"]
            return dict(zip(cols, row))
    except Exception:
        pass
    return None


async def _report_set_status(bot_id: int, rid: int, status: str):
    async with db._lock:
        await db.connection.execute(
            "UPDATE reports SET status = ? WHERE bot_id = ? AND id = ?",
            (status, bot_id, rid))
        await db.connection.commit()


async def _report_decide(bot_id: int, rid: int, decision: str, admin_id: int):
    """Apply a report decision: ignored/warned/blocked."""
    from datetime import datetime
    rep = await _report_get(bot_id, rid)
    if not rep:
        return
    async with db._lock:
        await db.connection.execute(
            "UPDATE reports SET status = 'closed', decision = ?, decided_by = ?, decided_at = ? "
            "WHERE bot_id = ? AND id = ?",
            (decision, admin_id, datetime.now().isoformat(), bot_id, rid))
        if decision == "blocked" and rep.get("target_id"):
            await db.connection.execute(
                "UPDATE bot_users SET is_blocked = 1 WHERE bot_id = ? AND chat_id = ?",
                (bot_id, rep["target_id"]))
        await db.connection.commit()
    await db.add_event(bot_id, "admin_action",
                       "Admin %d decided report #%d: %s" % (admin_id, rid, decision))
    from . import audit as _audit
    await _audit.log_action(bot_id, admin_id, _audit.A_REPORT_DECISION,
                            target=f"report#{rid}", success=True,
                            summary=f"decision={decision}")
    if decision == "warned" and rep.get("target_id"):
        await message_sender.send_message(
            bot_id, rep["target_id"],
            "تحذير من الإدارة: تم رصد مخالفة من حسابك. تكرار المخالفة قد يؤدي للحظر.",
            is_admin_flow=True)


async def _build_screen(bot_id: int, chat_id: int, screen: str, param: str = None):
    s = await get_settings(bot_id)
    
    if screen == "main":
        stats = await st.command_center_stats(bot_id)
        from config import FACTORY_BOT_ID
        factory_bot = bot_registry.get_bot(FACTORY_BOT_ID) if FACTORY_BOT_ID else None
        factory_username = factory_bot["username"] if factory_bot else None
        return sc.main_menu(stats), kb.main_menu(s, factory_username,
                                                pending_reports=stats["pending_reports"])
    
    if screen == "settings":
        return sc.settings_menu(), kb.settings_menu(s)
    
    if screen == "verify":
        verified_count = await db.count_verified(bot_id)
        return sc.verify_menu(s, verified_count), kb.verify_menu(s, verified_count)
    if screen == "verify:msg":
        return sc.placeholder("📝 <b>رسائل التحقق</b>"), kb.back_only("adm:verify")
    if screen == "verify:stats":
        verified_count = await db.count_verified(bot_id)
        return sc.verify_menu(s, verified_count), kb.back_only("adm:verify")
    if screen == "verify:list":
        return sc.placeholder("👥 <b>المتحققون</b>"), kb.back_only("adm:verify")
    if screen == "verify:help":
        return sc.verify_methods_help(), kb.back_only("adm:verify")
    
    if screen == "verifym":
        return sc.verify_methods_menu(), kb.verify_methods_menu(s)
    if screen == "verifym:help":
        return sc.verify_methods_help(), kb.back_only("adm:verifym")
    
    if screen == "protect":
        return sc.protect_menu(), kb.protect_menu(s)
    if screen == "protect:help":
        return sc.protect_help(), kb.back_only("adm:protect")
    
    if screen == "notif":
        return sc.notif_menu(), kb.notif_menu(s)
    if screen == "notif:help":
        return sc.notif_help(), kb.back_only("adm:notif")
    
    if screen == "autodel":
        from scheduler import get_autodel_stats
        stats = await get_autodel_stats(bot_id)
        return sc.autodel_menu(s, stats), kb.autodel_menu(s)
    if screen == "autodel:help":
        return sc.autodel_help(), kb.back_only("adm:autodel")
    
    if screen == "inactive":
        from scheduler import get_inactive_stats
        stats = await get_inactive_stats(bot_id)
        return sc.inactive_menu(s, stats), kb.inactive_menu(s)
    if screen == "inactive:help":
        return sc.inactive_help(), kb.back_only("adm:inactive")
    if screen == "inactive:reminders":
        reminders = s.get("inactive_reminders", [])
        return sc.inactive_reminders_menu(reminders), kb.inactive_reminders_menu(reminders)
    
    if screen == "qr" or screen.startswith("qr:page:"):
        offset = int(screen.split(":")[-1]) if screen.startswith("qr:page:") else 0
        items = s.get("quick_replies", [])
        return sc.quick_replies_menu(items), kb.quick_replies_menu(items, offset)
    if screen == "qr:help":
        return sc.quick_replies_help(), kb.back_only("adm:qr")
    
    if screen == "content":
        return sc.content_menu(), kb.content_menu()
    if screen == "content:help":
        return sc.content_help(), kb.back_only("adm:content")
    
    if screen == "welcome":
        text = s.get("welcome_message") or DEFAULT_WELCOME
        is_custom = bool(s.get("welcome_message"))
        return sc.welcome_menu(text, is_custom), kb.welcome_menu(is_custom)
    
    if screen == "autoreply" or screen.startswith("autoreply:page:"):
        offset = int(screen.split(":")[-1]) if screen.startswith("autoreply:page:") else 0
        from auto_reply_manager import auto_reply_manager
        items = await auto_reply_manager.get_auto_replies(bot_id)
        return sc.autoreply_menu(items), kb.autoreply_menu(items, offset)
    
    if screen == "tbtn":
        buttons = s.get("transparent_buttons", [])
        return sc.tbtn_menu(buttons), kb.transparent_buttons_menu(buttons)
    
    if screen == "btnedit":
        from auto_reply_manager import auto_reply_manager
        items = await auto_reply_manager.get_auto_replies(bot_id)
        return sc.btnedit_pick_prompt(), kb.button_edit_pick_menu(items)
    if screen.startswith("btnedit:item:"):
        item_id = int(screen.split(":")[-1])
        from auto_reply_manager import auto_reply_manager
        items = await auto_reply_manager.get_auto_replies(bot_id)
        item = next((i for i in items if i["id"] == item_id), None)
        if not item:
            return sc.placeholder("❌ ما لقيت هذا الرد"), kb.back_only("adm:btnedit")
        buttons = await db.get_setting(bot_id, f"autoreply_buttons_{item_id}", [])
        return sc.btnedit_item(item["keyword"], item["reply"], buttons), kb.button_edit_item_menu(item_id, buttons)
    
    if screen == "shortcuts":
        commands = s.get("bot_commands", [])
        return sc.shortcuts_menu(commands), kb.shortcuts_menu(commands)
    if screen.startswith("shortcuts:item:"):
        idx = int(screen.split(":")[-1])
        commands = s.get("bot_commands", [])
        if 0 <= idx < len(commands):
            c = commands[idx]
            return f"/{c['command']}\n{c['description']}", kb.shortcut_item_menu(idx)
        return sc.placeholder("❌ غير موجود"), kb.back_only("adm:shortcuts")
    
    if screen == "contentedit":
        overrides = {}
        for key in CONTENT_EDIT_KEYS:
            val = await db.get_setting(bot_id, f"content_override_{key}")
            if val:
                overrides[key] = val
        return sc.content_edit_menu(), kb.content_edit_menu(overrides)
    if screen.startswith("contentedit:item:"):
        key = screen.split(":", 2)[-1]
        current = await db.get_setting(bot_id, f"content_override_{key}")
        is_custom = bool(current)
        return sc.content_edit_item(key, current or "(الافتراضي من الكود)", is_custom), \
            kb.content_edit_item_menu(key, is_custom)
    
    if screen == "editlist":
        overrides = {}
        for key in CONTENT_EDIT_KEYS:
            val = await db.get_setting(bot_id, f"content_override_{key}")
            if val:
                overrides[key] = val
        return sc.edit_list_menu(), kb.edit_list_menu(overrides)
    
    if screen == "botinfo":
        bot = bot_registry.get_bot(bot_id)
        cursor = await db.connection.execute("SELECT created_at FROM bots WHERE bot_id = ?", (bot_id,))
        row = await cursor.fetchone()
        created_at = row[0] if row else "?"
        cursor = await db.connection.execute("SELECT COUNT(*) FROM bot_users WHERE bot_id = ?", (bot_id,))
        user_count = (await cursor.fetchone())[0]
        cursor = await db.connection.execute("SELECT COUNT(*) FROM messages WHERE bot_id = ?", (bot_id,))
        msg_count = (await cursor.fetchone())[0]
        uname = bot["username"] if bot else "?"
        return sc.bot_info(uname, bot_id, created_at, user_count, msg_count), kb.back_only("adm:content")
    
    if screen == "users":
        return sc.users_menu(), kb.users_menu()
    if screen == "ustats":
        stats = await st.users_stats(bot_id)
        return sc.users_stats(stats), kb.back_only("adm:users")
    if screen == "uadmins" or screen.startswith("uadmins:page:"):
        offset = int(screen.split(":")[-1]) if screen.startswith("uadmins:page:") else 0
        admins = await db.list_admins_full(bot_id)
        return sc.admins_menu2(admins), kb.admins_menu2(admins, offset)
    if screen == "ublocks" or screen.startswith("ublocks:page:"):
        offset = int(screen.split(":")[-1]) if screen.startswith("ublocks:page:") else 0
        blocked = await st.get_blocked_users(bot_id)
        return sc.blocks_menu(blocked), kb.blocks_menu(blocked, offset)
    if screen == "uactivity":
        events = await st.get_recent_events(bot_id)
        return sc.activity_log(events), kb.back_only("adm:users")
    
    if screen == "sub":
        from subscription_handler import subscription_handler
        items = await subscription_handler.get_subscriptions(bot_id)
        return sc.sub_menu(items), kb.sub_menu(items, s)
    if screen == "sub:help":
        return sc.sub_help(), kb.back_only("adm:sub")
    
    if screen == "contact":
        return sc.contact_menu(), kb.contact_menu()
    
    if screen == "system:updates":
        return sc.placeholder("🔄 <b>آخر التحديثات</b>"), kb.back_only("adm:system")
    
    if screen == "help":
        return sc.help_guide(), kb.back_only("adm:main")
    
    # ---- Phase 1: user search & detail ----
    if screen == "usearch":
        return sc.user_search_prompt(), kb.back_only("adm:users")
    if screen.startswith("uview:"):
        parts = screen.split(":")
        if len(parts) == 2:
            detail = await st.user_detail(bot_id, int(parts[1]))
            if not detail:
                return sc.placeholder("ما لقيت هذا المستخدم"), kb.back_only("adm:users")
            return sc.user_detail_card(detail), kb.user_detail_menu(
                detail["chat_id"], bool(detail["is_blocked"]), bool(detail.get("admin_note")))
        action, cid = parts[1], int(parts[2])
        if action == "block":
            async with db._lock:
                await db.connection.execute(
                    "UPDATE bot_users SET is_blocked = 1 WHERE bot_id = ? AND chat_id = ?",
                    (bot_id, cid))
                await db.connection.commit()
            await db.add_event(bot_id, "admin_action",
                               "Admin %d blocked user %d" % (chat_id, cid))
            from . import audit as _audit
            await _audit.log_action(bot_id, chat_id, _audit.A_BAN, target=cid,
                                    summary="blocked from user detail")
            return await _build_screen(bot_id, chat_id, "uview:%d" % cid)
        if action == "unblock":
            async with db._lock:
                await db.connection.execute(
                    "UPDATE bot_users SET is_blocked = 0 WHERE bot_id = ? AND chat_id = ?",
                    (bot_id, cid))
                await db.connection.commit()
            await db.add_event(bot_id, "admin_action",
                               "Admin %d unblocked user %d" % (chat_id, cid))
            from . import audit as _audit
            await _audit.log_action(bot_id, chat_id, _audit.A_UNBAN, target=cid,
                                    summary="unblocked from user detail")
            return await _build_screen(bot_id, chat_id, "uview:%d" % cid)
        if action == "note":
            await db.set_conversation_state(chat_id, bot_id, "user_note",
                                            {"target": cid, "cancel_screen": "uview:%d" % cid})
            await message_sender.send_message(bot_id, chat_id, sc.user_note_prompt(),
                                              is_admin_flow=True)
            return None, None

    # ---- Phase 1: active conversations (honest, no content) ----
    if screen == "convos":
        convos = await st.active_conversations(bot_id, hours=24)
        return sc.active_conversations_menu(convos, 24), kb.back_only("adm:main")

    # ---- Phase 1: reports ----
    if screen == "reports":
        counts = await _report_counts(bot_id)
        return sc.reports_menu(counts), kb.reports_menu(counts)
    if screen.startswith("reports:"):
        status = screen.split(":")[1]
        reps = await _report_list(bot_id, status)
        if not reps:
            return sc.placeholder("لا توجد بلاغات بحالة: " + status), kb.back_only("adm:reports")
        return "البلاغات", kb.report_list_menu(reps, status)
    if screen.startswith("report:"):
        parts = screen.split(":")
        if parts[1] == "reviewing":
            rid = int(parts[2])
            await _report_set_status(bot_id, rid, "reviewing")
            return await _build_screen(bot_id, chat_id, "report:%d" % rid)
        if parts[1] == "decide":
            decision, rid = parts[2], int(parts[3])
            await _report_decide(bot_id, rid, decision, chat_id)
            return await _build_screen(bot_id, chat_id, "report:%d" % rid)
        rid = int(parts[1])
        rep = await _report_get(bot_id, rid)
        if not rep:
            return sc.placeholder("ما لقيت هذا البلاغ"), kb.back_only("adm:reports")
        return sc.report_detail(rep), kb.report_detail_menu(rid, rep["status"])

    # ---- Phase 2: backup center ----
    if screen == "backup":
        from backup import BACKUP_SCOPE
        records = await db.list_backup_records(5)
        last_good = await db.get_last_good_backup()
        return sc.backup_center(records, last_good, BACKUP_SCOPE), kb.backup_menu(records)
    if screen.startswith("backup:verify:"):
        from backup import backup_manager
        import os
        bid = int(screen.split(":")[-1])
        recs = await db.list_backup_records(50)
        rec = next((r for r in recs if r["id"] == bid), None)
        if not rec:
            return sc.placeholder("X"), kb.back_only("adm:backup")
        from config import BACKUP_DIR
        fp = str(BACKUP_DIR / rec["filename"])
        if not os.path.isfile(fp):
            return sc.backup_verify_result(rec["filename"], {"ok": False, "error": "file missing"}), kb.back_only("adm:backup")
        report = await backup_manager.verify_backup_file(fp)
        return sc.backup_verify_result(rec["filename"], report), kb.back_only("adm:backup")
    if screen.startswith("backup:restore:"):
        bid = int(screen.split(":")[-1])
        return sc.backup_restore_confirm(bid), kb.backup_restore_confirm_menu(bid)

    # ---- Phase 2: audit log ----
    if screen == "audit" or screen.startswith("audit:page:"):
        page = int(screen.split(":")[-1]) if screen.startswith("audit:page:") else 0
        per_page = 10
        total = await db.count_audit_log(bot_id)
        entries = await db.get_audit_log(bot_id, limit=per_page, offset=page * per_page)
        return sc.audit_log_menu(entries, page, per_page, total), kb.audit_menu(page, per_page, total)

    # ---- Phase 2: per-admin permission editor ----
    if screen.startswith("uadmin:perms:"):
        uid = int(screen.split(":")[-1])
        from . import permissions as pm
        from .auth import is_owner
        if await is_owner(bot_id, uid):
            return sc.placeholder("X"), kb.back_only("adm:uadmins")
        perms = await db.get_admin_permissions(bot_id, uid)
        current = set(perms) if perms else set(pm.ALL_PERMISSIONS)
        return sc.admin_perms_menu(uid, current), kb.admin_perms_menu(uid, current)

    # ---- Phase 2: system status (real data) ----
    if screen == "system":
        info = await _system_info(bot_id)
        return sc.system_status(info), kb.system_menu2(info)

    # ---- Phase 3: analytics / health / alerts ----
    if screen == "analytics":
        a = await st.analytics_overview(bot_id)
        return sc.analytics_menu(a), kb.analytics_kb()
    if screen == "health":
        info = await _health_info(bot_id)
        total_open = sum(info["open_alerts"].values())
        return sc.health_center(info), kb.health_kb(total_open)
    if screen == "alerts":
        alerts = await db.get_alerts(bot_id, limit=20)
        return sc.alerts_menu(alerts), kb.alerts_kb(alerts)
    if screen.startswith("alert:"):
        try:
            aid = int(screen.split(":", 1)[1])
        except ValueError:
            return sc.placeholder("X"), kb.back_only("adm:alerts")
        alerts = await db.get_alerts(bot_id, limit=100)
        al = next((x for x in alerts if x["id"] == aid), None)
        if not al:
            return sc.placeholder("X"), kb.back_only("adm:alerts")
        return sc.alert_detail(al), kb.alert_detail_kb(aid, al["status"])
    if screen == "bchistory":
        hist = await db.get_broadcast_history(bot_id, limit=10)
        return sc.broadcast_history_menu(hist), kb.bchistory_kb()
    if screen == "maintenance":
        s = await get_settings(bot_id)
        return sc.maintenance_menu(s), kb.maintenance_menu(s)
    return None, None
    return None, None


def _required_permission(rest: str):
    """Map an admin callback to the granular permission it needs.
    Returns None for view-only/navigation callbacks (any admin may view)."""
    # --- destructive / sensitive actions ---
    if rest.startswith(("uview:block", "uview:unblock",
                        "ublocks:unblock", "ublocks:add")):
        return "ban"
    if rest.startswith("report:decide") or ":reviewing" in rest:
        return "review_reports"
    if rest == "bc:go":
        return "broadcast"
    if rest.startswith("backup:create"):
        return "create_backup"
    if rest.startswith("backup:restore"):
        return "restore"
    if rest.startswith("uadmins:del:") or rest.startswith("uadmins:perms") or \
            rest.startswith("uadmins:setperm") or rest.startswith("uadmins:preset"):
        return "manage_admins"
    if rest.startswith("maintenance:"):
        return "edit_settings"
    # ---- Phase 3 ----
    if rest == "analytics" or rest == "analytics:export":
        return "view_stats"
    if rest in ("health", "alerts", "bchistory") or rest.startswith("alert:") or \
            rest == "health:check":
        return "view_logs"
    if rest.startswith("alertack:") or rest.startswith("alertresolve:"):
        return "view_logs"
    # --- settings-changing callbacks ---
    for prefix in ("tg:", "welcome:", "autoreply:", "contentedit:", "btnedit:",
                   "tbtn:", "shortcuts:", "qr:", "autodel:", "inactive:",
                   "sub:toggle:", "sub:del:", "sub:add", "sub:checktext",
                   "sub:allon", "sub:alloff"):
        if rest.startswith(prefix):
            return "edit_settings"
    return None


async def _health_info(bot_id: int) -> dict:
    """Phase 3: centralized verifiable health data for the health center."""
    import time
    info = await _system_info(bot_id)
    try:
        from poller import poller_supervisor as _sup
        _p = _sup.pollers.get(bot_id)
        lpt = getattr(_p, "last_poll_time", 0) if _p else 0
        if lpt:
            ago = time.time() - lpt
            if ago < 120:
                info["last_poll_ago"] = f"قبل {int(ago)} ثانية"
            else:
                info["last_poll_ago"] = f"قبل {int(ago // 60)} دقيقة"
        else:
            info["last_poll_ago"] = None
    except Exception:
        info["last_poll_ago"] = None
    info["open_alerts"] = await db.count_open_alerts(bot_id)
    stuck = await db.get_stuck_jobs(bot_id, timeout_minutes=120)
    info["stuck_jobs"] = len(stuck)
    info["running_broadcasts"] = await db.count_processing_broadcasts(bot_id)
    c = await db.connection.execute(
        "SELECT message, created_at FROM logs WHERE source = ? AND level = 'error' "
        "ORDER BY created_at DESC LIMIT 1", (f"bot:{bot_id}",))
    info["last_error"] = await c.fetchone()
    from admin_panel.health import classify_health
    info["health"] = classify_health(info["open_alerts"], info.get("polling", "?"),
                                     info.get("db_integrity", "?"))
    return info


async def _system_info(bot_id: int) -> dict:
    """Real system data only - nothing claimed without a check."""
    import os, time
    info = {}
    # DB integrity (real check)
    try:
        c = await db.connection.execute("PRAGMA integrity_check")
        rows = await c.fetchall()
        info["db_integrity"] = "ok" if (len(rows) == 1 and str(rows[0][0]).lower() == "ok") else "FAILED"
    except Exception as e:
        info["db_integrity"] = f"error: {type(e).__name__}"
    # DB size (real)
    try:
        info["db_size_mb"] = round(os.path.getsize(os.path.expanduser("~/factory/data/factory.db")) / 1024 / 1024, 2)
    except OSError:
        info["db_size_mb"] = 0
    # Uptime (tracked in main.py as START_TIME; main may run as __main__)
    try:
        import sys
        start_ts = None
        for mod_name in ("main", "__main__"):
            mod = sys.modules.get(mod_name)
            if mod is not None:
                start_ts = getattr(mod, "START_TIME", None)
                if start_ts:
                    break
        info["uptime"] = _humanize_uptime(time.time() - start_ts) if start_ts else "غير معروف"
    except Exception:
        info["uptime"] = "غير معروف"
    # Polling: is there a live poller for this bot? (real check via supervisor)
    try:
        from poller import poller_supervisor as _sup
        _p = _sup.pollers.get(bot_id)
        if _p is not None:
            info["polling"] = "يعمل" if getattr(_p, "is_running", False) else "متوقف"
        else:
            info["polling"] = "لا يوجد poller"
    except Exception:
        info["polling"] = "غير معروف"
    # Last backup (from history table)
    last_good = await db.get_last_good_backup()
    info["last_backup"] = last_good["filename"] if last_good else None
    info["last_backup_at"] = last_good["created_at"] if last_good else None
    # Maintenance state
    s = await get_settings(bot_id)
    info["maintenance"] = bool(s.get("maintenance_mode"))
    return info


def _humanize_uptime(secs: float) -> str:
    secs = int(secs)
    d, secs = divmod(secs, 86400)
    h, secs = divmod(secs, 3600)
    m, _ = divmod(secs, 60)
    parts = []
    if d: parts.append(f"{d} يوم")
    if h: parts.append(f"{h} ساعة")
    if m or not parts: parts.append(f"{m} دقيقة")
    return " ".join(parts)


async def handle_callback(bot_id: int, chat_id: int, message_id: int,
                           callback_id: str, data: str, user_id: int):
    from .auth import is_admin, has_permission
    if not await is_admin(bot_id, user_id):
        await _ack(bot_id, callback_id, "⛔ غير مصرح", alert=True)
        return

    await _ack(bot_id, callback_id)

    # Phase 2: granular backend permission enforcement (never UI-only)
    if data.startswith("adm:"):
        need = _required_permission(data[len("adm:"):])
        if need and not await has_permission(bot_id, user_id, need):
            from . import permissions as _pm
            await _ack(bot_id, callback_id,
                       f"⛔ صلاحيتك لا تشمل: {_pm.label(need)}", alert=True)
            from . import audit as _audit
            await _audit.log_action(bot_id, user_id, "permission_denied",
                                    target=data, success=False,
                                    summary=f"denied: {need}")
            return
    
    if not data.startswith("adm:"):
        return
    rest = data[len("adm:"):]
    
    if rest == "noop":
        return
    
    # Toggle: adm:tg:<screen>:<key>
    if rest.startswith("tg:"):
        _, screen, key = rest.split(":", 2)
        from .settings import SETTINGS_DEFAULTS
        new_val = await db.toggle_setting(bot_id, key, SETTINGS_DEFAULTS.get(key, False))
        from . import audit as _audit
        await _audit.log_action(bot_id, chat_id, _audit.A_SETTING_CHANGE,
                                target=key, summary=f"toggled to {new_val}")
        await send_screen(bot_id, chat_id, screen, message_id=message_id)
        return
    
    # Start a simple text-input flow: adm:<flow_trigger>
    flow_starts = {
        "welcome:edit": ("welcome_edit", sc.welcome_edit_prompt(), "welcome"),
        "autoreply:add": ("autoreply_add_keyword", sc.autoreply_add_prompt_keyword(), "autoreply"),
        "uadmins:add": ("admin_add", sc.add_admin_prompt(), "uadmins"),
        "ublocks:add": ("block_add", sc.add_block_prompt(), "ublocks"),
        "sub:add": ("sub_add", sc.sub_add_prompt(), "sub"),
        "sub:checktext": ("sub_check_text", sc.sub_check_text_prompt(), "sub"),
        "contact:bc": ("broadcast_text", sc.broadcast_prompt(), "contact"),
        "usearch": ("user_search", sc.user_search_prompt(), "users"),
        "contact:qbc": ("broadcast_text_quick", sc.broadcast_prompt(), "contact"),
        "qr:add": ("qr_add_label", "🏷 أرسل اسم مختصر للرد (للتعرف عليه لاحقاً)، أو /cancel", "qr"),
        "autodel:duration": ("autodel_duration", sc.autodel_duration_prompt(), "autodel"),
        "inactive:hours": ("inactive_hours", sc.inactive_hours_prompt(), "inactive"),
        "inactive:remadd": ("inactive_rem_days", sc.inactive_reminder_add_days_prompt(), "inactive:reminders"),
        "tbtn:add": ("tbtn_add", sc.tbtn_add_prompt(), "tbtn"),
        "shortcuts:add": ("shortcut_add_command", sc.shortcut_add_command_prompt(), "shortcuts"),
        "verifym:linkcode": ("vm_link_code", sc.vm_link_code_prompt(), "verifym"),
        "verifym:visiturl": ("vm_visit_url", "🔗 أرسل رابط الموقع (لازم يبدأ بـ https://)، أو /cancel", "verifym"),
    }
    if rest in flow_starts:
        state, prompt, cancel_screen = flow_starts[rest]
        await db.set_conversation_state(chat_id, bot_id, state, {"cancel_screen": cancel_screen})
        await message_sender.send_message(bot_id, chat_id, prompt, is_admin_flow=True)
        return
    
    if rest == "welcome:reset":
        await db.set_setting(bot_id, "welcome_message", None)
        await send_screen(bot_id, chat_id, "welcome", message_id=message_id)
        return
    if rest == "welcome:preview":
        s = await get_settings(bot_id)
        preview = s.get("welcome_message") or DEFAULT_WELCOME
        await message_sender.send_message(bot_id, chat_id, preview, is_admin_flow=True)
        return
    
    # autoreply item detail / delete / toggle
    if rest.startswith("autoreply:item:"):
        item_id = int(rest.split(":")[-1])
        from auto_reply_manager import auto_reply_manager
        items = await auto_reply_manager.get_auto_replies(bot_id)
        item = next((i for i in items if i["id"] == item_id), None)
        if item:
            text = f"💬 <b>{item['keyword']}</b>\n—————\n{item['reply']}"
            await message_sender.edit_message(bot_id, chat_id, message_id, text,
                                               reply_markup=kb.autoreply_item_menu(item_id, item["active"]))
        return
    if rest.startswith("autoreply:del:"):
        item_id = int(rest.split(":")[-1])
        from auto_reply_manager import auto_reply_manager
        items = await auto_reply_manager.get_auto_replies(bot_id)
        item = next((i for i in items if i["id"] == item_id), None)
        if item:
            await auto_reply_manager.remove_auto_reply(bot_id, item["keyword"])
        await send_screen(bot_id, chat_id, "autoreply", message_id=message_id)
        return
    if rest.startswith("autoreply:toggle:"):
        item_id = int(rest.split(":")[-1])
        from auto_reply_manager import auto_reply_manager
        items = await auto_reply_manager.get_auto_replies(bot_id)
        item = next((i for i in items if i["id"] == item_id), None)
        if item:
            await auto_reply_manager.toggle_auto_reply(bot_id, item["keyword"], not item["active"])
        await send_screen(bot_id, chat_id, "autoreply", message_id=message_id)
        return
    
    # transparent buttons: delete one / clear all
    if rest.startswith("tbtn:del:"):
        idx = int(rest.split(":")[-1])
        buttons = await db.get_setting(bot_id, "transparent_buttons", [])
        if 0 <= idx < len(buttons):
            buttons.pop(idx)
            await db.set_setting(bot_id, "transparent_buttons", buttons)
        await send_screen(bot_id, chat_id, "tbtn", message_id=message_id)
        return
    if rest == "tbtn:clear":
        await db.set_setting(bot_id, "transparent_buttons", [])
        await send_screen(bot_id, chat_id, "tbtn", message_id=message_id)
        return
    
    # button editor: pick / add-button flow / delete-button
    if rest.startswith("btnedit:pick:"):
        item_id = int(rest.split(":")[-1])
        await send_screen(bot_id, chat_id, f"btnedit:item:{item_id}", message_id=message_id)
        return
    if rest.startswith("btnedit:addbtn:"):
        item_id = int(rest.split(":")[-1])
        await db.set_conversation_state(chat_id, bot_id, "btnedit_add_label",
                                         {"item_id": item_id, "cancel_screen": f"btnedit:item:{item_id}"})
        await message_sender.send_message(bot_id, chat_id, sc.btnedit_add_label_prompt(), is_admin_flow=True)
        return
    if rest.startswith("btnedit:delbtn:"):
        _, _, item_id_str, idx_str = rest.split(":")
        item_id, idx = int(item_id_str), int(idx_str)
        buttons = await db.get_setting(bot_id, f"autoreply_buttons_{item_id}", [])
        if 0 <= idx < len(buttons):
            buttons.pop(idx)
            await db.set_setting(bot_id, f"autoreply_buttons_{item_id}", buttons)
        await send_screen(bot_id, chat_id, f"btnedit:item:{item_id}", message_id=message_id)
        return
    
    # shortcuts: delete / publish
    if rest.startswith("shortcuts:del:"):
        idx = int(rest.split(":")[-1])
        commands = await db.get_setting(bot_id, "bot_commands", [])
        if 0 <= idx < len(commands):
            commands.pop(idx)
            await db.set_setting(bot_id, "bot_commands", commands)
        await send_screen(bot_id, chat_id, "shortcuts", message_id=message_id)
        return
    if rest == "shortcuts:publish":
        commands = await db.get_setting(bot_id, "bot_commands", [])
        bot = bot_registry.get_bot(bot_id)
        if bot and commands:
            adapter = await telegram_pool.get_adapter(bot["token"])
            await adapter.set_my_commands([{"command": c["command"], "description": c["description"]} for c in commands])
            await message_sender.send_message(bot_id, chat_id, sc.shortcut_published(), is_admin_flow=True)
        await send_screen(bot_id, chat_id, "shortcuts", message_id=message_id)
        return
    
    # content edit: start editing a key / reset a key
    if rest.startswith("contentedit:edit:"):
        key = rest.split(":", 2)[-1]
        await db.set_conversation_state(chat_id, bot_id, "content_edit_text",
                                         {"key": key, "cancel_screen": f"contentedit:item:{key}"})
        await message_sender.send_message(bot_id, chat_id, sc.content_edit_prompt(key), is_admin_flow=True)
        return
    if rest.startswith("contentedit:reset:"):
        key = rest.split(":", 2)[-1]
        await db.set_setting(bot_id, f"content_override_{key}", None)
        await send_screen(bot_id, chat_id, f"contentedit:item:{key}", message_id=message_id)
        return
    
    # subscription item detail / toggle / delete / enable-all / disable-all / preview
    if rest.startswith("sub:item:"):
        sub_id = int(rest.split(":")[-1])
        from subscription_handler import subscription_handler
        items = await subscription_handler.get_subscriptions(bot_id)
        item = next((i for i in items if i["id"] == sub_id), None)
        if item:
            text = f"🔐 <b>{item['channel_id']}</b>\nالحالة: {'✅ مفعل' if item['active'] else '❌ معطل'}"
            await message_sender.edit_message(bot_id, chat_id, message_id, text,
                                               reply_markup=kb.sub_item_menu(sub_id, item["active"]))
        return
    if rest.startswith("sub:toggle:"):
        sub_id = int(rest.split(":")[-1])
        async with db._lock:
            await db.connection.execute(
                "UPDATE subscriptions SET active = NOT active WHERE id = ? AND bot_id = ?", (sub_id, bot_id))
            await db.connection.commit()
        await send_screen(bot_id, chat_id, "sub", message_id=message_id)
        return
    if rest.startswith("sub:del:"):
        sub_id = int(rest.split(":")[-1])
        async with db._lock:
            await db.connection.execute(
                "DELETE FROM subscriptions WHERE id = ? AND bot_id = ?", (sub_id, bot_id))
            await db.connection.commit()
        await send_screen(bot_id, chat_id, "sub", message_id=message_id)
        return
    if rest in ("sub:allon", "sub:alloff"):
        active = 1 if rest == "sub:allon" else 0
        async with db._lock:
            await db.connection.execute(
                "UPDATE subscriptions SET active = ? WHERE bot_id = ?", (active, bot_id))
            await db.connection.commit()
        await send_screen(bot_id, chat_id, "sub", message_id=message_id)
        return
    if rest == "sub:preview":
        from subscription_handler import subscription_handler
        items = await subscription_handler.get_subscriptions(bot_id)
        channels = [i["channel_id"] for i in items if i["active"]] or ["@مثال_قناة"]
        gate_text, gate_kb = await subscription_handler.build_gate(bot_id, channels, chat_id)
        await message_sender.send_message(bot_id, chat_id, sc.sub_preview_intro(), is_admin_flow=True)
        await message_sender.send_message(bot_id, chat_id, gate_text, reply_markup=gate_kb, is_admin_flow=True)
        return
    
    # admins: delete
    if rest.startswith("uadmins:del:"):
        uid = int(rest.split(":")[-1])
        # Safety: never remove the owner, never let a non-owner remove anyone
        # with manage_admins implicitly — gate already enforced above; owner is
        # protected here as a second layer.
        from .auth import is_owner
        if await is_owner(bot_id, uid):
            await _ack(bot_id, callback_id, "⛔ لا يمكن إزالة مالك البوت", alert=True)
            return
        ok = await db.remove_admin(bot_id, uid)
        from . import audit as _audit
        await _audit.log_action(bot_id, chat_id, _audit.A_ADMIN_REMOVE,
                                target=uid, success=ok)
        await send_screen(bot_id, chat_id, "uadmins", message_id=message_id)
        return
    
    # blocks: unblock
    if rest.startswith("ublocks:unblock:"):
        uid = int(rest.split(":")[-1])
        async with db._lock:
            await db.connection.execute(
                "UPDATE bot_users SET is_blocked = 0 WHERE bot_id = ? AND chat_id = ?", (bot_id, uid))
            await db.connection.commit()
        await send_screen(bot_id, chat_id, "ublocks", message_id=message_id)
        return
    
    # ---- Phase 3: analytics export / health check / alerts ----
    if rest == "analytics:export":
        a = await st.analytics_overview(bot_id)
        bot = bot_registry.get_bot(bot_id)
        uname = (bot or {}).get("username", str(bot_id))
        from . import audit as _audit
        await _audit.log_action(bot_id, chat_id, "analytics_export", success=True,
                                summary="text report generated")
        await message_sender.send_message(bot_id, chat_id, sc.analytics_export_text(a, uname),
                                           is_admin_flow=True)
        await _ack(bot_id, callback_id, "📤 تم إرسال التقرير")
        return

    if rest == "health:check":
        from admin_panel import health as _health
        found = await _health.run_health_checks(bot_id)
        from . import audit as _audit
        await _audit.log_action(bot_id, chat_id, "health_check", success=True,
                                summary=f"{len(found)} issues found")
        await _ack(bot_id, callback_id, f"🔍 اكتمل الفحص: {len(found)} مشكلة")
        await send_screen(bot_id, chat_id, "health", message_id=message_id)
        return

    if rest.startswith("alertack:"):
        try:
            aid = int(rest.split(":")[1])
        except ValueError:
            return
        ok = await db.ack_alert(bot_id, aid, chat_id)
        from . import audit as _audit
        await _audit.log_action(bot_id, chat_id, "alert_ack", target=f"alert#{aid}", success=ok)
        await _ack(bot_id, callback_id, "👁 تم الإقرار" if ok else "❌ تعذر الإقرار")
        await send_screen(bot_id, chat_id, "alerts", message_id=message_id)
        return

    if rest.startswith("alertresolve:"):
        try:
            aid = int(rest.split(":")[1])
        except ValueError:
            return
        ok = await db.resolve_alert(bot_id, aid)
        from . import audit as _audit
        await _audit.log_action(bot_id, chat_id, "alert_resolve", target=f"alert#{aid}", success=ok)
        await _ack(bot_id, callback_id, "✅ تم الحل" if ok else "❌ تعذر")
        await send_screen(bot_id, chat_id, "alerts", message_id=message_id)
        return

    # quick reply item detail
    if rest.startswith("qr:item:"):
        idx = int(rest.split(":")[-1])
        s = await get_settings(bot_id)
        items = s.get("quick_replies", [])
        if 0 <= idx < len(items):
            it = items[idx]
            text = f"⚡ /r{idx+1} — <b>{it.get('label','')}</b>\n—————\n{it.get('text','')}"
            await message_sender.edit_message(bot_id, chat_id, message_id, text,
                                               reply_markup=kb.back_only("adm:qr"))
        return
    
    # broadcast confirm/cancel
    if rest == "bc:go":
        convo = await db.get_conversation_state(chat_id)
        if not convo or convo["state"] != "broadcast_confirm":
            return
        # Phase 2: double-run protection - refuse if a broadcast is already processing
        c = await db.connection.execute(
            "SELECT COUNT(*) FROM queue_jobs WHERE bot_id = ? AND job_type = 'broadcast' AND status = 'processing'",
            (bot_id,))
        if (await c.fetchone())[0] > 0:
            await _ack(bot_id, callback_id, "\u23f3 \u0625\u0630\u0627\u0639\u0629 \u0642\u064a\u062f \u0627\u0644\u062a\u0646\u0641\u064a\u0630 \u0628\u0627\u0644\u0641\u0639\u0644\u060c \u0627\u0646\u062a\u0638\u0631", alert=True)
            return
        text = convo["context"].get("text", "")
        await db.clear_conversation_state(chat_id)
        from broadcast_engine import broadcast_engine
        broadcast_id = await broadcast_engine.start_broadcast(bot_id, text)
        from . import audit as _audit
        await _audit.log_action(bot_id, chat_id, _audit.A_BROADCAST,
                                target=f"broadcast#{broadcast_id}",
                                summary=f"text_len={len(text)}")
        await message_sender.edit_message(bot_id, chat_id, message_id,
                                           sc.broadcast_started(broadcast_id), reply_markup=None)
        return
    if rest == "bc:no":
        await db.clear_conversation_state(chat_id)
        await send_screen(bot_id, chat_id, "contact", message_id=message_id)
        return
    if rest == "bc:test":
        convo = await db.get_conversation_state(chat_id)
        if not convo or convo["state"] != "broadcast_confirm":
            return
        text = convo["context"].get("text", "")
        # Send a test copy to the owner only (no broadcast started)
        await message_sender.send_message(bot_id, chat_id, text, is_admin_flow=True)
        await message_sender.send_message(bot_id, chat_id, sc.broadcast_test_sent(),
                                          is_admin_flow=True)
        return
    
    # inactivity: reset stats + reminded flags / delete a reminder stage
    if rest == "inactive:reset":
        from scheduler import reset_inactive_stats
        await reset_inactive_stats(bot_id)
        await send_screen(bot_id, chat_id, "inactive", message_id=message_id)
        return
    if rest.startswith("inactive:rem:"):
        idx = int(rest.split(":")[-1])
        reminders = await db.get_setting(bot_id, "inactive_reminders", [])
        if 0 <= idx < len(reminders):
            r = reminders[idx]
            text = f"📅 بعد {r['days']} يوم\n💬 {r['text']}"
            await message_sender.edit_message(bot_id, chat_id, message_id, text,
                                               reply_markup=kb.inactive_reminder_item_menu(idx))
        return
    if rest.startswith("inactive:remdel:"):
        idx = int(rest.split(":")[-1])
        reminders = await db.get_setting(bot_id, "inactive_reminders", [])
        if 0 <= idx < len(reminders):
            reminders.pop(idx)
            await db.set_setting(bot_id, "inactive_reminders", reminders)
        await send_screen(bot_id, chat_id, "inactive:reminders", message_id=message_id)
        return
    
    # ---- Phase 2: backup create (double-click guarded) ----
    if rest == "backup:create":
        # Guard: refuse if a backup was started < 60s ago (double-press)
        import time
        last = await db.get_setting(bot_id, "_backup_running_since", 0)
        if time.time() - float(last or 0) < 60:
            await _ack(bot_id, callback_id, "⏳ نسخة قيد الإنشاء بالفعل، انتظر", alert=True)
            return
        await db.set_setting(bot_id, "_backup_running_since", time.time())
        await message_sender.edit_message(bot_id, chat_id, message_id,
                                           sc.backup_started(), reply_markup=None)
        from backup import backup_manager
        from . import audit as _audit
        try:
            path = await backup_manager.create_backup()
            import os
            size_mb = os.path.getsize(path) / 1024 / 1024
            await _audit.log_action(bot_id, chat_id, _audit.A_BACKUP_CREATE,
                                    success=True, summary=f"{os.path.basename(path)} {size_mb:.1f}MB")
            await message_sender.edit_message(bot_id, chat_id, message_id,
                                               sc.backup_done(path, size_mb),
                                               reply_markup=kb.back_only("adm:backup"))
        except Exception as e:
            await _audit.log_action(bot_id, chat_id, _audit.A_BACKUP_CREATE,
                                    success=False, summary=f"{type(e).__name__}")
            await db.add_log("error", "backup", f"Backup failed: {type(e).__name__}: {e}")
            await message_sender.edit_message(bot_id, chat_id, message_id,
                                               f"❌ فشل إنشاء النسخة: {type(e).__name__}",
                                               reply_markup=kb.back_only("adm:backup"))
        finally:
            await db.set_setting(bot_id, "_backup_running_since", 0)
        return
    # ---- Phase 2: backup restore (confirmed, additive merge) ----
    if rest.startswith("backup:restore:go:"):
        bid = int(rest.split(":")[-1])
        recs = await db.list_backup_records(50)
        rec = next((r for r in recs if r["id"] == bid), None)
        if not rec:
            await _ack(bot_id, callback_id, "❌ النسخة غير موجودة", alert=True)
            return
        from config import BACKUP_DIR
        import os
        fp = str(BACKUP_DIR / rec["filename"])
        # Isolation pre-check: verify the file first, never blind-restore
        from backup import backup_manager
        report = await backup_manager.verify_backup_file(fp)
        from . import audit as _audit
        if not report.get("ok"):
            await _audit.log_action(bot_id, chat_id, _audit.A_BACKUP_RESTORE,
                                    target=rec["filename"], success=False,
                                    summary=f"verify failed: {report.get(error)}")
            await message_sender.edit_message(bot_id, chat_id, message_id,
                f"❌ فشل فحص النسخة — لن تتم الاستعادة.\n{report.get(error) or report.get(integrity)}",
                reply_markup=kb.back_only("adm:backup"))
            return
        ok = await backup_manager.restore_from_backup(fp)
        await _audit.log_action(bot_id, chat_id, _audit.A_BACKUP_RESTORE,
                                target=rec["filename"], success=ok,
                                summary="additive merge restore")
        await message_sender.edit_message(bot_id, chat_id, message_id,
            "✅ تمت الاستعادة (دمج — الصفوف الموجودة لم تُمس)" if ok else "❌ فشلت الاستعادة",
            reply_markup=kb.back_only("adm:backup"))
        return
    # ---- Phase 2: per-admin permission toggles ----
    if rest.startswith("uadmins:setperm:"):
        _, _, uid_s, perm = rest.split(":", 3)
        uid = int(uid_s)
        from . import permissions as pm
        from .auth import is_owner
        if await is_owner(bot_id, uid) or perm not in pm.ALL_PERMISSIONS:
            return
        cur = await db.get_admin_permissions(bot_id, uid)
        cur_set = set(cur) if cur else set(pm.ALL_PERMISSIONS)
        if perm in cur_set:
            cur_set.discard(perm)
        else:
            cur_set.add(perm)
        ok = await db.set_admin_permissions(bot_id, uid, sorted(cur_set))
        from . import audit as _audit
        await _audit.log_action(bot_id, chat_id, _audit.A_ADMIN_PERMS, target=uid,
                                success=ok, summary=f"now={len(cur_set)} perms")
        await send_screen(bot_id, chat_id, f"uadmin:perms:{uid}", message_id=message_id)
        return
    if rest.startswith("uadmins:preset:"):
        _, _, uid_s, preset = rest.split(":", 3)
        uid = int(uid_s)
        from . import permissions as pm
        from .auth import is_owner
        if await is_owner(bot_id, uid) or preset not in pm.PRESETS:
            return
        perms, _ = pm.PRESETS[preset]
        ok = await db.set_admin_permissions(bot_id, uid, perms)
        from . import audit as _audit
        await _audit.log_action(bot_id, chat_id, _audit.A_ADMIN_PERMS, target=uid,
                                success=ok, summary=f"preset={preset}")
        await send_screen(bot_id, chat_id, f"uadmin:perms:{uid}", message_id=message_id)
        return
    # ---- Phase 2: maintenance mode ----
    if rest == "maintenance:toggle":
        s = await get_settings(bot_id)
        new_val = not s.get("maintenance_mode", False)
        await db.set_setting(bot_id, "maintenance_mode", new_val)
        from . import audit as _audit
        await _audit.log_action(bot_id, chat_id, _audit.A_MAINTENANCE,
                                success=True, summary="maintenance=" + ("ON" if new_val else "OFF"))
        await send_screen(bot_id, chat_id, "maintenance", message_id=message_id)
        return
    if rest == "maintenance:msg":
        await db.set_conversation_state(chat_id, bot_id, "maintenance_msg",
                                         {"cancel_screen": "maintenance"})
        await message_sender.send_message(bot_id, chat_id, sc.maintenance_msg_prompt(),
                                          is_admin_flow=True)
        return

    # Plain navigation / detail screens: adm:<screen>
    await send_screen(bot_id, chat_id, rest, message_id=message_id)
