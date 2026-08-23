"""
Inline keyboard layouts for the admin panel - one function per screen,
matching the button text/order from the reference screenshots exactly.

Every button is `callback_data` driven (no bottom reply-keyboard buttons
anywhere, per the explicit requirement). A toggle button's callback_data
is "adm:tg:<screen>:<key>" so router.py can generically flip the setting
and redraw the same screen.
"""

from typing import Dict, List, Optional


def _kb(rows: List[List[Dict]]) -> Dict:
    return {"inline_keyboard": rows}


def _btn(text: str, data: str = None, url: str = None) -> Dict:
    if url:
        return {"text": text, "url": url}
    return {"text": text, "callback_data": data}


def _on_off(flag: bool) -> str:
    return "🟢" if flag else "🔴"


def _check(flag: bool) -> str:
    return "✅" if flag else "❌"


# ---------------------------------------------------------------- main ----

def main_menu(s: dict = None, factory_username: str = None) -> Dict:
    s = s or {}
    rows = [
        [_btn("⚙️ الإعدادات", "adm:settings"), _btn("📝 المحتوى", "adm:content")],
        [_btn("👥 المستخدمون", "adm:users"), _btn("🔐 الاشتراك", "adm:sub")],
        [_btn("🚚 التواصل", "adm:contact")],
        [_btn("🌐 النظام والدعم", "adm:system")],
        [
            _btn(f"{_check(s.get('notif_join', True))} إشعار الدخول 🔔", "adm:tg:main:notif_join"),
            _btn(f"{_check(s.get('notif_block', True))} إشعار الحظر ⛔", "adm:tg:main:notif_block"),
        ],
        [_btn("❓ دليل الاستخدام", "adm:help")],
    ]
    if factory_username:
        rows.append([_btn("• لوحة تحكم في بوت السايت •", url=f"https://t.me/{factory_username}")])
    return _kb(rows)


# ------------------------------------------------------------ settings ----

def settings_menu(s: dict) -> Dict:
    return _kb([
        [_btn("🛂 قسم التحقق من العضوية", "adm:verify")],
        [_btn("🔒 حماية المحتوى", "adm:protect")],
        [_btn("🔔 الإشعارات", "adm:notif")],
        [_btn(f"{_on_off(s.get('autodel_enabled', False))} الحذف التلقائي", "adm:autodel")],
        [_btn(f"{_on_off(s.get('inactive_enabled', False))} تذكير غير النشطين", "adm:inactive")],
        [_btn(f"⚡ ردود سريعة ({s.get('qr_count', 0)})", "adm:qr")],
        [_btn("• رجوع •", "adm:main")],
    ])


def verify_menu(s: dict, verified_count: int = 0) -> Dict:
    return _kb([
        [_btn(f"{_on_off(s.get('verify_enabled', False))} التحقق: {'مفعل — يعمل' if s.get('verify_enabled') else 'معطل — اضغط للتفعيل'}",
              "adm:tg:verify:verify_enabled")],
        [_btn("📝 رسائل التحقق", "adm:verify:msg")],
        [_btn("📊 الإحصائيات", "adm:verify:stats"), _btn(f"👥 المتحققون ({verified_count})", "adm:verify:list")],
        [_btn(f"{_on_off(s.get('verify_autoscan', False))} المسح التلقائي", "adm:tg:verify:verify_autoscan")],
        [_btn("❓ المساعدة", "adm:verify:help"), _btn("◀ رجوع", "adm:settings")],
    ])


def verify_methods_menu(s: dict) -> Dict:
    return _kb([
        [_btn(f"{_on_off(s.get('vm_direct', True))} دخول مباشر", "adm:tg:verifym:vm_direct")],
        [_btn(f"{_on_off(s.get('vm_captcha', False))} 🔐 CAPTCHA - اختبار تلقائي", "adm:tg:verifym:vm_captcha")],
        [_btn(f"{_on_off(s.get('vm_visit', False))} 🌐 زيارة موقع - رابط", "adm:tg:verifym:vm_visit")],
        [_btn(f"🔗 الرابط: {s.get('vm_visit_url', 'غير محدد')[:28]}", "adm:verifym:visiturl")],
        [_btn(f"{_on_off(s.get('vm_phone', False))} 📱 مشاركة الرقم - هاتف", "adm:tg:verifym:vm_phone")],
        [_btn(f"{_on_off(s.get('vm_link', False))} 🔗 رابط خاص - دعوة", "adm:tg:verifym:vm_link")],
        [_btn(f"🔑 كود الدخول: {s.get('vm_link_code') or 'غير محدد'}", "adm:verifym:linkcode")],
        [_btn(f"{_on_off(s.get('vm_manual', False))} ✋ قبول يدوي - موافقة", "adm:tg:verifym:vm_manual")],
        [_btn("❓ شرح", "adm:verifym:help"), _btn("◀ رجوع", "adm:verify")],
    ])


