"""
Real membership-verification gate for regular (non-admin) users - each
method actually enforces something. Admins never go through this; see
dispatcher.py, which checks admin_panel.auth.is_admin() first.
"""

import random
from db import db
from message_sender import message_sender
from admin_panel import screens as sc
from admin_panel import keyboards as kb


async def _methods(bot_id: int) -> dict:
    keys = ["verify_enabled", "vm_direct", "vm_captcha", "vm_visit", "vm_phone", "vm_link", "vm_manual", "vm_link_code"]
    defaults = {"verify_enabled": False, "vm_direct": True, "vm_captcha": False, "vm_visit": False,
                "vm_phone": False, "vm_link": False, "vm_manual": False, "vm_link_code": ""}
    return await db.get_settings(bot_id, keys, defaults)


async def is_gated(bot_id: int, chat_id: int) -> bool:
    """True if this user still needs to pass verification before using the bot."""
    s = await _methods(bot_id)
    if not s["verify_enabled"]:
        return False
    return not await db.is_verified(bot_id, chat_id)


def _method_menu_kb(s: dict) -> dict:
    rows = []
    if s["vm_captcha"]:
        rows.append([kb._btn("🔐 CAPTCHA", "vfy:choose:captcha")])
    if s["vm_visit"]:
        rows.append([kb._btn("🌐 زيارة موقع", "vfy:choose:visit")])
    if s["vm_phone"]:
        rows.append([kb._btn("📱 مشاركة الرقم", "vfy:choose:phone")])
    if s["vm_link"]:
        rows.append([kb._btn("🔗 رابط خاص", "vfy:choose:link")])
    if s["vm_manual"]:
        rows.append([kb._btn("✋ قبول يدوي", "vfy:choose:manual")])
    return kb._kb(rows)


async def start_challenge(bot_id: int, chat_id: int, username: str = "", first_name: str = ""):
    """Entry point: called whenever a gated user needs to be challenged."""
    s = await _methods(bot_id)
    intro = await db.get_setting(bot_id, "content_override_verification_prompt_text") or sc.verify_challenge_intro()
    
    if s["vm_direct"]:
        await message_sender.send_message(bot_id, chat_id, intro, reply_markup=kb.verify_direct_kb())
        return
    
    enabled_methods = [k for k in ("vm_captcha", "vm_visit", "vm_phone", "vm_link", "vm_manual") if s[k]]
    if not enabled_methods:
        await db.mark_verified(bot_id, chat_id)
        return
    
    if len(enabled_methods) == 1:
        await message_sender.send_message(bot_id, chat_id, intro)
        await _start_method(bot_id, chat_id, enabled_methods[0][3:])
        return
    
    await message_sender.send_message(
        bot_id, chat_id, intro + "\nاختر طريقة:", reply_markup=_method_menu_kb(s)
    )


async def _start_method(bot_id: int, chat_id: int, method: str):
    if method == "captcha":
        a, b = random.randint(1, 9), random.randint(1, 9)
        correct = a + b
        wrong1 = correct + random.choice([-2, -1, 1, 2, 3])
        wrong2 = correct + random.choice([4, 5, -3, -4])
        options = list({correct, wrong1, wrong2})
        while len(options) < 3:
            options.append(correct + random.randint(-5, 5))
        correct_index = options.index(correct)
        await message_sender.send_message(
            bot_id, chat_id, sc.verify_captcha_question(a, b),
            reply_markup=kb.verify_captcha_kb(options, correct_index)
        )
    
    elif method == "visit":
        url = await db.get_setting(bot_id, "vm_visit_url", "https://example.com")
        await message_sender.send_message(bot_id, chat_id, sc.verify_visit_prompt(url), reply_markup=kb.verify_visit_kb(url))
    
    elif method == "phone":
        # Native contact-share only works via a reply keyboard - the one
        # scoped exception to "no bottom buttons": a one-time end-user
        # system prompt, not admin-panel navigation.
        reply_kb = {
            "keyboard": [[{"text": "📱 مشاركة رقمي", "request_contact": True}]],
            "resize_keyboard": True, "one_time_keyboard": True,
        }
        await message_sender.send_message(bot_id, chat_id, sc.verify_phone_prompt(), reply_markup=reply_kb)
    
    elif method == "link":
        await db.set_conversation_state(chat_id, bot_id, "vfy_link_wait", {})
        await message_sender.send_message(bot_id, chat_id, sc.verify_link_prompt())
    
    elif method == "manual":
        await message_sender.send_message(bot_id, chat_id, sc.verify_manual_pending(), reply_markup=kb.verify_manual_pending_kb())
        from bot_registry import bot_registry
        bot = bot_registry.get_bot(bot_id)
        if bot:
            await message_sender.send_message(
                bot_id, bot["owner_id"], sc.verify_manual_admin_request(chat_id, ""),
                reply_markup=kb.verify_manual_admin_kb(bot_id, chat_id), is_admin_flow=True,
            )


