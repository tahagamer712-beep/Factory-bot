"""Text-reply flows for the factory admin panel (fadm_* states)."""

from db import db
from message_sender import message_sender
from . import screens as sc
from . import keyboards as kb


async def _send(chat_id, text, reply_markup=None):
    from config import FACTORY_BOT_ID
    return await message_sender.send_message(FACTORY_BOT_ID, chat_id, text, reply_markup=reply_markup, is_admin_flow=True)


async def handle_text(chat_id: int, text: str, user_id: int = None) -> bool:
    convo = await db.get_conversation_state(chat_id)
    if not convo or not convo["state"].startswith("fadm_"):
        return False
    from .auth import has_permission
    state_permissions = {
        "fadm_bots_search": "bots", "fadm_owners_search": "owners",
        "fadm_owner_msg": "owners", "fadm_bcast_text": "broadcast",
        "fadm_bcast_confirm": "broadcast", "fadm_sub_add": "subscriptions",
        "fadm_block_new": "blocks", "fadm_maxbots": "settings",
        "fadm_bcastlimit": "settings", "fadm_admin_add": "admins",
    }
    permission = state_permissions.get(convo["state"])
    if permission and user_id is not None and not await has_permission(user_id, permission):
        await db.clear_conversation_state(chat_id)
        return True
    
    if text.strip() == "/cancel":
        await db.clear_conversation_state(chat_id)
        from . import router
        await router.send_screen(chat_id, "main")
        return True
    
    handler = _HANDLERS.get(convo["state"])
    if not handler:
        await db.clear_conversation_state(chat_id)
        return False
    await handler(chat_id, text.strip(), convo["context"])
    return True


async def _bots_search(chat_id, text, ctx):
    await db.clear_conversation_state(chat_id)
    from . import router
    bots = await db.list_all_bots(search=text, limit=10)
    if not bots:
        await _send(chat_id, "❌ ما لقيت أي بوت مطابق")
        await router.send_screen(chat_id, "bots")
        return
    rows = [[kb._btn(f"@{b['username'] or b['bot_id']}", f"fadm:bots:item:{b['bot_id']}")] for b in bots]
    rows.append([kb._btn("◀ رجوع", "fadm:bots")])
    await _send(chat_id, f"🔍 لقيت {len(bots)} نتيجة:", kb._kb(rows))


async def _owners_search(chat_id, text, ctx):
    await db.clear_conversation_state(chat_id)
    from . import router
    if not text.isdigit():
        await _send(chat_id, "⚠️ لازم رقم (ID)")
        await router.send_screen(chat_id, "owners")
        return
    owner_id = int(text)
    info = await db.get_owner_info(owner_id)
    if not info["bots"]:
        await _send(chat_id, "❌ هذا المستخدم ما عنده بوتات")
        await router.send_screen(chat_id, "owners")
        return
    await _send(chat_id, sc.owner_info(info), kb.owner_info_kb(owner_id, info["bots"]))


async def _owner_msg(chat_id, text, ctx):
    owner_id = ctx.get("owner_id")
    await db.clear_conversation_state(chat_id)
    from config import FACTORY_BOT_ID
    result = await message_sender.send_message(FACTORY_BOT_ID, owner_id, text)
    await _send(chat_id, "✅ تم الإرسال" if result else "❌ فشل الإرسال (المستخدم ما بدأ محادثة مع بوت المصنع)")


async def _bcast_text(chat_id, text, ctx):
    from config import FACTORY_BOT_ID
    audience = ctx.get("audience", "all")
    
    if audience == "everyone":
        targets = await db.get_factory_user_ids("all")
        cursor = await db.connection.execute("SELECT COUNT(*) FROM bots WHERE bot_id != ?", (FACTORY_BOT_ID,))
        bots_count = (await cursor.fetchone())[0]
        await db.set_conversation_state(chat_id, FACTORY_BOT_ID, "fadm_bcast_confirm", {"text": text, "audience": audience})
        await _send(
            chat_id,
            f"📢 <b>تأكيد الإعلان — للكل</b>\n"
            f"مستخدمو المصنع: {len(targets)}\n"
            f"+ إذاعة عبر {bots_count} بوت مصنوع لكل مستخدميهم\n"
            f"—————\n{text}\n—————",
            kb.bcast_confirm_kb()
        )
        return
    
    targets = await db.get_factory_user_ids(audience)
    await db.set_conversation_state(chat_id, FACTORY_BOT_ID, "fadm_bcast_confirm", {"text": text, "audience": audience})
    await _send(chat_id, sc.bcast_confirm(text, len(targets)), kb.bcast_confirm_kb())


async def _sub_add(chat_id, text, ctx):
    from config import FACTORY_BOT_ID
    from subscription_handler import subscription_handler
    if not text.startswith("@"):
        await _send(chat_id, "⚠️ لازم يبدأ بـ @")
        return
    ok = await subscription_handler.add_subscription(FACTORY_BOT_ID, text, mandatory=True)
    await db.clear_conversation_state(chat_id)
    from . import router
    await _send(chat_id, "✅ تمت الإضافة" if ok else "❌ فشلت (وصلت الحد أو خطأ)")
    await router.send_screen(chat_id, "sub")


async def _block_new(chat_id, text, ctx):
    if not text.isdigit():
        await _send(chat_id, "⚠️ لازم رقم (Telegram ID)")
        return
    uid = int(text)
    await db.clear_conversation_state(chat_id)
    current = await db.get_factory_block(uid) or {"block_factory_use": False, "block_bot_creation": False, "bots_disabled": False}
    await _send(chat_id, sc.block_options(uid), kb.block_options_kb(uid, current))


async def _maxbots(chat_id, text, ctx):
    if not text.isdigit():
        await _send(chat_id, "⚠️ لازم رقم")
        return
    from config import FACTORY_BOT_ID
    await db.set_setting(FACTORY_BOT_ID, "max_bots_per_user", int(text))
    await db.clear_conversation_state(chat_id)
    from . import router
    await _send(chat_id, "✅ تم الحفظ")
    await router.send_screen(chat_id, "settings")


async def _bcastlimit(chat_id, text, ctx):
    if not text.isdigit():
        await _send(chat_id, "⚠️ لازم رقم")
        return
    from config import FACTORY_BOT_ID
    await db.set_setting(FACTORY_BOT_ID, "broadcast_max_targets", int(text))
    await db.clear_conversation_state(chat_id)
    from . import router
    await _send(chat_id, "✅ تم الحفظ")
    await router.send_screen(chat_id, "settings")


async def _admin_add(chat_id, text, ctx):
    if not text.isdigit():
        await _send(chat_id, "⚠️ لازم رقم (Telegram ID)")
        return
    uid = int(text)
    await db.clear_conversation_state(chat_id)
    await _send(chat_id, sc.admin_pick_role(), kb.admin_role_pick_kb(uid))


_HANDLERS = {
    "fadm_bots_search": _bots_search,
    "fadm_owners_search": _owners_search,
    "fadm_owner_msg": _owner_msg,
    "fadm_bcast_text": _bcast_text,
    "fadm_sub_add": _sub_add,
    "fadm_block_new": _block_new,
    "fadm_maxbots": _maxbots,
    "fadm_bcastlimit": _bcastlimit,
    "fadm_admin_add": _admin_add,
}
