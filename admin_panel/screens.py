"""Text content for each admin panel screen. Functions take whatever
live data they need (stats dict, settings dict, lists...) and return the
HTML-formatted message text - matching the wording seen in the reference
screenshots as closely as possible."""


def main_menu(stats: dict) -> str:
    """Command-center home: all numbers from real DB queries (see stats.command_center_stats)."""
    lines = [
        "🎛 <b>مركز القيادة</b>",
        "————————————",
        f"👥 إجمالي المستخدمين: <b>{stats['total_users']}</b>",
        f"🆕 جدد اليوم: <b>{stats['new_today']}</b>",
        f"💬 نشطون (24h): <b>{stats['active_24h']}</b>",
        f"🚩 بلاغات معلقة: <b>{stats['pending_reports']}</b>",
        f"⛔ محظورون: <b>{stats['blocked']}</b>",
        f"🕐 آخر نشاط: {stats['last_activity']}",
        "————————————",
    ]
    ev = stats.get("recent_events") or []
    if ev:
        lines.append("📋 <b>آخر الأحداث:</b>")
        for etype, desc, ts in ev[:5]:
            d = (desc or "")[:45]
            lines.append(f"• {d}")
    else:
        lines.append("📋 لا أحداث مسجلة بعد")
    return "\n".join(lines)


def settings_menu() -> str:
    return "⚙️ <b>الإعدادات</b>\nإدارة إعدادات البوت الاساسية"


def verify_menu(s: dict, verified_count: int) -> str:
    status = "معطل - المستخدمين يدخلون مباشرة" if not s.get("verify_enabled") else "مفعل - يعمل"
    return (
        "🛂 <b>قسم التحقق</b>\n"
        f"الحالة: {status}\n"
        f"👥 المتحققون: {verified_count}"
    )


def verify_methods_menu() -> str:
    return "🔒 <b>اختر طريقة التحقق</b>\nاضغط على الطريقة لتفعيلها (تقدر تفعل أكثر من وحدة، تكفي وحدة ينجح فيها المستخدم)"


def verify_methods_help() -> str:
    return (
        "❓ <b>شرح طرق التحقق</b>\n\n"
        "🔐 <b>CAPTCHA</b>: سؤال حسابي بسيط بأزرار، يمر مباشرة عند اختيار الجواب الصحيح\n"
        "🌐 <b>زيارة موقع</b>: يفتح رابط ثم يضغط تحقق (ملاحظة: ما نقدر نتأكد تقنياً إنه زار الرابط فعلاً، هذا اعتراف صريح)\n"
        "📱 <b>مشاركة الرقم</b>: يشارك رقمه عبر زر تيليجرام الرسمي - تحقق حقيقي\n"
        "🔗 <b>رابط خاص</b>: يرسل كود دخول محدد تحدده أنت\n"
        "✋ <b>قبول يدوي</b>: يوصلك طلب وتوافق أو ترفض بنفسك"
    )


def vm_link_code_prompt() -> str:
    return "🔗 أرسل الآن كود الدخول اللي المستخدم لازم يرسله للتحقق، أو /cancel للإلغاء"


def protect_menu() -> str:
    return "🔒 <b>حماية المحتوى</b>\nحماية رسائل البوت من الحفظ والتوجيه"


def protect_help() -> str:
    return (
        "ℹ️ <b>شرح قسم حماية المحتوى</b>\n\n"
        "عند التفعيل، تيليجرام يمنع فعلياً توجيه أو حفظ رسائل البوت (ميزة protect_content الرسمية).\n"
        "استثناء الروابط: الرسائل اللي فيها رابط ما تتحمى.\n"
        "استثناء النصوص: الرسائل النصية العادية ما تتحمى (تبقى الحماية بس للرسائل الثانية).\n"
        "استثناء الميديا: غير فعّال حالياً - المحرك ما يرسل صور/فيديو أصلاً، بس نص."
    )


def notif_menu() -> str:
    return "🔔 <b>الإشعارات</b>\nإدارة إشعارات البوت - توصلك رسالة فعلية بحسابك"


def notif_help() -> str:
    return (
        "ℹ️ <b>شرح قسم الإشعارات</b>\n\n"
        "🔔 إشعار الدخول: توصلك رسالة فعلية عند دخول مستخدم جديد لأول مرة\n"
        "⛔ إشعار الحظر: توصلك رسالة فعلية عند ما مستخدم يحظر البوت"
    )


def notif_new_user(chat_id: int, username: str, first_name: str) -> str:
    uname = f"@{username}" if username else "بدون يوزر"
    return f"🆕 <b>مستخدم جديد</b>\n👤 {first_name or ''} ({uname})\n🆔 <code>{chat_id}</code>"


def notif_user_blocked(chat_id: int) -> str:
    return f"🚫 <b>مستخدم حظر البوت</b>\n🆔 <code>{chat_id}</code>"


def autodel_menu(s: dict, stats: dict) -> str:
    return (
        "⏱️ <b>الحذف التلقائي للرسائل</b>\n"
        "يتم حذف رسائل البوت تلقائياً بعد مدة محددة\n\n"
        f"الحالة: {'🟢 مفعل' if s.get('autodel_enabled') else '🔴 معطل'}\n"
        f"مدة الحذف: {s.get('autodel_minutes', 5)} دقيقة\n\n"
        "<b>الإحصائيات:</b>\n"
        f"حذف اليوم: {stats.get('today', 0)}\n"
        f"إجمالي الحذف: {stats.get('total', 0)}"
    )