def protect_menu(s: dict) -> Dict:
    return _kb([
        [_btn("ℹ️ شرح القسم", "adm:protect:help")],
        [_btn(f"{_check(s.get('protect_content', False))} حماية محتوى البوت", "adm:tg:protect:protect_content")],
        [_btn(f"{_check(s.get('protect_media_exc', False))} استثناء الميديا", "adm:tg:protect:protect_media_exc")],
        [_btn(f"{_check(s.get('protect_links_exc', False))} استثناء الروابط", "adm:tg:protect:protect_links_exc")],
        [_btn(f"{_check(s.get('protect_text_exc', False))} استثناء النصوص", "adm:tg:protect:protect_text_exc")],
        [_btn("• رجوع •", "adm:settings")],
    ])


def notif_menu(s: dict) -> Dict:
    return _kb([
        [_btn("ℹ️ شرح القسم", "adm:notif:help")],
        [_btn(f"{_check(s.get('notif_join', True))} إشعار الدخول", "adm:tg:notif:notif_join")],
        [_btn(f"{_check(s.get('notif_block', True))} إشعار الحظر", "adm:tg:notif:notif_block")],
        [_btn("• رجوع •", "adm:settings")],
    ])


def autodel_menu(s: dict) -> Dict:
    enabled = s.get("autodel_enabled", False)
    minutes = s.get("autodel_minutes", 5)
    return _kb([
        [_btn(f"{_on_off(enabled)} {'تعطيل' if enabled else 'تفعيل'}", "adm:tg:autodel:autodel_enabled")],
        [_btn(f"⏱️ مدة الحذف: {minutes} دقيقة", "adm:autodel:duration")],
        [
            _btn(f"{_check(s.get('autodel_private', True))} خاص", "adm:tg:autodel:autodel_private"),
            _btn(f"{_check(s.get('autodel_group', False))} مجموعة", "adm:tg:autodel:autodel_group"),
            _btn(f"{_check(s.get('autodel_channel', False))} قناة", "adm:tg:autodel:autodel_channel"),
        ],
        [_btn(f"{_check(s.get('autodel_user_msgs', False))} حذف رسائل المستخدم", "adm:tg:autodel:autodel_user_msgs")],
        [_btn(f"{_check(s.get('autodel_between', False))} حذف ما بين الرسائل", "adm:tg:autodel:autodel_between")],
        [_btn(f"{_check(s.get('autodel_reaction', False))} ردة فعل قبل الحذف", "adm:tg:autodel:autodel_reaction")],
        [_btn("—— الاستثناءات ——", "adm:noop")],
        [
            _btn(f"{_check(s.get('autodel_exc_buttons', False))} أزرار", "adm:tg:autodel:autodel_exc_buttons"),
            _btn(f"{_check(s.get('autodel_exc_start', False))} بدء", "adm:tg:autodel:autodel_exc_start"),
        ],
        [
            _btn(f"{_check(s.get('autodel_exc_admin', False))} مشرف", "adm:tg:autodel:autodel_exc_admin"),
            _btn(f"{_check(s.get('autodel_exc_pay', False))} دفع", "adm:tg:autodel:autodel_exc_pay"),
        ],
        [_btn("❓ المساعدة", "adm:autodel:help"), _btn("◀ رجوع", "adm:settings")],
    ])


def inactive_menu(s: dict) -> Dict:
    enabled = s.get("inactive_enabled", False)
    reminders = s.get("inactive_reminders", [])
    return _kb([
        [_btn(f"{_on_off(enabled)} {'تعطيل' if enabled else 'تفعيل'}", "adm:tg:inactive:inactive_enabled")],
        [_btn(f"📝 التذكيرات ({len(reminders)})", "adm:inactive:reminders")],
        [_btn(f"⏰ ساعات الإرسال: {s.get('inactive_hours', 24)}h", "adm:inactive:hours")],
        [_btn(f"{_check(s.get('inactive_exc_subs', False))} 🎁 استثناء المشتركين", "adm:tg:inactive:inactive_exc_subs")],
        [_btn(f"{_check(s.get('inactive_reward', False))} 🎁 مكافأة العودة", "adm:tg:inactive:inactive_reward")],
        [_btn("🔁 إعادة تعيين", "adm:inactive:reset")],
        [_btn("❓ المساعدة", "adm:inactive:help"), _btn("◀ رجوع", "adm:settings")],
    ])


