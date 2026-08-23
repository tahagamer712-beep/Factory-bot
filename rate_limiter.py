import asyncio
import time
from typing import Dict, Optional
from collections import deque

class BotRateLimiter:
    """
    Per-bot rate limiter
    Telegram: max 30 messages/second per bot
    """
    
    def __init__(self, bot_id: int, limit: int = 30, window: int = 1):
        """
        Args:
            bot_id: Telegram bot ID
            limit: Max requests per window (default: 30)
            window: Time window in seconds (default: 1)
        """
        self.bot_id = bot_id
        self.limit = limit
        self.window = window
        self.requests = deque()  # (timestamp, request_type)
        self.retry_after = 0  # If Telegram returns 429
    
    async def acquire(self, wait: bool = True) -> bool:
        """
        Acquire permission to make request
        
        Args:
            wait: If True, wait until permission. If False, check immediately.
        
        Returns:
            True if allowed, False if rate limited
        """
        now = time.time()
        
        # Remove old requests outside window
        while self.requests and self.requests[0][0] < now - self.window:
            self.requests.popleft()
        
        # Check retry_after from 429 error
        if self.retry_after > now:
            if wait:
                wait_time = self.retry_after - now
                print(f"⏳ Bot #{self.bot_id}: Rate limited, waiting {wait_time:.1f}s")
                await asyncio.sleep(wait_time)
                self.retry_after = 0
                return await self.acquire(wait=False)
            else:
                return False
        
        # Check if under limit
        if len(self.requests) < self.limit:
            self.requests.append((now, "request"))
            return True
        
        if wait:
            # Calculate wait time
            oldest = self.requests[0][0]
            wait_time = max(0.01, self.window - (now - oldest))
            await asyncio.sleep(wait_time)
            return await self.acquire(wait=False)
        
        return False
    
    def on_429(self, retry_after: int):
        """
        Handle 429 Too Many Requests error from Telegram
        
        Args:
            retry_after: Seconds to wait before retry
        """
        self.retry_after = time.time() + retry_after
        print(f"⚠️ Bot #{self.bot_id}: 429 error, retry after {retry_after}s")
    
    def get_current_rate(self) -> float:
        """Get current request rate (requests per second)"""
        if not self.requests:
            return 0
        
        now = time.time()
        old_requests = sum(1 for ts, _ in self.requests if ts > now - 1)
        return old_requests / 1.0


class RateLimiterPool:
    """
    Manage rate limiters for all bots
    """
    
    def __init__(self):
        self.limiters = {}  # bot_id -> BotRateLimiter
    
    def get_limiter(self, bot_id: int, limit: int = 30) -> BotRateLimiter:
        """Get or create limiter for bot"""
        if bot_id not in self.limiters:
            self.limiters[bot_id] = BotRateLimiter(bot_id, limit)
        return self.limiters[bot_id]
    
    async def acquire(self, bot_id: int) -> bool:
        """Acquire permission to send message"""
        limiter = self.get_limiter(bot_id)
        return await limiter.acquire(wait=True)
    
    def on_429(self, bot_id: int, retry_after: int):
        """Handle 429 error"""
        limiter = self.get_limiter(bot_id)
        limiter.on_429(retry_after)
    
    def get_status(self) -> Dict:
        """Get status of all limiters"""
        return {
            bot_id: {
                "rate": limiter.get_current_rate(),
                "queued_requests": len(limiter.requests),
                "retry_after": limiter.retry_after
            }
            for bot_id, limiter in self.limiters.items()
        }

# Global instance
rate_limiter_pool = RateLimiterPool()
