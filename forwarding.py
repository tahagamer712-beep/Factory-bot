"""
Message forwarding: relays a regular user's message (text, photo, video,
document, GIF, sticker, voice - anything) to every admin of the bot as:
  1. the content itself ("- الرساله !" + text/caption) with an
     "ارسال رساله" inline button underneath
  2. a reply to (1) with the sender's info:
     "المرسل : <name as a t.me link>"
and routes an admin's reply back to - or against - that user, either via a
normal Telegram reply-to-message, or via the "ارسال رساله" button which
puts the admin in reply-mode (next message goes straight to that user,
no Telegram reply needed). Supports حظر / الغاء حظر in both paths.
"""

import html
import re
from db import db
from message_sender import message_sender
from telegram_adapter import telegram_pool

_QUICK_REPLY_RE = re.compile(r"^/r(\d{1,2})$")
_BAN_WORDS = {"حظر", "/ban", "ban"}
_UNBAN_WORDS = {"الغاء حظر", "إلغاء حظر", "الغاء الحظر", "إلغاء الحظر",
                "/unban", "unban"}
_MEDIA_KEYS = ("photo", "video", "document", "animation", "sticker",
               "voice", "audio", "video_note")

_REPLY_PROMPT = (
    "- ارسل الرساله التي تريد ارسالها 📮\n"
    "\n"
    " يمكنك الرد مباشرتا على رساله الشخص بدون الضغط على الزر \n"
    " يمكنك ارسال حظر او الغاء حظر بالرد على الشخص او بعد ضغط ارسال رساله."
)

_FWD_REPLY_CB = "fwd:reply:"


def _has_media(message: dict) -> bool:
    return any(k in message for k in _MEDIA_KEYS)


async def _admin_ids_for(bot_id: int, bot: dict) -> list:
    """Owner + every additional admin, deduped, owner first."""
    ids = [bot["owner_id"]] + await db.list_admins(bot_id)
    seen = set()
    result = []
    for uid in ids:
        if uid not in seen:
            seen.add(uid)
            result.append(uid)
    return result


def _sender_line(first_name: str, username: str) -> str:
    """'المرسل : <name>' with the name linking to t.me/username when known."""
    name = html.escape((first_name or "مستخدم").strip() or "مستخدم")
    if username:
        u = html.escape(username.lstrip("@"))
        return f'المرسل : <a href="https://t.me/{u}">{name}</a>'
    return f"المرسل : {name}"


def _reply_keyboard(origin_chat_id: int) -> dict:
    return {"inline_keyboard": [[
        {"text": "ارسال رساله", "callback_data": f"{_FWD_REPLY_CB}{origin_chat_id}"}
    ]]}


async def _set_blocked(bot_id: int, chat_id: int, blocked: bool) -> None:
    async with db._lock:
        await db.connection.execute(
            "UPDATE bot_users SET is_blocked = ? WHERE bot_id = ? AND chat_id = ?",
            (1 if blocked else 0, bot_id, chat_id),
        )
        await db.connection.commit()


async def forward_to_admins(bot_id: int, chat_id: int, message: dict,
                             first_name: str, username: str) -> bool:
    """Relays `message` (the full incoming message dict) to every admin.
    Always on - this is the bot's core purpose, not an optional toggle.
    Returns True if at least one copy was sent."""
    from bot_registry import bot_registry
    bot = bot_registry.get_bot(bot_id)
    if not bot:
        return False

    admin_ids = await _admin_ids_for(bot_id, bot)
    if chat_id in admin_ids:
        return False  # an admin messaging their own bot - nothing to relay

    message_id = message.get("message_id")
    if message_id is None:
        return False

    has_media = _has_media(message)
    sender_line = _sender_line(first_name, username)
    kb = _reply_keyboard(chat_id)

    adapter = await telegram_pool.get_adapter(bot["token"])
    any_sent = False

    for admin_chat_id in admin_ids:
        content_msg_id = None

        if has_media:
            caption = message.get("caption") or ""
            new_caption = f"- الرساله !\n{caption}" if caption else "- الرساله !"
            result = await adapter.copy_message(admin_chat_id, chat_id, message_id,
                                                caption=new_caption, reply_markup=kb)
            if result.get("ok"):
                content_msg_id = result["result"]["message_id"]
        else:
            text = message.get("text") or ""
            sent = await message_sender.send_message(
                bot_id, admin_chat_id, f"- الرساله !\n{text}",
                reply_markup=kb, is_admin_flow=True)
            if sent and sent.get("ok"):
                content_msg_id = sent["result"]["message_id"]

        if content_msg_id is not None:
            await db.add_forwarded_mapping(bot_id, admin_chat_id, content_msg_id,
                                           chat_id, message_id)
            any_sent = True
            # sender info as a reply to the content message
            info_sent = await message_sender.send_message(
                bot_id, admin_chat_id, sender_line,
                reply_to_message_id=content_msg_id, is_admin_flow=True)
            if info_sent and info_sent.get("ok"):
                info_msg_id = info_sent["result"]["message_id"]
                await db.add_forwarded_mapping(bot_id, admin_chat_id, info_msg_id,
                                               chat_id, message_id)

    return any_sent