def inactive_reminders_menu(reminders: list) -> Dict:
    rows = [[_btn(f"{i+1}. بعد {r['days']} يوم — {r['text'][:20]}", f"adm:inactive:rem:{i}")]
            for i, r in enumerate(reminders)]
    rows.append([_btn("➕ إضافة تذكير", "adm:inactive:remadd")])
    rows.append([_btn("◀ رجوع", "adm:inactive")])
    return _kb(rows)


def inactive_reminder_item_menu(idx: int) -> Dict:
    return _kb([
        [_btn("🗑 حذف", f"adm:inactive:remdel:{idx}")],
        [_btn("◀ رجوع", "adm:inactive:reminders")],
    ])


def _paginated(items: list, offset: int, row_builder, nav_prefix: str, back_data: str,
               extra_rows: list = None, page_size: int = 8) -> Dict:
    """Generic pager: shows items[offset:offset+page_size] as rows built
    by row_builder(item, absolute_index), plus ◀ السابق / التالي ▶ nav when
    there's more, then any extra_rows, then a back button."""
    page = items[offset:offset + page_size]
    rows = [row_builder(it, offset + i) for i, it in enumerate(page)]
    nav = []
    if offset > 0:
        nav.append(_btn("◀ السابق", f"{nav_prefix}:{max(0, offset - page_size)}"))
    if offset + page_size < len(items):
        nav.append(_btn("التالي ▶", f"{nav_prefix}:{offset + page_size}"))
    if nav:
        rows.append(nav)
    for row in (extra_rows or []):
        rows.append(row)
    rows.append([_btn("• رجوع •", back_data)])
    return _kb(rows)


def quick_replies_menu(items: list, offset: int = 0) -> Dict:
    return _paginated(
        items, offset,
        lambda it, i: [_btn(f"/r{i+1} — {it.get('label','')[:20]}", f"adm:qr:item:{i}")],
        "adm:qr:page", "adm:settings",
        extra_rows=[[_btn("➕ إضافة رد سريع", "adm:qr:add")], [_btn("❓ المساعدة", "adm:qr:help")]],
    )


# ------------------------------------------------------------- content ----

def content_menu() -> Dict:
    return _kb([
        [_btn("👋 رسالة الترحيب", "adm:welcome")],
        [_btn("💬 الردود التلقائية", "adm:autoreply")],
        [_btn("🎚 الأزرار الشفافة", "adm:tbtn"), _btn("✏️ تعديل الأزرار", "adm:btnedit")],
        [_btn("✂️ الاختصارات", "adm:shortcuts")],
        [_btn("✏️ تعديل المحتوى", "adm:contentedit"), _btn("📄 قائمة التعديلات", "adm:editlist")],
        [_btn("ℹ️ معلومات البوت", "adm:botinfo")],
        [_btn("❓ المساعدة", "adm:content:help"), _btn("• رجوع •", "adm:main")],
    ])


def transparent_buttons_menu(buttons: list) -> Dict:
    rows = [[_btn(f"🗑 {b}", f"adm:tbtn:del:{i}")] for i, b in enumerate(buttons)]
    rows.append([_btn("➕ إضافة زر", "adm:tbtn:add")])
    if buttons:
        rows.append([_btn("🧹 مسح الكل", "adm:tbtn:clear")])
    rows.append([_btn("• رجوع •", "adm:content")])
    return _kb(rows)


def button_edit_pick_menu(items: list) -> Dict:
    rows = [[_btn(it["keyword"][:30], f"adm:btnedit:pick:{it['id']}")] for it in items[:15]]
    if not rows:
        rows = [[_btn("ما فيه ردود تلقائية بعد", "adm:noop")]]
    rows.append([_btn("• رجوع •", "adm:content")])
    return _kb(rows)


def button_edit_item_menu(item_id: int, buttons: list) -> Dict:
    rows = [[_btn(f"🗑 {b['label']}", f"adm:btnedit:delbtn:{item_id}:{i}")] for i, b in enumerate(buttons)]
    rows.append([_btn("➕ إضافة زر رابط", f"adm:btnedit:addbtn:{item_id}")])
    rows.append([_btn("◀ رجوع", "adm:btnedit")])
    return _kb(rows)


def shortcuts_menu(commands: list) -> Dict:
    rows = [[_btn(f"/{c['command']} — {c['description'][:20]}", f"adm:shortcuts:item:{i}")]
            for i, c in enumerate(commands)]
    rows.append([_btn("➕ إضافة أمر", "adm:shortcuts:add")])
    if commands:
        rows.append([_btn("📤 نشر للقائمة بتيليجرام", "adm:shortcuts:publish")])
    rows.append([_btn("• رجوع •", "adm:content")])
    return _kb(rows)