def autodel_help() -> str:
    return (
        "❓ <b>مساعدة — الحذف التلقائي</b>\n\n"
        "يحذف البوت رسائله تلقائياً بعد المدة المحددة، حتى تبقى المحادثة نظيفة.\n"
        "«حذف رسائل المستخدم»: يحذف رسائل المستخدم نفسه بعد نفس المدة كمان.\n"
        "«حذف ما بين الرسائل»: كل رسالة جديدة من البوت تحذف اللي قبلها فوراً (يبقى بس آخر رسالة).\n"
        "«ردة فعل قبل الحذف»: يضيف تفاعل 👀 على الرسالة قبل ما يحذفها.\n"
        "«خاص/مجموعة/قناة»: يحدد نوع المحادثة اللي يشتغل فيها الحذف.\n"
        "الاستثناءات (أزرار/بدء/مشرف): تمنع رسائل معينة من الحذف."
    )


def autodel_duration_prompt() -> str:
    return "⏱️ أرسل عدد الدقائق الجديد لمدة الحذف (رقم فقط)، أو /cancel للإلغاء"


def inactive_menu(s: dict, stats: dict) -> str:
    reminders = s.get("inactive_reminders", [])
    lines = "\n".join(f"{i+1}. بعد {r['days']} يوم — 💬 \"{r['text']}\"" for i, r in enumerate(reminders)) \
        or "ما فيه تذكيرات مضافة"
    return (
        "🔔 <b>تذكير المستخدمين غير النشطين</b>\n\n"
        f"الحالة: {'🟢 مفعل' if s.get('inactive_enabled') else '🔴 معطل'}\n"
        f"ساعات الإرسال (فترة السويب): {s.get('inactive_hours', 24)} ساعة\n"
        f"استثناء المشتركين: {'✅' if s.get('inactive_exc_subs') else '❌'}\n"
        f"مكافأة العودة: {'✅' if s.get('inactive_reward') else '❌'}\n\n"
        f"<b>التذكيرات ({len(reminders)}):</b>\n{lines}\n\n"
        f"<b>الإحصائيات:</b>\n"
        f"أرسل: {stats.get('sent', 0)} | عاد: {stats.get('returned', 0)} | حظر: {stats.get('blocked', 0)}\n"
        f"في الانتظار: {stats.get('pending', 0)}"
    )


def inactive_help() -> str:
    return (
        "❓ <b>مساعدة — تذكير غير النشطين</b>\n\n"
        "يرسل البوت رسالة تلقائية لكل مستخدم توقف عن التفاعل، حسب جدول التذكيرات "
        "اللي تحدده (مثلاً: تذكير بعد 7 أيام، وتذكير ثاني بعد 14 يوم).\n"
        "«ساعات الإرسال»: كل قد ايش تتفحص حالة المستخدمين (فترة السويب بالساعات).\n"
        "استثناء المشتركين يتحقق فعلياً من اشتراكهم بالقنوات الإجبارية.\n"
        "مكافأة العودة ترسل تلقائياً أول ما يرجع يكتب للبوت."
    )


def inactive_reminders_menu(reminders: list) -> str:
    if not reminders:
        return "📝 <b>التذكيرات</b>\nما فيه تذكيرات مضافة بعد."
    lines = "\n".join(f"{i+1}. بعد {r['days']} يوم — {r['text']}" for i, r in enumerate(reminders))
    return f"📝 <b>التذكيرات ({len(reminders)})</b>\n{lines}"


def inactive_reminder_add_days_prompt() -> str:
    return "📅 أرسل عدد أيام عدم النشاط قبل هذا التذكير (رقم فقط)، أو /cancel للإلغاء"


def inactive_reminder_add_text_prompt() -> str:
    return "✏️ الآن أرسل نص التذكير، أو /cancel للإلغاء"


def inactive_hours_prompt() -> str:
    return "⏰ أرسل عدد الساعات الجديد بين كل فحص لغير النشطين (رقم فقط)، أو /cancel للإلغاء"


def quick_replies_menu(items: list) -> str:
    if not items:
        body = "لا توجد ردود سريعة محفوظة بعد."
    else:
        body = "\n".join(f"/r{i+1} — {it.get('label','')}" for i, it in enumerate(items))
    return (
        "⚡ <b>الردود السريعة</b>\n\n"
        "أي رسالة تجيك من مستخدم، رد عليها بـ /r1 /r2 ... "
        "لإرسال رد سريع محفوظ فوراً للمستخدم\n\n"
        f"<b>الردود المحفوظة ({len(items)}):</b>\n{body}"
    )


def quick_replies_help() -> str:
    return (
        "❓ <b>مساعدة — الردود السريعة</b>\n\n"
        "<b>ما هي؟</b> ردود محفوظة يمكنك إرسالها بسرعة عند الرد على رسائل المستخدمين المحوّلة\n\n"
        "<b>كيف تستخدمها؟</b>\n"
        "1. أضف رداً سريعاً من هذه اللوحة\n"
        "2. عندما يرسل مستخدم رسالة، توصلك محوّلة تلقائياً\n"
        "3. رد على الرسالة المحوّلة بـ /r1 أو /r2 أو /r3 ...\n"
        "4. سيتم إرسال الرد المحفوظ للمستخدم تلقائياً\n\n"
        "الحد الأقصى: 20 رد سريع"
    )


def content_menu() -> str:
    return "📝 <b>المحتوى</b>\nإدارة رسائل البوت والردود والأزرار"


