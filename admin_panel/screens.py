"""Text content for each admin panel screen. Functions take whatever
live data they need (stats dict, settings dict, lists...) and return the
HTML-formatted message text - matching the wording seen in the reference
screenshots as closely as possible."""


def main_menu(stats: dict) -> str:
    return (
        "🎛 <b>لوحة التحكم</b>\n"
        "————————————\n"
        "📊 <b>إحصائيات اليوم</b>\n"
        f"👥 الإجمالي: {stats['total_users']}\n"
        f"🆕 مستخدمون جدد: {stats['new_users']}\n"
        f"💬 الرسائل: {stats['messages']}\n"
        f"🔁 الجلسات: {stats['sessions']}\n"
        f"⚡ متوسط الاستجابة: {stats['avg_response_ms']}ms\n"
        f"🕐 آخر نشاط: {stats['last_activity']}"
    )


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
