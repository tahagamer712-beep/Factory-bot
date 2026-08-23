#!/usr/bin/env python3
"""
Test Phase 3: Priority Queue + Rate Limiting
"""

import asyncio
from priority_queue import job_queue, JobPriority
from rate_limiter import rate_limiter_pool

async def test_job(job_id: str, duration: float = 1):
    """Dummy job for testing"""
    print(f"  ⏳ Job {job_id} processing for {duration}s...")
    await asyncio.sleep(duration)
    return f"Job {job_id} completed"

async def test_phase3():
    print("🧪 Phase 3 Testing: Priority Queue + Rate Limiting")
    print("=" * 50)
    
    # Test 1: Priority Queue
    print("\n✓ Test 1: Priority Queue")
    print("  Adding jobs with different priorities...")
    
    # Start queue workers
    workers_task = asyncio.create_task(job_queue.start_workers())
    await asyncio.sleep(0.5)  # Let workers start
    
    # Add jobs with different priorities
    await job_queue.add_job("job_low_1", JobPriority.LOW, test_job, "low_1", 0.5)
    await job_queue.add_job("job_high_1", JobPriority.HIGH, test_job, "high_1", 0.5)
    await job_queue.add_job("job_low_2", JobPriority.LOW, test_job, "low_2", 0.5)
    await job_queue.add_job("job_high_2", JobPriority.HIGH, test_job, "high_2", 0.5)
    
    # Wait for processing
    await asyncio.sleep(3)
    
    # Check status
    status = job_queue.get_status()
    print(f"  ✅ Queue status: {status}")
    print(f"  ✅ Completed {len(job_queue.completed_jobs)} job(s)")
    
    # Verify HIGH priority was processed first
    if job_queue.completed_jobs:
        first_job = job_queue.completed_jobs[0]
        if first_job.priority == JobPriority.HIGH:
            print(f"  ✅ HIGH priority job processed first (as expected)")
        else:
            print(f"  ⚠️ Priority ordering may not be correct")
    
    # Stop workers
    await job_queue.stop_workers()
    
    # Test 2: Rate Limiter
    print("\n✓ Test 2: Rate Limiter")
    
    bot_id = 123456789
    limiter = rate_limiter_pool.get_limiter(bot_id, limit=5)
    
    print(f"  Bot #{bot_id}: Max 5 requests per second")
    
    # Send 10 requests
    print("  Sending 10 requests...")
    for i in range(10):
        allowed = await limiter.acquire(wait=False)
        if allowed:
            print(f"    Request {i+1}: ✅ Allowed")
        else:
            print(f"    Request {i+1}: ⏳ Rate limited (waiting...)")
            await limiter.acquire(wait=True)
            print(f"    Request {i+1}: ✅ Allowed (after wait)")
    
    # Test 429 error handling
    print("\n✓ Test 3: 429 Error Handling")
    limiter.on_429(5)
    print(f"  ✅ 429 error registered (retry after 5s)")
    
    allowed = await limiter.acquire(wait=False)
    print(f"  ✅ Rate limiter blocked requests: {not allowed}")
    
    print("\n" + "=" * 50)
    print("✅ Phase 3 Tests Complete!")
    print("=" * 50)

if __name__ == "__main__":
    asyncio.run(test_phase3())
