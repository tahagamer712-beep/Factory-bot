"""
The master "factory" bot - matches the reference screenshots exactly:
a user DMs this bot, presses "صنع بوت جديد", sends a token, and gets a
brand-new bot registered and polling live, with the full admin_panel
control panel already wired up for it.

Kept entirely separate from admin_panel/ (which runs *inside* each
created bot) and from message_handler.py (which runs for that created
bot's regular end-users). This module only ever runs for updates arriving
on config.FACTORY_BOT_ID.
"""

from db import db
from bot_registry import bot_registry
from telegram_adapter import telegram_pool, TelegramAdapter
from message_sender import message_sender

def welcome_text(first_name=""):
    name_part = f"أهلًا <b>{first_name}</b> 👋\n\n" if first_name and first_name != "None" else ""
    return (
        f"{name_part}"
        "🏭 <b>مصنع سايت للبوتات</b>\n"
        "✨ بإشراف <b>طه</b>\n"
        "\n"
        "━━━━━━━━━━━━━━━━\n"
        "🤖 اصنع بوت تيليجرام خاص بك في دقيقة\n"
        "🎁 البداية مجانية\n"
        "💡 بدون أي خبرة برمجية\n"
        "━━━━━━━━━━━━━━━━\n"
        "\n"
        "👇 اختر من القائمة بالأسفل:"
)

# Keep backward-compat constant for any other callers
WELCOME_TEXT = welcome_text()

NEW_BOT_PROMPT = (
    "🎯 <b>إنشاء بوت جديد</b>\n\n"
    "⚡ <b>الطريقة السريعة:</b> اضغط «فتح BotFather» بالأسفل، أنشئ بوتك بأمر /newbot، ثم انسخ التوكن والصقه هنا.\n\n"
    "🔑 أو أرسل التوكن مباشرة إذا كان جاهزًا لديك.\n\n"
    "👇 لا تملك توكن؟ اضغط «كيف احصل على توكن؟» للشرح خطوة بخطوة."
)

HOW_TO_GET_TOKEN = (
    "🔑 <b>كيف تحصل على توكن؟</b>\n\n"
    "1. افتح محادثة مع @BotFather بتيليجرام\n"
    "2. أرسل الأمر /newbot\n"
    "3. اختر اسم للبوت (يظهر بالمحادثات)\n"
    "4. اختر يوزر ينتهي بـ bot (مثال: MyCoolBot)\n"
    "5. راح يرسلك BotFather التوكن مباشرة - انسخه وارسله هنا"
)

WHAT_IS_TOKEN = (
    "❓ <b>ما هو التوكن؟</b>\n\n"
    "التوكن هو مفتاح سري يعطيك ياه @BotFather عند إنشاء بوت جديد. "
    "شكله يشبه:\n<code>123456789:ABCDefGhIJKlmNoPQRsTUVwxyZ</code>\n\n"
    "هذا التوكن هو اللي يخلي بوتك يشتغل - خله سري وما تشاركه مع حد."
)

HOW_TO_MAKE_BOT = (
    "❓ <b>كيف اصنع بوت خاص بي؟</b>\n\n"
    "الامر بسيط جداً ولا يحتاج اي خبرة:\n\n"
    "1️⃣ <b>اختر نوع البوت</b>\n"
    "اضغط صنع بوت جديد واختر ما يناسبك\n\n"
    "2️⃣ <b>اربط بوتك</b>\n"
    "احصل على توكن مجاني من @BotFather وارسله هنا (سنرشدك خطوة بخطوة)\n\n"
    "3️⃣ <b>بوتك جاهز!</b>\n"
    "يعمل فوراً، ويمكنك تعديل اسمه وصورته وأوامره من لوحة تحكمه الخاصة "
    "(افتح بوتك الجديد واكتب /start فيه)"
)

PAID_VERSION = (
    "⭐ <b>النسخة المدفوعة</b>\n\n"
    "━━━━━━━━━━━━━━━━\n"
    "💡 حاليًا جميع مزايا المصنع <b>مجانية بالكامل</b> — صنع البوتات وإدارتها بلا أي رسوم.\n\n"
    "🔔 عند إطلاق باقات مدفوعة مستقبلًا سنعلن عنها هنا أولًا.\n"
    "━━━━━━━━━━━━━━━━"
)

