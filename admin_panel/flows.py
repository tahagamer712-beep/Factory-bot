"""
Handles the admin's next text message when the panel is "waiting" for a
reply (e.g. after pressing "broadcast", the next thing the admin types is
the broadcast text). Each state has a handler that processes the text and
either advances to the next state or clears it and re-renders a screen.

Returns True if the message was consumed as part of a flow (dispatcher
should not process it as a normal chat message), False otherwise.
"""

from db import db
from message_sender import message_sender
from . import keyboards as kb
from . import screens as sc


async def _send(bot_id: int, chat_id: int, text: str, reply_markup=None):
    """Every message the admin panel sends is is_admin_flow=True, so the
    "استثناء مشرف" auto-delete exception applies to it consistently."""
    return await message_sender.send_message(bot_id, chat_id, text, reply_markup=reply_markup, is_admin_flow=True)


async def _cancel(bot_id: int, chat_id: int, back_screen: str):
    await db.clear_conversation_state(chat_id)
    from . import router
    await router.send_screen(bot_id, chat_id, back_screen)


async def handle_text(bot_id: int, chat_id: int, text: str) -> bool:
    convo = await db.get_conversation_state(chat_id)
    if not convo or convo["bot_id"] != bot_id:
        return False
    
    state = convo["state"]
    ctx = convo["context"]
    
    if text.strip() == "/cancel":
        back = ctx.get("cancel_screen", "main")
        await _cancel(bot_id, chat_id, back)
        await _send(bot_id, chat_id, "❌ تم الإلغاء")
        return True
    
    handler = _HANDLERS.get(state)
    if not handler:
        # Unknown/stale state - don't silently eat the message
        await db.clear_conversation_state(chat_id)
        return False
    
    await handler(bot_id, chat_id, text.strip(), ctx)
    return True


# ---------------------------------------------------------------- welcome --

async def _welcome_edit(bot_id, chat_id, text, ctx):
    if len(text) > 4000:
        await _send(bot_id, chat_id, "⚠️ النص طويل جداً (حد أقصى 4000 حرف)، حاول تقصيره.")
        return
    await db.set_setting(bot_id, "welcome_message", text)
    await db.clear_conversation_state(chat_id)
    from . import router
    await _send(bot_id, chat_id, "✅ تم حفظ رسالة الترحيب")
    await router.send_screen(bot_id, chat_id, "welcome")


# ------------------------------------------------------------- autoreply --

async def _autoreply_keyword(bot_id, chat_id, text, ctx):
    await db.set_conversation_state(chat_id, bot_id, "autoreply_add_reply",
                                     {"keyword": text, "cancel_screen": "autoreply"})
    await _send(bot_id, chat_id, sc.autoreply_add_prompt_reply())


async def _autoreply_reply(bot_id, chat_id, text, ctx):
    from auto_reply_manager import auto_reply_manager
    keyword = ctx.get("keyword", "")
    ok = await auto_reply_manager.add_auto_reply(bot_id, keyword, text)
    await db.clear_conversation_state(chat_id)
    from . import router
    await _send(
        bot_id, chat_id,
        "✅ تم إضافة الرد التلقائي" if ok else "❌ فشل إضافة الرد (تأكد أن الكلمة صيغة regex صحيحة)"
    )
    await router.send_screen(bot_id, chat_id, "autoreply")


# ------------------------------------------------------------------ admin --

async def _admin_add(bot_id, chat_id, text, ctx):
    if not text.lstrip("-").isdigit():
        await _send(bot_id, chat_id, "⚠️ لازم يكون رقم (Telegram ID). حاول مرة ثانية أو /cancel")
        return
    ok = await db.add_admin(bot_id, int(text))
    await db.clear_conversation_state(chat_id)
    from . import router
    await _send(bot_id, chat_id, "✅ تمت الإضافة" if ok else "❌ فشلت الإضافة")
    await router.send_screen(bot_id, chat_id, "uadmins")


# ------------------------------------------------------------------ block --

