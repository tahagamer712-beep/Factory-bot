"""Central registry of every admin-panel setting key + its default value.
Every toggle/value shown across the panel is read from here in one query
via get_settings(), instead of scattering default values across screens.py
and keyboards.py."""

from db import db

SETTINGS_DEFAULTS = {
    # الحذف التلقائي
    "autodel_enabled": False, "autodel_minutes": 5,
    "autodel_private": True, "autodel_group": False, "autodel_channel": False,
    "autodel_user_msgs": False, "autodel_between": False, "autodel_reaction": False,
    "autodel_exc_buttons": False, "autodel_exc_start": False, "autodel_exc_admin": False, "autodel_exc_pay": False,
    # تذكير غير النشطين
    "inactive_enabled": False, "inactive_hours": 24, "inactive_reminders": [],
    "inactive_exc_subs": False, "inactive_reward": False,
    # التحقق من العضوية
    "verify_enabled": False, "verify_autoscan": False,
    "vm_direct": True, "vm_captcha": False, "vm_visit": False,
    "vm_phone": False, "vm_link": False, "vm_manual": False,
    "vm_link_code": "", "vm_visit_url": "",
    # حماية المحتوى
    "protect_content": False, "protect_media_exc": False,
    "protect_links_exc": False, "protect_text_exc": False,
    # الإشعارات
    "notif_join": True, "notif_block": True,
    # الاشتراك الإجباري
    "sub_notify": False, "sub_check_text": "✅ تحقق",
    # التواصل
    
    # المحتوى
    "welcome_message": None,
    "quick_replies": [],
    "transparent_buttons": [],
    "bot_commands": [],
}


# Keys editable via "✏️ تعديل المحتوى" - each has a hardcoded default text
# that lives wherever it's actually used (message_handler.py etc); this
# just tracks which ones have been overridden.
CONTENT_EDIT_KEYS = [
    "help_text", "unknown_command_text",
    "subscription_prompt_text", "verification_prompt_text",
]


async def get_settings(bot_id: int) -> dict:
    """Fetch every known setting for a bot in one query, with defaults
    filled in for anything not yet saved."""
    s = await db.get_settings(bot_id, list(SETTINGS_DEFAULTS.keys()), SETTINGS_DEFAULTS)
    s["qr_count"] = len(s.get("quick_replies") or [])
    return s