FACTORY_HELP_TEXT = (
    "📖 <b>مساعدة المصنع</b>\n\n"
    "المصنع يساعدك على إنشاء وإدارة بوتات تيليجرام بسهولة.\n"
    "استخدم «صنع بوت جديد» وأرسل توكن البوت من @BotFather، "
    "وسيبدأ بوتك بالعمل مباشرة.\n\n"
    "للبداية أرسل /start."
)


def _kb(rows):
    return {"inline_keyboard": rows}


def _btn(text, data=None, url=None):
    b = {"text": text}
    if url:
        b["url"] = url
    else:
        b["callback_data"] = data
    return b


def main_menu_kb():
    return _kb([
        [_btn("🤖 صنع بوت جديد", "fac:new")],
        [_btn("📋 قائمه بوتاتك", "fac:list")],
        [_btn("❓ كيف اصنع بوت؟", "fac:help")],
        [_btn("⭐ النسخة المدفوعة", "fac:paid")],
    ])


def new_bot_kb():
    return _kb([
        [_btn("⚡ فتح BotFather لإنشاء بوت", url="https://t.me/BotFather")],
        [_btn("🔑 كيف احصل على توكن؟", "fac:new:howtoken")],
        [_btn("❓ ما هو التوكن؟", "fac:new:whattoken")],
        [_btn("• رجوع •", "fac:main")],
    ])


def back_kb(target="fac:main", label="رجوع"):
    return _kb([[_btn(label, target)]])


async def _send(chat_id, text, reply_markup=None):
    from config import FACTORY_BOT_ID
    return await message_sender.send_message(FACTORY_BOT_ID, chat_id, text, reply_markup=reply_markup)


async def _edit(chat_id, message_id, text, reply_markup=None):
    from config import FACTORY_BOT_ID
    return await message_sender.edit_message(FACTORY_BOT_ID, chat_id, message_id, text, reply_markup=reply_markup)


# ------------------------------------------------------------- screens ----

async def _bots_list_text_kb(owner_id: int):
    cursor = await db.connection.execute(
        "SELECT bot_id, username FROM bots WHERE owner_id = ?", (owner_id,)
    )
    rows = await cursor.fetchall()
    
    if not rows:
        return "📋 <b>قائمه بوتاتك المصنوعه (0):</b>\n\nما صنعت أي بوت لسا.", \
            _kb([[_btn("🤖 صنع بوت جديد", "fac:new")], [_btn("• رجوع •", "fac:main")]])
    
    text = f"📋 <b>قائمه بوتاتك المصنوعه ({len(rows)}):</b>"
    kb_rows = []
    for bot_id, username in rows:
        uname = username or str(bot_id)
        kb_rows.append([
            _btn(f"{uname} ↗", url=f"https://t.me/{uname}"),
            _btn("معلومات اكثر", f"fac:list:item:{bot_id}"),
        ])
    kb_rows.append([_btn("• رجوع •", "fac:main")])
    return text, _kb(kb_rows)


async def _bot_info_text_kb(bot_id: int, owner_id: int):
    cursor = await db.connection.execute(
        "SELECT username, created_at FROM bots WHERE bot_id = ? AND owner_id = ?", (bot_id, owner_id)
    )
    row = await cursor.fetchone()
    if not row:
        return "❌ ما لقيت هذا البوت.", back_kb("fac:list")
    
    username, created_at = row
    cursor = await db.connection.execute(
        "SELECT COUNT(*) FROM bot_users WHERE bot_id = ?", (bot_id,)
    )
    user_count = (await cursor.fetchone())[0]
    
    text = (
        f"🤖 <b>@{username}</b>\n\n"
        f"📅 تاريخ الإنشاء: {created_at}\n"
        f"👥 عدد المستخدمين: {user_count}\n\n"
        f"افتح البوت واكتب /start فيه للوصول للوحة تحكمه الكاملة."
    )
    kb = _kb([
        [_btn(f"فتح @{username} ↗", url=f"https://t.me/{username}")],
        [_btn("✏️ إدارة البوت", f"fac:manage:{bot_id}")],
        [_btn("🗑 حذف البوت", f"fac:list:del:{bot_id}")],
        [_btn("◀ رجوع", "fac:list")],
    ])
    return text, kb