async def _block_add(bot_id, chat_id, text, ctx):
    if not text.lstrip("-").isdigit():
        await _send(bot_id, chat_id, "⚠️ لازم يكون رقم (chat_id). حاول مرة ثانية أو /cancel")
        return
    target = int(text)
    async with db._lock:
        try:
            await db.connection.execute("BEGIN")
            await db.connection.execute(
                "INSERT OR IGNORE INTO bot_users (bot_id, chat_id) VALUES (?, ?)", (bot_id, target)
            )
            await db.connection.execute(
                "UPDATE bot_users SET is_blocked = 1 WHERE bot_id = ? AND chat_id = ?", (bot_id, target)
            )
            await db.connection.commit()
        except Exception as e:
            await db.connection.rollback()
            print(f"❌ Error blocking user: {e}")
    await db.clear_conversation_state(chat_id)
    from . import router
    await _send(bot_id, chat_id, "✅ تم الحظر")
    await router.send_screen(bot_id, chat_id, "ublocks")


# --------------------------------------------------------------- subscribe --

async def _sub_add(bot_id, chat_id, text, ctx):
    from subscription_handler import subscription_handler, MAX_SUBSCRIPTIONS
    if not text.startswith("@") and not text.startswith("-100"):
        await _send(
            bot_id, chat_id,
            "⚠️ لازم يبدأ بـ @ (يوزر القناة) أو -100 (آيدي رقمي). حاول مرة ثانية أو /cancel"
        )
        return
    current = await subscription_handler.get_subscriptions(bot_id)
    if len(current) >= MAX_SUBSCRIPTIONS:
        await db.clear_conversation_state(chat_id)
        from . import router
        await _send(bot_id, chat_id, sc.sub_limit_reached())
        await router.send_screen(bot_id, chat_id, "sub")
        return
    ok = await subscription_handler.add_subscription(bot_id, text, mandatory=True)
    await db.clear_conversation_state(chat_id)
    from . import router
    await _send(bot_id, chat_id, "✅ تمت الإضافة" if ok else "❌ فشلت الإضافة")
    await router.send_screen(bot_id, chat_id, "sub")


async def _sub_check_text(bot_id, chat_id, text, ctx):
    await db.set_setting(bot_id, "sub_check_text", text[:32])
    await db.clear_conversation_state(chat_id)
    from . import router
    await _send(bot_id, chat_id, "✅ تم الحفظ")
    await router.send_screen(bot_id, chat_id, "sub")


# --------------------------------------------------------------- broadcast --

async def _broadcast_text(bot_id, chat_id, text, ctx):
    from db import db as _db
    cursor = await _db.connection.execute(
        "SELECT COUNT(*) FROM bot_users WHERE bot_id = ? AND is_blocked = 0", (bot_id,)
    )
    user_count = (await cursor.fetchone())[0]
    
    await db.set_conversation_state(chat_id, bot_id, "broadcast_confirm",
                                     {"text": text, "cancel_screen": "contact"})
    await _send(
        bot_id, chat_id,
        sc.broadcast_confirm(text, user_count),
        reply_markup=kb.confirm_cancel("adm:bc:go", "adm:bc:no")
    )


async def _broadcast_text_quick(bot_id, chat_id, text, ctx):
    """⚡ إذاعة سريعة: skips the confirmation step entirely and starts
    sending immediately - this is what actually makes it "quick" versus
    the regular 📣 الإذاعة flow."""
    await db.clear_conversation_state(chat_id)
    from broadcast_engine import broadcast_engine
    from . import router
    broadcast_id = await broadcast_engine.start_broadcast(bot_id, text)
    await _send(bot_id, chat_id, sc.broadcast_started(broadcast_id))


# --------------------------------------------------------------- quick reply --

async def _qr_label(bot_id, chat_id, text, ctx):
    await db.set_conversation_state(chat_id, bot_id, "qr_text",
                                     {"label": text[:40], "cancel_screen": "qr"})
    await _send(bot_id, chat_id, "✏️ الآن أرسل نص الرد، أو /cancel للإلغاء")


