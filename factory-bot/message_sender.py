from telegram_adapter import telegram_pool
from rate_limiter import rate_limiter_pool
from db import db
from typing import Optional
import asyncio
import re
from pathlib import Path

_URL_RE = re.compile(r"https?://|t\.me/|www\.", re.IGNORECASE)

class MessageSender:
    """
    Send messages with rate limiting
    """
    
    async def send_message(self, bot_id: int, chat_id: int, text: str, 
                          parse_mode: str = "HTML", reply_markup: Optional[dict] = None,
                          _retry: bool = True, is_start: bool = False,
                          is_admin_flow: bool = False) -> Optional[dict]:
        """
        Send message with rate limiting
        
        Args:
            bot_id: Bot sending the message
            chat_id: Recipient chat ID
            text: Message text
            parse_mode: HTML or Markdown
            reply_markup: optional inline keyboard dict (e.g. from keyboards.py)
            _retry: internal flag - allow exactly one retry after a 429
            is_start: this message is a reply to /start (for the auto-delete
                "استثناء بدء" exception)
            is_admin_flow: this message is part of the admin control panel
                (for the auto-delete "استثناء مشرف" exception, and it's
                never content-protected - protection is for end-user content)
        
        Returns:
            Response from Telegram or None if failed
        """
        
        # --- input validation ---
        if not isinstance(bot_id, int) or not isinstance(chat_id, int):
            print("❌ send_message: invalid bot_id/chat_id")
            return None
        if not text or not isinstance(text, str):
            print("❌ send_message: empty or invalid text")
            return None
        if len(text) > 4096:  # Telegram's hard limit
            text = text[:4096]
        
        # Get bot token
        from bot_registry import bot_registry
        bot = bot_registry.get_bot(bot_id)
        if not bot:
            print(f"❌ Bot #{bot_id} not found")
            return None
        
        protect = False
        if not is_admin_flow:
            protect = await self._should_protect(bot_id, text)
        
        # Acquire rate limit
        await rate_limiter_pool.acquire(bot_id)
        
        # Get adapter and send
        adapter = await telegram_pool.get_adapter(bot['token'])
        response = await adapter.send_message(chat_id, text, parse_mode, reply_markup=reply_markup,
                                               protect_content=protect)
        
        # Handle errors
        if not response.get("ok"):
            error_code = response.get("error_code")
            
            # 429 = Too Many Requests - wait retry_after then retry once
            if error_code == 429:
                retry_after = response.get("parameters", {}).get("retry_after", 5)
                rate_limiter_pool.on_429(bot_id, retry_after)
                print(f"❌ 429 error for bot #{bot_id}, retry_after={retry_after}s")
                
                if _retry:
                    await asyncio.sleep(retry_after)
                    return await self.send_message(bot_id, chat_id, text, parse_mode, reply_markup,
                                                    _retry=False, is_start=is_start, is_admin_flow=is_admin_flow)
                return None
            
            # 403 = user blocked the bot - mark them so we stop retrying/broadcasting to them
            elif error_code == 403:
                print(f"🚫 Bot #{bot_id}: user {chat_id} has blocked the bot")
                was_blocked_already = False
                try:
                    cursor = await db.connection.execute(
                        "SELECT is_blocked FROM bot_users WHERE bot_id = ? AND chat_id = ?",
                        (bot_id, chat_id)
                    )
                    row = await cursor.fetchone()
                    was_blocked_already = bool(row and row[0])
                    await db.connection.execute(
                        "UPDATE bot_users SET is_blocked = 1 WHERE bot_id = ? AND chat_id = ?",
                        (bot_id, chat_id)
                    )
                    await db.connection.commit()
                except Exception as e:
                    print(f"⚠️ Failed to mark user blocked: {e}")
                
                if not was_blocked_already and not is_admin_flow:
                    await self._notify_admin_block(bot_id, chat_id)
                return None
            
            else:
                print(f"❌ Error sending message to bot #{bot_id}: {response}")
                from db import db as _db
                await _db.add_log("error", f"bot:{bot_id}", f"send_message failed: {response}")
                return None
        
        # Log sent message
        message_id = response.get("result", {}).get("message_id")
        await db.add_message(
            bot_id=bot_id,
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            is_incoming=False
        )
        
        if message_id is not None:
            await self._maybe_schedule_autodelete(
                bot_id, chat_id, message_id,
                has_buttons=reply_markup is not None,
                is_start=is_start, is_admin_flow=is_admin_flow,
            )
            if not is_admin_flow:
                await self._maybe_delete_between(bot_id, chat_id, message_id)
        
        print(f"✅ Message sent to {chat_id}: {text[:50]}")
        return response
    
    async def _should_protect(self, bot_id: int, text: str) -> bool:
        keys = ["protect_content", "protect_links_exc", "protect_text_exc"]
        defaults = {"protect_content": False, "protect_links_exc": False, "protect_text_exc": False}
        s = await db.get_settings(bot_id, keys, defaults)
        if not s["protect_content"]:
            return False
        if s["protect_text_exc"]:
            # "exempt plain text" - only protect if this message is NOT
            # plain text, i.e. never (this engine is text-only), so
            # protection effectively never applies when this is on.
            return False
        if s["protect_links_exc"] and _URL_RE.search(text):
            return False
        return True
    
    async def _notify_admin_block(self, bot_id: int, blocked_chat_id: int):
        notif_on = await db.get_setting(bot_id, "notif_block", True)
        if not notif_on:
            return
        from bot_registry import bot_registry
        bot = bot_registry.get_bot(bot_id)
        if not bot:
            return
        from admin_panel import screens as sc
        await self.send_message(bot_id, bot["owner_id"], sc.notif_user_blocked(blocked_chat_id), is_admin_flow=True)
    
    async def _maybe_delete_between(self, bot_id: int, chat_id: int, new_message_id: int):
        """"حذف ما بين الرسائل": if enabled, only the latest bot message
        in a chat is ever left visible - delete the previous one the
        instant a new one is sent."""
        enabled = await db.get_setting(bot_id, "autodel_between", False)
        if not enabled:
            await db.set_last_bot_message(bot_id, chat_id, new_message_id)
            return
        
        previous_id = await db.set_last_bot_message(bot_id, chat_id, new_message_id)
        if previous_id and previous_id != new_message_id:
            from bot_registry import bot_registry
            bot = bot_registry.get_bot(bot_id)
            if bot:
                adapter = await telegram_pool.get_adapter(bot["token"])
                await adapter.delete_message(chat_id, previous_id)
    
    async def _maybe_schedule_autodelete(self, bot_id: int, chat_id: int, message_id: int,
                                          has_buttons: bool, is_start: bool, is_admin_flow: bool):
        """If this bot has auto-delete enabled and none of its configured
        exceptions apply to this message, schedule it for deletion. See
        scheduler.py for the background sweep that actually deletes it."""
        keys = ["autodel_enabled", "autodel_minutes", "autodel_private", "autodel_group", "autodel_channel",
                "autodel_exc_buttons", "autodel_exc_start", "autodel_exc_admin"]
        defaults = {"autodel_enabled": False, "autodel_minutes": 5, "autodel_private": True,
                    "autodel_group": False, "autodel_channel": False,
                    "autodel_exc_buttons": False, "autodel_exc_start": False, "autodel_exc_admin": False}
        s = await db.get_settings(bot_id, keys, defaults)
        
        if not s["autodel_enabled"]:
            return
        
        chat_type = await self._get_chat_type(bot_id, chat_id)
        type_enabled = {
            "private": s["autodel_private"],
            "group": s["autodel_group"], "supergroup": s["autodel_group"],
            "channel": s["autodel_channel"],
        }.get(chat_type, s["autodel_private"])
        if not type_enabled:
            return
        
        if is_start and s["autodel_exc_start"]:
            return
        if is_admin_flow and s["autodel_exc_admin"]:
            return
        if has_buttons and s["autodel_exc_buttons"]:
            return
        
        from datetime import datetime, timedelta
        delete_at = (datetime.now() + timedelta(minutes=s["autodel_minutes"])).isoformat()
        await db.add_scheduled_deletion(bot_id, chat_id, message_id, delete_at)
    
    async def _get_chat_type(self, bot_id: int, chat_id: int) -> str:
        cursor = await db.connection.execute(
            "SELECT chat_type FROM bot_users WHERE bot_id = ? AND chat_id = ?", (bot_id, chat_id)
        )
        row = await cursor.fetchone()
        return row[0] if row and row[0] else "private"
    
    async def maybe_schedule_user_message_autodelete(self, bot_id: int, chat_id: int, message_id: int):
        """"حذف رسائل المستخدم": schedules the USER's own incoming message
        for deletion too, on the same timer, when that option is on."""
        keys = ["autodel_enabled", "autodel_minutes", "autodel_user_msgs"]
        defaults = {"autodel_enabled": False, "autodel_minutes": 5, "autodel_user_msgs": False}
        s = await db.get_settings(bot_id, keys, defaults)
        if not s["autodel_enabled"] or not s["autodel_user_msgs"]:
            return
        from datetime import datetime, timedelta
        delete_at = (datetime.now() + timedelta(minutes=s["autodel_minutes"])).isoformat()
        await db.add_scheduled_deletion(bot_id, chat_id, message_id, delete_at)
    
    async def send_document(self, bot_id: int, chat_id: int, file_path: str,
                            caption: str = "", _retry: bool = True) -> Optional[dict]:
        """Send a local file as a Telegram document."""
        if not isinstance(bot_id, int) or not isinstance(chat_id, int):
            print("❌ send_document: invalid bot_id/chat_id")
            return None
        path = Path(file_path)
        if not path.is_file():
            print(f"❌ send_document: file not found: {path}")
            return None

        from bot_registry import bot_registry
        bot = bot_registry.get_bot(bot_id)
        if not bot:
            print(f"❌ Bot #{bot_id} not found")
            return None

        await rate_limiter_pool.acquire(bot_id)
        adapter = await telegram_pool.get_adapter(bot["token"])
        response = await adapter.send_document(chat_id, str(path), caption=caption)
        if response.get("ok"):
            print(f"✅ Document sent to {chat_id}: {path.name}")
            return response

        if response.get("error_code") == 429 and _retry:
            retry_after = response.get("parameters", {}).get("retry_after", 5)
            rate_limiter_pool.on_429(bot_id, retry_after)
            await asyncio.sleep(retry_after)
            return await self.send_document(
                bot_id, chat_id, str(path), caption, _retry=False
            )

        print(f"❌ Document send failed for bot #{bot_id}: "
              f"{response.get('description', response.get('error', 'unknown error'))}")
        return None

    async def edit_message(self, bot_id: int, chat_id: int, message_id: int, text: str,
                           parse_mode: str = "HTML", reply_markup: Optional[dict] = None) -> Optional[dict]:
        """Edit an existing message in place - used by the admin panel to
        navigate between screens (main menu -> settings -> ... ) without
        sending a new message for every button press."""
        if not isinstance(bot_id, int) or not isinstance(chat_id, int) or not isinstance(message_id, int):
            print("❌ edit_message: invalid bot_id/chat_id/message_id")
            return None
        if not text or not isinstance(text, str):
            print("❌ edit_message: empty or invalid text")
            return None
        if len(text) > 4096:
            text = text[:4096]
        
        from bot_registry import bot_registry
        bot = bot_registry.get_bot(bot_id)
        if not bot:
            print(f"❌ Bot #{bot_id} not found")
            return None
        
        await rate_limiter_pool.acquire(bot_id)
        adapter = await telegram_pool.get_adapter(bot['token'])
        response = await adapter.edit_message_text(
            chat_id, message_id, text, parse_mode, reply_markup=reply_markup
        )
        
        if not response.get("ok"):
            print(f"❌ Error editing message for bot #{bot_id}: {response}")
            return None
        return response

# Global instance
message_sender = MessageSender()
