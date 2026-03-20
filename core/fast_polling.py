"""Fast polling scheduler with intelligent backoff."""

from __future__ import annotations

import asyncio
from typing import Callable, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import random

@dataclass
class PollTask:
    """A polling task with adaptive frequency."""
    name: str
    query: str
    callback: Callable
    base_interval: int  # Base seconds between polls
    priority: int = 5  # 1-10, higher = poll more frequently
    last_run: Optional[datetime] = None
    last_hit: Optional[datetime] = None  # When we found a deal
    hit_count: int = 0
    miss_count: int = 0
    
    @property
    def current_interval(self) -> int:
        """Calculate current poll interval based on performance."""
        # If we found deals recently, poll faster
        if self.last_hit:
            hours_since_hit = (datetime.now() - self.last_hit).total_seconds() / 3600
            if hours_since_hit < 1:
                return max(15, self.base_interval // 3)  # 3x faster
            elif hours_since_hit < 6:
                return max(30, self.base_interval // 2)  # 2x faster
        
        # If many misses, slow down
        if self.miss_count > 10:
            return min(300, self.base_interval * 2)  # 2x slower, max 5min
        
        # Priority adjustment
        priority_mult = 1 + (10 - self.priority) / 10  # 1.0 to 1.9
        return int(self.base_interval * priority_mult)

class FastPollingScheduler:
    """Adaptive polling scheduler for multiple sources."""
    
    def __init__(self):
        self.tasks: Dict[str, PollTask] = {}
        self._running = False
        self._task_handles: List[asyncio.Task] = []
    
    def add_task(
        self,
        name: str,
        query: str,
        callback: Callable,
        base_interval: int = 60,
        priority: int = 5,
    ) -> PollTask:
        """Add a polling task."""
        task = PollTask(
            name=name,
            query=query,
            callback=callback,
            base_interval=base_interval,
            priority=priority,
        )
        self.tasks[name] = task
        return task
    
    def record_hit(self, task_name: str):
        """Record that a task found a deal."""
        if task_name in self.tasks:
            task = self.tasks[task_name]
            task.last_hit = datetime.now()
            task.hit_count += 1
            task.miss_count = 0
    
    def record_miss(self, task_name: str):
        """Record that a task found nothing."""
        if task_name in self.tasks:
            self.tasks[task_name].miss_count += 1
    
    async def _run_task(self, task: PollTask):
        """Run a single polling task with adaptive timing."""
        while self._running:
            try:
                task.last_run = datetime.now()
                result = await task.callback(task.query)
                
                if result:
                    self.record_hit(task.name)
                else:
                    self.record_miss(task.name)
                
                # Wait for next poll with jitter
                interval = task.current_interval
                jitter = random.uniform(0.8, 1.2)
                await asyncio.sleep(interval * jitter)
                
            except Exception as e:
                print(f"Poll task {task.name} error: {e}")
                await asyncio.sleep(60)  # Back off on error
    
    async def start(self):
        """Start all polling tasks."""
        self._running = True
        self._task_handles = [
            asyncio.create_task(self._run_task(task))
            for task in self.tasks.values()
        ]
        print(f"Started {len(self._task_handles)} polling tasks")
    
    async def stop(self):
        """Stop all polling tasks."""
        self._running = False
        for handle in self._task_handles:
            handle.cancel()
        await asyncio.gather(*self._task_handles, return_exceptions=True)
        self._task_handles = []
        print("Stopped all polling tasks")
    
    def get_stats(self) -> Dict:
        """Get polling statistics."""
        return {
            name: {
                "hits": task.hit_count,
                "misses": task.miss_count,
                "hit_rate": task.hit_count / (task.hit_count + task.miss_count) if (task.hit_count + task.miss_count) > 0 else 0,
                "current_interval": task.current_interval,
                "last_hit": task.last_hit.isoformat() if task.last_hit else None,
            }
            for name, task in self.tasks.items()
        }