async def _qr_text(bot_id, chat_id, text, ctx):
    items = await db.get_setting(bot_id, "quick_replies", [])
    if len(items) >= 20:
        await _send(bot_id, chat_id, "⚠️ وصلت الحد الأقصى (20 رد سريع)")
    else:
        items.append({"label": ctx.get("label", ""), "text": text})
        await db.set_setting(bot_id, "quick_replies", items)
    await db.clear_conversation_state(chat_id)
    from . import router
    await _send(bot_id, chat_id, "✅ تم الحفظ")
    await router.send_screen(bot_id, chat_id, "qr")


async def _autodel_duration(bot_id, chat_id, text, ctx):
    if not text.strip().isdigit() or int(text.strip()) <= 0:
        await _send(bot_id, chat_id, "⚠️ لازم رقم صحيح أكبر من صفر. حاول ثانية أو /cancel")
        return
    await db.set_setting(bot_id, "autodel_minutes", int(text.strip()))
    await db.clear_conversation_state(chat_id)
    from . import router
    await _send(bot_id, chat_id, "✅ تم الحفظ")
    await router.send_screen(bot_id, chat_id, "autodel")


async def _inactive_hours(bot_id, chat_id, text, ctx):
    if not text.strip().isdigit() or int(text.strip()) <= 0:
        await _send(bot_id, chat_id, "⚠️ لازم رقم صحيح أكبر من صفر. حاول ثانية أو /cancel")
        return
    await db.set_setting(bot_id, "inactive_hours", int(text.strip()))
    await db.clear_conversation_state(chat_id)
    from . import router
    await _send(bot_id, chat_id, "✅ تم الحفظ")
    await router.send_screen(bot_id, chat_id, "inactive")


async def _inactive_rem_days(bot_id, chat_id, text, ctx):
    if not text.strip().isdigit() or int(text.strip()) <= 0:
        await _send(bot_id, chat_id, "⚠️ لازم رقم صحيح أكبر من صفر. حاول ثانية أو /cancel")
        return
    await db.set_conversation_state(chat_id, bot_id, "inactive_rem_text",
                                     {"days": int(text.strip()), "cancel_screen": "inactive:reminders"})
    await _send(bot_id, chat_id, sc.inactive_reminder_add_text_prompt())


async def _inactive_rem_text(bot_id, chat_id, text, ctx):
    reminders = await db.get_setting(bot_id, "inactive_reminders", [])
    reminders.append({"days": ctx.get("days", 7), "text": text})
    reminders.sort(key=lambda r: r["days"])
    await db.set_setting(bot_id, "inactive_reminders", reminders)
    await db.clear_conversation_state(chat_id)
    from . import router
    await _send(bot_id, chat_id, "✅ تمت الإضافة")
    await router.send_screen(bot_id, chat_id, "inactive:reminders")


async def _tbtn_add(bot_id, chat_id, text, ctx):
    buttons = await db.get_setting(bot_id, "transparent_buttons", [])
    if len(buttons) >= 8:
        await _send(bot_id, chat_id, "⚠️ وصلت الحد الأقصى (8 أزرار)")
    else:
        buttons.append(text[:32])
        await db.set_setting(bot_id, "transparent_buttons", buttons)
    await db.clear_conversation_state(chat_id)
    from . import router
    await _send(bot_id, chat_id, "✅ تمت الإضافة")
    await router.send_screen(bot_id, chat_id, "tbtn")


async def _shortcut_add_command(bot_id, chat_id, text, ctx):
    cmd = text.strip().lstrip("/").lower()
    if not cmd.replace("_", "").isalnum():
        await _send(bot_id, chat_id, "⚠️ حروف إنجليزي وأرقام بس. حاول ثانية أو /cancel")
        return
    await db.set_conversation_state(chat_id, bot_id, "shortcut_add_desc",
                                     {"command": cmd, "cancel_screen": "shortcuts"})
    await _send(bot_id, chat_id, sc.shortcut_add_desc_prompt())


