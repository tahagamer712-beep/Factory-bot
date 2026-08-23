from db import db
from priority_queue import job_queue, JobPriority
from message_sender import message_sender
from rate_limiter import rate_limiter_pool
from typing import Dict, Any
import re

DEFAULT_HELP_TEXT = "📖 مساعدة:\n/start - البداية\n/help - المساعدة\n/stats - الإحصائيات"
DEFAULT_UNKNOWN_TEXT = "❓ أمر غير معروف: {command}\nاستخدم /help للمساعدة"


class MessageHandler:
    """Handle incoming messages"""
    
    async def handle_message(self, bot_id: int, message: Dict[str, Any]):
        """
        Process incoming message. Note: user tracking (db.add_user) and
        the subscription/verification gates already happened in
        dispatcher.py before this is called - this only handles the
        actual content response (commands / auto-replies).
        """
        chat = message.get("chat")
        chat_id = chat.get("id") if isinstance(chat, dict) else None
        text = message.get("text") or ""
        if not isinstance(text, str):
            text = str(text)
        message_id = message.get("message_id")
        
        if not isinstance(chat_id, int):
            return
        
        # Save message
        await db.add_message(
            bot_id=bot_id,
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            is_incoming=True
        )
        
        # Check if user is blocked
        cursor = await db.connection.execute(
            "SELECT is_blocked FROM bot_users WHERE bot_id = ? AND chat_id = ?",
            (bot_id, chat_id)
        )
        row = await cursor.fetchone()
        if row and row[0]:
            print(f"🚫 Bot #{bot_id}: Blocked user {chat_id} tried to message")
            return
        
        # Process message (check commands, auto-replies, etc)
        await self._process_message(bot_id, chat_id, text, message_id)
    
    async def _process_message(self, bot_id: int, chat_id: int, text: str, message_id: int):
        """Process message content"""
        
        if text.startswith("/"):
            await self._handle_command(bot_id, chat_id, text)
        else:
            await self._check_auto_replies(bot_id, chat_id, text)
    
    async def _transparent_buttons_kb(self, bot_id: int):
        """"الأزرار الشفافة": a persistent reply-keyboard shown to regular
        end-users only (never the admin panel, which stays 100% inline).
        Each button just sends its own label text when tapped."""
        buttons = await db.get_setting(bot_id, "transparent_buttons", [])
        if not buttons:
            return None
        return {
            "keyboard": [[{"text": b}] for b in buttons],
            "resize_keyboard": True,
        }
    
    async def _handle_command(self, bot_id: int, chat_id: int, text: str):
        """Handle slash commands"""
        
        command = text.split()[0].lower()
        
        if command == "/start":
            welcome = await db.get_setting(bot_id, "welcome_message") or \
                "👋 مرحباً بك في البوت!\n\nأرسل رسالة أو استخدم /help"
            reply_markup = await self._transparent_buttons_kb(bot_id)
            await job_queue.add_job(
                f"cmd_start_{bot_id}_{chat_id}",
                JobPriority.HIGH,
                message_sender.send_message,
                bot_id,
                chat_id,
                welcome,
                "HTML",
                reply_markup,
                True,
                True,  # is_start
            )
        
        elif command == "/help":
            help_text = await db.get_setting(bot_id, "content_override_help_text") or DEFAULT_HELP_TEXT
            await job_queue.add_job(
                f"cmd_help_{bot_id}_{chat_id}",
                JobPriority.HIGH,
                message_sender.send_message,
                bot_id,
                chat_id,
                help_text
            )
        
        elif command == "/stats":
            await self._send_stats(bot_id, chat_id)
        
        else:
            unknown_text = await db.get_setting(bot_id, "content_override_unknown_command_text") or DEFAULT_UNKNOWN_TEXT
            try:
                unknown_text = unknown_text.format(command=command)
            except (KeyError, IndexError):
                pass
            await job_queue.add_job(
                f"cmd_unknown_{bot_id}_{chat_id}",
                JobPriority.HIGH,
                message_sender.send_message,
                bot_id,
                chat_id,
                unknown_text
            )
    
    async def _check_auto_replies(self, bot_id: int, chat_id: int, text: str):
        """Check and send auto-replies (with optional attached link buttons)"""
        
        cursor = await db.connection.execute(
            "SELECT id, keyword, reply FROM auto_replies WHERE bot_id = ? AND active = 1",
            (bot_id,)
        )
        rows = await cursor.fetchall()
        
        for reply_id, keyword, reply in rows:
            try:
                matched = re.search(keyword, text, re.IGNORECASE)
            except re.error as e:
                print(f"⚠️ Bot #{bot_id}: invalid auto-reply pattern '{keyword}': {e}")
                continue
            
            if matched:
                buttons = await db.get_setting(bot_id, f"autoreply_buttons_{reply_id}", [])
                reply_markup = None
                if buttons:
                    reply_markup = {"inline_keyboard": [[{"text": b["label"], "url": b["url"]}] for b in buttons]}
                
                await job_queue.add_job(
                    f"auto_reply_{bot_id}_{chat_id}",
                    JobPriority.HIGH,
                    message_sender.send_message,
                    bot_id,
                    chat_id,
                    reply,
                    "HTML",
                    reply_markup,
                )
                return
    
    async def _send_stats(self, bot_id: int, chat_id: int):
        """Send bot statistics"""
        
        cursor = await db.connection.execute(
            "SELECT COUNT(*) FROM bot_users WHERE bot_id = ? AND is_blocked = 0",
            (bot_id,)
        )
        total_users = (await cursor.fetchone())[0]
        
        cursor = await db.connection.execute(
            "SELECT COUNT(*) FROM messages WHERE bot_id = ?",
            (bot_id,)
        )
        total_messages = (await cursor.fetchone())[0]
        
        stats_text = f"""📊 إحصائيات البوت:
👥 المستخدمين: {total_users}
💬 الرسائل: {total_messages}"""
        
        await job_queue.add_job(
            f"stats_{bot_id}_{chat_id}",
            JobPriority.HIGH,
            message_sender.send_message,
            bot_id,
            chat_id,
            stats_text
        )

# Global instance
message_handler = MessageHandler()
