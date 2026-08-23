"""
Telegram API adapter using only the Python standard library.

Why not httpx: on Termux, PyPI's pre-built wheels target glibc Linux and
aren't compatible with Android's Bionic libc, so pip has to build many
packages from source - which needs a C compiler and often fails/hangs.
`urllib.request` ships with every Python install, so this removes one
more thing that can fail to `pip install`.

Trade-off (stated plainly, not hidden): urllib.request is blocking, so
each call runs on a background thread via asyncio.to_thread() instead of
using a truly async socket like httpx did. A getUpdates long-poll call
holds its thread for up to `timeout` seconds. See main.py, which sizes
the thread pool comfortably above the expected number of concurrently
polled bots so this doesn't become a bottleneck.
"""

import json
import socket
import ssl
import urllib.request
import urllib.error
import asyncio
from typing import Dict, Optional


class TelegramAdapter:
    """Lightweight Telegram API adapter using urllib.request"""
    
    BASE_URL = "https://api.telegram.org"
    _ssl_context = ssl.create_default_context()
    
    def __init__(self, token: str, timeout: int = 30):
        self.token = token
        self.timeout = timeout
    
    async def init(self):
        """No persistent connection to set up - urllib.request opens a
        fresh connection per call. Kept for API-compatibility with the
        rest of the codebase (pool.get_adapter() calls this)."""
        pass
    
    async def close(self):
        """Nothing to close - see init()."""
        pass
    
    def _get_url(self, method: str) -> str:
        """Build API URL"""
        return f"{self.BASE_URL}/bot{self.token}/{method}"
    
    def _post_sync(self, url: str, payload: dict, timeout: float):
        """Blocking POST - always called via asyncio.to_thread, never
        directly from the event loop."""
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"}, method="POST"
        )
        with urllib.request.urlopen(req, timeout=timeout, context=self._ssl_context) as resp:
            return resp.status, resp.read()
    
    async def _post(self, method: str, payload: dict, timeout: float, 
                    raise_on_connection_error: bool = False) -> Dict:
        url = self._get_url(method)
        try:
            status, body = await asyncio.to_thread(self._post_sync, url, payload, timeout)
            try:
                return json.loads(body)
            except json.JSONDecodeError:
                return {"ok": False, "error": f"invalid_json_response (status {status})"}
        
        except socket.timeout:
            # Normal for long-polling - not an error, just nothing to report
            return {"ok": False, "error": "timeout"}
        
        except urllib.error.HTTPError as e:
            # Telegram returns a JSON error body even on 4xx/5xx - try to
            # surface its real error_code/description instead of just the
            # HTTP status.
            try:
                parsed = json.loads(e.read())
                parsed.setdefault("ok", False)
                return parsed
            except Exception:
                return {"ok": False, "error_code": e.code, "description": str(e)}
        
        except urllib.error.URLError as e:
            # DNS failure, connection refused, TLS failure, etc - a real
            # connectivity issue rather than an API-level error.
            if raise_on_connection_error:
                raise ConnectionError(f"{method} connection failed: {e.reason}") from e
            return {"ok": False, "error": f"connection_error: {e.reason}"}
    
    async def get_updates(self, offset: int = 0, timeout: int = 30, limit: int = 100) -> Dict:
        """
        Get updates from Telegram with long polling
        
        Args:
            offset: Last update ID + 1
            timeout: Long poll timeout (seconds)
            limit: Max updates to return
        
        Returns:
            {"ok": bool, "result": [...]}
        """
        # Socket timeout must exceed Telegram's own long-poll timeout, or
        # we'd cut the connection before Telegram responds.
        return await self._post(
            "getUpdates",
            {
                "offset": offset,
                "timeout": timeout,
                "limit": limit,
                "allowed_updates": ["message", "callback_query", "my_chat_member"]
            },
            timeout=timeout + 10.0,
            raise_on_connection_error=True,  # let the poller's retry/backoff handle it
        )
    
    async def send_message(self, chat_id: int, text: str, parse_mode: str = "HTML",
                           reply_markup: Optional[dict] = None,
                           protect_content: bool = False) -> Dict:
        """Send message, optionally with an inline keyboard (reply_markup)
        and/or Telegram's native forward/save protection."""
        payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        if protect_content:
            payload["protect_content"] = True
        return await self._post("sendMessage", payload, timeout=self.timeout)
    
    async def edit_message_text(self, chat_id: int, message_id: int, text: str,
                                parse_mode: str = "HTML",
                                reply_markup: Optional[dict] = None) -> Dict:
        """Edit an existing message's text/keyboard in place - this is how
        the admin panel navigates between screens without spamming new
        messages for every button press."""
        payload = {
            "chat_id": chat_id, "message_id": message_id,
            "text": text, "parse_mode": parse_mode,
        }
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        result = await self._post("editMessageText", payload, timeout=self.timeout)
        if not result.get("ok") and "message is not modified" in str(result.get("description", "")):
            # Harmless: happens when a button is pressed but the screen
            # content didn't actually change (e.g. re-opening the same
            # menu). Treat as success rather than surfacing an error.
            return {"ok": True, "result": None, "_unmodified": True}
        return result
    
    async def answer_callback_query(self, callback_query_id: str, text: Optional[str] = None,
                                    show_alert: bool = False) -> Dict:
        """Acknowledge a button press. Telegram shows a small loading
        spinner on the button until this is called (or ~30s times out),
        so every callback_query handler should call this quickly."""
        payload = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text
            payload["show_alert"] = show_alert
        return await self._post("answerCallbackQuery", payload, timeout=self.timeout)
    
    async def get_me(self) -> Dict:
        """Get bot info"""
        return await self._post("getMe", {}, timeout=self.timeout)
    
    async def delete_message(self, chat_id: int, message_id: int) -> Dict:
        """Delete a message the bot sent - used by the auto-delete feature"""
        return await self._post(
            "deleteMessage", {"chat_id": chat_id, "message_id": message_id}, timeout=self.timeout
        )
    
    async def forward_message(self, chat_id: int, from_chat_id: int, message_id: int) -> Dict:
        """Forward a message the bot received into another chat (keeps
        Telegram's native "Forwarded from" tag)."""
        return await self._post(
            "forwardMessage",
            {"chat_id": chat_id, "from_chat_id": from_chat_id, "message_id": message_id},
            timeout=self.timeout,
        )
    
    async def copy_message(self, chat_id: int, from_chat_id: int, message_id: int,
                           caption: Optional[str] = None) -> Dict:
        """Copy ANY message type (text, photo, video, document, animation/
        gif, sticker, voice, audio, video note...) into another chat
        without the "Forwarded from" tag - Telegram figures out the
        content type itself, so this is how the engine relays arbitrary
        user content (forwarding to admin, sending admin replies back)
        without needing separate code per media type. `caption` overrides
        the caption for media messages only (Telegram ignores it for pure
        text messages and for stickers)."""
        payload = {"chat_id": chat_id, "from_chat_id": from_chat_id, "message_id": message_id}
        if caption is not None:
            payload["caption"] = caption
            payload["parse_mode"] = "HTML"
        return await self._post("copyMessage", payload, timeout=self.timeout)
    
    async def set_message_reaction(self, chat_id: int, message_id: int, emoji: str = "👀") -> Dict:
        """Set an emoji reaction on a message - used for the auto-delete
        "react before deleting" option."""
        return await self._post(
            "setMessageReaction",
            {"chat_id": chat_id, "message_id": message_id,
             "reaction": [{"type": "emoji", "emoji": emoji}]},
            timeout=self.timeout,
        )
    
    async def set_my_commands(self, commands: list) -> Dict:
        """Register the bot's `/` command list (the "الاختصارات" feature).
        `commands` is a list of {"command": "...", "description": "..."}."""
        return await self._post("setMyCommands", {"commands": commands}, timeout=self.timeout)
    
    async def get_chat_member(self, chat_id, user_id: int) -> Dict:
        """Get a user's membership status in a chat/channel"""
        return await self._post(
            "getChatMember",
            {"chat_id": chat_id, "user_id": user_id},
            timeout=self.timeout,
        )
    
    async def create_chat_invite_link(self, chat_id) -> Dict:
        """Generate a real invite link for a channel/group the bot admins
        - used so private numeric (-100...) mandatory-subscription
        channels get a working join button too, not just @username ones."""
        return await self._post(
            "createChatInviteLink", {"chat_id": chat_id}, timeout=self.timeout
        )


class TelegramAdapterPool:
    """Pool of Telegram adapters for multiple bots"""
    
    def __init__(self):
        self.adapters = {}  # bot_token -> TelegramAdapter
    
    async def get_adapter(self, token: str, timeout: int = 30) -> TelegramAdapter:
        """Get or create adapter for token"""
        if token not in self.adapters:
            adapter = TelegramAdapter(token, timeout)
            await adapter.init()
            self.adapters[token] = adapter
        
        return self.adapters[token]
    
    async def close_all(self):
        """Close all adapters"""
        for adapter in self.adapters.values():
            try:
                await adapter.close()
            except Exception as e:
                print(f"⚠️ Error closing adapter: {e}")
        self.adapters.clear()

# Global instance
telegram_pool = TelegramAdapterPool()
