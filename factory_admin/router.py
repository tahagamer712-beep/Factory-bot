"""Routes fadm: callbacks + factory admin conversation flows."""

from db import db
from bot_registry import bot_registry
from message_sender import message_sender
from config import FACTORY_BOT_ID
from . import keyboards as kb
from . import screens as sc
from .auth import is_factory_admin, has_permission, get_role, ROLE_DEFAULTS

PAGE_SIZE = 8


async def _send(chat_id: int, text: str, reply_markup=None):
    from config import FACTORY_BOT_ID
    return await message_sender.send_message(FACTORY_BOT_ID, chat_id, text, reply_markup=reply_markup, is_admin_flow=True)


async def _edit(chat_id: int, message_id: int, text: str, reply_markup=None):
    from config import FACTORY_BOT_ID
    result = await message_sender.edit_message(FACTORY_BOT_ID, chat_id, message_id, text, reply_markup=reply_markup)
    if result is None:
        await _send(chat_id, text, reply_markup)


async def send_screen(chat_id: int, screen: str, message_id: int = None):
    text, markup = await _build_screen(screen)
    if text is None:
        return
    if message_id is not None:
        await _edit(chat_id, message_id, text, markup)
    else:
        await _send(chat_id, text, markup)


async def _build_screen(screen: str):
    if screen == "main":
        s = await db.factory_wide_stats()
        return sc.main_menu(s), kb.main_menu()
    if screen == "bots":
        total = await db.count_all_bots()
        return sc.bots_menu(total), kb.bots_menu()
    if screen == "owners":
        total = await db.count_owners()
        return sc.owners_menu(total), kb.owners_menu()
    if screen == "stats":
        return "📊 اختر الفترة:", kb.stats_menu()
    if screen == "bcast":
        return "📢 اختر الجمهور:", kb.bcast_audience_kb()
    if screen == "blocks":
        return sc.blocks_menu(), kb.blocks_menu()
    if screen == "sub":
        from config import FACTORY_BOT_ID
        from subscription_handler import subscription_handler
        items = await subscription_handler.get_subscriptions(FACTORY_BOT_ID)
        return sc.sub_menu(items), kb.sub_menu(items)
    if screen == "backup":
        from backup import backup_manager
        backups = await backup_manager.list_backups()
        import os
        from config import DATABASE_PATH
        size = os.path.getsize(DATABASE_PATH) / 1024 / 1024 if os.path.exists(DATABASE_PATH) else 0
        return sc.backup_menu({"db_size_mb": size, "backup_count": len(backups)}), kb.backup_menu(bool(backups))
    if screen == "dbtools":
        info = await _db_info()
        return sc.dbtools_menu(info), kb.dbtools_menu()
    if screen == "settings":
        from config import FACTORY_BOT_ID
        maxbots = await db.get_setting(FACTORY_BOT_ID, "max_bots_per_user", 0)
        bl = await db.get_setting(FACTORY_BOT_ID, "broadcast_max_targets", 0)
        return sc.settings_menu(), kb.settings_menu({"max_bots_per_user": maxbots, "broadcast_max_targets": bl})
    if screen == "system":
        from poller import poller_supervisor
        from priority_queue import job_queue
        status = {"pollers": len(poller_supervisor.pollers), "queued": job_queue.get_status()["total_queued"]}
        return sc.system_menu(status), kb.system_menu()
    if screen == "logs":
        return sc.logs_menu(), kb.logs_menu()
    if screen == "admins":
        admins = await db.list_factory_admins()
        return sc.admins_menu(admins), kb.admins_menu(admins)
    if screen == "help":
        return sc.help_guide(), kb.back_only()
    return None, None


async def _db_info() -> dict:
    import os
    from config import DATABASE_PATH
    size = os.path.getsize(DATABASE_PATH) / 1024 / 1024 if os.path.exists(DATABASE_PATH) else 0
    cursor = await db.connection.execute("SELECT COUNT(*) FROM bots")
    bots_n = (await cursor.fetchone())[0]
    cursor = await db.connection.execute("SELECT COUNT(*) FROM bot_users")
    users_n = (await cursor.fetchone())[0]
    cursor = await db.connection.execute("SELECT COUNT(*) FROM messages")
    msgs_n = (await cursor.fetchone())[0]
    return {"size_mb": size, "bots": bots_n, "users": users_n, "messages": msgs_n}