# ------------------------------------------------------- manage bot ----

EDIT_FIELDS = {
    "name": ("📛 الاسم", 64, "set_managed_bot_name",
              "📛 <b>تعديل اسم البوت</b>\n\nأرسل الاسم الجديد (حد أقصى 64 حرفًا).\nأرسل /cancel للإلغاء."),
    "bio": ("ℹ️ البايو", 120, "set_managed_bot_short_description",
            "ℹ️ <b>تعديل البايو</b>\n\nأرسل البايو الجديد (حد أقصى 120 حرفًا) — يظهر قبل بدء المحادثة.\nأرسل /cancel للإلغاء."),
    "desc": ("📝 الوصف", 512, "set_managed_bot_description",
             "📝 <b>تعديل الوصف</b>\n\nأرسل الوصف الجديد (حد أقصى 512 حرفًا) — يظهر في صفحة البوت.\nأرسل /cancel للإلغاء."),
    "commands": ("⚙️ الأوامر", 0, None,
                 "⚙️ <b>تعديل الأوامر</b>\n\nأرسل القائمة الجديدة — كل أمر بسطر بهذا الشكل:\n"
                 "<code>start - بدء البوت</code>\n<code>help - المساعدة</code>\n\nأرسل /cancel للإلغاء."),
    "photo": ("🖼 الصورة", 0, None,
              "🖼 <b>تعديل صورة البوت</b>\n\nأرسل الصورة الجديدة كصورة (ليست ملفًا).\nأرسل /cancel للإلغاء."),
}


async def _check_bot_owner(bot_id: int, user_id: int):
    """Return (username, token) if user owns the bot, else (None, None)."""
    cursor = await db.connection.execute(
        "SELECT username, token FROM bots WHERE bot_id = ? AND owner_id = ?",
        (bot_id, user_id),
    )
    row = await cursor.fetchone()
    if not row:
        return None, None
    return row[0], row[1]


async def _manage_text_kb(bot_id: int, user_id: int):
    username, _ = await _check_bot_owner(bot_id, user_id)
    if not username:
        return "❌ ما لقيت هذا البوت.", back_kb(f"fac:list")
    text = (
        f"✏️ <b>إدارة @{username}</b>\n\n"
        "👇 اختر ما تريد تعديله:"
    )
    kb = _kb([
        [_btn("📛 الاسم", f"fac:edit:name:{bot_id}"), _btn("ℹ️ البايو", f"fac:edit:bio:{bot_id}")],
        [_btn("📝 الوصف", f"fac:edit:desc:{bot_id}"), _btn("🖼 الصورة", f"fac:edit:photo:{bot_id}")],
        [_btn("⚙️ الأوامر", f"fac:edit:commands:{bot_id}")],
        [_btn("◀ رجوع", f"fac:list:item:{bot_id}")],
    ])
    return text, kb


async def _apply_text_edit(chat_id: int, user_id: int, bot_id: int, field: str, value: str):
    """Apply a text edit via Bot API. Returns (ok, message)."""
    from config import FACTORY_BOT_ID
    username, token = await _check_bot_owner(bot_id, user_id)
    if not token:
        return False, "❌ ما لقيت هذا البوت أو ما تملكه."
    label, limit, method, _ = EDIT_FIELDS[field]
    if limit and len(value) > limit:
        return False, f"⚠️ النص أطول من الحد ({limit} حرف). اختصره وحاول مجددًا."
    if not value.strip():
        return False, "⚠️ النص فارغ. أرسل نصًا صحيحًا أو /cancel للإلغاء."

    bot = bot_registry.get_bot(FACTORY_BOT_ID)
    adapter = await telegram_pool.get_adapter(bot["token"]) if bot else TelegramAdapter(token)

    if field == "commands":
        cmds = []
        for line in value.strip().split("\n"):
            line = line.strip().lstrip("/").strip()
            if not line or "-" not in line:
                continue
            cmd, _, desc = line.partition("-")
            cmd, desc = cmd.strip(), desc.strip()
            if cmd and desc and len(cmd) <= 32:
                cmds.append({"command": cmd, "description": desc[:256]})
        if not cmds:
            return False, "⚠️ ما لقيت أوامر صحيحة. الصيغة: <code>start - بدء البوت</code> بسطر لكل أمر."
        result = await adapter.bot_api_call(token, "setMyCommands", {"commands": cmds})
    else:
        api = getattr(adapter, method)
        result = await api(token, value.strip())

    if result.get("ok"):
        await db.add_log("info", "factory", f"Bot edit @{username} #{bot_id}: {field} by {user_id}")
        return True, f"✅ تم تعديل {label} لبوت @{username} بنجاح."
    desc = result.get("description", result.get("error", "خطأ غير معروف"))
    return False, f"❌ فشل التعديل: {desc}\nحاول مجددًا أو أرسل /cancel."


