"""Text content for the FACTORY admin panel screens."""


def main_menu(s: dict) -> str:
    return (
        "🏭 <b>NEXA FACTORY</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🟢 Engine Online\n"
        f"🤖 {s['total_bots']} بوت | 👤 {s['total_owners']} مالك\n"
        f"👥 {s['total_users']} مستخدم\n"
        f"📨 {s['messages_today']} رسالة اليوم\n"
        f"📢 {s['broadcasts_today']} إذاعة اليوم\n"
        f"🚫 {s['total_blocks']} حظر"
    )


def bots_menu(total: int) -> str:
    return f"🤖 <b>إدارة البوتات</b>\n📊 الإجمالي: {total}"


def bot_info(b: dict) -> str:
    return (
        f"🤖 <b>معلومات البوت</b>\n"
        f"الاسم: @{b['username']}\n"
        f"ID: <code>{b['bot_id']}</code>\n"
        f"🔑 التوكن: <code>{b['token']}</code>\n"
        f"👤 المالك ID: <code>{b['owner_id']}</code>\n"
        f"📅 الإنشاء: {b['created_at']}\n"
        f"👥 المستخدمون: {b['user_count']}\n"
        f"📨 الرسائل: {b['msg_count']}\n"
        f"📢 الإذاعات: {b['broadcast_count']}"
    )


def bot_deleted() -> str:
    return "✅ تم حذف البوت وإيقافه نهائياً."


def confirm_delete_bot(username: str) -> str:
    return f"⚠️ متأكد تريد تحذف @{username}؟ هذا الإجراء نهائي."


def bots_search_prompt() -> str:
    return "🔍 أرسل اسم البوت أو الآيدي، أو /cancel"


def owners_menu(total: int) -> str:
    return f"👤 <b>أصحاب البوتات</b>\n👥 عدد المالكين: {total}"


def owner_info(o: dict) -> str:
    username = f"@{o['username']}" if o.get("username") else "غير متوفر"
    return (
        f"👤 <b>صاحب البوت</b>\n"
        f"اليوزر: <b>{username}</b>\n"
        f"ID: <code>{o['owner_id']}</code>\n"
        f"🤖 البوتات: {len(o['bots'])}\n"
        f"👥 مستخدمو بوتاته: {o['total_users']}"
    )


def owners_search_prompt() -> str:
    return "🔍 أرسل آيدي المالك، أو /cancel"


def owner_msg_prompt() -> str:
    return "📨 أرسل الرسالة اللي تريد توصلها لهذا المالك، أو /cancel"


def stats_view(s: dict, period_label: str) -> str:
    return (
        f"📊 <b>إحصائيات المصنع — {period_label}</b>\n"
        f"🤖 البوتات\n"
        f"├ الإجمالي: {s['total_bots']}\n"
        f"└ المالكين: {s['total_owners']}\n"
        f"👥 المستخدمون: {s['total_users']}\n"
        f"📨 الرسائل اليوم: {s['messages_today']}\n"
        f"📢 الإذاعات اليوم: {s['broadcasts_today']}\n"
        f"🚫 المحظورون: {s['total_blocks']}"
    )


def bcast_prompt() -> str:
    return "📢 أرسل نص الإعلان (نص فقط بهذا الإصدار)، أو /cancel"


def bcast_confirm(text: str, count: int) -> str:
    return f"📢 <b>تأكيد الإعلان</b>\nالجمهور: {count} مستخدم\n—————\n{text}\n—————"


def bcast_started() -> str:
    return "✅ بدأ إرسال الإعلان بالخلفية."


def blocks_menu() -> str:
    return "🚫 <b>الحظر</b>\nإدارة الحظر على مستوى المصنع"


def blocks_list(blocks: list) -> str:
    if not blocks:
        return "📋 <b>قائمة المحظورين</b>\nما فيه أي حظر مسجل."
    return f"📋 <b>قائمة المحظورين ({len(blocks)})</b>"


def block_new_prompt() -> str:
    return "🚫 أرسل Telegram ID الشخص اللي تريد تحظره، أو /cancel"


def block_options(user_id: int, reason: str = "") -> str:
    return f"🚫 <b>حظر مستخدم</b>\nID: <code>{user_id}</code>\nحدد نوع الحظر بالأزرار تحت، وبعدها اضغط تأكيد:"


def block_confirmed() -> str:
    return "✅ تم تطبيق الحظر."


def block_cleared() -> str:
    return "✅ تم إلغاء الحظر بالكامل."


def sub_menu(items: list) -> str:
    return f"🔐 <b>الاشتراك الإجباري للمصنع</b>\nهذا ينطبق تلقائياً على بوت المصنع + كل البوتات المصنوعة\nالقنوات: {len(items)}"


def sub_add_prompt() -> str:
    return "➕ أرسل معرّف القناة (@Channel)، أو /cancel"


