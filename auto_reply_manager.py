from db import db
from typing import List

class AutoReplyManager:
    """Manage auto-reply keywords and responses"""
    
    async def add_auto_reply(self, bot_id: int, keyword: str, reply: str) -> bool:
        """
        Add keyword-based auto-reply
        
        Args:
            bot_id: Bot ID
            keyword: Regex pattern to match (e.g., "السلام|أهلا")
            reply: Message to send when matched
        """
        
        try:
            # Create table if not exists
            await db.connection.execute("""
                CREATE TABLE IF NOT EXISTS auto_replies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bot_id INTEGER NOT NULL,
                    keyword TEXT NOT NULL,
                    reply TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    active BOOLEAN DEFAULT 1,
                    FOREIGN KEY (bot_id) REFERENCES bots(bot_id) ON DELETE CASCADE,
                    UNIQUE(bot_id, keyword)
                )
            """)
            
            await db.connection.execute(
                """INSERT OR REPLACE INTO auto_replies (bot_id, keyword, reply, active)
                   VALUES (?, ?, ?, 1)""",
                (bot_id, keyword, reply)
            )
            
            await db.connection.commit()
            print(f"✅ Auto-reply added: '{keyword}'")
            return True
        
        except Exception as e:
            print(f"❌ Error adding auto-reply: {e}")
            return False
    
    async def remove_auto_reply(self, bot_id: int, keyword: str) -> bool:
        """Remove auto-reply"""
        
        try:
            await db.connection.execute(
                "DELETE FROM auto_replies WHERE bot_id = ? AND keyword = ?",
                (bot_id, keyword)
            )
            await db.connection.commit()
            print(f"✅ Auto-reply removed: '{keyword}'")
            return True
        except Exception as e:
            print(f"❌ Error removing auto-reply: {e}")
            return False
    
    async def get_auto_replies(self, bot_id: int) -> List[dict]:
        """Get all auto-replies for bot"""
        
        try:
            cursor = await db.connection.execute(
                """SELECT id, keyword, reply, active 
                   FROM auto_replies WHERE bot_id = ?""",
                (bot_id,)
            )
            
            rows = await cursor.fetchall()
            return [
                {
                    "id": row[0],
                    "keyword": row[1],
                    "reply": row[2],
                    "active": row[3]
                }
                for row in rows
            ]
        except:
            return []
    
    async def toggle_auto_reply(self, bot_id: int, keyword: str, active: bool) -> bool:
        """Enable/disable auto-reply"""
        
        try:
            await db.connection.execute(
                "UPDATE auto_replies SET active = ? WHERE bot_id = ? AND keyword = ?",
                (active, bot_id, keyword)
            )
            await db.connection.commit()
            status = "enabled" if active else "disabled"
            print(f"✅ Auto-reply {status}: '{keyword}'")
            return True
        except Exception as e:
            print(f"❌ Error updating auto-reply: {e}")
            return False

# Global instance
auto_reply_manager = AutoReplyManager()
