"""Inline keyboards for the FACTORY admin panel (fadm: prefix, entirely
separate from a single bot's admin_panel which uses adm:)."""

from typing import Dict, List


def _kb(rows: List[List[Dict]]) -> Dict:
    return {"inline_keyboard": rows}


def _btn(text: str, data: str = None, url: str = None) -> Dict:
    if url:
        return {"text": text, "url": url}
    return {"text": text, "callback_data": data}


def main_menu() -> Dict:
    return _kb([
        [_btn("🤖 البوتات", "fadm:bots"), _btn("👤 أصحاب البوتات", "fadm:owners")],
        [_btn("📊 الإحصائيات", "fadm:stats"), _btn("📢 الإعلانات", "fadm:bcast")],
        [_btn("🚫 الحظر", "fadm:blocks"), _btn("🔐 الاشتراك الإجباري", "fadm:sub")],
        [_btn("💾 النسخ الاحتياطي", "fadm:backup"), _btn("🗄️ قاعدة البيانات", "fadm:dbtools")],
        [_btn("⚙️ إعدادات المصنع", "fadm:settings"), _btn("🛠️ النظام والصيانة", "fadm:system")],
        [_btn("📋 السجلات", "fadm:logs"), _btn("👑 المشرفون", "fadm:admins")],
        [_btn("❓ دليل الاستخدام", "fadm:help")],
    ])


def back_only(target: str = "fadm:main", label: str = "◀ رجوع") -> Dict:
    return _kb([[_btn(label, target)]])


# --------------------------------------------------------------- bots -----

def bots_menu() -> Dict:
    return _kb([
        [_btn("🔍 بحث عن بوت", "fadm:bots:search")],
        [_btn("📋 جميع البوتات", "fadm:bots:list:0")],
        [_btn("🆕 آخر البوتات", "fadm:bots:list:0")],
        [_btn("◀ رجوع", "fadm:main")],
    ])


def bots_list_kb(bots: list, offset: int, total: int, page_size: int = 8) -> Dict:
    rows = [[_btn(f"@{b['username'] or b['bot_id']}", f"fadm:bots:item:{b['bot_id']}")] for b in bots]
    nav = []
    if offset > 0:
        nav.append(_btn("◀ السابق", f"fadm:bots:list:{max(0, offset - page_size)}"))
    if offset + page_size < total:
        nav.append(_btn("التالي ▶", f"fadm:bots:list:{offset + page_size}"))
    if nav:
        rows.append(nav)
    rows.append([_btn("◀ رجوع", "fadm:bots")])
    return _kb(rows)


def bot_info_kb(bot_id: int, can_delete: bool) -> Dict:
    rows = [[_btn("👤 معلومات المالك", f"fadm:owners:item:{{owner}}")]]
    if can_delete:
        rows.append([_btn("🗑️ حذف البوت", f"fadm:bots:del:{bot_id}")])
    rows.append([_btn("◀ رجوع", "fadm:bots")])
    return _kb(rows)


def confirm_delete_bot(bot_id: int) -> Dict:
    return _kb([[
        _btn("✅ تأكيد الحذف", f"fadm:bots:delconfirm:{bot_id}"),
        _btn("❌ إلغاء", f"fadm:bots:item:{bot_id}"),
    ]])


# -------------------------------------------------------------- owners ----

def owners_menu() -> Dict:
    return _kb([
        [_btn("🔍 بحث", "fadm:owners:search")],
        [_btn("📋 جميع المالكين", "fadm:owners:list:0")],
        [_btn("◀ رجوع", "fadm:main")],
    ])


def owners_list_kb(owners: list, offset: int, total: int, page_size: int = 8) -> Dict:
    rows = []
    for owner in owners:
        username = f"@{owner['username']}" if owner.get("username") else "بدون يوزر"
        rows.append([_btn(
            f"👤 {username} — {owner['owner_id']} ({owner['bot_count']} بوت)",
            f"fadm:owners:item:{owner['owner_id']}"
        )])
    nav = []
    if offset > 0:
        nav.append(_btn("◀ السابق", f"fadm:owners:list:{max(0, offset - page_size)}"))
    if offset + page_size < total:
        nav.append(_btn("التالي ▶", f"fadm:owners:list:{offset + page_size}"))
    if nav:
        rows.append(nav)
    rows.append([_btn("◀ رجوع", "fadm:owners")])
    return _kb(rows)


