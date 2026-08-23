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

WELCOME_TEXT = (
    "بوت صنع سايت الافضل <b>طاها</b>\n\n"
    "• يمكنك صنع بوتك الان مدفوع ، مجانا .\n"
    "• قم بصنع بوتك الان بالعديد من المميزات ."
)

NEW_BOT_PROMPT = (
    "🎯 <b>سايت</b>\n\n"
    "🔑 ارسل التوكن الخاص بك الان.\n\n"
    "👇 لا تملك توكن؟ اضغط الزر للشرح خطوة بخطوة."
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

PAID_VERSION = "⭐ <b>النسخة المدفوعة</b>\n\n🚧 قيد التطوير حالياً."


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
        [_btn("🗑 حذف البوت", f"fac:list:del:{bot_id}")],
        [_btn("◀ رجوع", "fac:list")],
    ])
    return text, kb


# --------------------------------------------------------------- entry ----

async def handle_message(chat_id: int, user_id: int, text: str):
    from admin_panel.flows import handle_text as admin_flow_handle_text
    from config import FACTORY_BOT_ID
    from factory_admin.auth import is_factory_admin
    
    # Factory admin panel takes over entirely for factory admins
    if await is_factory_admin(user_id):
        import factory_admin.flows as fa_flows
        import factory_admin.router as fa_router
        if text.strip() == "/start":
            await db.clear_conversation_state(chat_id)
            await fa_router.send_screen(chat_id, "main")
            return
        if await fa_flows.handle_text(chat_id, text, user_id):
            return
    
    # Factory-wide block check (regular users only)
    block = await db.get_factory_block(user_id)
    if block and block.get("block_factory_use"):
        return
    
    convo = await db.get_conversation_state(chat_id)
    if convo and convo["bot_id"] == FACTORY_BOT_ID and convo["state"] == "fac_new_token":
        if text.strip() == "/cancel":
            await db.clear_conversation_state(chat_id)
            await _send(chat_id, "❌ تم الإلغاء", main_menu_kb())
            return
        await _process_token_submission(chat_id, user_id, text.strip())
        return
    
    is_new = await db.add_factory_user(chat_id, "", "")
    
    if text.strip() == "/start":
        await db.clear_conversation_state(chat_id)
        # Factory-wide mandatory subscription applies here too
        from subscription_handler import subscription_handler
        if not await subscription_handler.check_subscription(FACTORY_BOT_ID, chat_id, user_id=user_id):
            return
        await _send(chat_id, WELCOME_TEXT, main_menu_kb())
        return
    
    await _send(chat_id, WELCOME_TEXT, main_menu_kb())


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
        await _edit(chat_id, message_id, WELCOME_TEXT, main_menu_kb())
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
    
    if rest == "paid":
        await _edit(chat_id, message_id, PAID_VERSION, back_kb("fac:main"))
        return