def content_help() -> str:
    return (
        "❓ <b>مساعدة قسم المحتوى</b>\n\n"
        "👋 <b>رسالة الترحيب</b>: الرسالة التي تظهر عند إرسال /start\n"
        "💬 <b>الردود التلقائية</b>: ردود عند استقبال كلمات معينة\n"
        "🎚 <b>الأزرار الشفافة</b>: أزرار ثابتة تظهر تحت رسالة الترحيب (مرة وحدة لكل مستخدم)\n"
        "✏️ <b>تعديل الأزرار</b>: إضافة أزرار روابط لأي رد تلقائي\n"
        "✂️ <b>الاختصارات</b>: أوامر البوت التي تظهر بقائمة / بتيليجرام فعلياً\n"
        "✏️ <b>تعديل المحتوى</b>: تخصيص نصوص البوت الجاهزة (المساعدة، رسالة الاشتراك...)\n"
        "ℹ️ <b>معلومات البوت</b>: بيانات بوتك الأساسية"
    )


def welcome_menu(current_text: str, is_custom: bool) -> str:
    return (
        "👋 <b>رسالة الترحيب</b>\n\n"
        f"{'✏️ النص الحالي (مخصص):' if is_custom else '📄 النص الحالي (افتراضي):'}\n"
        f"—————\n{current_text}"
    )


def welcome_edit_prompt() -> str:
    return "✏️ أرسل الآن نص رسالة الترحيب الجديدة (النص فقط، أرسل /cancel للإلغاء)"


def autoreply_menu(items: list) -> str:
    return f"💬 <b>الردود التلقائية</b>\nالردود المحفوظة: {len(items)}"


def autoreply_add_prompt_keyword() -> str:
    return "➕ أرسل الكلمة/الجملة المفتاحية (يدعم regex)، أو /cancel للإلغاء"


def autoreply_add_prompt_reply() -> str:
    return "✏️ الآن أرسل نص الرد التلقائي، أو /cancel للإلغاء"


def tbtn_menu(buttons: list) -> str:
    if not buttons:
        return (
            "🎚 <b>الأزرار الشفافة</b>\n\n"
            "أزرار ثابتة تظهر تحت رسالة الترحيب لأي مستخدم عادي (زر واحد بكل سطر).\n"
            "لسا ما أضفت أي زر."
        )
    lines = "\n".join(f"• {b}" for b in buttons)
    return f"🎚 <b>الأزرار الشفافة ({len(buttons)})</b>\n{lines}"


def tbtn_add_prompt() -> str:
    return "➕ أرسل نص الزر الجديد (اللي يظهر ويُرسل نفسه لما يضغط عليه المستخدم)، أو /cancel"


def btnedit_pick_prompt() -> str:
    return "✏️ <b>تعديل الأزرار</b>\nاختر رد تلقائي تضيفله أزرار روابط:"


def btnedit_item(keyword: str, reply: str, buttons: list) -> str:
    btn_lines = "\n".join(f"• {b['label']} → {b['url']}" for b in buttons) or "ما فيه أزرار مضافة"
    return f"💬 <b>{keyword}</b>\n{reply}\n\n<b>الأزرار:</b>\n{btn_lines}"


def btnedit_add_label_prompt() -> str:
    return "🏷 أرسل نص الزر، أو /cancel"


def btnedit_add_url_prompt() -> str:
    return "🔗 الآن أرسل الرابط (لازم يبدأ بـ https://)، أو /cancel"


def shortcuts_menu(commands: list) -> str:
    if not commands:
        return "✂️ <b>الاختصارات</b>\nما فيه أوامر مضافة. هذي تظهر بقائمة / بتيليجرام."
    lines = "\n".join(f"/{c['command']} — {c['description']}" for c in commands)
    return f"✂️ <b>الاختصارات ({len(commands)})</b>\n{lines}\n\n💡 اضغط «نشر» حتى تظهر فعلياً بقائمة / بتيليجرام"


def shortcut_add_command_prompt() -> str:
    return "✂️ أرسل اسم الأمر بدون / (حروف إنجليزي وأرقام بس، مثال: help)، أو /cancel"


def shortcut_add_desc_prompt() -> str:
    return "📝 الآن أرسل وصف قصير للأمر، أو /cancel"


def shortcut_published() -> str:
    return "✅ تم نشر الأوامر - جرب اكتب / بمحادثة البوت راح تشوفها"


def content_edit_menu() -> str:
    return "✏️ <b>تعديل المحتوى</b>\nاختر نص جاهز تعدله (✏️ = معدّل، • = افتراضي):"


CONTENT_EDIT_LABELS = {
    "help_text": "📖 نص /help",
    "unknown_command_text": "❓ نص الأمر غير المعروف",
    "subscription_prompt_text": "🔐 نص طلب الاشتراك",
    "verification_prompt_text": "🛂 نص طلب التحقق",
}


def content_edit_item(key: str, current: str, is_custom: bool) -> str:
    label = CONTENT_EDIT_LABELS.get(key, key)
    return f"{label}\n\n{'✏️ (مخصص)' if is_custom else '📄 (افتراضي)'}:\n—————\n{current}"


def content_edit_prompt(key: str) -> str:
    label = CONTENT_EDIT_LABELS.get(key, key)
    return f"✏️ أرسل النص الجديد لـ «{label}»، أو /cancel"


def edit_list_menu() -> str:
    return "📄 <b>قائمة التعديلات</b>\nكل النصوص اللي عدّلتها عن الافتراضي:"


