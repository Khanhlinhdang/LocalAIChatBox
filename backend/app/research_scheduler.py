"""
Research Scheduler for LocalAIChatBox.
Schedule recurring research tasks with cron-like scheduling.
Inspired by local-deep-research's APScheduler-based scheduling.
"""

import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class ResearchScheduler:
    """Manages scheduled research tasks.
    Uses a simple threading-based scheduler (no external dependency).
    """

    def __init__(self):
        self._schedules: Dict[str, Dict] = {}
        self._running = False
        self._thread = None
        self._lock = threading.Lock()

    def start(self):
        """Start the scheduler background thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("Research Scheduler started")

    def stop(self):
        """Stop the scheduler."""
        self._running = False

    def add_schedule(self, schedule_id: str, query: str, strategy: str,
                     user_id: int, interval_hours: int = 24,
                     name: str = None, enabled: bool = True) -> Dict:
        """Add a scheduled research task."""
        with self._lock:
            schedule = {
                "id": schedule_id,
                "name": name or f"Schedule: {query[:50]}",
                "query": query,
                "strategy": strategy,
                "user_id": user_id,
                "interval_hours": interval_hours,
                "enabled": enabled,
                "last_run": None,
                "next_run": datetime.utcnow() + timedelta(hours=interval_hours),
                "run_count": 0,
                "last_task_id": None,
                "created_at": datetime.utcnow().isoformat(),
            }
            self._schedules[schedule_id] = schedule
            logger.info(f"Added schedule '{schedule_id}': {query[:50]}")
            return schedule

    def remove_schedule(self, schedule_id: str) -> bool:
        """Remove a scheduled task."""
        with self._lock:
            if schedule_id in self._schedules:
                del self._schedules[schedule_id]
                return True
            return False

    def update_schedule(self, schedule_id: str, **kwargs) -> Optional[Dict]:
        """Update a scheduled task."""
        with self._lock:
            if schedule_id not in self._schedules:
                return None
            for key, value in kwargs.items():
                if key in self._schedules[schedule_id]:
                    self._schedules[schedule_id][key] = value
            return self._schedules[schedule_id]

    def get_schedule(self, schedule_id: str) -> Optional[Dict]:
        """Get a specific schedule."""
        return self._schedules.get(schedule_id)

    def get_all_schedules(self, user_id: int = None) -> List[Dict]:
        """Get all schedules, optionally filtered by user."""
        schedules = list(self._schedules.values())
        if user_id:
            schedules = [s for s in schedules if s["user_id"] == user_id]
        return schedules

    def _run_loop(self):
        """Background loop to check and execute scheduled tasks."""
        while self._running:
            try:
                now = datetime.utcnow()
                with self._lock:
                    for schedule_id, schedule in list(self._schedules.items()):
                        if not schedule["enabled"]:
                            continue

                        next_run = schedule.get("next_run")
                        if next_run and isinstance(next_run, str):
                            next_run = datetime.fromisoformat(next_run)

                        if next_run and now >= next_run:
                            self._execute_scheduled_task(schedule)
            except Exception as e:
                logger.error(f"Scheduler loop error: {e}")

            # Check every 60 seconds
            time.sleep(60)

    def _execute_scheduled_task(self, schedule: Dict):
        """Execute a scheduled research task."""
        try:
            from app.database import SessionLocal
            from app.deep_research import get_research_service

            db = SessionLocal()
            try:
                service = get_research_service()
                task_id = service.start_research(
                    query=schedule["query"],
                    strategy=schedule["strategy"],
                    user_id=schedule["user_id"],
                    db=db,
                )

                # Update schedule
                schedule["last_run"] = datetime.utcnow().isoformat()
                schedule["next_run"] = datetime.utcnow() + timedelta(hours=schedule["interval_hours"])
                schedule["run_count"] = schedule.get("run_count", 0) + 1
                schedule["last_task_id"] = task_id

                logger.info(f"Scheduled research started: {schedule['id']} -> task {task_id}")

                # Send notification
                try:
                    from app.notification_service import get_notification_service
                    notifier = get_notification_service()
                    notifier.notify_scheduled_research(
                        schedule["name"],
                        task_id,
                        schedule["query"],
                    )
                except Exception:
                    pass

            finally:
                db.close()

        except Exception as e:
            logger.error(f"Failed to execute scheduled task {schedule['id']}: {e}")

    def get_status(self) -> Dict:
        """Get scheduler status."""
        return {
            "running": self._running,
            "total_schedules": len(self._schedules),
            "active_schedules": sum(1 for s in self._schedules.values() if s["enabled"]),
        }


# Singleton
_scheduler: Optional[ResearchScheduler] = None


def get_research_scheduler() -> ResearchScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = ResearchScheduler()
    return _scheduler
