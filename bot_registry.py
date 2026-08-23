from typing import List, Dict, Optional
from db import db

class BotRegistry:
    """Manage all registered bots and their tokens"""
    
    def __init__(self):
        self.bots = {}  # bot_id -> bot_info
    
    async def load_bots(self):
        """Load all bots from database"""
        bots = await db.get_all_bots()
        self.bots = {bot['bot_id']: bot for bot in bots}
        print(f"✅ Loaded {len(self.bots)} bots")
    
    async def register_bot(self, bot_id: int, token: str, owner_id: int, username: str) -> bool:
        """Register new bot"""
        if bot_id in self.bots:
            print(f"⚠️ Bot #{bot_id} already registered")
            return False
        
        success = await db.add_bot(bot_id, token, owner_id, username)
        if success:
            self.bots[bot_id] = {
                'bot_id': bot_id,
                'token': token,
                'owner_id': owner_id,
                'username': username
            }
        return success
    
    async def unregister_bot(self, bot_id: int) -> bool:
        """Remove bot"""
        success = await db.delete_bot(bot_id)
        if success and bot_id in self.bots:
            del self.bots[bot_id]
        return success
    
    def get_bot(self, bot_id: int) -> Optional[Dict]:
        """Get bot info"""
        return self.bots.get(bot_id)
    
    def get_token(self, bot_id: int) -> Optional[str]:
        """Get bot token"""
        bot = self.bots.get(bot_id)
        return bot['token'] if bot else None
    
    def get_all_bots(self) -> List[int]:
        """Get all bot IDs"""
        return list(self.bots.keys())
    
    def count(self) -> int:
        """Get total bots"""
        return len(self.bots)
    
    def list_bots(self) -> List[Dict]:
        """List all bots with info"""
        return list(self.bots.values())

# Global instance
bot_registry = BotRegistry()