def bot_info(username: str, bot_id: int, created_at: str, user_count: int, msg_count: int) -> str:
    return (
        f"ℹ️ <b>معلومات البوت</b>\n\n"
        f"🤖 اليوزر: @{username}\n"
        f"🆔 المعرف: <code>{bot_id}</code>\n"
        f"📅 تاريخ الإنشاء: {created_at}\n"
        f"👥 المستخدمين: {user_count}\n"
        f"💬 الرسائل: {msg_count}"
    )


def users_menu() -> str:
    return "👥 <b>المستخدمين</b>\nإدارة المستخدمين والأدمنية"


def users_stats(stats: dict) -> str:
    return (
        "📊 <b>إحصائيات المستخدمين</b>\n\n"
        f"👥 الإجمالي: {stats['total']}\n"
        f"🟢 نشط (7 أيام): {stats['active_7d']}\n"
        f"🚫 محظورون: {stats['blocked']}\n"
        f"🆕 اليوم: {stats['today']}"
    )


def admins_menu(admin_ids: list) -> str:
    if not admin_ids:
        return "👤 <b>المسؤولون</b>\nما فيه مسؤولين إضافيين — بس أنت (المالك)."
    return "👤 <b>المسؤولون</b>\n" + "\n".join(f"• <code>{uid}</code>" for uid in admin_ids)


def add_admin_prompt() -> str:
    return "➕ أرسل الآن Telegram ID الخاص بالمسؤول الجديد، أو /cancel للإلغاء"


def blocks_menu(blocked: list) -> str:
    if not blocked:
        return "⛔ <b>إدارة الحظر</b>\nما فيه مستخدمين محظورين حالياً."
    return "⛔ <b>إدارة الحظر</b>\n" + "\n".join(f"• <code>{b}</code>" for b in blocked)


def add_block_prompt() -> str:
    return "🚫 أرسل chat_id المستخدم اللي تريد تحظره، أو /cancel للإلغاء"


def activity_log(events: list) -> str:
    if not events:
        return "📋 <b>سجل النشاط</b>\nما فيه أحداث مسجلة بعد."
    lines = []
    for etype, desc, ts in events[:15]:
        lines.append(f"• <code>{ts}</code> [{etype}] {desc}")
    return "📋 <b>سجل النشاط (آخر 15)</b>\n" + "\n".join(lines)


def sub_menu(items: list) -> str:
    return f"🔐 <b>الاشتراك الإجباري</b>\nالاشتراكات: {len(items)}/10"


def sub_add_prompt() -> str:
    return "➕ أرسل معرّف القناة/المجموعة (مثال: @MyChannel)، أو /cancel للإلغاء"


def sub_limit_reached() -> str:
    return "⚠️ وصلت الحد الأقصى (10 اشتراكات). احذف وحدة قبل ما تضيف جديدة."


def sub_check_text_prompt() -> str:
    return "🔘 أرسل النص الجديد لزر التحقق (مثال: ✅ تحقق من اشتراكي)، أو /cancel"


def sub_preview_intro() -> str:
    return "🎭 <b>معاينة البوابة</b>\nهذا بالضبط اللي يشوفه مستخدم غير مشترك:"


def sub_help() -> str:
    return (
        "❓ <b>شرح قسم الاشتراك الإجباري</b>\n\n"
        "<b>ما هو هذا القسم؟</b>\n"
        "يجبر مستخدمي البوت على الاشتراك في قنواتك قبل استخدام البوت. "
        "حد أقصى 10 اشتراكات (مطبّق فعلياً).\n\n"
        "✅ = مفعل ويعمل | ❌ = معطل ومتوقف\n\n"
        "✅ تفعيل الكل / ❌ تعطيل الكل: تفعيل أو تعطيل جميع الاشتراكات دفعة واحدة\n"
        "🎭 معاينة البوابة: تشوف شكل رسالة الاشتراك زي ما يشوفها المستخدم بالضبط"
    )


def contact_menu() -> str:
    return (
        "🚚 <b>التواصل</b>\n"
        "إدارة الإذاعة\n\n"
        "💬 كل رسالة يرسلها مستخدم توصلك تلقائياً — رد عليها (Reply) وردك يوصله، "
        "أو اكتب «حظر»/«/ban» على رسالته عشان تحظره."
    )


def broadcast_prompt() -> str:
    return "📣 أرسل الآن نص رسالة الإذاعة (سترسل لكل المستخدمين غير المحظورين)، أو /cancel للإلغاء"


def broadcast_confirm(text: str, user_count: int) -> str:
    return (
        f"📣 <b>تأكيد الإذاعة</b>\n\n"
        f"سيتم الإرسال إلى <b>{user_count}</b> مستخدم:\n"
        f"—————\n{text}\n—————\n\n"
        "متأكد؟"
    )


def broadcast_started(broadcast_id: int) -> str:
    return f"✅ بدأت الإذاعة #{broadcast_id} بالخلفية — راح تستلم تحديث لما تخلص."


def system_menu() -> str:
    return "🌐 <b>النظام والدعم</b>\nأدوات النظام والصيانة"


def backup_started() -> str:
    return "💾 جاري إنشاء نسخة احتياطية..."


def backup_done(path: str, size_mb: float) -> str:
    return f"✅ <b>تم إنشاء النسخة الاحتياطية</b>\n📁 {path}\n📦 {size_mb:.2f} MB"


def placeholder(title: str) -> str:
    return f"{title}\n\n🚧 هذا القسم قيد التطوير حالياً."


