"""
Deep Research Service - Wraps LDR's AdvancedSearchSystem and IntegratedReportGenerator
for programmatic use within the ChatBox backend.

NOTE: Deep Research feature requires local-deep-research package.
If not installed, the service will return error messages gracefully.
"""
import json
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Dict, Optional

from sqlalchemy.orm import Session
from app.models import ResearchTask
from app.ldr_settings import build_settings_snapshot

# Check if local-deep-research is available
LDR_AVAILABLE = False
LDR_ERROR = None

try:
    import local_deep_research
    LDR_AVAILABLE = True
except ImportError as e:
    LDR_ERROR = f"local-deep-research package not installed: {str(e)}"
    print(f"WARNING: {LDR_ERROR}")
    print("Deep Research features will be disabled.")


# Available research strategies
STRATEGIES = [
    {"id": "source-based", "name": "Source-Based", "description": "Comprehensive source tracking with citations (default)", "best_for": "General research"},
    {"id": "rapid", "name": "Rapid", "description": "Speed-optimized single-pass search", "best_for": "Quick answers"},
    {"id": "parallel", "name": "Parallel", "description": "Concurrent multi-query search", "best_for": "Thorough analysis"},
    {"id": "standard", "name": "Standard", "description": "Balanced iterative search", "best_for": "General use"},
    {"id": "iterative", "name": "Iterative", "description": "Loop-based persistent knowledge building", "best_for": "Complex topics"},
    {"id": "focused-iteration", "name": "Focused Iteration", "description": "Adaptive refinement with focus", "best_for": "Deep analysis"},
    {"id": "smart", "name": "Smart", "description": "Auto-selects best strategy for the query", "best_for": "Auto"},
]