def shortcut_item_menu(idx: int) -> Dict:
    return _kb([
        [_btn("🗑 حذف", f"adm:shortcuts:del:{idx}")],
        [_btn("◀ رجوع", "adm:shortcuts")],
    ])


def content_edit_menu(overrides: dict) -> Dict:
    keys = [
        ("help_text", "📖 نص /help"),
        ("unknown_command_text", "❓ نص الأمر غير المعروف"),
        ("subscription_prompt_text", "🔐 نص طلب الاشتراك"),
        ("verification_prompt_text", "🛂 نص طلب التحقق"),
    ]
    rows = []
    for key, label in keys:
        mark = "✏️" if key in overrides else "•"
        rows.append([_btn(f"{mark} {label}", f"adm:contentedit:item:{key}")])
    rows.append([_btn("• رجوع •", "adm:content")])
    return _kb(rows)


def content_edit_item_menu(key: str, has_override: bool) -> Dict:
    rows = [[_btn("✏️ تعديل", f"adm:contentedit:edit:{key}")]]
    if has_override:
        rows.append([_btn("♻️ استعادة الافتراضي", f"adm:contentedit:reset:{key}")])
    rows.append([_btn("◀ رجوع", "adm:contentedit")])
    return _kb(rows)


def edit_list_menu(overrides: dict) -> Dict:
    if not overrides:
        return _kb([[_btn("• رجوع •", "adm:content")]])
    rows = [[_btn(f"✏️ {key}", f"adm:contentedit:item:{key}")] for key in overrides]
    rows.append([_btn("• رجوع •", "adm:content")])
    return _kb(rows)


def welcome_menu(has_custom: bool) -> Dict:
    return _kb([
        [_btn("✏️ تعديل الرسالة", "adm:welcome:edit")],
        [_btn("👁 معاينة", "adm:welcome:preview")],
        ([_btn("♻️ استعادة الافتراضي", "adm:welcome:reset")] if has_custom else []),
        [_btn("• رجوع •", "adm:content")],
    ])


def autoreply_menu(items: list, offset: int = 0) -> Dict:
    return _paginated(
        items, offset,
        lambda it, i: [_btn(f"{'✅' if it['active'] else '❌'} {it['keyword'][:24]}", f"adm:autoreply:item:{it['id']}")],
        "adm:autoreply:page", "adm:content",
        extra_rows=[[_btn("➕ إضافة رد تلقائي", "adm:autoreply:add")]],
    )


def autoreply_item_menu(item_id: int, active: bool) -> Dict:
    return _kb([
        [_btn("🗑 حذف", f"adm:autoreply:del:{item_id}")],
        [_btn(f"{'🔴 تعطيل' if active else '🟢 تفعيل'}", f"adm:autoreply:toggle:{item_id}")],
        [_btn("◀ رجوع", "adm:autoreply")],
    ])


def placeholder_menu(back: str) -> Dict:
    return _kb([[_btn("• رجوع •", back)]])


# --------------------------------------------------------------- users ----

def users_menu() -> Dict:
    return _kb([
        [_btn("👤 المسؤولون", "adm:uadmins"), _btn("📊 الإحصائيات", "adm:ustats")],
        [_btn("⛔ إدارة الحظر", "adm:ublocks")],
        [_btn("📋 سجل النشاط", "adm:uactivity")],
        [_btn("• رجوع •", "adm:main")],
    ])


def admins_menu(admin_ids: list, offset: int = 0) -> Dict:
    return _paginated(
        admin_ids, offset,
        lambda uid, i: [_btn(f"👤 {uid}", "adm:noop"), _btn("🗑", f"adm:uadmins:del:{uid}")],
        "adm:uadmins:page", "adm:users",
        extra_rows=[[_btn("➕ إضافة مسؤول", "adm:uadmins:add")]],
    )


def blocks_menu(blocked: list, offset: int = 0) -> Dict:
    return _paginated(
        blocked, offset,
        lambda b, i: [_btn(f"🚫 {b}", "adm:noop"), _btn("♻️ فك الحظر", f"adm:ublocks:unblock:{b}")],
        "adm:ublocks:page", "adm:users",
        extra_rows=[[_btn("➕ حظر مستخدم يدوياً", "adm:ublocks:add")]],
    )


def back_only(target: str, label: str = "◀ رجوع") -> Dict:
    return _kb([[_btn(label, target)]])