def help_guide() -> str:
    return (
        "❓ <b>دليل الاستخدام</b>\n"
        "————————————\n\n"
        "⚙️ <b>الإعدادات</b>\n"
        "• التحقق من العضوية (5 طرق فعلية)\n"
        "• حماية المحتوى، الإشعارات\n"
        "• الحذف التلقائي، تذكير غير النشطين\n\n"
        "📝 <b>المحتوى</b>\n"
        "• رسالة البدء، الردود التلقائية وأزرارها\n"
        "• الأزرار الشفافة، الاختصارات\n"
        "• تعديل نصوص البوت الجاهزة\n\n"
        "👥 <b>المستخدمين</b>\n"
        "• المسؤولون، الحظر، سجل النشاط\n\n"
        "🔐 <b>الاشتراك</b>\n"
        "• نظام الاشتراك الإجباري (حد 10)\n\n"
        "🚚 <b>التواصل</b>\n"
        "• الإذاعة، توجيه رسائل المستخدمين إليك مباشرة\n\n"
        "🌐 <b>النظام والدعم</b>\n"
        "• النسخ الاحتياطي"
    )


# ------------------------------------------------- verification (end users) --

def verify_challenge_intro() -> str:
    return "🛂 <b>تحقق سريع قبل ما تكمل</b>"


def verify_captcha_question(a: int, b: int) -> str:
    return f"🔐 كم ناتج {a} + {b}؟"


def verify_visit_prompt(url: str) -> str:
    return f"🌐 افتح الرابط أول، وبعدها اضغط تحقق:\n{url}"


def verify_link_prompt() -> str:
    return "🔗 أرسل كود الدخول اللي عندك، أو /cancel"


def verify_phone_prompt() -> str:
    return "📱 اضغط الزر تحت لمشاركة رقمك والتحقق"


def verify_manual_pending() -> str:
    return "⏳ طلبك وصل للأدمن، بانتظار الموافقة..."


def verify_manual_admin_request(chat_id: int, username: str) -> str:
    uname = f"@{username}" if username else "بدون يوزر"
    return f"✋ <b>طلب تحقق يدوي</b>\n👤 {uname}\n🆔 <code>{chat_id}</code>"


def verify_success() -> str:
    return "✅ تم التحقق! تفضل استخدم البوت."


def verify_failed() -> str:
    return "❌ إجابة غلط، جرب مرة ثانية أو اضغط /start"


def verify_rejected() -> str:
    return "❌ ما تمت الموافقة على طلبك."

# ------------------------------------------- command center phase 1 ----

def user_search_prompt() -> str:
    return "🔍 أرسل <b>ID</b> المستخدم أو <b>username</b> (بدون @)، أو /cancel"


def user_search_results(results: list) -> str:
    if not results:
        return "🔍 ما لقيت مستخدم بهذا المعرف."
    lines = ["🔍 <b>نتائج البحث:</b>"]
    for u in results:
        nm = f"@{u['username']}" if u.get("username") else (u.get("first_name") or "بدون اسم")
        blk = " ⛔ محظور" if u.get("is_blocked") else ""
        lines.append(f"• {nm} — <code>{u['chat_id']}</code>{blk}")
    lines.append("\nاضغط على المستخدم لعرض التفاصيل.")
    return "\n".join(lines)


def user_detail_card(u: dict) -> str:
    nm = f"@{u['username']}" if u.get("username") else (u.get("first_name") or "بدون اسم")
    blk = "⛔ محظور" if u.get("is_blocked") else "✅ نشط"
    lines = [
        f"👤 <b>{nm}</b>",
        f"🆔 <code>{u['chat_id']}</code>",
        f"الحالة: {blk}",
        f"📅 التسجيل: {u.get('first_seen') or '—'}",
        f"🕐 آخر نشاط: {u.get('last_active') or '—'}",
        f"💬 الرسائل: <b>{u.get('msg_count', 0)}</b>",
        f"🚩 بلاغات ضده: <b>{u.get('reports_against', 0)}</b>",
    ]
    note = u.get("admin_note")
    lines.append(f"📝 ملاحظة: {note}" if note else "📝 لا توجد ملاحظة إدارية")
    acts = u.get("admin_actions") or []
    if acts:
        lines.append("————————————\n🛡 <b>إجراءات المشرف:</b>")
        for desc, ts in acts[:5]:
            lines.append(f"• {(desc or '')[:50]}")
    return "\n".join(lines)


def user_note_prompt() -> str:
    return "📝 أرسل الملاحظة الإدارية (تُحفظ داخليًا ولا يراها المستخدم)، أو /cancel"


def active_conversations_menu(convos: list, hours: int) -> str:
    if not convos:
        return f"💬 <b>النشاط الحالي</b>\n\nلا يوجد نشاط رسائل خلال آخر {hours} ساعة.\n(يُعرض النشطون فقط — بدون محتوى الرسائل)"
    lines = [f"💬 <b>النشاط الحالي</b> (آخر {hours} ساعة)\n"]
    for c in convos:
        nm = f"@{c['username']}" if c.get("username") else (c.get("first_name") or str(c['chat_id']))
        lines.append(f"• {nm} — {c['msg_count']} رسالة")
    lines.append("\n(بدون عرض محتوى الرسائل — خصوصية)")
    return "\n".join(lines)


def reports_menu(counts: dict) -> str:
    return (
        "🚩 <b>البلاغات والحماية</b>\n"
        "————————————\n"
        f"🆕 جديدة: <b>{counts.get('new', 0)}</b>\n"
        f"👀 قيد المراجعة: <b>{counts.get('reviewing', 0)}</b>\n"
        f"✅ مغلقة: <b>{counts.get('closed', 0)}</b>"
    )


