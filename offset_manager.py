from db import db
from typing import Dict

class OffsetManager:
    """
    Manage offsets for each bot
    This is CRITICAL - offsets prevent duplicate message processing
    """
    
    def __init__(self):
        self.offsets = {}  # bot_id -> offset value
    
    async def load_offsets(self):
        """Load all saved offsets from database"""
        bots = await db.get_all_bots()
        for bot in bots:
            offset = await db.get_offset(bot['bot_id'])
            self.offsets[bot['bot_id']] = offset
        
        print(f"✅ Loaded offsets for {len(self.offsets)} bots")
    
    def get_offset(self, bot_id: int) -> int:
        """
        Get current offset for bot
        
        Offset = last_update_id + 1
        This ensures we don't re-process messages
        """
        return self.offsets.get(bot_id, 0)
    
    async def update_offset(self, bot_id: int, update_id: int):
        """
        Update offset for bot
        
        Called after processing an update successfully
        Next getUpdates will start from update_id + 1
        
        DB is the source of truth: persist first, then mirror to the
        in-memory cache. If the DB write fails, the in-memory value is
        left untouched so the next poll re-fetches (and re-persists) the
        same update instead of the two getting out of sync.
        """
        new_offset = update_id + 1
        
        # Persist to database first
        await db.update_offset(bot_id, new_offset, update_id)
        
        # Only mirror to memory once the DB write succeeded
        self.offsets[bot_id] = new_offset
    
    def get_all_offsets(self) -> Dict[int, int]:
        """Get all offsets"""
        return self.offsets.copy()
    
    async def reset_offset(self, bot_id: int):
        """Reset offset to 0 (USE WITH CAUTION)"""
        self.offsets[bot_id] = 0
        await db.update_offset(bot_id, 0, 0)
        print(f"⚠️ Offset reset for bot #{bot_id}")

# Global instance
offset_manager = OffsetManager()