async def _act_on_target(bot_id: int, admin_chat_id: int, origin_chat_id: int,
                         reply_message: dict) -> bool:
    """Shared logic: ban / unban / quick-reply / relay back to the user."""
    text = (reply_message.get("text") or "").strip()

    if text in _BAN_WORDS or text.lower() in _BAN_WORDS:
        await _set_blocked(bot_id, origin_chat_id, True)
        await message_sender.send_message(
            bot_id, admin_chat_id,
            f"🚫 تم حظر المستخدم <code>{origin_chat_id}</code>",
            is_admin_flow=True)
        return True

    if text in _UNBAN_WORDS or text.lower() in _UNBAN_WORDS:
        await _set_blocked(bot_id, origin_chat_id, False)
        await message_sender.send_message(
            bot_id, admin_chat_id,
            f"✅ تم إلغاء حظر المستخدم <code>{origin_chat_id}</code>",
            is_admin_flow=True)
        return True

    m = _QUICK_REPLY_RE.match(text)
    if m:
        idx = int(m.group(1)) - 1
        items = await db.get_setting(bot_id, "quick_replies", [])
        if 0 <= idx < len(items):
            await message_sender.send_message(bot_id, origin_chat_id, items[idx]["text"])
        else:
            await message_sender.send_message(
                bot_id, admin_chat_id, f"⚠️ ما فيه رد سريع رقم {idx+1}",
                is_admin_flow=True)
        return True

    reply_message_id = reply_message.get("message_id")
    if _has_media(reply_message) and reply_message_id is not None:
        from bot_registry import bot_registry
        bot = bot_registry.get_bot(bot_id)
        if bot:
            adapter = await telegram_pool.get_adapter(bot["token"])
            await adapter.copy_message(origin_chat_id, admin_chat_id, reply_message_id)
        return True

    if text:
        await message_sender.send_message(bot_id, origin_chat_id, text)
    return True


async def handle_admin_reply(bot_id: int, admin_chat_id: int, reply_to_message_id: int,
                              reply_message: dict) -> bool:
    """If `reply_to_message_id` is a message we previously forwarded from
    a user, act on this admin's reply: ban/unban, quick replies, or relay
    it back to that user. Returns True if handled."""
    origin_chat_id = await db.get_forwarded_origin(bot_id, admin_chat_id, reply_to_message_id)
    if origin_chat_id is None:
        return False
    return await _act_on_target(bot_id, admin_chat_id, origin_chat_id, reply_message)


async def handle_fwd_callback(bot_id: int, admin_chat_id: int, user_id: int,
                              callback_id: str, data: str) -> bool:
    """Handles 'fwd:' callbacks - currently the 'ارسال رساله' button."""
    from bot_registry import bot_registry
    from admin_panel.auth import is_admin
    bot = bot_registry.get_bot(bot_id)
    if not bot:
        return False
    adapter = await telegram_pool.get_adapter(bot["token"])

    if not await is_admin(bot_id, user_id):
        await adapter.answer_callback_query(callback_id, text="⛔ غير مصرح",
                                            show_alert=True)
        return False

    if data.startswith(_FWD_REPLY_CB):
        try:
            origin_chat_id = int(data[len(_FWD_REPLY_CB):])
        except ValueError:
            await adapter.answer_callback_query(callback_id)
            return False
        await db.set_conversation_state(admin_chat_id, bot_id, "fwd_reply",
                                        {"target": origin_chat_id})
        await adapter.answer_callback_query(callback_id)
        await message_sender.send_message(bot_id, admin_chat_id, _REPLY_PROMPT,
                                          is_admin_flow=True)
        return True

    await adapter.answer_callback_query(callback_id)
    return False


async def handle_reply_mode(bot_id: int, admin_chat_id: int, message: dict) -> bool:
    """If the admin pressed 'ارسال رساله' and is now in reply-mode, route
    this message to the target user (no Telegram reply needed).
    One-shot: the mode clears after a single message. Returns True if handled."""
    st = await db.get_conversation_state(admin_chat_id)
    if not st or st.get("state") != "fwd_reply":
        return False
    ctx = st.get("context") or {}
    target = ctx.get("target")
    await db.clear_conversation_state(admin_chat_id)
    if not isinstance(target, int):
        return False
    return await _act_on_target(bot_id, admin_chat_id, target, message)