def report_detail(r: dict) -> str:
    status_ar = {"new": "🆕 جديد", "reviewing": "👀 قيد المراجعة", "closed": "✅ مغلق"}.get(r["status"], r["status"])
    dec_ar = {"ignored": "تجاهل", "warned": "تحذير", "blocked": "حظر", "escalated": "تصعيد"}.get(r.get("decision") or "", "—")
    return (
        f"🚩 <b>بلاغ #{r['id']}</b> — {status_ar}\n"
        "————————————\n"
        f"👤 المُبلِّغ: <code>{r['reporter_id']}</code>\n"
        f"🎯 المُبلَّغ عنه: <code>{r['target_id'] or '—'}</code>\n"
        f"📝 السبب: {r['reason'] or '—'}\n"
        f"📅 التاريخ: {r['created_at']}\n"
        f"⚖ القرار: {dec_ar}"
    )


def broadcast_test_sent() -> str:
    return "✅ أُرسلت نسخة تجريبية إلى حسابك. راجعها ثم أكّد الإرسال للجميع."


def broadcast_stats(status: dict) -> str:
    if not status:
        return "❌ ما لقيت بيانات الإذاعة."
    return (
        f"📣 <b>نتيجة الإذاعة</b>\n"
        "————————————\n"
        f"✅ ناجح: <b>{status.get('sent', 0)}</b>\n"
        f"❌ فاشل: <b>{status.get('failed', 0)}</b>\n"
        f"⛔ محظور/متعذر: <b>{status.get('blocked', 0)}</b>\n"
        f"📊 نسبة النجاح: {status.get('success_rate', 0):.1f}%"
    )

# ------------------------------------------------------- Phase 2 screens --

def backup_center(records, last_good, scope):
    lines = []
    lines.append("💾 <b>مركز النسخ الاحتياطي</b>")
    lines.append("————————————")
    if last_good:
        mb = (last_good.get("size_bytes") or 0) / 1024 / 1024
        lines.append("✅ آخر نسخة سليمة: <code>" + last_good["filename"] + "</code>")
        lines.append("🕐 " + str(last_good["created_at"]) + " — 📦 %.2f MB" % mb)
    else:
        lines.append("⚠️ لا توجد نسخة سليمة مسجلة بعد")
    lines.append("————————————")
    if records:
        lines.append("📋 <b>أحدث النسخ:</b>")
        for r in records[:5]:
            mark = "✅" if r["integrity_ok"] else "❌"
            mb = (r["size_bytes"] or 0) / 1024 / 1024
            lines.append(mark + " <code>" + r["filename"] + "</code> (%.1fMB)" % mb)
    else:
        lines.append("لا نسخ مسجلة بعد")
    lines.append("————————————")
    lines.append("📝 " + scope)
    return "\n".join(lines)


def backup_verify_result(filename, report):
    lines = []
    lines.append("🔍 <b>فحص النسخة</b>")
    lines.append("<code>" + filename + "</code>")
    lines.append("————————————")
    if report.get("ok"):
        lines.append("✅ النسخة سليمة وقابلة للاستعادة")
        lines.append("🔧 سلامة قاعدة البيانات: " + str(report.get("integrity")))
        tables = report.get("tables", {})
        total = sum(v for v in tables.values() if isinstance(v, int))
        lines.append("📊 %d جدول — %d صف إجمالًا" % (len(tables), total))
    else:
        lines.append("❌ النسخة غير صالحة للاستعادة")
        lines.append("السبب: " + str(report.get("error") or report.get("integrity")))
    return "\n".join(lines)


def backup_restore_confirm(bid):
    return (
        "⚠️ <b>تأكيد الاستعادة</b>\n"
        "————————————\n"
        "سيتم فحص النسخة أولًا في بيئة معزولة، "
        "ثم دمج صفوفها مع قاعدة البيانات "
        "الحالية (الصفوف الموجودة لن تُمس).\n\n"
        "هل أنت متأكد؟"
    )