async def _apply_photo_edit(chat_id: int, user_id: int, bot_id: int, photo_file_id: str):
    from config import FACTORY_BOT_ID
    username, token = await _check_bot_owner(bot_id, user_id)
    if not token:
        return False, "❌ ما لقيت هذا البوت أو ما تملكه."
    bot = bot_registry.get_bot(FACTORY_BOT_ID)
    adapter = await telegram_pool.get_adapter(bot["token"]) if bot else TelegramAdapter(token)
    photo_bytes = await adapter.download_managed_file(token, photo_file_id)
    if not photo_bytes:
        return False, "❌ تعذر تحميل الصورة. حاول إرسالها مجددًا."
    if len(photo_bytes) > 5 * 1024 * 1024:
        return False, "⚠️ الصورة كبيرة (الحد 5MB)."
    result = await adapter.set_managed_bot_photo(token, photo_bytes)
    if result.get("ok"):
        await db.add_log("info", "factory", f"Bot edit @{username} #{bot_id}: photo by {user_id}")
        return True, f"✅ تم تعديل صورة بوت @{username} بنجاح."
    desc = result.get("description", result.get("error", "خطأ غير معروف"))
    return False, f"❌ فشل تعديل الصورة: {desc}"


# --------------------------------------------------------------- entry ----
async def handle_message(chat_id: int, user_id: int, text: str, first_name: str = "", photo_file_id: str = None):
    from admin_panel.flows import handle_text as admin_flow_handle_text
    from config import FACTORY_BOT_ID
    from factory_admin.auth import is_factory_admin
    
    # Factory admin panel takes over entirely for factory admins
    if await is_factory_admin(user_id):
        import factory_admin.flows as fa_flows
        import factory_admin.router as fa_router
        if text.strip() == "/start":
            await db.clear_conversation_state(chat_id)
            await _send(chat_id, welcome_text(first_name), main_menu_kb())
            await fa_router.send_screen(chat_id, "main")
            return
        if text.strip() == "/admin":
            await db.clear_conversation_state(chat_id)
            await fa_router.send_screen(chat_id, "main")
            return
        if text.strip() == "/help":
            await _send(chat_id, FACTORY_HELP_TEXT)
            return
        if await fa_flows.handle_text(chat_id, text, user_id):
            return
    
    # Factory-wide block check (regular users only)
    block = await db.get_factory_block(user_id)
    if block and block.get("block_factory_use"):
        return

    # /admin is reserved for factory admins and must not reveal anything to
    # regular users.
    if text.strip() == "/admin":
        return
    
    convo = await db.get_conversation_state(chat_id)
    if convo and convo["bot_id"] == FACTORY_BOT_ID and convo["state"] == "fac_new_token":
        if text.strip() == "/cancel":
            await db.clear_conversation_state(chat_id)
            await _send(chat_id, "❌ تم الإلغاء", main_menu_kb())
            return
        await _process_token_submission(chat_id, user_id, text.strip())
        return

    # --- Bot edit states (fac_edit:<field>:<bot_id>) ---
    if convo and convo["bot_id"] == FACTORY_BOT_ID and convo["state"].startswith("fac_edit:"):
        parts = convo["state"].split(":")
        field, bot_id = parts[1], int(parts[2])
        if text.strip() == "/cancel":
            await db.clear_conversation_state(chat_id)
            await _send(chat_id, "❌ تم الإلغاء دون حفظ.", main_menu_kb())
            return
        if field == "photo":
            if photo_file_id:
                ok, msg = await _apply_photo_edit(chat_id, user_id, bot_id, photo_file_id)
            else:
                await _send(chat_id, "⚠️ أرسل الصورة كصورة (ليست ملفًا)، أو /cancel للإلغاء.")
                return
        else:
            ok, msg = await _apply_text_edit(chat_id, user_id, bot_id, field, text)
            if not ok and msg.startswith("⚠️"):
                await _send(chat_id, msg)  # validation error -> let user retry
                return
        await db.clear_conversation_state(chat_id)
        text2, kb2 = await _manage_text_kb(bot_id, user_id)
        await _send(chat_id, msg, kb2)
        return

    is_new = await db.add_factory_user(chat_id, "", "")
    
    if text.strip() == "/start":
        await db.clear_conversation_state(chat_id)
        # Factory-wide mandatory subscription applies here too
        from subscription_handler import subscription_handler
        if not await subscription_handler.check_subscription(FACTORY_BOT_ID, chat_id, user_id=user_id):
            return
        await _send(chat_id, welcome_text(first_name), main_menu_kb())
        return

    if text.strip() == "/help":
        await _send(chat_id, FACTORY_HELP_TEXT)
        return
    
    await _send(chat_id, welcome_text(first_name), main_menu_kb())


