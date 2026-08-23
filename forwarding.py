"""
Message forwarding: relays a regular user's message (text, photo, video,
document, GIF, sticker, voice - anything) to every admin of the bot as
TWO messages:
  1. the content itself, with a "الرسالة:" prefix/caption
  2. the sender's info ("المرسل: name (@username)")
and routes an admin's reply (typed normally, via /r1../r20 quick replies,
or the literal words "حظر"/"/ban") back to - or against - that user.
"""

import re
from db import db
from message_sender import message_sender
from telegram_adapter import telegram_pool

_QUICK_REPLY_RE = re.compile(r"^/r(\d{1,2})$")
_BAN_WORDS = {"حظر", "/ban", "ban"}
_MEDIA_KEYS = ("photo", "video", "document", "animation", "sticker", "voice", "audio", "video_note")


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
    uname = f"@{username}" if username else "بدون يوزر"
    sender_info = f"👤 المرسل: {first_name or ''} ({uname})\n🆔 <code>{chat_id}</code>"
    
    adapter = await telegram_pool.get_adapter(bot["token"])
    any_sent = False
    
    for admin_chat_id in admin_ids:
        content_msg_id = None
        
        if has_media:
            caption = message.get("caption") or ""
            new_caption = f"الرسالة:\n{caption}" if caption else "الرسالة:"
            result = await adapter.copy_message(admin_chat_id, chat_id, message_id, caption=new_caption)
            if result.get("ok"):
                content_msg_id = result["result"]["message_id"]
        else:
            text = message.get("text") or ""
            sent = await message_sender.send_message(bot_id, admin_chat_id, f"الرسالة:\n{text}", is_admin_flow=True)
            if sent:
                content_msg_id = sent["result"]["message_id"]
        
        if content_msg_id is not None:
            await db.add_forwarded_mapping(bot_id, admin_chat_id, content_msg_id, chat_id, message_id)
            any_sent = True
        
        info_sent = await message_sender.send_message(bot_id, admin_chat_id, sender_info, is_admin_flow=True)
        if info_sent:
            info_msg_id = info_sent["result"]["message_id"]
            await db.add_forwarded_mapping(bot_id, admin_chat_id, info_msg_id, chat_id, message_id)
    
    return any_sent


async def handle_admin_reply(bot_id: int, admin_chat_id: int, reply_to_message_id: int,
                              reply_message: dict) -> bool:
    """If `reply_to_message_id` is a message we previously forwarded from
    a user, act on this admin's reply: ban (حظر/`/ban`), a quick reply
    (`/r1`../`/r20`), or relay it back (text or any media) to that user.
    Returns True if handled."""
    origin_chat_id = await db.get_forwarded_origin(bot_id, admin_chat_id, reply_to_message_id)
    if origin_chat_id is None:
        return False
    
    text = (reply_message.get("text") or "").strip()
    
    if text.lower() in _BAN_WORDS:
        async with db._lock:
            await db.connection.execute(
                "UPDATE bot_users SET is_blocked = 1 WHERE bot_id = ? AND chat_id = ?", (bot_id, origin_chat_id)
            )
            await db.connection.commit()
        await message_sender.send_message(bot_id, admin_chat_id, f"🚫 تم حظر المستخدم <code>{origin_chat_id}</code>", is_admin_flow=True)
        return True
    
    m = _QUICK_REPLY_RE.match(text)
    if m:
        idx = int(m.group(1)) - 1
        items = await db.get_setting(bot_id, "quick_replies", [])
        if 0 <= idx < len(items):
            await message_sender.send_message(bot_id, origin_chat_id, items[idx]["text"])
        else:
            await message_sender.send_message(bot_id, admin_chat_id, f"⚠️ ما فيه رد سريع رقم {idx+1}", is_admin_flow=True)
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
