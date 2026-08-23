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


async def _build_screen(bot_id: int, chat_id: int, screen: str, param: str = None):
    s = await get_settings(bot_id)
    
    if screen == "main":
        stats = await st.today_stats(bot_id)
        from config import FACTORY_BOT_ID
        factory_bot = bot_registry.get_bot(FACTORY_BOT_ID) if FACTORY_BOT_ID else None
        factory_username = factory_bot["username"] if factory_bot else None
        return sc.main_menu(stats), kb.main_menu(s, factory_username)
    
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
        admin_ids = await db.list_admins(bot_id)
        return sc.admins_menu(admin_ids), kb.admins_menu(admin_ids, offset)
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
    
    if screen == "system":
        return sc.system_menu(), kb.system_menu()
    if screen == "system:updates":
        return sc.placeholder("🔄 <b>آخر التحديثات</b>"), kb.back_only("adm:system")
    
    if screen == "help":
        return sc.help_guide(), kb.back_only("adm:main")
    
    return None, None


async def handle_callback(bot_id: int, chat_id: int, message_id: int,
                           callback_id: str, data: str, user_id: int):
    from .auth import is_admin
    if not await is_admin(bot_id, user_id):
        await _ack(bot_id, callback_id, "⛔ غير مصرح", alert=True)
        return
    
    await _ack(bot_id, callback_id)
    
    if not data.startswith("adm:"):
        return
    rest = data[len("adm:"):]
    
    if rest == "noop":
        return
    
    # Toggle: adm:tg:<screen>:<key>
    if rest.startswith("tg:"):
        _, screen, key = rest.split(":", 2)
        from .settings import SETTINGS_DEFAULTS
        await db.toggle_setting(bot_id, key, SETTINGS_DEFAULTS.get(key, False))
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
        await db.remove_admin(bot_id, uid)
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
        text = convo["context"].get("text", "")
        await db.clear_conversation_state(chat_id)
        from broadcast_engine import broadcast_engine
        broadcast_id = await broadcast_engine.start_broadcast(bot_id, text)
        await message_sender.edit_message(bot_id, chat_id, message_id,
                                           sc.broadcast_started(broadcast_id), reply_markup=None)
        return
    if rest == "bc:no":
        await db.clear_conversation_state(chat_id)
        await send_screen(bot_id, chat_id, "contact", message_id=message_id)
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
    
    # Plain navigation / detail screens: adm:<screen>
    await send_screen(bot_id, chat_id, rest, message_id=message_id)