def backup_menu(counts: dict) -> str:
    return (
        f"💾 <b>النسخ الاحتياطي</b>\n"
        f"📦 حجم قاعدة البيانات: {counts.get('db_size_mb', 0):.2f} MB\n"
        f"📊 عدد النسخ المحفوظة: {counts.get('backup_count', 0)}"
    )


def backup_creating() -> str:
    return "💾 جاري إنشاء نسخة احتياطية كاملة (كل البوتات)..."


def backup_done(path: str, size_mb: float) -> str:
    return f"✅ <b>تم إنشاء النسخة الاحتياطية</b>\n📁 {path}\n📦 {size_mb:.2f} MB"


def backup_sent() -> str:
    return "✅ <b>تم إنشاء النسخة الاحتياطية وإرسالها كملف</b>"


def backup_send_failed() -> str:
    return "⚠️ تم إنشاء النسخة الاحتياطية، لكن تعذر إرسال الملف. حاول مرة أخرى."


def backup_list(backups: list) -> str:
    if not backups:
        return "📦 ما فيه نسخ محفوظة."
    return f"📦 <b>النسخ السابقة ({len(backups)})</b>"


def confirm_restore(name: str) -> str:
    return f"⚠️ <b>استعادة نسخة احتياطية</b>\n{name}\n\nهذا راح يضيف بيانات النسخة فوق البيانات الحالية (البيانات المكررة تُتجاهل، الموجودة تبقى). متأكد؟"


def restore_done() -> str:
    return "✅ تمت الاستعادة."


def dbtools_menu(info: dict) -> str:
    return (
        f"🗄️ <b>قاعدة البيانات</b>\n"
        f"📦 الحجم: {info.get('size_mb', 0):.2f} MB\n"
        f"🤖 Bots: {info.get('bots', 0)}\n"
        f"👥 Users: {info.get('users', 0)}\n"
        f"📨 Messages: {info.get('messages', 0)}"
    )


def cleanup_done(removed: int) -> str:
    return f"🧹 تم حذف {removed} سجل قديم."


def settings_menu() -> str:
    return "⚙️ <b>إعدادات المصنع</b>"


def maxbots_prompt() -> str:
    return "🤖 أرسل أقصى عدد بوتات يقدر المستخدم يصنعه (0 = بلا حد)، أو /cancel"


def bcastlimit_prompt() -> str:
    return "📢 أرسل أقصى عدد مستخدمين للإذاعة الواحدة (0 = بلا حد)، أو /cancel"


def system_menu(status: dict) -> str:
    return (
        f"🛠️ <b>النظام والصيانة</b>\n"
        f"🟢 Engine: يعمل\n"
        f"🟢 Pollers: {status.get('pollers', 0)}\n"
        f"🟢 Queue: {status.get('queued', 0)} قيد الانتظار"
    )


def reload_done(count: int) -> str:
    return f"🔄 تم إعادة تحميل {count} بوت."


def logs_menu() -> str:
    return "📋 <b>السجلات</b>\nاختر نوع السجل:"


def logs_view(rows: list) -> str:
    if not rows:
        return "📋 ما فيه سجلات من هذا النوع."
    icons = {"error": "🔴", "warning": "⚠️", "info": "ℹ️"}
    lines = [f"{icons.get(lvl,'•')} <code>{ts}</code> [{src}] {msg[:80]}" for lvl, src, msg, ts in rows]
    return "📋 <b>آخر السجلات</b>\n" + "\n".join(lines)


def admins_menu(admins: list) -> str:
    return f"👑 <b>مشرفو المصنع</b>\nالعدد: {len(admins)}"


def add_admin_prompt() -> str:
    return "➕ أرسل Telegram ID الشخص اللي تريد تضيفه كمشرف، أو /cancel"


def admin_pick_role() -> str:
    return "اختر صلاحيته:"


def admin_added(role: str) -> str:
    return f"✅ تمت الإضافة بصلاحية {role}"


def help_guide() -> str:
    return (
        "❓ <b>دليل استخدام لوحة المصنع</b>\n"
        "————————————\n"
        "🤖 البوتات: عرض/بحث/حذف أي بوت بالمنظومة\n"
        "👤 أصحاب البوتات: كل صاحب بوتاته وعدد مستخدميه\n"
        "📊 الإحصائيات: أرقام المصنع الكاملة\n"
        "📢 الإعلانات: بث رسالة لمستخدمي المصنع نفسه\n"
        "🚫 الحظر: حظر شخص من المصنع/إنشاء بوتات/بوتاته الحالية\n"
        "🔐 الاشتراك الإجباري: قنوات إجبارية على مستوى كل المنظومة\n"
        "💾 النسخ الاحتياطي: نسخة كاملة من كل شي (حصري هنا فقط)\n"
        "🗄️ قاعدة البيانات: حجم وتنظيف\n"
        "⚙️ إعدادات المصنع: حدود الاستخدام\n"
        "🛠️ النظام: حالة المحرك\n"
        "📋 السجلات: الأخطاء والتحذيرات\n"
        "👑 المشرفون: صلاحيات متعددة المستويات"
    )
