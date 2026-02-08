"""
Deep Research Service for LocalAIChatBox.
Self-contained deep research engine - NO external LDR dependency required.
Uses built-in AdvancedResearchEngine with multiple strategies,
multi-engine search, and structured report generation.

Phase 5: Fully integrated research engine replacing LDR dependency.
"""
import json
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Dict, Optional

from sqlalchemy.orm import Session
from app.models import ResearchTask
from app.ldr_settings import build_settings_snapshot
from app.advanced_research import (
    AdvancedResearchEngine, get_research_engine,
    STRATEGIES, ResearchState,
)
from app.citation_handler import CitationHandler

# Re-export STRATEGIES for backward compatibility
__all__ = ["DeepResearchService", "get_research_service", "STRATEGIES"]


class DeepResearchService:
    """Service for running deep research tasks using the built-in engine."""

    def __init__(self):
        self._active_tasks: Dict[str, dict] = {}
        self._executor = ThreadPoolExecutor(max_workers=3)
        self._engine = get_research_engine()

    def start_research(self, query: str, strategy: str, user_id: int,
                       db: Session, overrides: Optional[Dict] = None) -> str:
        """Start a deep research task in a background thread."""
        # Create task in database
        task = ResearchTask(
            user_id=user_id,
            query=query,
            strategy=strategy,
            status="pending",
            progress=0.0,
            progress_message="Initializing research..."
        )
        db.add(task)
        db.commit()
        db.refresh(task)

        task_id = task.id

        # Track in memory
        self._active_tasks[task_id] = {
            "status": "pending",
            "progress": 0.0,
            "message": "Initializing research..."
        }

        # Build settings snapshot
        snapshot = build_settings_snapshot(db, overrides)

        # Submit to thread pool
        self._executor.submit(self._run_research, task_id, query, strategy, snapshot, user_id)

        return task_id

    def _run_research(self, task_id: str, query: str, strategy: str,
                      snapshot: dict, user_id: int):
        """Run the actual research in a background thread."""
        from app.database import SessionLocal

        db = SessionLocal()
        try:
            # Update status to running
            self._update_task(db, task_id, status="running", progress=5.0,
                              message="Initializing research engine...")

            # Progress callback
            def on_progress(progress: float, message: str):
                self._update_task(db, task_id, progress=progress, message=message)

            # Run research using built-in engine
            state = self._engine.run_research(
                query=query,
                strategy=strategy,
                settings=snapshot,
                progress_callback=on_progress,
            )

            # Process results
            self._update_task(db, task_id, progress=90.0,
                              message="Processing research results...")

            # Build citation handler
            citation_handler = CitationHandler()
            citation_handler.add_from_search_results(state.sources)

            # Save to database
            task = db.query(ResearchTask).filter(ResearchTask.id == task_id).first()
            if task:
                task.status = "completed"
                task.progress = 100.0
                task.progress_message = "Research completed"
                task.result_knowledge = state.knowledge_summary or ""
                task.result_sources = json.dumps(state.sources[:30], default=str)

                # Build metadata
                metadata = {
                    "strategy": state.strategy,
                    "iterations": state.iteration,
                    "total_searches": state.total_searches,
                    "total_findings": len(state.findings),
                    "total_sources": len(state.sources),
                    "sub_questions": state.sub_questions,
                    "answered_questions": state.answered_questions,
                    "duration_seconds": round(
                        (datetime.utcnow() - datetime.utcfromtimestamp(state.start_time)).total_seconds()
                    ) if state.start_time else 0,
                    "citations": citation_handler.get_all_citations(),
                }
                task.result_metadata = json.dumps(metadata, default=str)
                task.completed_at = datetime.utcnow()
                db.commit()

            self._active_tasks[task_id] = {
                "status": "completed",
                "progress": 100.0,
                "message": "Research completed"
            }

            # Send notification
            try:
                from app.notification_service import get_notification_service
                notifier = get_notification_service()
                if notifier.available:
                    from app.models import User
                    user = db.query(User).filter(User.id == user_id).first()
                    notifier.notify_research_complete(
                        task_id=task_id,
                        query=query,
                        user_email=user.email if user else None,
                        status="completed",
                    )
            except Exception:
                pass

            # Track token usage
            try:
                from app.token_tracker import get_token_tracker
                tracker = get_token_tracker()
                total_input = sum(len(f.content) for f in state.findings)
                tracker.track_usage(
                    db=db,
                    user_id=user_id,
                    model=snapshot.get("llm.model", "llama3.1"),
                    input_text="x" * min(total_input // 4, 10000),
                    output_text=state.knowledge_summary or "",
                    action="research",
                    resource_id=task_id,
                )
            except Exception:
                pass

        except Exception as e:
            error_msg = f"{str(e)}\n{traceback.format_exc()}"
            print(f"Research task {task_id} failed: {error_msg}")

            try:
                task = db.query(ResearchTask).filter(ResearchTask.id == task_id).first()
                if task:
                    task.status = "failed"
                    task.error_message = error_msg[:2000]
                    task.progress_message = f"Failed: {str(e)[:200]}"
                    db.commit()
            except Exception:
                pass

            self._active_tasks[task_id] = {
                "status": "failed",
                "progress": 0.0,
                "message": f"Failed: {str(e)[:200]}"
            }

            # Notify failure
            try:
                from app.notification_service import get_notification_service
                notifier = get_notification_service()
                if notifier.available:
                    notifier.notify_research_complete(
                        task_id=task_id, query=query, status="failed",
                    )
            except Exception:
                pass
        finally:
            db.close()

    def generate_report(self, task_id: str, db: Session) -> Dict:
        """Generate a detailed report from research findings."""
        task = db.query(ResearchTask).filter(ResearchTask.id == task_id).first()
        if not task:
            raise ValueError(f"Task {task_id} not found")
        if task.status != "completed":
            raise ValueError(f"Task is not completed (status: {task.status})")

        try:
            snapshot = build_settings_snapshot(db)

            # Reconstruct research state
            state = ResearchState(
                query=task.query,
                strategy=task.strategy or "source-based",
            )
            state.knowledge_summary = task.result_knowledge or ""

            try:
                state.sources = json.loads(task.result_sources) if task.result_sources else []
            except (json.JSONDecodeError, TypeError):
                state.sources = []

            try:
                metadata = json.loads(task.result_metadata) if task.result_metadata else {}
                state.iteration = metadata.get("iterations", 1)
                state.sub_questions = metadata.get("sub_questions", [])
                state.total_searches = metadata.get("total_searches", 0)
            except (json.JSONDecodeError, TypeError):
                pass

            # Generate report using built-in engine
            report_content = self._engine.generate_report(
                query=task.query,
                state=state,
                settings=snapshot,
            )

            # Save report to task
            task.result_report = report_content
            db.commit()

            return {"report": report_content, "task_id": task_id}

        except Exception as e:
            raise ValueError(f"Report generation failed: {str(e)}")

    def get_progress(self, task_id: str, db: Session) -> Dict:
        """Get the progress of a research task."""
        if task_id in self._active_tasks:
            return self._active_tasks[task_id]

        task = db.query(ResearchTask).filter(ResearchTask.id == task_id).first()
        if not task:
            return {"status": "not_found", "progress": 0, "message": "Task not found"}

        return {
            "status": task.status,
            "progress": task.progress or 0,
            "message": task.progress_message or ""
        }

    def cancel_task(self, task_id: str, db: Session) -> bool:
        """Cancel a running research task."""
        task = db.query(ResearchTask).filter(ResearchTask.id == task_id).first()
        if not task:
            return False

        if task.status in ("pending", "running"):
            task.status = "cancelled"
            task.progress_message = "Cancelled by user"
            db.commit()

            if task_id in self._active_tasks:
                self._active_tasks[task_id]["status"] = "cancelled"
                self._active_tasks[task_id]["message"] = "Cancelled by user"

        return True

    def _update_task(self, db: Session, task_id: str, status: str = None,
                     progress: float = None, message: str = None):
        """Update task progress in both DB and memory."""
        try:
            task = db.query(ResearchTask).filter(ResearchTask.id == task_id).first()
            if task:
                if status:
                    task.status = status
                if progress is not None:
                    task.progress = progress
                if message:
                    task.progress_message = message
                db.commit()
        except Exception as e:
            print(f"Warning: Could not update task {task_id}: {e}")
            try:
                db.rollback()
            except Exception:
                pass

        if task_id not in self._active_tasks:
            self._active_tasks[task_id] = {}
        if status:
            self._active_tasks[task_id]["status"] = status
        if progress is not None:
            self._active_tasks[task_id]["progress"] = progress
        if message:
            self._active_tasks[task_id]["message"] = message


# Singleton
_research_service: Optional[DeepResearchService] = None


def get_research_service() -> DeepResearchService:
    global _research_service
    if _research_service is None:
        _research_service = DeepResearchService()
    return _research_service
