import asyncio
from typing import Any, Callable, Optional
from enum import Enum
import time

class JobPriority(Enum):
    """Job priority levels"""
    CRITICAL = 0  # System critical
    HIGH = 1      # User messages, commands
    NORMAL = 2    # Regular operations
    LOW = 3       # Background (broadcasts, backups)

class Job:
    """Single job in queue"""
    
    def __init__(self, job_id: str, priority: JobPriority, handler: Callable, *args, **kwargs):
        self.job_id = job_id
        self.priority = priority
        self.handler = handler
        self.args = args
        self.kwargs = kwargs
        self.created_at = time.time()
        self.started_at = None
        self.completed_at = None
        self.status = "pending"  # pending, processing, completed, failed
        self.result = None
        self.error = None
    
    async def execute(self):
        """Execute this job"""
        self.status = "processing"
        self.started_at = time.time()
        
        try:
            self.result = await self.handler(*self.args, **self.kwargs)
            self.status = "completed"
        except Exception as e:
            self.status = "failed"
            self.error = str(e)
        finally:
            self.completed_at = time.time()
    
    def get_wait_time(self) -> float:
        """How long this job waited before processing"""
        if self.started_at:
            return self.started_at - self.created_at
        return time.time() - self.created_at

class PriorityQueue:
    """
    Multi-priority queue for jobs
    
    HIGH priority: User messages, commands
    LOW priority: Broadcasts, backups (background)
    """
    
    def __init__(self, max_concurrent_jobs: int = 4):
        self.max_concurrent = max_concurrent_jobs
        self.queues = {
            JobPriority.CRITICAL: asyncio.Queue(),
            JobPriority.HIGH: asyncio.Queue(),
            JobPriority.NORMAL: asyncio.Queue(),
            JobPriority.LOW: asyncio.Queue(),
        }
        self.active_jobs = {}
        self.completed_jobs = []
        self.is_running = False
        self.worker_tasks = []
    
    async def add_job(self, job_id: str, priority: JobPriority, 
                      handler: Callable, *args, **kwargs) -> Job:
        """Add job to queue"""
        job = Job(job_id, priority, handler, *args, **kwargs)
        await self.queues[priority].put(job)
        
        print(f"📥 Job queued: {job_id} ({priority.name})")
        return job
    
    async def start_workers(self):
        """Start queue workers, with a watchdog that restarts any worker
        task that crashes out of its own try/except (unexpected exception
        during queue bookkeeping itself, not job execution errors - those
        are already caught inside Job.execute)."""
        self.is_running = True
        print(f"👷 Starting {self.max_concurrent} queue worker(s)")
        
        self.worker_tasks = [
            asyncio.create_task(self._worker(i))
            for i in range(self.max_concurrent)
        ]
        
        while self.is_running:
            await asyncio.sleep(10)
            for i, task in enumerate(self.worker_tasks):
                if task.done() and self.is_running:
                    exc = task.exception() if not task.cancelled() else None
                    print(f"🔁 Worker #{i} died unexpectedly ({exc}) - restarting")
                    self.worker_tasks[i] = asyncio.create_task(self._worker(i))
    
    async def _worker(self, worker_id: int):
        """Single worker process"""
        print(f"🔧 Worker #{worker_id} started")
        
        while self.is_running:
            job = None
            
            try:
                # Check queues in priority order
                for priority in [
                    JobPriority.CRITICAL,
                    JobPriority.HIGH,
                    JobPriority.NORMAL,
                    JobPriority.LOW
                ]:
                    try:
                        job = self.queues[priority].get_nowait()
                        break
                    except asyncio.QueueEmpty:
                        continue
                
                if job:
                    # Execute job
                    self.active_jobs[job.job_id] = job
                    print(f"⚙️ Worker #{worker_id} processing: {job.job_id}")
                    
                    await job.execute()
                    
                    self.completed_jobs.append(job)
                    # Cap history so this can't grow unbounded over a long run
                    if len(self.completed_jobs) > 500:
                        self.completed_jobs = self.completed_jobs[-500:]
                    del self.active_jobs[job.job_id]
                    
                    if job.status == "completed":
                        print(f"✅ Job completed: {job.job_id}")
                    else:
                        print(f"❌ Job failed: {job.job_id} - {job.error}")
                
                else:
                    # No jobs, sleep briefly
                    await asyncio.sleep(0.1)
            
            except Exception as e:
                print(f"❌ Worker #{worker_id} error: {type(e).__name__}: {e}")
                await asyncio.sleep(1)
    
    async def stop_workers(self):
        """Stop all workers"""
        self.is_running = False
        print("⏹️ Stopping queue workers...")
        tasks = getattr(self, "worker_tasks", [])
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    def get_status(self) -> dict:
        """Get queue status"""
        return {
            "total_queued": sum(q.qsize() for q in self.queues.values()),
            "active_jobs": len(self.active_jobs),
            "completed_jobs": len(self.completed_jobs),
            "queue_sizes": {
                priority.name: self.queues[priority].qsize()
                for priority in JobPriority
            }
        }
    
    def get_active_jobs(self):
        """Get currently processing jobs"""
        return dict(self.active_jobs)
    
    def get_completed_jobs(self, limit: int = 100):
        """Get recently completed jobs"""
        return self.completed_jobs[-limit:]

# Global instance
job_queue = PriorityQueue(max_concurrent_jobs=4)