async def _process_token_submission(chat_id: int, user_id: int, token: str):
    from config import FACTORY_BOT_ID
    
    block = await db.get_factory_block(user_id)
    if block and block.get("block_bot_creation"):
        await _send(chat_id, "⛔ ممنوع من إنشاء بوتات جديدة.")
        return
    
    max_bots = await db.get_setting(FACTORY_BOT_ID, "max_bots_per_user", 0)
    if max_bots and max_bots > 0:
        cursor = await db.connection.execute("SELECT COUNT(*) FROM bots WHERE owner_id = ?", (user_id,))
        current_count = (await cursor.fetchone())[0]
        if current_count >= max_bots:
            await _send(chat_id, f"⚠️ وصلت الحد الأقصى المسموح ({max_bots} بوت). احذف بوت قديم قبل ما تسوي جديد.")
            return
    
    if ":" not in token or not token.split(":")[0].isdigit():
        await _send(chat_id, "⚠️ هذا مو شكل توكن صحيح. جرب مرة ثانية أو أرسل /cancel للإلغاء")
        return
    
    new_bot_id = int(token.split(":")[0])
    
    existing = bot_registry.get_bot(new_bot_id)
    if existing:
        await db.clear_conversation_state(chat_id)
        await _send(chat_id, "⚠️ هذا التوكن مسجل مسبقاً بالمصنع.", main_menu_kb())
        return
    
    # Validate the token actually works before registering anything
    temp_adapter = TelegramAdapter(token, timeout=10)
    await temp_adapter.init()
    result = await temp_adapter.get_me()
    await temp_adapter.close()
    
    if not result.get("ok"):
        await _send(
            chat_id,
            f"❌ التوكن مو صحيح أو منتهي: {result.get('description', result.get('error', 'خطأ غير معروف'))}\n"
            "جرب توكن ثاني أو أرسل /cancel للإلغاء"
        )
        return
    
    bot_username = result["result"].get("username", str(new_bot_id))
    
    ok = await bot_registry.register_bot(new_bot_id, token, owner_id=user_id, username=bot_username)
    await db.clear_conversation_state(chat_id)
    
    if not ok:
        await _send(chat_id, "❌ صار خطأ بالتسجيل، جرب مرة ثانية.", main_menu_kb())
        return
    
    # Go live immediately - no restart needed
    from poller import poller_supervisor
    await poller_supervisor.add_and_start_poller(new_bot_id, token)
    from command_menu import sync_created_bot_commands
    await sync_created_bot_commands(new_bot_id)
    await db.add_log("info", "factory", f"New bot registered: @{bot_username} (#{new_bot_id}) by owner {user_id}")
    
    await _send(
        chat_id,
        f"✅ تم! بوتك @{bot_username} جاهز وشغال 🎉\n\n"
        f"افتحه من هنا واكتب /start فيه عشان توصل للوحة التحكم الكاملة:",
        _kb([
            [_btn(f"فتح @{bot_username} ↗", url=f"https://t.me/{bot_username}")],
            [_btn("• رجوع للقائمة الرئيسية •", "fac:main")],
        ])
    )