def owner_info_kb(owner_id: int, bots: list) -> Dict:
    rows = [[_btn(f"🤖 @{b['username'] or b['bot_id']}", f"fadm:bots:item:{b['bot_id']}")] for b in bots[:8]]
    rows.append([_btn("🚫 حظر من المصنع", f"fadm:blocks:new:{owner_id}")])
    rows.append([_btn("📨 إرسال رسالة", f"fadm:owners:msg:{owner_id}")])
    rows.append([_btn("◀ رجوع", "fadm:owners")])
    return _kb(rows)


# --------------------------------------------------------------- stats ----

def stats_menu() -> Dict:
    return _kb([
        [_btn("📅 اليوم", "fadm:stats:today"), _btn("📅 آخر 7 أيام", "fadm:stats:7d")],
        [_btn("📅 آخر 30 يوم", "fadm:stats:30d"), _btn("📅 الكل", "fadm:stats:all")],
        [_btn("◀ رجوع", "fadm:main")],
    ])


# ------------------------------------------------------------ broadcast ---

def bcast_audience_kb() -> Dict:
    return _kb([
        [_btn("👥 مستخدمو المصنع", "fadm:bcast:aud:all")],
        [_btn("🤖 أصحاب البوتات فقط", "fadm:bcast:aud:owners")],
        [_btn("🌐 للكل (+ عبر كل البوتات المصنوعة)", "fadm:bcast:aud:everyone")],
        [_btn("🆕 المستخدمون الجدد", "fadm:bcast:aud:new_today")],
        [_btn("🟢 المستخدمون النشطون", "fadm:bcast:aud:active_7d")],
        [_btn("🚫 غير النشطين", "fadm:bcast:aud:inactive_30d")],
        [_btn("◀ رجوع", "fadm:main")],
    ])


def bcast_confirm_kb() -> Dict:
    return _kb([[_btn("✅ إرسال", "fadm:bcast:go"), _btn("❌ إلغاء", "fadm:bcast:no")]])


# -------------------------------------------------------------- blocks ----

def blocks_menu() -> Dict:
    return _kb([
        [_btn("➕ حظر مستخدم", "fadm:blocks:new")],
        [_btn("📋 قائمة المحظورين", "fadm:blocks:list")],
        [_btn("◀ رجوع", "fadm:main")],
    ])


def blocks_list_kb(blocks: list) -> Dict:
    rows = [[_btn(f"🚫 {b['user_id']}", f"fadm:blocks:item:{b['user_id']}")] for b in blocks[:15]]
    rows.append([_btn("◀ رجوع", "fadm:blocks")])
    return _kb(rows)


def block_options_kb(user_id: int, current: dict) -> Dict:
    def c(flag):
        return "☑" if flag else "☐"
    return _kb([
        [_btn(f"{c(current.get('block_factory_use'))} من استخدام المصنع", f"fadm:blocks:toggle:{user_id}:use")],
        [_btn(f"{c(current.get('block_bot_creation'))} من إنشاء بوتات جديدة", f"fadm:blocks:toggle:{user_id}:create")],
        [_btn(f"{c(current.get('bots_disabled'))} إيقاف بوتاته الحالية", f"fadm:blocks:toggle:{user_id}:disable")],
        [_btn("🚫 تأكيد الحظر", f"fadm:blocks:confirm:{user_id}")],
        [_btn("♻️ إلغاء الحظر كلياً", f"fadm:blocks:clear:{user_id}")],
        [_btn("◀ رجوع", "fadm:blocks:list")],
    ])


# -------------------------------------------------------- factory subscription --

def sub_menu(items: list) -> Dict:
    rows = [[_btn(f"{'✅' if it['active'] else '❌'} {it['channel_id']}", f"fadm:sub:item:{it['id']}")]
            for it in items[:10]]
    rows.append([_btn("➕ إضافة قناة", "fadm:sub:add")])
    rows.append([_btn("◀ رجوع", "fadm:main")])
    return _kb(rows)