async def _shortcut_add_desc(bot_id, chat_id, text, ctx):
    commands = await db.get_setting(bot_id, "bot_commands", [])
    commands.append({"command": ctx.get("command", ""), "description": text[:60]})
    await db.set_setting(bot_id, "bot_commands", commands)
    await db.clear_conversation_state(chat_id)
    from . import router
    await _send(bot_id, chat_id, "✅ تمت الإضافة - اضغط «نشر» حتى تفعّلها بتيليجرام")
    await router.send_screen(bot_id, chat_id, "shortcuts")


async def _btnedit_add_label(bot_id, chat_id, text, ctx):
    await db.set_conversation_state(
        chat_id, bot_id, "btnedit_add_url",
        {"item_id": ctx.get("item_id"), "label": text[:32], "cancel_screen": f"btnedit:item:{ctx.get('item_id')}"}
    )
    await _send(bot_id, chat_id, sc.btnedit_add_url_prompt())


async def _btnedit_add_url(bot_id, chat_id, text, ctx):
    if not text.strip().startswith("https://"):
        await _send(bot_id, chat_id, "⚠️ الرابط لازم يبدأ بـ https://. حاول ثانية أو /cancel")
        return
    item_id = ctx.get("item_id")
    key = f"autoreply_buttons_{item_id}"
    buttons = await db.get_setting(bot_id, key, [])
    if len(buttons) >= 3:
        await _send(bot_id, chat_id, "⚠️ وصلت الحد الأقصى (3 أزرار)")
    else:
        buttons.append({"label": ctx.get("label", "رابط"), "url": text.strip()})
        await db.set_setting(bot_id, key, buttons)
    await db.clear_conversation_state(chat_id)
    from . import router
    await _send(bot_id, chat_id, "✅ تمت الإضافة")
    await router.send_screen(bot_id, chat_id, f"btnedit:item:{item_id}")


async def _content_edit_text(bot_id, chat_id, text, ctx):
    key = ctx.get("key", "")
    await db.set_setting(bot_id, f"content_override_{key}", text)
    await db.clear_conversation_state(chat_id)
    from . import router
    await _send(bot_id, chat_id, "✅ تم الحفظ")
    await router.send_screen(bot_id, chat_id, f"contentedit:item:{key}")


async def _vm_link_code(bot_id, chat_id, text, ctx):
    await db.set_setting(bot_id, "vm_link_code", text.strip()[:64])
    await db.clear_conversation_state(chat_id)
    from . import router
    await _send(bot_id, chat_id, "✅ تم الحفظ")
    await router.send_screen(bot_id, chat_id, "verifym")


async def _vm_visit_url(bot_id, chat_id, text, ctx):
    if not text.strip().startswith("https://"):
        await _send(bot_id, chat_id, "⚠️ الرابط لازم يبدأ بـ https://. حاول ثانية أو /cancel")
        return
    await db.set_setting(bot_id, "vm_visit_url", text.strip())
    await db.clear_conversation_state(chat_id)
    from . import router
    await _send(bot_id, chat_id, "✅ تم الحفظ")
    await router.send_screen(bot_id, chat_id, "verifym")


_HANDLERS = {
    "welcome_edit": _welcome_edit,
    "autoreply_add_keyword": _autoreply_keyword,
    "autoreply_add_reply": _autoreply_reply,
    "admin_add": _admin_add,
    "block_add": _block_add,
    "sub_add": _sub_add,
    "sub_check_text": _sub_check_text,
    "broadcast_text": _broadcast_text,
    "broadcast_text_quick": _broadcast_text_quick,
    "qr_add_label": _qr_label,
    "qr_add_text": _qr_text,
    "autodel_duration": _autodel_duration,
    "inactive_hours": _inactive_hours,
    "inactive_rem_days": _inactive_rem_days,
    "inactive_rem_text": _inactive_rem_text,
    "tbtn_add": _tbtn_add,
    "shortcut_add_command": _shortcut_add_command,
    "shortcut_add_desc": _shortcut_add_desc,
    "btnedit_add_label": _btnedit_add_label,
    "btnedit_add_url": _btnedit_add_url,
    "content_edit_text": _content_edit_text,
    "vm_link_code": _vm_link_code,
    "vm_visit_url": _vm_visit_url,
}