# ---------------------------------------------------------- subscription --

def sub_menu(items: list, s: dict) -> Dict:
    rows = [[_btn(f"{'✅' if it['active'] else '❌'} {it['channel_id']}", f"adm:sub:item:{it['id']}")]
            for it in items[:10]]
    rows.append([_btn(f"➕ إضافة اشتراك جديد ({len(items)}/10)", "adm:sub:add")])
    rows.append([_btn("—— الإعدادات ——", "adm:noop")])
    rows.append([_btn(f"{_check(s.get('sub_notify', False))} الإشعار", "adm:tg:sub:sub_notify")])
    rows.append([_btn(f"🔘 نص زر التحقق: {s.get('sub_check_text', '✅ تحقق')}", "adm:sub:checktext")])
    rows.append([_btn("🎭 معاينة البوابة", "adm:sub:preview")])
    rows.append([_btn("✅ تفعيل الكل", "adm:sub:allon"), _btn("❌ تعطيل الكل", "adm:sub:alloff")])
    rows.append([_btn("❓ شرح القسم", "adm:sub:help"), _btn("◀ رجوع", "adm:main")])
    return _kb(rows)


def sub_item_menu(sub_id: int, active: bool) -> Dict:
    return _kb([
        [_btn(f"{'🔴 تعطيل' if active else '🟢 تفعيل'}", f"adm:sub:toggle:{sub_id}")],
        [_btn("🗑 حذف", f"adm:sub:del:{sub_id}")],
        [_btn("◀ رجوع", "adm:sub")],
    ])


# --------------------------------------------------------------- contact --

def contact_menu() -> Dict:
    return _kb([
        [_btn("⚡ إذاعة سريعة", "adm:contact:qbc")],
        [_btn("📣 الإذاعة", "adm:contact:bc")],
        [_btn("• رجوع •", "adm:main")],
    ])


# --------------------------------------------------------------- system ---

def system_menu() -> Dict:
    return _kb([
        [_btn("🔄 آخر التحديثات", "adm:system:updates")],
        [_btn("• رجوع •", "adm:main")],
    ])


def confirm_cancel(confirm_data: str, cancel_data: str) -> Dict:
    return _kb([[_btn("✅ تأكيد", confirm_data), _btn("❌ إلغاء", cancel_data)]])


# ------------------------------------------------- verification (end users) --
# These render for regular bot users, not the admin - callback_data uses a
# "vfy:" prefix so dispatcher routes them outside the admin-only "adm:" path.

def verify_direct_kb(user_id: int) -> Dict:
    return _kb([[_btn("✅ متابعة", f"vfy:direct:{user_id}")]])


def verify_captcha_kb(options: list, correct_index: int, user_id: int) -> Dict:
    import random
    indexed = list(enumerate(options))
    random.shuffle(indexed)
    row = [_btn(str(val), f"vfy:captcha:{1 if i == correct_index else 0}:{user_id}") for i, val in indexed]
    return _kb([row])


def verify_visit_kb(url: str, user_id: int) -> Dict:
    return _kb([
        [_btn("🌐 زيارة الموقع", url=url)],
        [_btn("✅ تحقق", f"vfy:visit_confirm:{user_id}")],
    ])


def verify_link_kb(user_id: int) -> Dict:
    return _kb([[_btn("❌ إلغاء", f"vfy:cancel:{user_id}")]])


def verify_manual_pending_kb(user_id: int) -> Dict:
    return _kb([[_btn("🔄 تحقق من الحالة", f"vfy:manual_check:{user_id}")]])


def verify_manual_admin_kb(bot_id: int, chat_id: int) -> Dict:
    return _kb([[
        _btn("✅ قبول", f"vfy:approve:{chat_id}"),
        _btn("❌ رفض", f"vfy:reject:{chat_id}"),
    ]])


# ------------------------------------------------ subscription gate (end users) --

def sub_gate_kb(channels: list, check_text: str = "✅ تحقق", invite_links: dict = None, user_id: int = None) -> Dict:
    invite_links = invite_links or {}
    rows = []
    for ch in channels:
        if ch.startswith("@"):
            rows.append([_btn(f"📢 {ch}", url=f"https://t.me/{ch.lstrip('@')}")])
        elif ch in invite_links:
            rows.append([_btn("📢 قناة", url=invite_links[ch])])
        # else: no working join link could be generated (bot isn't admin
        # there, or link creation failed) - still listed in the message
        # text, just without a clickable button.
    rows.append([_btn(check_text, f"chk:sub:{user_id}")])
    return _kb(rows)