async def handle_text(bot_id: int, chat_id: int, text: str) -> bool:
    convo = await db.get_conversation_state(chat_id)
    if not convo or convo["bot_id"] != bot_id or convo["state"] != "vfy_link_wait":
        return False
    
    if text.strip() == "/cancel":
        await db.clear_conversation_state(chat_id)
        return True
    
    code = await db.get_setting(bot_id, "vm_link_code", "")
    await db.clear_conversation_state(chat_id)
    if code and text.strip() == code:
        await db.mark_verified(bot_id, chat_id)
        await message_sender.send_message(bot_id, chat_id, sc.verify_success())
    else:
        await message_sender.send_message(bot_id, chat_id, sc.verify_failed())
    return True


async def handle_contact(bot_id: int, chat_id: int) -> bool:
    vm_phone = await db.get_setting(bot_id, "vm_phone", False)
    if not vm_phone:
        return False
    await db.mark_verified(bot_id, chat_id)
    await message_sender.send_message(bot_id, chat_id, sc.verify_success())
    return True


async def handle_callback(bot_id: int, chat_id: int, user_id: int, callback_id: str, data: str):
    from bot_registry import bot_registry
    from telegram_adapter import telegram_pool
    bot = bot_registry.get_bot(bot_id)
    if bot:
        adapter = await telegram_pool.get_adapter(bot["token"])
        await adapter.answer_callback_query(callback_id)
    
    rest = data[len("vfy:"):]
    
    if rest == "direct":
        await db.mark_verified(bot_id, chat_id)
        await message_sender.send_message(bot_id, chat_id, sc.verify_success())
        return
    
    if rest.startswith("choose:"):
        await _start_method(bot_id, chat_id, rest.split(":")[-1])
        return
    
    if rest.startswith("captcha:"):
        correct = rest.split(":")[-1] == "1"
        if correct:
            await db.mark_verified(bot_id, chat_id)
            await message_sender.send_message(bot_id, chat_id, sc.verify_success())
        else:
            await message_sender.send_message(bot_id, chat_id, sc.verify_failed())
        return
    
    if rest == "visit_confirm":
        await db.mark_verified(bot_id, chat_id)
        await message_sender.send_message(bot_id, chat_id, sc.verify_success())
        return
    
    if rest == "cancel":
        await db.clear_conversation_state(chat_id)
        return
    
    if rest == "manual_check":
        if await db.is_verified(bot_id, chat_id):
            await message_sender.send_message(bot_id, chat_id, sc.verify_success())
        else:
            await message_sender.send_message(bot_id, chat_id, sc.verify_manual_pending())
        return
    
    if rest.startswith("approve:") or rest.startswith("reject:"):
        from admin_panel.auth import is_admin
        if not await is_admin(bot_id, user_id):
            return
        target_chat_id = int(rest.split(":")[-1])
        if rest.startswith("approve:"):
            await db.mark_verified(bot_id, target_chat_id)
            await message_sender.send_message(bot_id, target_chat_id, sc.verify_success())
        else:
            await message_sender.send_message(bot_id, target_chat_id, sc.verify_rejected())
        return