async def handle_callback(chat_id: int, message_id: int, user_id: int, callback_id: str, data: str):
    if data.startswith("fadm:"):
        from factory_admin import router as fa_router
        await fa_router.handle_callback(chat_id, message_id, user_id, callback_id, data)
        return
    
    from config import FACTORY_BOT_ID
    bot = bot_registry.get_bot(FACTORY_BOT_ID)
    if bot:
        adapter = await telegram_pool.get_adapter(bot["token"])
        await adapter.answer_callback_query(callback_id)
    
    if not data.startswith("fac:"):
        return
    rest = data[len("fac:"):]
    
    if rest == "main":
        await db.clear_conversation_state(chat_id)
        await _edit(chat_id, message_id, welcome_text(), main_menu_kb())
        return
    
    if rest == "new":
        await db.set_conversation_state(chat_id, FACTORY_BOT_ID, "fac_new_token", {})
        await _edit(chat_id, message_id, NEW_BOT_PROMPT, new_bot_kb())
        return
    
    if rest == "new:howtoken":
        await _edit(chat_id, message_id, HOW_TO_GET_TOKEN, back_kb("fac:new"))
        return
    
    if rest == "new:whattoken":
        await _edit(chat_id, message_id, WHAT_IS_TOKEN, back_kb("fac:new"))
        return
    
    if rest == "list":
        text, kb = await _bots_list_text_kb(user_id)
        await _edit(chat_id, message_id, text, kb)
        return
    
    if rest.startswith("list:item:"):
        bot_id = int(rest.split(":")[-1])
        text, kb = await _bot_info_text_kb(bot_id, user_id)
        await _edit(chat_id, message_id, text, kb)
        return
    
    if rest.startswith("list:del:"):
        bot_id = int(rest.split(":")[-1])
        cursor = await db.connection.execute(
            "SELECT 1 FROM bots WHERE bot_id = ? AND owner_id = ?", (bot_id, user_id)
        )
        if await cursor.fetchone():
            from poller import poller_supervisor
            await poller_supervisor.remove_poller(bot_id)
            await bot_registry.unregister_bot(bot_id)
        text, kb = await _bots_list_text_kb(user_id)
        await _edit(chat_id, message_id, text, kb)
        return
    
    if rest == "help":
        await _edit(chat_id, message_id, HOW_TO_MAKE_BOT,
                    _kb([[_btn("🤖 صنع بوت جديد", "fac:new")], [_btn("• رجوع •", "fac:main")]]))
        return
    
    if rest.startswith("manage:"):
        bot_id = int(rest.split(":")[-1])
        text, kb = await _manage_text_kb(bot_id, user_id)
        await _edit(chat_id, message_id, text, kb)
        return

    if rest.startswith("edit:"):
        parts = rest.split(":")
        field, bot_id = parts[1], int(parts[2])
        username, _ = await _check_bot_owner(bot_id, user_id)
        if not username:
            await _edit(chat_id, message_id, "❌ ما لقيت هذا البوت.", back_kb("fac:list"))
            return
        if field not in EDIT_FIELDS:
            return
        label, _, _, prompt = EDIT_FIELDS[field]
        await db.set_conversation_state(chat_id, FACTORY_BOT_ID, f"fac_edit:{field}:{bot_id}", {})
        await _edit(chat_id, message_id, prompt,
                    _kb([[_btn("❌ إلغاء", f"fac:manage:{bot_id}")]]))
        return

    if rest == "paid":
        await _edit(chat_id, message_id, PAID_VERSION, back_kb("fac:main"))
        return