def sub_item_kb(sub_id: int, active: bool) -> Dict:
    return _kb([
        [_btn(f"{'🔴 تعطيل' if active else '🟢 تفعيل'}", f"fadm:sub:toggle:{sub_id}")],
        [_btn("🗑 حذف", f"fadm:sub:del:{sub_id}")],
        [_btn("◀ رجوع", "fadm:sub")],
    ])


# --------------------------------------------------------------- backup ---

def backup_menu(has_backups: bool) -> Dict:
    rows = [[_btn("💾 إنشاء نسخة الآن", "fadm:backup:create")]]
    if has_backups:
        rows.append([_btn("📦 النسخ السابقة", "fadm:backup:list")])
    rows.append([_btn("◀ رجوع", "fadm:main")])
    return _kb(rows)


def backup_list_kb(backups: list) -> Dict:
    rows = [[_btn(b["name"], f"fadm:backup:item:{i}")] for i, b in enumerate(backups[:10])]
    rows.append([_btn("◀ رجوع", "fadm:backup")])
    return _kb(rows)


def backup_item_kb(idx: int) -> Dict:
    return _kb([
        [_btn("♻️ استعادة", f"fadm:backup:restore:{idx}")],
        [_btn("◀ رجوع", "fadm:backup:list")],
    ])


def confirm_restore_kb(idx: int) -> Dict:
    return _kb([[
        _btn("✅ تأكيد الاستعادة", f"fadm:backup:restoreconfirm:{idx}"),
        _btn("❌ إلغاء", f"fadm:backup:item:{idx}"),
    ]])


# ------------------------------------------------------------- db tools ---

def dbtools_menu() -> Dict:
    return _kb([
        [_btn("🧹 تنظيف البيانات القديمة", "fadm:dbtools:cleanup")],
        [_btn("◀ رجوع", "fadm:main")],
    ])


# ------------------------------------------------------------- settings ---

def settings_menu(s: dict) -> Dict:
    return _kb([
        [_btn(f"🤖 حد البوتات لكل مستخدم: {s.get('max_bots_per_user', 0) or 'بلا حد'}", "fadm:settings:maxbots")],
        [_btn(f"📢 حد المستخدمين بالإذاعة: {s.get('broadcast_max_targets', 0) or 'بلا حد'}", "fadm:settings:bcastlimit")],
        [_btn("◀ رجوع", "fadm:main")],
    ])


# --------------------------------------------------------------- system ---

def system_menu() -> Dict:
    return _kb([
        [_btn("🔄 إعادة تحميل البوتات", "fadm:system:reload")],
        [_btn("🧹 تنظيف السجلات القديمة", "fadm:system:cleanlogs")],
        [_btn("◀ رجوع", "fadm:main")],
    ])


# ---------------------------------------------------------------- logs ----

def logs_menu() -> Dict:
    return _kb([
        [_btn("🔴 أخطاء", "fadm:logs:view:error"), _btn("⚠️ تحذيرات", "fadm:logs:view:warning")],
        [_btn("ℹ️ الكل", "fadm:logs:view:")],
        [_btn("◀ رجوع", "fadm:main")],
    ])


# -------------------------------------------------------------- admins ----

def admins_menu(admins: list) -> Dict:
    rows = [[_btn(f"👑 {a['user_id']} — {a['role']}", f"fadm:admins:item:{a['user_id']}")] for a in admins]
    rows.append([_btn("➕ إضافة مشرف", "fadm:admins:add")])
    rows.append([_btn("◀ رجوع", "fadm:main")])
    return _kb(rows)


def admin_role_pick_kb(user_id: int) -> Dict:
    return _kb([
        [_btn("👑 Admin", f"fadm:admins:role:{user_id}:admin")],
        [_btn("🛠️ Support", f"fadm:admins:role:{user_id}:support")],
        [_btn("📊 Analyst", f"fadm:admins:role:{user_id}:analyst")],
        [_btn("◀ رجوع", "fadm:admins")],
    ])


def admin_item_kb(user_id: int) -> Dict:
    return _kb([
        [_btn("🗑 إزالة", f"fadm:admins:del:{user_id}")],
        [_btn("◀ رجوع", "fadm:admins")],
    ])