async def handle_callback(chat_id: int, message_id: int, user_id: int, callback_id: str, data: str):
    from bot_registry import bot_registry
    from telegram_adapter import telegram_pool
    from config import FACTORY_BOT_ID
    bot = bot_registry.get_bot(FACTORY_BOT_ID)
    if bot:
        adapter = await telegram_pool.get_adapter(bot["token"])
        await adapter.answer_callback_query(callback_id)
    
    if not await is_factory_admin(user_id):
        return
    if not data.startswith("fadm:"):
        return
    rest = data[len("fadm:"):]
    
    # ---- bots ----
    if rest.startswith("bots:list:"):
        offset = int(rest.split(":")[-1])
        if not await has_permission(user_id, "bots"):
            return
        total = await db.count_all_bots()
        bots = await db.list_all_bots(limit=PAGE_SIZE, offset=offset)
        await _edit(chat_id, message_id, sc.bots_menu(total), kb.bots_list_kb(bots, offset, total, PAGE_SIZE))
        return
    if rest.startswith("bots:item:"):
        bot_id = int(rest.split(":")[-1])
        info = await db.get_bot_full_info(bot_id)
        if not info:
            return
        can_del = await has_permission(user_id, "delete_bots")
        markup = kb.bot_info_kb(bot_id, can_del)
        markup["inline_keyboard"][0][0]["callback_data"] = f"fadm:owners:item:{info['owner_id']}"
        await _edit(chat_id, message_id, sc.bot_info(info), markup)
        return
    if rest.startswith("bots:del:"):
        bot_id = int(rest.split(":")[-1])
        if not await has_permission(user_id, "delete_bots"):
            return
        info = await db.get_bot_full_info(bot_id)
        if info:
            await _edit(chat_id, message_id, sc.confirm_delete_bot(info["username"]), kb.confirm_delete_bot(bot_id))
        return
    if rest.startswith("bots:delconfirm:"):
        bot_id = int(rest.split(":")[-1])
        if not await has_permission(user_id, "delete_bots"):
            return
        from poller import poller_supervisor
        await poller_supervisor.remove_poller(bot_id)
        await bot_registry.unregister_bot(bot_id)
        await db.add_log("warning", "factory", f"Bot #{bot_id} deleted by factory admin {user_id}")
        await _edit(chat_id, message_id, sc.bot_deleted(), kb.back_only("fadm:bots"))
        return
    if rest == "bots:search":
        await db.set_conversation_state(chat_id, FACTORY_BOT_ID, "fadm_bots_search", {})
        await _send(chat_id, sc.bots_search_prompt())
        return
    
    # ---- owners ----
    if rest.startswith("owners:list:"):
        offset = int(rest.split(":")[-1])
        total = await db.count_owners()
        owners = await db.list_owners(limit=PAGE_SIZE, offset=offset)
        await _edit(chat_id, message_id, sc.owners_menu(total), kb.owners_list_kb(owners, offset, total, PAGE_SIZE))
        return
    if rest.startswith("owners:item:"):
        owner_id = int(rest.split(":")[-1])
        info = await db.get_owner_info(owner_id)
        await _edit(chat_id, message_id, sc.owner_info(info), kb.owner_info_kb(owner_id, info["bots"]))
        return
    if rest == "owners:search":
        await db.set_conversation_state(chat_id, FACTORY_BOT_ID, "fadm_owners_search", {})
        await _send(chat_id, sc.owners_search_prompt())
        return
    if rest.startswith("owners:msg:"):
        owner_id = int(rest.split(":")[-1])
        await db.set_conversation_state(chat_id, FACTORY_BOT_ID, "fadm_owner_msg", {"owner_id": owner_id})
        await _send(chat_id, sc.owner_msg_prompt())
        return
    
    # ---- stats ----
    if rest.startswith("stats:"):
        period = rest.split(":")[-1]
        labels = {"today": "اليوم", "7d": "آخر 7 أيام", "30d": "آخر 30 يوم", "all": "الكل"}
        s = await db.factory_wide_stats()
        await _edit(chat_id, message_id, sc.stats_view(s, labels.get(period, period)), kb.back_only("fadm:main"))
        return
    
    # ---- broadcast ----
    if rest.startswith("bcast:aud:"):
        audience = rest.split(":")[-1]
        if not await has_permission(user_id, "broadcast"):
            return
        await db.set_conversation_state(chat_id, FACTORY_BOT_ID, "fadm_bcast_text", {"audience": audience})
        await _send(chat_id, sc.bcast_prompt())
        return
    if rest == "bcast:go":
        convo = await db.get_conversation_state(chat_id)
        if not convo or convo["state"] != "fadm_bcast_confirm":
            return
        text = convo["context"].get("text", "")
        audience = convo["context"].get("audience", "all")
        await db.clear_conversation_state(chat_id)
        
        if audience == "everyone":
            # Message every factory user directly, AND trigger every
            # created bot's own broadcast engine so each bot's end-users
            # get it too - a true system-wide announcement.
            await _edit(chat_id, message_id, "📢 جاري النشر لمستخدمي المصنع وكل البوتات المصنوعة...", None)
            targets = await db.get_factory_user_ids("all")
            for uid in targets:
                await message_sender.send_message(FACTORY_BOT_ID, uid, text)
            
            from broadcast_engine import broadcast_engine
            cursor = await db.connection.execute("SELECT bot_id FROM bots WHERE bot_id != ?", (FACTORY_BOT_ID,))
            bot_ids = [r[0] for r in await cursor.fetchall()]
            for bid in bot_ids:
                await broadcast_engine.start_broadcast(bid, text)
            
            await db.add_log("info", "factory", f"System-wide announcement sent to {len(targets)} factory users + {len(bot_ids)} bots")
            await _send(chat_id, f"✅ تم! أرسلت لـ {len(targets)} مستخدم بالمصنع، وبدأت إذاعة بكل {len(bot_ids)} بوت مصنوع.")
            return
        
        targets = await db.get_factory_user_ids(audience)
        await _edit(chat_id, message_id, sc.bcast_started(), None)
        for uid in targets:
            await message_sender.send_message(FACTORY_BOT_ID, uid, text)
        await db.add_log("info", "factory", f"Announcement sent to {len(targets)} users (audience={audience})")
        return
    if rest == "bcast:no":
        await db.clear_conversation_state(chat_id)
        await send_screen(chat_id, "main", message_id)
        return
    
    # ---- blocks ----
    if rest == "blocks:new" or rest.startswith("blocks:new:"):
        target = rest.split(":")[-1] if rest.startswith("blocks:new:") and rest.split(":")[-1].isdigit() else None
        if target:
            await _show_block_options(chat_id, message_id, int(target))
        else:
            await db.set_conversation_state(chat_id, FACTORY_BOT_ID, "fadm_block_new", {})
            await _send(chat_id, sc.block_new_prompt())
        return
    if rest == "blocks:list":
        blocks = await db.list_factory_blocks()
        await _edit(chat_id, message_id, sc.blocks_list(blocks), kb.blocks_list_kb(blocks))
        return
    if rest.startswith("blocks:item:"):
        uid = int(rest.split(":")[-1])
        await _show_block_options(chat_id, message_id, uid)
        return
    if rest.startswith("blocks:toggle:"):
        _, _, uid_s, field = rest.split(":")
        uid = int(uid_s)
        current = await db.get_factory_block(uid) or {"block_factory_use": False, "block_bot_creation": False, "bots_disabled": False, "reason": ""}
        key = {"use": "block_factory_use", "create": "block_bot_creation", "disable": "bots_disabled"}[field]
        current[key] = not current[key]
        await db.set_factory_block(uid, current["block_factory_use"], current["block_bot_creation"], current["bots_disabled"], current.get("reason", ""))
        await _show_block_options(chat_id, message_id, uid)
        return
    if rest.startswith("blocks:confirm:"):
        uid = int(rest.split(":")[-1])
        if current := await db.get_factory_block(uid):
            if current["bots_disabled"]:
                from poller import poller_supervisor
                cursor = await db.connection.execute("SELECT bot_id FROM bots WHERE owner_id = ?", (uid,))
                for (bid,) in await cursor.fetchall():
                    await poller_supervisor.remove_poller(bid)
        await _edit(chat_id, message_id, sc.block_confirmed(), kb.back_only("fadm:blocks"))
        return
    if rest.startswith("blocks:clear:"):
        uid = int(rest.split(":")[-1])
        await db.clear_factory_block(uid)
        await _edit(chat_id, message_id, sc.block_cleared(), kb.back_only("fadm:blocks"))
        return
    
    # ---- factory-wide subscription ----
    if rest == "sub:add":
        await db.set_conversation_state(chat_id, FACTORY_BOT_ID, "fadm_sub_add", {})
        await _send(chat_id, sc.sub_add_prompt())
        return
    if rest.startswith("sub:item:") or rest.startswith("sub:toggle:") or rest.startswith("sub:del:"):
        from config import FACTORY_BOT_ID
        parts = rest.split(":")
        action, sub_id = parts[1], int(parts[2])
        if action == "toggle":
            async with db._lock:
                await db.connection.execute("UPDATE subscriptions SET active = NOT active WHERE id = ?", (sub_id,))
                await db.connection.commit()
        elif action == "del":
            async with db._lock:
                await db.connection.execute("DELETE FROM subscriptions WHERE id = ?", (sub_id,))
                await db.connection.commit()
        elif action == "item":
            from subscription_handler import subscription_handler
            items = await subscription_handler.get_subscriptions(FACTORY_BOT_ID)
            item = next((i for i in items if i["id"] == sub_id), None)
            if item:
                await _edit(chat_id, message_id, f"🔐 {item['channel_id']}", kb.sub_item_kb(sub_id, item["active"]))
            return
        await send_screen(chat_id, "sub", message_id)
        return
    
    # ---- backup (factory-only, full DB) ----
    if rest == "backup:create":
        if not await has_permission(user_id, "backups"):
            return
        await _edit(chat_id, message_id, sc.backup_creating(), None)
        from backup import backup_manager
        path = await backup_manager.create_backup()
        import os
        size_mb = os.path.getsize(path) / 1024 / 1024
        await _send(chat_id, sc.backup_done(path, size_mb))
        return
    if rest == "backup:list":
        from backup import backup_manager
        backups = await backup_manager.list_backups()
        await _edit(chat_id, message_id, sc.backup_list(backups), kb.backup_list_kb(backups))
        return
    if rest.startswith("backup:item:"):
        idx = int(rest.split(":")[-1])
        from backup import backup_manager
        backups = await backup_manager.list_backups()
        if 0 <= idx < len(backups):
            await _edit(chat_id, message_id, backups[idx]["name"], kb.backup_item_kb(idx))
        return
    if rest.startswith("backup:restore:"):
        idx = int(rest.split(":")[-1])
        from backup import backup_manager
        backups = await backup_manager.list_backups()
        if 0 <= idx < len(backups):
            await _edit(chat_id, message_id, sc.confirm_restore(backups[idx]["name"]), kb.confirm_restore_kb(idx))
        return
    if rest.startswith("backup:restoreconfirm:"):
        if not await has_permission(user_id, "backups"):
            return
        idx = int(rest.split(":")[-1])
        from backup import backup_manager
        backups = await backup_manager.list_backups()
        if 0 <= idx < len(backups):
            await backup_manager.restore_from_backup(backups[idx]["name"] and str((__import__("config").BACKUP_DIR / backups[idx]["name"])))
        await _edit(chat_id, message_id, sc.restore_done(), kb.back_only("fadm:backup"))
        return
    
    # ---- db tools ----
    if rest == "dbtools:cleanup":
        await db.cleanup_old_data()
        await db.cleanup_old_logs()
        await _edit(chat_id, message_id, sc.cleanup_done(1), kb.back_only("fadm:dbtools"))
        return
    
    # ---- settings ----
    if rest == "settings:maxbots":
        await db.set_conversation_state(chat_id, FACTORY_BOT_ID, "fadm_maxbots", {})
        await _send(chat_id, sc.maxbots_prompt())
        return
    if rest == "settings:bcastlimit":
        await db.set_conversation_state(chat_id, FACTORY_BOT_ID, "fadm_bcastlimit", {})
        await _send(chat_id, sc.bcastlimit_prompt())
        return
    
    # ---- system ----
    if rest == "system:reload":
        from poller import poller_supervisor
        n = 0
        cursor = await db.connection.execute("SELECT bot_id, token FROM bots")
        for bid, token in await cursor.fetchall():
            await poller_supervisor.add_and_start_poller(bid, token)
            n += 1
        await _edit(chat_id, message_id, sc.reload_done(n), kb.back_only("fadm:system"))
        return
    if rest == "system:cleanlogs":
        await db.cleanup_old_logs()
        await _edit(chat_id, message_id, "✅ تم تنظيف السجلات القديمة", kb.back_only("fadm:system"))
        return
    
    # ---- logs ----
    if rest.startswith("logs:view:"):
        level = rest.split(":", 2)[-1] or None
        rows = await db.get_logs(level=level, limit=15)
        await _edit(chat_id, message_id, sc.logs_view(rows), kb.back_only("fadm:logs"))
        return
    
    # ---- admins (RBAC) ----
    if rest == "admins:add":
        await db.set_conversation_state(chat_id, FACTORY_BOT_ID, "fadm_admin_add", {})
        await _send(chat_id, sc.add_admin_prompt())
        return
    if rest.startswith("admins:item:"):
        uid = int(rest.split(":")[-1])
        role = await get_role(uid)
        await _edit(chat_id, message_id, f"👑 <code>{uid}</code>\nالصلاحية: {role}", kb.admin_item_kb(uid))
        return
    if rest.startswith("admins:del:"):
        uid = int(rest.split(":")[-1])
        await db.remove_factory_admin(uid)
        await send_screen(chat_id, "admins", message_id)
        return
    if rest.startswith("admins:role:"):
        _, _, uid_s, role = rest.split(":")
        uid = int(uid_s)
        await db.set_factory_admin(uid, role, ROLE_DEFAULTS.get(role, []))
        await _edit(chat_id, message_id, sc.admin_added(role), kb.back_only("fadm:admins"))
        return
    
    # plain navigation
    await send_screen(chat_id, rest, message_id)


async def _show_block_options(chat_id, message_id, uid):
    current = await db.get_factory_block(uid) or {"block_factory_use": False, "block_bot_creation": False, "bots_disabled": False}
    await _edit(chat_id, message_id, sc.block_options(uid), kb.block_options_kb(uid, current))
