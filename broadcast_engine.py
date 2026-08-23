from db import db
from priority_queue import job_queue, JobPriority
from message_sender import message_sender
from rate_limiter import rate_limiter_pool
from typing import Optional
import json
import time

class BroadcastEngine:
    """
    Broadcast messages to multiple users efficiently
    
    Uses streaming/batching to avoid RAM overload
    """
    
    async def start_broadcast(self, bot_id: int, text: str, 
                             batch_size: int = 1000) -> int:
        """
        Start broadcast to all users
        
        Args:
            bot_id: Bot sending broadcast
            text: Message text
            batch_size: Users to process per batch
        
        Returns:
            broadcast_id for tracking
        """
        if not isinstance(bot_id, int) or bot_id <= 0:
            raise ValueError("invalid bot_id")
        if not text or not isinstance(text, str):
            raise ValueError("broadcast text must be a non-empty string")
        if not isinstance(batch_size, int) or batch_size <= 0:
            batch_size = 1000
        
        # Create broadcast record. `data` carries both the message text and
        # the resume checkpoint (offset), so a restart can pick up where it
        # left off instead of re-sending to everyone from the start.
        data = json.dumps({"text": text, "offset": 0})
        cursor = await db.connection.execute(
            """INSERT INTO queue_jobs (bot_id, job_type, status, priority, data)
               VALUES (?, ?, ?, ?, ?)""",
            (bot_id, "broadcast", "processing", JobPriority.LOW.value, data)
        )
        await db.connection.commit()
        
        broadcast_id = cursor.lastrowid
        print(f"📢 Broadcast #{broadcast_id} started")
        
        # Queue broadcast job
        await job_queue.add_job(
            f"broadcast_{bot_id}_{broadcast_id}",
            JobPriority.LOW,
            self._execute_broadcast,
            bot_id,
            text,
            broadcast_id,
            batch_size,
            0,  # start_offset
        )
        
        return broadcast_id
    
    async def resume_pending_broadcasts(self):
        """Call on startup: any broadcast left in 'processing' status when
        the process died gets requeued from its last checkpointed offset
        instead of being silently abandoned or restarted from zero."""
        cursor = await db.connection.execute(
            "SELECT job_id, bot_id, data FROM queue_jobs WHERE job_type = 'broadcast' AND status = 'processing'"
        )
        rows = await cursor.fetchall()
        
        for job_id, bot_id, data_str in rows:
            try:
                data = json.loads(data_str) if data_str else {}
            except (json.JSONDecodeError, TypeError):
                data = {}
            
            text = data.get("text")
            offset = data.get("offset", 0)
            if not text:
                continue
            
            print(f"🔁 Resuming broadcast #{job_id} for bot #{bot_id} from offset {offset}")
            await job_queue.add_job(
                f"broadcast_resume_{bot_id}_{job_id}",
                JobPriority.LOW,
                self._execute_broadcast,
                bot_id,
                text,
                job_id,
                1000,
                offset,
            )
    
    async def _execute_broadcast(self, bot_id: int, text: str, 
                                broadcast_id: int, batch_size: int = 1000,
                                start_offset: int = 0):
        """
        Execute broadcast in background
        Uses streaming to avoid loading all users into RAM.
        Checkpoints its offset into queue_jobs.data after every batch so a
        crash/restart resumes instead of re-sending to already-messaged users.
        """
        
        total_sent = 0
        total_failed = 0
        start_time = time.time()
        
        offset = start_offset
        while True:
            # Bail out early if the broadcast was cancelled mid-run
            cursor = await db.connection.execute(
                "SELECT status FROM queue_jobs WHERE job_id = ?", (broadcast_id,)
            )
            row = await cursor.fetchone()
            if row and row[0] == "cancelled":
                print(f"⏹️ Broadcast #{broadcast_id} cancelled - stopping")
                return
            
            # Get batch of users
            cursor = await db.connection.execute(
                """SELECT chat_id FROM bot_users 
                   WHERE bot_id = ? AND is_blocked = 0
                   ORDER BY id LIMIT ? OFFSET ?""",
                (bot_id, batch_size, offset)
            )
            
            batch = await cursor.fetchall()
            if not batch:
                break  # No more users
            
            # Process batch
            for (chat_id,) in batch:
                result = await message_sender.send_message(
                    bot_id, chat_id, text
                )
                
                if result:
                    total_sent += 1
                else:
                    total_failed += 1
            
            offset += batch_size
            
            # Checkpoint progress so a restart resumes from here, not zero
            checkpoint = json.dumps({"text": text, "offset": offset})
            await db.connection.execute(
                "UPDATE queue_jobs SET data = ? WHERE job_id = ?",
                (checkpoint, broadcast_id)
            )
            await db.connection.commit()
            
            print(f"  📤 Batch progress: {offset} users processed")
        
        # Get blocked count
        cursor = await db.connection.execute(
            "SELECT COUNT(*) FROM bot_users WHERE bot_id = ? AND is_blocked = 1",
            (bot_id,)
        )
        total_blocked = (await cursor.fetchone())[0]
        
        # Calculate statistics
        end_time = time.time()
        duration = end_time - start_time
        total_users = total_sent + total_failed
        success_rate = (total_sent / total_users * 100) if total_users > 0 else 0
        
        # Save broadcast result
        stats = {
            "sent": total_sent,
            "failed": total_failed,
            "blocked": total_blocked,
            "total": total_users,
            "success_rate": success_rate,
            "duration": duration
        }
        
        await db.connection.execute(
            """UPDATE queue_jobs SET status = ?, data = ?, completed_at = CURRENT_TIMESTAMP
               WHERE job_id = ?""",
            ("completed", json.dumps(stats), broadcast_id)
        )
        await db.connection.commit()
        
        print(f"✅ Broadcast #{broadcast_id} completed")
        print(f"   📊 Sent: {total_sent} | Failed: {total_failed} | Blocked: {total_blocked}")
        print(f"   ⏱️ Duration: {duration:.1f}s | Success: {success_rate:.1f}%")
        
        level = "warning" if success_rate < 80 and total_users > 0 else "info"
        await db.add_log(level, f"bot:{bot_id}",
                          f"Broadcast #{broadcast_id} done: sent={total_sent} failed={total_failed} "
                          f"blocked={total_blocked} success={success_rate:.0f}%")
    
    async def get_broadcast_status(self, broadcast_id: int) -> Optional[dict]:
        """Get broadcast status"""
        
        cursor = await db.connection.execute(
            """SELECT status, data, created_at, completed_at 
               FROM queue_jobs WHERE job_id = ?""",
            (broadcast_id,)
        )
        
        row = await cursor.fetchone()
        if not row:
            return None
        
        try:
            stats = json.loads(row[1]) if row[1] else {}
        except (json.JSONDecodeError, TypeError):
            stats = {}
        
        return {
            "id": broadcast_id,
            "status": row[0],
            "stats": stats,
            "created_at": row[2],
            "completed_at": row[3]
        }
    
    async def cancel_broadcast(self, broadcast_id: int) -> bool:
        """Cancel ongoing broadcast (checked cooperatively between batches)"""
        
        try:
            await db.connection.execute(
                "UPDATE queue_jobs SET status = ? WHERE job_id = ?",
                ("cancelled", broadcast_id)
            )
            await db.connection.commit()
            return True
        except Exception as e:
            print(f"❌ Error cancelling broadcast #{broadcast_id}: {e}")
            return False

# Global instance
broadcast_engine = BroadcastEngine()
