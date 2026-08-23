from db import db
from typing import Dict, Any
from message_handler import message_handler
from subscription_handler import subscription_handler

class Dispatcher:
    """
    Route updates to appropriate handlers
    
    Handles:
    - Messages (with verification, subscriptions, forwarding, auto-replies, commands)
    - Callbacks
    - Chat member changes (blocking)
    """
    
    async def dispatch(self, bot_id: int, update: Dict[str, Any]):
        if not isinstance(update, dict):
            print(f"⚠️ Bot #{bot_id}: dropped malformed update (not a dict)")
            return
        
        if "message" in update and isinstance(update["message"], dict):
            await self._handle_message(bot_id, update["message"])
        
        elif "callback_query" in update and isinstance(update["callback_query"], dict):
            await self._handle_callback(bot_id, update["callback_query"])
        
        elif "my_chat_member" in update and isinstance(update["my_chat_member"], dict):
            await self._handle_chat_member(bot_id, update["my_chat_member"])
    
    async def _handle_message(self, bot_id: int, message: Dict):
        """Handle incoming message with full processing"""
        chat = message.get("chat")
        chat_id = chat.get("id") if isinstance(chat, dict) else None
        chat_type = chat.get("type", "private") if isinstance(chat, dict) else "private"
        from_user = message.get("from") if isinstance(message.get("from"), dict) else {}
        user_id = from_user.get("id")
        username = from_user.get("username", "")
        first_name = from_user.get("first_name", "")
        text = message.get("text") or ""
        if not isinstance(text, str):
            text = str(text)
        message_id = message.get("message_id")
        reply_to = message.get("reply_to_message")
        reply_to_id = reply_to.get("message_id") if isinstance(reply_to, dict) else None
        has_contact = isinstance(message.get("contact"), dict)
        
        if not isinstance(chat_id, int):
            print(f"⚠️ Bot #{bot_id}: message with no valid chat_id - dropped")
            return
        
        # The master factory bot has its own completely separate flow
        from config import FACTORY_BOT_ID
        if FACTORY_BOT_ID is not None and bot_id == FACTORY_BOT_ID:
            if isinstance(user_id, int):
                import factory_bot
                await factory_bot.handle_message(chat_id, user_id, text, username)
            return
        
        from admin_panel.auth import is_admin
        admin = isinstance(user_id, int) and await is_admin(bot_id, user_id)
        
        if admin:
            from admin_panel import flows, router
            
            if text.strip() == "/start":
                await db.clear_conversation_state(chat_id)
                await router.send_screen(bot_id, chat_id, "main")
                return
            
            # A reply to a forwarded user message (ban/quick-reply/freeform/media)
            import forwarding
            if reply_to_id is not None:
                if await forwarding.handle_admin_reply(bot_id, chat_id, reply_to_id, message):
                    return
            
            consumed = await flows.handle_text(bot_id, chat_id, text)
            if consumed:
                return
            # Falls through to normal handling below (e.g. /help still works)
        
        else:
            # ---- regular (non-admin) user path ----
            import verification
            
            if has_contact:
                if await verification.handle_contact(bot_id, chat_id, user_id):
                    return
            
            if await verification.is_gated(bot_id, chat_id):
                if await verification.handle_text(bot_id, chat_id, text, user_id):
                    return
                await verification.start_challenge(bot_id, chat_id, username, first_name, user_id)
                return
        
        # Subscription gate (skips for admins too - check_subscription is
        # only ever reached here for non-admins since admins return above
        # unless their message fell through, in which case treat them the
        # same as anyone else for subscription purposes)
        is_subscribed = await subscription_handler.check_subscription(bot_id, chat_id, user_id=user_id)
        if not is_subscribed:
            print(f"⚠️ Bot #{bot_id} | User {chat_id} missing subscription")
            return
        
        # Track whether this is a first-ever contact (for the join notification)
        is_new = await db.add_user(bot_id, chat_id, username, first_name, chat_type)
        if is_new:
            await self._notify_new_user(bot_id, chat_id, username, first_name)
        
        # Process message (commands, auto-replies, etc)
        await message_handler.handle_message(bot_id, message)
        
        # Relay to every admin if forwarding is enabled (any content type)
        if not admin and not text.startswith("/"):
            import forwarding
            await forwarding.forward_to_admins(bot_id, chat_id, message, first_name, username)
        
        # "حذف رسائل المستخدم": schedule this incoming message for deletion too
        if isinstance(message_id, int):
            from message_sender import message_sender
            await message_sender.maybe_schedule_user_message_autodelete(bot_id, chat_id, message_id)
        
        # If this user had previously been flagged inactive, this message
        # means they're back
        from scheduler import handle_possible_return
        await handle_possible_return(bot_id, chat_id)
        
        # Log event
        await db.connection.execute(
            """INSERT INTO events (bot_id, event_type, description)
               VALUES (?, ?, ?)""",
            (bot_id, "message", f"Message from {chat_id}: {text[:50]}")
        )
        await db.connection.commit()
        
        print(f"💬 Bot #{bot_id} | User {chat_id}: {text[:50]}")
    
    async def _notify_new_user(self, bot_id: int, chat_id: int, username: str, first_name: str):
        notif_on = await db.get_setting(bot_id, "notif_join", True)
        if not notif_on:
            return
        from bot_registry import bot_registry
        bot = bot_registry.get_bot(bot_id)
        if not bot:
            return
        from admin_panel import screens as sc
        from message_sender import message_sender
        await message_sender.send_message(
            bot_id, bot["owner_id"], sc.notif_new_user(chat_id, username, first_name), is_admin_flow=True
        )
    
    async def _handle_callback(self, bot_id: int, callback: Dict):
        """Handle callback query (button presses)"""
        from_user = callback.get("from")
        user_id = from_user.get("id") if isinstance(from_user, dict) else None
        callback_data = callback.get("data") or ""
        if not isinstance(callback_data, str):
            callback_data = str(callback_data)
        callback_id = callback.get("id") or ""
        message = callback.get("message") if isinstance(callback.get("message"), dict) else {}
        chat = message.get("chat") if isinstance(message.get("chat"), dict) else {}
        chat_id = chat.get("id")
        message_id = message.get("message_id")
        
        if not isinstance(user_id, int):
            print(f"⚠️ Bot #{bot_id}: callback with no valid user id - dropped")
            return
        
        print(f"🔘 Bot #{bot_id} | Callback from {user_id}: {callback_data[:100]}")
        
        await db.connection.execute(
            """INSERT INTO events (bot_id, event_type, description)
               VALUES (?, ?, ?)""",
            (bot_id, "callback", f"Callback from {user_id}: {callback_data[:100]}")
        )
        await db.connection.commit()
        
        if callback_data.startswith("fac:") or callback_data.startswith("fadm:"):
            from config import FACTORY_BOT_ID
            if FACTORY_BOT_ID is not None and bot_id == FACTORY_BOT_ID and isinstance(chat_id, int) and isinstance(message_id, int):
                import factory_bot
                await factory_bot.handle_callback(chat_id, message_id, user_id, callback_id, callback_data)
            return
        
        if callback_data.startswith("adm:") and isinstance(chat_id, int) and isinstance(message_id, int):
            from admin_panel import router
            await router.handle_callback(bot_id, chat_id, message_id, callback_id, callback_data, user_id)
            return
        
        if callback_data.startswith("vfy:") and isinstance(chat_id, int):
            import verification
            await verification.handle_callback(bot_id, chat_id, user_id, callback_id, callback_data)
            return
        
        if callback_data.startswith("chk:") and isinstance(chat_id, int):
            await self._handle_check_callback(bot_id, chat_id, user_id, callback_id, callback_data)
            return
    
    async def _handle_check_callback(self, bot_id: int, chat_id: int, user_id: int, callback_id: str, data: str):
        """"chk:sub" - the "✅ تحقق" button on the subscription gate."""
        from bot_registry import bot_registry
        from telegram_adapter import telegram_pool
        bot = bot_registry.get_bot(bot_id)
        if bot:
            adapter = await telegram_pool.get_adapter(bot["token"])
            await adapter.answer_callback_query(callback_id)
        
        parts = data.split(":")
        if len(parts) != 3 or parts[0:2] != ["chk", "sub"] or parts[2] != str(user_id):
            return
        if data.startswith("chk:sub:"):
            fully_subscribed = await subscription_handler.check_subscription(
                bot_id, chat_id, send_prompt=False, user_id=user_id
            )
            if fully_subscribed:
                from message_sender import message_sender
                await message_sender.send_message(bot_id, chat_id, "✅ تم! اكتب /start للمتابعة")
                notify_on = await db.get_setting(bot_id, "sub_notify", False)
                if notify_on and bot:
                    await message_sender.send_message(
                        bot_id, bot["owner_id"],
                        f"🔔 مستخدم اجتاز بوابة الاشتراك\n🆔 <code>{chat_id}</code>",
                        is_admin_flow=True
                    )
            else:
                from message_sender import message_sender
                await message_sender.send_message(bot_id, chat_id, "⚠️ لسا ناقصك تشترك ببعض القنوات")
    
    async def _handle_chat_member(self, bot_id: int, chat_member: Dict):
        """Handle chat member status change (blocking)"""
        from_user = chat_member.get("from")
        user_id = from_user.get("id") if isinstance(from_user, dict) else None
        new_member = chat_member.get("new_chat_member")
        new_status = new_member.get("status") if isinstance(new_member, dict) else None
        
        if not isinstance(user_id, int):
            print(f"⚠️ Bot #{bot_id}: chat_member update with no valid user id - dropped")
            return
        
        if new_status == "kicked":
            print(f"🚫 Bot #{bot_id} | User {user_id} blocked the bot")
            
            was_blocked_already = False
            cursor = await db.connection.execute(
                "SELECT is_blocked FROM bot_users WHERE bot_id = ? AND chat_id = ?", (bot_id, user_id)
            )
            row = await cursor.fetchone()
            was_blocked_already = bool(row and row[0])
            
            await db.connection.execute(
                "UPDATE bot_users SET is_blocked = 1 WHERE bot_id = ? AND chat_id = ?",
                (bot_id, user_id)
            )
            
            await db.connection.execute(
                """INSERT INTO events (bot_id, event_type, description)
                   VALUES (?, ?, ?)""",
                (bot_id, "blocked", f"User {user_id} blocked bot")
            )
            await db.connection.commit()
            
            if not was_blocked_already:
                notif_on = await db.get_setting(bot_id, "notif_block", True)
                if notif_on:
                    from bot_registry import bot_registry
                    bot = bot_registry.get_bot(bot_id)
                    if bot:
                        from admin_panel import screens as sc
                        from message_sender import message_sender
                        await message_sender.send_message(
                            bot_id, bot["owner_id"], sc.notif_user_blocked(user_id), is_admin_flow=True
                        )

# Global instance
dispatcher = Dispatcher()