class DeepResearchService:
    """Service for running deep research tasks using LDR."""

    def __init__(self):
        self._active_tasks: Dict[str, dict] = {}
        self._executor = ThreadPoolExecutor(max_workers=3)
        self._ldr_available = LDR_AVAILABLE

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

        # Check if LDR is available
        if not self._ldr_available:
            task.status = "failed"
            task.error_message = LDR_ERROR or "local-deep-research not available"
            task.progress_message = "Deep Research feature is not installed"
            db.commit()
            
            self._active_tasks[task_id] = {
                "status": "failed",
                "progress": 0.0,
                "message": "Deep Research feature is not installed. Please install local-deep-research package."
            }
            return task_id

        # Track in memory
        self._active_tasks[task_id] = {
            "status": "pending",
            "progress": 0.0,
            "message": "Initializing research..."
        }

        # Build settings snapshot
        snapshot = build_settings_snapshot(db, overrides)

        # Submit to thread pool
        self._executor.submit(self._run_research, task_id, query, strategy, snapshot)

        return task_id

    def _run_research(self, task_id: str, query: str, strategy: str, snapshot: dict):
        """Run the actual research in a background thread."""
        from app.database import SessionLocal

        db = SessionLocal()
        try:
            # Update status to running
            self._update_task(db, task_id, status="running", progress=5.0,
                              message="Loading AI models...")

            # Import LDR modules
            from local_deep_research.config.llm_config import get_llm
            from local_deep_research.config.search_config import get_search
            from local_deep_research.search_system import AdvancedSearchSystem

            # Create LLM instance
            self._update_task(db, task_id, progress=10.0,
                              message="Connecting to LLM...")

            llm = get_llm(
                provider=snapshot.get("llm.provider", "ollama"),
                model_name=snapshot.get("llm.model", "llama3.1"),
                temperature=snapshot.get("llm.temperature", 0.7),
                settings_snapshot=snapshot
            )

            # Create search engine
            self._update_task(db, task_id, progress=15.0,
                              message="Initializing search engine...")

            search = get_search(
                search_tool=snapshot.get("search.tool", "searxng"),
                llm_instance=llm,
                programmatic_mode=True,
                settings_snapshot=snapshot
            )

            # Create search system
            self._update_task(db, task_id, progress=20.0,
                              message="Starting deep research...")

            search_system = AdvancedSearchSystem(
                llm=llm,
                search=search,
                strategy_name=strategy,
                max_iterations=snapshot.get("search.iterations", 3),
                questions_per_iteration=snapshot.get("search.questions_per_iteration", 3),
                programmatic_mode=True,
                settings_snapshot=snapshot
            )

            # Run research
            self._update_task(db, task_id, progress=25.0,
                              message=f"Researching: {query[:80]}...")

            results = search_system.analyze_topic(query)

            # Process results
            self._update_task(db, task_id, progress=85.0,
                              message="Processing research results...")

            # Extract knowledge and sources from results
            knowledge = ""
            sources_list = []
            metadata = {}

            if isinstance(results, dict):
                knowledge = results.get("knowledge", results.get("report", ""))
                if not knowledge:
                    # Try to extract from different result formats
                    for key in ["findings", "summary", "content", "result"]:
                        if key in results:
                            knowledge = str(results[key])
                            break
                    if not knowledge:
                        knowledge = json.dumps(results, indent=2, default=str)

                sources_list = results.get("sources", [])
                if isinstance(sources_list, dict):
                    sources_list = [sources_list]

                metadata = {
                    k: v for k, v in results.items()
                    if k not in ("knowledge", "report", "sources", "findings")
                    and not isinstance(v, (bytes, type))
                }

            # Save to database
            task = db.query(ResearchTask).filter(ResearchTask.id == task_id).first()
            if task:
                task.status = "completed"
                task.progress = 100.0
                task.progress_message = "Research completed"
                task.result_knowledge = str(knowledge) if knowledge else ""
                task.result_sources = json.dumps(sources_list, default=str)
                task.result_metadata = json.dumps(metadata, default=str)
                task.completed_at = datetime.utcnow()
                db.commit()

            self._active_tasks[task_id] = {
                "status": "completed",
                "progress": 100.0,
                "message": "Research completed"
            }

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
        finally:
            db.close()

    def generate_report(self, task_id: str, db: Session) -> Dict:
        """Generate a detailed report from research findings."""
        # Check if LDR is available
        if not self._ldr_available:
            return {
                "error": "Deep Research feature is not installed",
                "message": LDR_ERROR or "local-deep-research package not available",
                "task_id": task_id
            }
            
        task = db.query(ResearchTask).filter(ResearchTask.id == task_id).first()
        if not task:
            raise ValueError(f"Task {task_id} not found")
        if task.status != "completed":
            raise ValueError(f"Task is not completed (status: {task.status})")

        try:
            from local_deep_research.config.llm_config import get_llm
            from local_deep_research.config.search_config import get_search
            from local_deep_research.search_system import AdvancedSearchSystem
            from local_deep_research.report_generator import IntegratedReportGenerator

            snapshot = build_settings_snapshot(db)

            llm = get_llm(
                provider=snapshot.get("llm.provider", "ollama"),
                model_name=snapshot.get("llm.model", "llama3.1"),
                temperature=snapshot.get("llm.temperature", 0.7),
                settings_snapshot=snapshot
            )

            search = get_search(
                search_tool=snapshot.get("search.tool", "searxng"),
                llm_instance=llm,
                programmatic_mode=True,
                settings_snapshot=snapshot
            )

            search_system = AdvancedSearchSystem(
                llm=llm,
                search=search,
                strategy_name=task.strategy or "source-based",
                programmatic_mode=True,
                settings_snapshot=snapshot
            )

            report_gen = IntegratedReportGenerator(
                searches_per_section=snapshot.get("report.searches_per_section", 2),
                search_system=search_system,
                llm=llm,
                settings_snapshot=snapshot
            )

            # Build initial findings from stored results
            initial_findings = {
                "knowledge": task.result_knowledge or "",
                "sources": json.loads(task.result_sources) if task.result_sources else []
            }

            report_result = report_gen.generate_report(
                initial_findings=initial_findings,
                query=task.query
            )

            # Extract report content
            report_content = ""
            if isinstance(report_result, dict):
                report_content = report_result.get("content", report_result.get("report", ""))
                if not report_content:
                    report_content = json.dumps(report_result, indent=2, default=str)
            else:
                report_content = str(report_result)

            # Save report to task
            task.result_report = report_content
            db.commit()

            return {"report": report_content, "task_id": task_id}

        except Exception as e:
            raise ValueError(f"Report generation failed: {str(e)}")

    def get_progress(self, task_id: str, db: Session) -> Dict:
        """Get the progress of a research task."""
        # Check in-memory cache first (for active tasks)
        if task_id in self._active_tasks:
            return self._active_tasks[task_id]

        # Fall back to database
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

        # Always update in-memory
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