def audit_log_menu(entries, page, per_page, total):
    from .audit import action_label
    lines = []
    lines.append("📜 <b>سجل التدقيق الإداري</b>")
    lines.append("————————————")
    if not entries:
        lines.append("لا إجراءات مسجلة بعد")
    for e in entries:
        mark = "✅" if e["success"] else "❌"
        tgt = " ← " + str(e["target"]) if e["target"] else ""
        lines.append(mark + " <b>" + action_label(e["action"]) + "</b>" + tgt)
        lines.append("   👤 <code>" + str(e["admin_id"]) + "</code> • " + str(e["created_at"]))
        if e.get("summary"):
            lines.append("   " + str(e["summary"])[:60])
    lines.append("————————————")
    pages = max(1, (total + per_page - 1) // per_page)
    lines.append("📄 صفحة %d من %d (الإجمالي %d)" % (page + 1, pages, total))
    return "\n".join(lines)


def admin_perms_menu(uid, current):
    lines = []
    lines.append("🔑 <b>صلاحيات المشرف</b> <code>" + str(uid) + "</code>")
    lines.append("————————————")
    lines.append("اضغط على صلاحية لتفعيلها/تعطيلها:")
    return "\n".join(lines)


def system_status(info):
    lines = []
    lines.append("🌐 <b>النظام والصيانة</b>")
    lines.append("————————————")
    lines.append("📡 الـpolling: <b>" + str(info.get("polling", "?")) + "</b>")
    lines.append("⏱ مدة التشغيل: " + str(info.get("uptime", "?")))
    integ = info.get("db_integrity")
    if integ == "ok":
        lines.append("🗄 سلامة قاعدة البيانات: ✅ سليمة")
    else:
        lines.append("🗄 سلامة قاعدة البيانات: ❌ " + str(integ))
    lines.append("💾 حجم قاعدة البيانات: " + str(info.get("db_size_mb", 0)) + "MB")
    lb = info.get("last_backup")
    if lb:
        lines.append("📦 آخر نسخة سليمة: <code>" + str(lb) + "</code>")
    else:
        lines.append("📦 آخر نسخة سليمة: لا يوجد")
    if info.get("maintenance"):
        lines.append("🔧 وضع الصيانة: 🟠 مفعل")
    else:
        lines.append("🔧 وضع الصيانة: 🟢 معطل")
    return "\n".join(lines)


def maintenance_menu(s):
    on = bool(s.get("maintenance_mode"))
    msg = s.get("maintenance_message") or "(الرسالة الافتراضية)"
    lines = []
    lines.append("🔧 <b>وضع الصيانة</b>")
    lines.append("————————————")
    if on:
        lines.append("الحالة: 🟠 مفعل — المستخدمون العاديون يرون رسالة الصيانة")
    else:
        lines.append("الحالة: 🟢 معطل — البوت يعمل طبيعيًا")
    lines.append("💬 الرسالة الحالية:")
    lines.append(str(msg))
    lines.append("————————————")
    lines.append("⚠️ لوحة الإدارة تبقى متاحة لك دائمًا أثناء الصيانة.")
    return "\n".join(lines)


def maintenance_msg_prompt():
    return "💬 أرسل نص رسالة الصيانة الجديدة (حد أقصى 1000 حرف)، أو /cancel للإلغاء"

def admins_menu2(admins):
    from . import permissions as pm
    lines = []
    lines.append("👤 <b>المسؤولون والصلاحيات</b>")
    if not admins:
        lines.append("ما فيه مسؤولين إضافيين — بس أنت (المالك).")
    for a in admins:
        if a["legacy"]:
            badge = "👑 كاملة"
        else:
            badge = pm.describe(a["permissions"])
        lines.append("• <code>%d</code> — %s" % (a["user_id"], badge))
    return "\n".join(lines)



# ================= Phase 3: analytics / health / alerts =================

def analytics_menu(a: dict) -> str:
    L = []
    L.append("📊 <b>التحليلات</b>")
    L.append("————————————")
    L.append(f"👥 إجمالي المستخدمين: <b>{a['total_users']}</b>")
    n = a["new"]
    L.append(f"🆕 جدد اليوم: <b>{n['today']}</b> | 7 أيام: <b>{n['d7']}</b> | 30 يومًا: <b>{n['d30']}</b>")
    L.append(f"💬 نشطون (24h): <b>{a['active_24h']}</b> | (7d): <b>{a['active_7d']}</b>")
    L.append("<i>النشاط = آخر ظهور للمستخدم ضمن الفترة</i>")
    L.append("————————————")
    g = a.get("growth_pct")
    if g is None:
        L.append("📈 الاكتساب (7d مقابل السابقة): <b>لا أساس للمقارنة بعد</b>")
    else:
        arrow = "🔼" if g > 0 else ("🔽" if g < 0 else "➖")
        L.append(f"📈 الاكتساب: {arrow} <b>{g:+.1f}%</b> (الحالية {n['d7']} مقابل السابقة {a['prev7']})")
    L.append("————————————")
    ph = a.get("peak_hours")
    if ph:
        parts = "، ".join(f"{h:02d}:00 ({c})" for h, c in ph)
        L.append(f"⏰ أكثر الأوقات نشاطًا: {parts}")
    else:
        L.append("⏰ أكثر الأوقات نشاطًا: البيانات غير متاحة (تحتاج 20 رسالة على الأقل)")
    L.append("————————————")
    if a.get("reports_open") is None:
        L.append("🚩 البلاغات: البيانات غير متاحة")
    else:
        avg = a.get("reports_avg_hours")
        avg_s = f"{avg}h" if avg is not None else "لا يوجد محلول بعد"
        L.append(f"🚩 البلاغات: مفتوحة <b>{a['reports_open']}</b> | مغلقة <b>{a['reports_closed']}</b> | متوسط المعالجة: {avg_s}")
    L.append("————————————")
    bl = a.get("bc_last")
    if bl is None:
        L.append("📢 الإذاعات: لا يوجد بعد")
    else:
        st = bl["stats"] or {}
        if bl["status"] == "completed":
            L.append(f"📢 آخر إذاعة: ناجح {st.get('sent', '?')} | فاشل {st.get('failed', '?')} "
                     f"(دائم {st.get('failed_perm', '?')}) | محظورون {st.get('blocked', '?')}")
        else:
            L.append(f"📢 آخر إذاعة: الحالة {bl['status']}")
    L.append(f"⚠️ أخطاء (24h): <b>{a['errors_24h']}</b> | 💾 نسخ: <b>{a['backups_total']}</b>")
    L.append("————————————")
    L.append("<i>كل الأرقام من استعلامات فعلية بتوقيت بغداد</i>")
    return "\n".join(L)


def analytics_export_text(a: dict, bot_username: str) -> str:
    """Short text report - no heavy dependencies."""
    n = a["new"]
    lines = [
        f"تقرير تحليلات @{bot_username}",
        f"المستخدمون: {a['total_users']} (جدد اليوم {n['today']} / 7d {n['d7']} / 30d {n['d30']})",
        f"نشطون: 24h={a['active_24h']} 7d={a['active_7d']}",
        f"الرسائل: {a['msg_total']} | أخطاء 24h: {a['errors_24h']}",
    ]
    g = a.get("growth_pct")
    lines.append(f"نمو الاكتساب: {'لا أساس' if g is None else f'{g:+.1f}%'}")
    if a.get("reports_open") is not None:
        lines.append(f"بلاغات مفتوحة: {a['reports_open']} مغلقة: {a['reports_closed']}")
    if a.get("bc_last"):
        st = a["bc_last"]["stats"] or {}
        lines.append(f"آخر إذاعة: {a['bc_last']['status']} (ناجح {st.get('sent', '?')})")
    return "\n".join(lines)


def health_center(info: dict) -> str:
    from admin_panel.health import HEALTH_LABEL
    L = []
    L.append("🏥 <b>مركز صحة النظام</b>")
    L.append("————————————")
    L.append(f"الحالة العامة: <b>{HEALTH_LABEL.get(info.get('health'), '؟')}</b>")
    L.append(f"📡 الـpolling: <b>{info.get('polling', '?')}</b>")
    lp = info.get("last_poll_ago")
    L.append(f"🕐 آخر تحديث ناجح: {lp if lp else 'غير معروف'}")
    L.append(f"⏱ مدة التشغيل: {info.get('uptime', '?')}")
    L.append("————————————")
    integ = info.get("db_integrity")
    L.append("🗄 سلامة DB: " + ("✅ سليمة" if integ == "ok" else f"❌ {integ}"))
    L.append(f"💾 حجم DB: {info.get('db_size_mb', '?')}MB")
    lb = info.get("last_backup")
    L.append(f"📦 آخر نسخة: {lb if lb else 'لا يوجد'}")
    L.append("————————————")
    al = info.get("open_alerts", {})
    L.append(f"🚨 تنبيهات مفتوحة: 🔴 {al.get('critical', 0)} 🟡 {al.get('warning', 0)} 🔵 {al.get('info', 0)}")
    L.append(f"⏳ مهام عالقة: <b>{info.get('stuck_jobs', 0)}</b>")
    L.append(f"📢 إذاعات قيد التنفيذ: <b>{info.get('running_broadcasts', 0)}</b>")
    L.append("————————————")
    le = info.get("last_error")
    if le:
        L.append(f"⚠️ آخر خطأ: {(le[0] or '')[:60]}")
        L.append(f"   وقتها: {le[1][:16] if le[1] else '?'}")
    else:
        L.append("✅ لا أخطاء حديثة")
    m = info.get("maintenance")
    L.append(f"🔧 الصيانة: {'🟠 مفعلة' if m else '🟢 معطلة'}")
    return "\n".join(L)


def alerts_menu(alerts: list) -> str:
    L = ["🚨 <b>الإنذارات</b>", "————————————"]
    if not alerts:
        L.append("✅ لا توجد إنذارات مفتوحة")
        return "\n".join(L)
    sev_icon = {"critical": "🔴", "warning": "🟡", "info": "🔵"}
    st_icon = {"new": "🆕", "ack": "👁"}
    for al in alerts[:10]:
        L.append(f"{sev_icon.get(al['severity'], '⚪')} {st_icon.get(al['status'], '')} "
                 f"<b>{al['title'][:50]}</b>")
        L.append(f"   رصد: {(al['detected_at'] or '')[:16]}")
    L.append("————————————")
    L.append("<i>اضغط على إنذار للإقرار أو الحل</i>")
    return "\n".join(L)


def alert_detail(al: dict) -> str:
    sev_icon = {"critical": "🔴", "warning": "🟡", "info": "🔵"}
    L = [f"{sev_icon.get(al['severity'], '⚪')} <b>{al['title']}</b>", "————————————"]
    if al.get("detail"):
        L.append(al["detail"][:300])
        L.append("————————————")
    L.append(f"النوع: {al['alert_type']}")
    L.append(f"الرصد: {(al['detected_at'] or '')[:16]} | آخر ظهور: {(al['last_seen'] or '')[:16]}")
    L.append(f"الحالة: {al['status']}")
    if al.get("ack_by"):
        L.append(f"أقرّها: {al['ack_by']}")
    return "\n".join(L)


def broadcast_history_menu(history: list) -> str:
    L = ["📢 <b>سجل الإذاعات</b>", "————————————"]
    if not history:
        L.append("لا توجد إذاعات بعد")
        return "\n".join(L)
    import json
    st_icon = {"completed": "✅", "processing": "⏳", "failed": "❌", "cancelled": "⏹️", "pending": "🕐"}
    for h in history[:8]:
        try:
            st = json.loads(h["data"]) if h.get("data") else {}
        except Exception:
            st = {}
        # completed broadcasts store flat stats; running ones nest under progress
        s = st.get("progress", st) if isinstance(st, dict) else {}
        sent = s.get("sent", "?")
        failed = s.get("failed", "?")
        L.append(f"{st_icon.get(h['status'], '❓')} #{h['job_id']} — {h['status']}: "
                 f"ناجح {sent} / فاشل {failed}")
        L.append(f"   {(h['created_at'] or '')[:16]}")
    L.append("————————————")
    L.append("<i>الإحصاءات التفصيلية تُحفظ عند اكتمال كل إذاعة</i>")
    return "\n".join(L)
