from db import db
from priority_queue import job_queue, JobPriority
from message_sender import message_sender
from telegram_adapter import telegram_pool
from typing import List, Optional, Tuple

MAX_SUBSCRIPTIONS = 10
DEFAULT_GATE_TEXT = "⚠️ يجب الاشتراك بالقنوات التالية قبل استخدام البوت:"


class SubscriptionHandler:
    """Handle mandatory channel subscriptions"""
    
    async def check_subscription(self, bot_id: int, chat_id: int, send_prompt: bool = True, user_id: int = None) -> bool:
        """
        Check if user is subscribed to ALL mandatory channels. If not, and
        send_prompt is True, sends one gate message listing every channel
        still missing (not just the first one found).
        
        Returns:
            True if subscribed to all, False if missing any
        """
        subject_id = user_id if isinstance(user_id, int) else chat_id
        missing = await self._get_missing_channels(bot_id, subject_id)
        if missing is None:
            return True  # no mandatory channels configured
        if not missing:
            return True
        
        if send_prompt:
            await self._send_gate(bot_id, chat_id, missing, subject_id)
        return False
    
    async def _get_missing_channels(self, bot_id: int, chat_id: int) -> Optional[List[str]]:
        """Returns None if there are no mandatory channels at all (neither
        this bot's own nor the factory-wide ones), else the list of
        channel_ids the user still hasn't joined (possibly empty).
        Factory-wide channels (set from the factory admin panel) apply on
        top of every single created bot, in addition to that bot's own."""
        from config import FACTORY_BOT_ID
        bot_ids_to_check = [bot_id]
        if FACTORY_BOT_ID is not None and bot_id != FACTORY_BOT_ID:
            bot_ids_to_check.append(FACTORY_BOT_ID)
        
        placeholders = ",".join(["?"] * len(bot_ids_to_check))
        cursor = await db.connection.execute(
            f"""SELECT channel_id FROM subscriptions 
               WHERE bot_id IN ({placeholders}) AND is_mandatory = 1 AND active = 1""",
            tuple(bot_ids_to_check)
        )
        channels = await cursor.fetchall()
        if not channels:
            return None
        
        from bot_registry import bot_registry
        bot = bot_registry.get_bot(bot_id)
        if not bot:
            return None
        
        adapter = await telegram_pool.get_adapter(bot['token'])
        missing = []
        for (channel_id,) in channels:
            if channel_id not in missing and not await self._check_membership(adapter, channel_id, chat_id):
                missing.append(channel_id)
        return missing
    
    async def _check_membership(self, adapter, channel_id: str, chat_id: int) -> bool:
        """
        Check if user is member of channel
        
        Args:
            adapter: Telegram adapter
            channel_id: Channel identifier (@channel or -100...)
            chat_id: User chat ID
        
        Returns:
            True if member, False otherwise
        """
        
        try:
            # getChatMember returns the user's status in the channel/group
            data = await adapter.get_chat_member(channel_id, chat_id)
            
            if data.get("ok"):
                status = data.get("result", {}).get("status")
                # Valid statuses: creator, administrator, member, restricted, left, kicked
                return status in ["creator", "administrator", "member"]
            
            error = str(data.get("error", ""))
            if error == "timeout":
                print(f"⏳ Timeout checking subscription for channel {channel_id}")
            else:
                print(f"❌ Error checking subscription for channel {channel_id}: {data}")
                from db import db
                await db.add_log("warning", f"subscription", f"Check failed for {channel_id}: {data}")
            
            # Fail closed: if we can't verify, treat as not-subscribed
            # rather than silently letting the user through
            return False
        
        except ConnectionError as e:
            print(f"❌ Network error checking subscription: {e}")
            return False
    
    async def build_gate(self, bot_id: int, channels: List[str], user_id: int = None) -> Tuple[str, dict]:
        """Build the gate message text + inline keyboard - shared by the
        real prompt and the admin's "🎭 معاينة البوابة" preview so they're
        guaranteed to look identical."""
        from admin_panel import keyboards as kb
        
        custom_text = await db.get_setting(bot_id, "content_override_subscription_prompt_text")
        check_text = await db.get_setting(bot_id, "sub_check_text", "✅ تحقق")
        
        header = custom_text or DEFAULT_GATE_TEXT
        channel_lines = "\n".join(f"📢 {c}" for c in channels)
        text = f"{header}\n\n{channel_lines}"
        
        invite_links = await self._get_invite_links(bot_id, channels)
        keyboard = kb.sub_gate_kb(channels, check_text, invite_links, user_id)
        return text, keyboard
    
    async def _get_invite_links(self, bot_id: int, channels: List[str]) -> dict:
        """@username channels get a plain t.me/username link (free, no API
        call needed). Private numeric (-100...) channels need a real
        invite link generated via the API - cached in bot_settings so we
        don't call createChatInviteLink on every single gate render."""
        needed = [c for c in channels if not c.startswith("@")]
        if not needed:
            return {}
        
        from bot_registry import bot_registry
        bot = bot_registry.get_bot(bot_id)
        if not bot:
            return {}
        
        links = {}
        for channel_id in needed:
            cached = await db.get_setting(bot_id, f"invite_link_{channel_id}")
            if cached:
                links[channel_id] = cached
                continue
            adapter = await telegram_pool.get_adapter(bot["token"])
            result = await adapter.create_chat_invite_link(channel_id)
            if result.get("ok"):
                link = result["result"].get("invite_link")
                if link:
                    await db.set_setting(bot_id, f"invite_link_{channel_id}", link)
                    links[channel_id] = link
            # If it fails (bot isn't admin there, etc), we just don't add
            # a button for that one - honest fallback, not a crash.
        return links
    
    async def _send_gate(self, bot_id: int, chat_id: int, channels: List[str], user_id: int):
        text, keyboard = await self.build_gate(bot_id, channels, user_id)
        await job_queue.add_job(
            f"subscription_{bot_id}_{chat_id}",
            JobPriority.HIGH,
            message_sender.send_message,
            bot_id,
            chat_id,
            text,
            "HTML",
            keyboard,
        )
    
    async def add_subscription(self, bot_id: int, channel_id: str, mandatory: bool = True) -> bool:
        """Add subscription requirement for bot (max 10, enforced here)"""
        if not isinstance(bot_id, int) or not channel_id or not isinstance(channel_id, str):
            print("❌ Error adding subscription: invalid bot_id/channel_id")
            return False
        
        current = await self.get_subscriptions(bot_id)
        if len(current) >= MAX_SUBSCRIPTIONS and channel_id not in {c["channel_id"] for c in current}:
            print(f"❌ Bot #{bot_id}: subscription limit ({MAX_SUBSCRIPTIONS}) reached")
            return False
        
        try:
            await db.connection.execute(
                """INSERT OR IGNORE INTO subscriptions (bot_id, channel_id, is_mandatory, active)
                   VALUES (?, ?, ?, 1)""",
                (bot_id, channel_id, mandatory)
            )
            await db.connection.commit()
            print(f"✅ Subscription added: {channel_id}")
            return True
        except Exception as e:
            await db.connection.rollback()
            print(f"❌ Error adding subscription: {e}")
            return False
    
    async def remove_subscription(self, bot_id: int, channel_id: str):
        """Remove subscription requirement"""
        
        try:
            await db.connection.execute(
                "DELETE FROM subscriptions WHERE bot_id = ? AND channel_id = ?",
                (bot_id, channel_id)
            )
            await db.connection.commit()
            print(f"✅ Subscription removed: {channel_id}")
            return True
        except Exception as e:
            print(f"❌ Error removing subscription: {e}")
            return False
    
    async def get_subscriptions(self, bot_id: int) -> List[dict]:
        """Get all subscriptions for bot"""
        
        cursor = await db.connection.execute(
            """SELECT id, channel_id, is_mandatory, active 
               FROM subscriptions WHERE bot_id = ?""",
            (bot_id,)
        )
        
        rows = await cursor.fetchall()
        return [
            {
                "id": row[0],
                "channel_id": row[1],
                "is_mandatory": row[2],
                "active": row[3]
            }
            for row in rows
        ]

# Global instance
subscription_handler = SubscriptionHandler()
