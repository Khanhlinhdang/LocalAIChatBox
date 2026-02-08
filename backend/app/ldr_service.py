"""
Local Deep Research (LDR) Integration Service for LocalAIChatBox.
Wraps the full LDR engine with 30+ strategies, 27+ search engines,
multi-provider LLM support, and advanced report generation.

This is the "Advanced Engine" counterpart to the built-in research engine.
"""
import json
import os
import sys
import traceback
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# ==================== LDR ENVIRONMENT SETUP ====================
# Configure LDR before importing its modules

# Add app directory to sys.path so LDR's absolute imports
# (e.g., "from local_deep_research.xxx") resolve correctly.
# At runtime in Docker, the code lives at /app/app/local_deep_research/
# so adding /app/app makes "local_deep_research" importable.
_app_dir = os.path.dirname(os.path.abspath(__file__))  # .../app/
if _app_dir not in sys.path:
    sys.path.insert(0, _app_dir)

# Ollama config for LDR
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_LLM_MODEL", "llama3.1")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")

# SearXNG config
SEARXNG_URL = os.getenv("SEARXNG_URL", "http://searxng:8080")

# Set LDR environment variables
os.environ.setdefault("LDR_LLM__PROVIDER", "ollama")
os.environ.setdefault("LDR_LLM__MODEL", OLLAMA_MODEL)
os.environ.setdefault("LDR_LLM__BASE_URL", OLLAMA_HOST)
os.environ.setdefault("LDR_SEARCH__TOOL", "auto")
os.environ.setdefault("LDR_SEARCH__SEARXNG_URL", SEARXNG_URL)
os.environ.setdefault("LDR_LLM__TEMPERATURE", "0.7")
os.environ.setdefault("OLLAMA_BASE_URL", OLLAMA_HOST)
os.environ.setdefault("LDR_ALLOW_UNENCRYPTED", "true")

# ==================== LDR STRATEGIES ====================
# All strategies available from LDR's search_system_factory
LDR_STRATEGIES = [
    {"id": "source-based", "name": "Source-Based", "category": "general",
     "description": "Comprehensive source tracking with atomic fact decomposition",
     "best_for": "General research with proper citations"},
    {"id": "focused-iteration", "name": "Focused Iteration", "category": "advanced",
     "description": "Adaptive refinement with early termination and knowledge limits",
     "best_for": "High-accuracy deep analysis"},
    {"id": "standard", "name": "Standard", "category": "general",
     "description": "Basic iterative search",
     "best_for": "Standard research tasks"},
    {"id": "iterdrag", "name": "IterDRAG", "category": "advanced",
     "description": "Iterative Dense Retrieval Augmented Generation",
     "best_for": "Dense retrieval focused research"},
    {"id": "parallel", "name": "Parallel", "category": "general",
     "description": "Multiple search queries executed concurrently",
     "best_for": "Broad topics needing multiple perspectives"},
    {"id": "rapid", "name": "Rapid", "category": "general",
     "description": "Quick single-pass search",
     "best_for": "Quick factual answers"},
    {"id": "recursive", "name": "Recursive", "category": "advanced",
     "description": "Recursive decomposition of complex queries",
     "best_for": "Complex multi-faceted topics"},
    {"id": "iterative", "name": "Iterative", "category": "general",
     "description": "Loop-based reasoning with confidence threshold",
     "best_for": "Topics requiring iterative refinement"},
    {"id": "adaptive", "name": "Adaptive", "category": "advanced",
     "description": "Adaptive step-by-step reasoning",
     "best_for": "Complex queries needing dynamic approach"},
    {"id": "smart", "name": "Smart", "category": "general",
     "description": "Auto-selects best strategy based on query analysis",
     "best_for": "Any topic - automatic strategy selection"},
    {"id": "browsecomp", "name": "BrowseComp", "category": "specialized",
     "description": "Optimized for puzzle-style queries with deep web search",
     "best_for": "Specific factual answers, puzzle-type questions"},
    {"id": "evidence", "name": "Evidence-Based", "category": "advanced",
     "description": "Enhanced evidence verification with pattern learning",
     "best_for": "Fact-checking and evidence-heavy research"},
    {"id": "constrained", "name": "Constrained", "category": "advanced",
     "description": "Progressive constraint-based narrowing",
     "best_for": "Finding specific items matching criteria"},
    {"id": "parallel-constrained", "name": "Parallel Constrained", "category": "advanced",
     "description": "Parallel constraint search with combined execution",
     "best_for": "Complex constraint-based research"},
    {"id": "early-stop-constrained", "name": "Early-Stop Constrained", "category": "advanced",
     "description": "Parallel with immediate evaluation, 99% confidence early stop",
     "best_for": "Quick constraint matching"},
    {"id": "smart-query", "name": "Smart Query", "category": "advanced",
     "description": "LLM-driven query generation with constraint evaluation",
     "best_for": "Complex search query optimization"},
    {"id": "dual-confidence", "name": "Dual Confidence", "category": "specialized",
     "description": "Positive/negative/uncertainty scoring with entity seeding",
     "best_for": "High-precision research with confidence scoring"},
    {"id": "concurrent-dual-confidence", "name": "Concurrent Dual", "category": "specialized",
     "description": "Concurrent search & evaluation with progressive constraint relaxation",
     "best_for": "Parallel high-precision research"},
    {"id": "modular", "name": "Modular", "category": "advanced",
     "description": "Modular architecture with configurable components",
     "best_for": "Custom research pipelines"},
    {"id": "modular-parallel", "name": "Modular Parallel", "category": "advanced",
     "description": "Modular architecture with parallel exploration",
     "best_for": "Large-scale parallel research"},
    {"id": "browsecomp-entity", "name": "Entity Discovery", "category": "specialized",
     "description": "Entity-focused with knowledge graph building",
     "best_for": "Entity identification and knowledge graph construction"},
    {"id": "topic-organization", "name": "Topic Organization", "category": "general",
     "description": "Organizes findings by topics with similarity threshold",
     "best_for": "Topic mapping and content organization"},
    {"id": "iterative-refinement", "name": "Iterative Refinement", "category": "advanced",
     "description": "Iteratively refines results with LLM evaluation",
     "best_for": "Progressive quality improvement"},
    {"id": "news", "name": "News Aggregation", "category": "specialized",
     "description": "News-specific aggregation strategy",
     "best_for": "Current events and news analysis"},
    {"id": "iterative-reasoning", "name": "Iterative Reasoning", "category": "advanced",
     "description": "Depth-variant iterative reasoning chains",
     "best_for": "Deep analytical reasoning"},
    {"id": "enhanced-contextual-followup", "name": "Contextual Follow-up", "category": "specialized",
     "description": "Follow-up research using parent context",
     "best_for": "Follow-up questions on previous research"},
]

# Search engines available in LDR
LDR_SEARCH_ENGINES = [
    {"id": "auto", "name": "Auto (SearXNG)", "type": "meta", "api_key_required": False},
    {"id": "searxng", "name": "SearXNG", "type": "meta", "api_key_required": False},
    {"id": "duckduckgo", "name": "DuckDuckGo", "type": "general", "api_key_required": False},
    {"id": "wikipedia", "name": "Wikipedia", "type": "reference", "api_key_required": False},
    {"id": "arxiv", "name": "arXiv", "type": "academic", "api_key_required": False},
    {"id": "pubmed", "name": "PubMed", "type": "academic", "api_key_required": False},
    {"id": "semantic_scholar", "name": "Semantic Scholar", "type": "academic", "api_key_required": False},
    {"id": "openalex", "name": "OpenAlex", "type": "academic", "api_key_required": False},
    {"id": "github", "name": "GitHub", "type": "code", "api_key_required": False},
    {"id": "brave", "name": "Brave Search", "type": "general", "api_key_required": True},
    {"id": "tavily", "name": "Tavily AI", "type": "ai", "api_key_required": True},
    {"id": "google_pse", "name": "Google PSE", "type": "general", "api_key_required": True},
    {"id": "guardian", "name": "The Guardian", "type": "news", "api_key_required": True},
    {"id": "wikinews", "name": "Wikinews", "type": "news", "api_key_required": False},
    {"id": "wayback", "name": "Wayback Machine", "type": "historical", "api_key_required": False},
    {"id": "local", "name": "Local Documents", "type": "local", "api_key_required": False},
]


class LDRService:
    """
    Integration service for Local Deep Research engine.
    Provides access to LDR's 30+ strategies, 27+ search engines,
    and advanced report generation within the LocalAIChatBox architecture.
    """

    def __init__(self):
        self._active_tasks: Dict[str, dict] = {}
        self._executor = ThreadPoolExecutor(max_workers=3)
        self._initialized = False
        self._init_error = None
        self._try_init()

    def _try_init(self):
        """Try to initialize LDR components."""
        try:
            # Test import of LDR core modules
            from app.local_deep_research.api.research_functions import (
                quick_summary, generate_report, detailed_research
            )
            self._quick_summary = quick_summary
            self._generate_report = generate_report
            self._detailed_research = detailed_research
            self._initialized = True
            logger.info("LDR engine initialized successfully")
        except Exception as e:
            self._init_error = str(e)
            logger.warning(f"LDR engine initialization deferred: {e}")

    def _ensure_init(self):
        """Ensure LDR is initialized, retry if needed."""
        if self._initialized:
            return True
        self._try_init()
        return self._initialized

    @property
    def available(self) -> bool:
        return self._ensure_init()

    def get_health(self) -> Dict:
        """Check LDR engine health."""
        health = {
            "initialized": self._initialized,
            "error": self._init_error,
            "ollama_host": OLLAMA_HOST,
            "ollama_model": OLLAMA_MODEL,
            "searxng_url": SEARXNG_URL,
            "strategies_count": len(LDR_STRATEGIES),
            "search_engines_count": len(LDR_SEARCH_ENGINES),
        }

        if self._initialized:
            health["status"] = "ready"
        else:
            health["status"] = "unavailable"

        return health

    def get_strategies(self) -> List[Dict]:
        """Get all available LDR strategies."""
        return LDR_STRATEGIES

    def get_search_engines(self) -> List[Dict]:
        """Get all available LDR search engines."""
        return LDR_SEARCH_ENGINES

    def start_research(self, query: str, strategy: str, user_id: int,
                       db: Session, research_mode: str = "detailed",
                       search_engine: str = "auto",
                       iterations: int = 3,
                       questions_per_iteration: int = 3,
                       overrides: Optional[Dict] = None) -> str:
        """Start an LDR-powered research task."""
        from app.models import ResearchTask

        # Create task in DB
        task = ResearchTask(
            user_id=user_id,
            query=query,
            strategy=f"ldr:{strategy}",
            status="pending",
            progress=0.0,
            progress_message="Initializing LDR research engine..."
        )
        db.add(task)
        db.commit()
        db.refresh(task)

        task_id = task.id

        self._active_tasks[task_id] = {
            "status": "pending",
            "progress": 0.0,
            "message": "Initializing LDR engine..."
        }

        # Submit to thread pool
        self._executor.submit(
            self._run_research, task_id, query, strategy,
            research_mode, search_engine, iterations,
            questions_per_iteration, user_id, overrides
        )

        return task_id

    def _run_research(self, task_id: str, query: str, strategy: str,
                      research_mode: str, search_engine: str,
                      iterations: int, questions_per_iteration: int,
                      user_id: int, overrides: Optional[Dict]):
        """Run LDR research in background thread."""
        from app.database import SessionLocal
        from app.models import ResearchTask

        db = SessionLocal()
        start_time = datetime.utcnow()

        try:
            self._update_task(db, task_id, status="running", progress=5.0,
                              message="Starting LDR engine...")

            if not self._ensure_init():
                raise RuntimeError(f"LDR engine not available: {self._init_error}")

            # Progress callback
            def progress_callback(phase: str, progress_pct: int, details: dict = None):
                msg = f"{phase}"
                if details:
                    msg += f" - {details.get('message', '')}"
                pct = min(85.0, 5.0 + (progress_pct * 0.8))
                self._update_task(db, task_id, progress=pct, message=msg)

            # Build LDR settings
            ldr_settings = {
                "search.tool": search_engine,
                "search.iterations": iterations,
                "search.questions_per_iteration": questions_per_iteration,
            }
            if overrides:
                ldr_settings.update(overrides)

            self._update_task(db, task_id, progress=10.0,
                              message=f"Running {research_mode} research with {strategy} strategy...")

            result = None
            report = None

            if research_mode == "quick":
                # Quick summary mode
                result = self._quick_summary(
                    query=query,
                    search_tool=search_engine,
                    search_strategy=strategy,
                    iterations=iterations,
                    questions_per_iteration=questions_per_iteration,
                    progress_callback=progress_callback,
                    programmatic_mode=True,
                )

            elif research_mode == "report":
                # Full report mode
                report = self._generate_report(
                    query=query,
                    search_tool=search_engine,
                    search_strategy=strategy,
                    iterations=iterations,
                    questions_per_iteration=questions_per_iteration,
                    progress_callback=progress_callback,
                    programmatic_mode=True,
                )
                result = {
                    "report": report,
                    "summary": report[:2000] if report else "",
                }

            else:
                # Detailed research (default)
                result = self._detailed_research(
                    query=query,
                    search_tool=search_engine,
                    search_strategy=strategy,
                    iterations=iterations,
                    questions_per_iteration=questions_per_iteration,
                    progress_callback=progress_callback,
                    programmatic_mode=True,
                )

            self._update_task(db, task_id, progress=90.0,
                              message="Processing LDR results...")

            # Process and save results
            duration = (datetime.utcnow() - start_time).total_seconds()

            task = db.query(ResearchTask).filter(ResearchTask.id == task_id).first()
            if task:
                task.status = "completed"
                task.progress = 100.0
                task.progress_message = "LDR research completed"

                # Extract knowledge and sources from result
                if isinstance(result, dict):
                    task.result_knowledge = result.get("summary", result.get("report", str(result)))
                    sources = result.get("sources", [])
                    if isinstance(sources, list):
                        task.result_sources = json.dumps(sources[:50], default=str)
                    else:
                        task.result_sources = json.dumps([], default=str)

                    if "report" in result:
                        task.result_report = result["report"]

                    metadata = {
                        "engine": "ldr",
                        "strategy": strategy,
                        "research_mode": research_mode,
                        "search_engine": search_engine,
                        "iterations": iterations,
                        "questions_per_iteration": questions_per_iteration,
                        "duration_seconds": round(duration),
                        "total_sources": len(result.get("sources", [])),
                        "sub_questions": result.get("sub_questions", []),
                        "answered_questions": result.get("answered_questions", []),
                    }

                    # Add any additional metadata from LDR
                    if "metadata" in result:
                        metadata.update(result["metadata"])

                    task.result_metadata = json.dumps(metadata, default=str)
                elif isinstance(result, str):
                    task.result_knowledge = result
                    task.result_sources = json.dumps([], default=str)
                    task.result_metadata = json.dumps({
                        "engine": "ldr",
                        "strategy": strategy,
                        "research_mode": research_mode,
                        "duration_seconds": round(duration),
                    }, default=str)
                else:
                    task.result_knowledge = str(result) if result else "No results"
                    task.result_sources = json.dumps([], default=str)
                    task.result_metadata = json.dumps({"engine": "ldr"}, default=str)

                task.completed_at = datetime.utcnow()
                db.commit()

            self._active_tasks[task_id] = {
                "status": "completed",
                "progress": 100.0,
                "message": "LDR research completed"
            }

            # Notify completion
            self._notify(task_id, query, user_id, db, "completed")

            # Track tokens
            self._track_tokens(task_id, user_id, result, db)

        except Exception as e:
            error_msg = f"{str(e)}\n{traceback.format_exc()}"
            logger.error(f"LDR task {task_id} failed: {error_msg}")

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

            self._notify(task_id, query, user_id, db, "failed")
        finally:
            db.close()

    def get_progress(self, task_id: str, db: Session) -> Dict:
        """Get progress of an LDR task."""
        if task_id in self._active_tasks:
            return self._active_tasks[task_id]

        from app.models import ResearchTask
        task = db.query(ResearchTask).filter(ResearchTask.id == task_id).first()
        if not task:
            return {"status": "not_found", "progress": 0, "message": "Task not found"}

        return {
            "status": task.status,
            "progress": task.progress or 0,
            "message": task.progress_message or ""
        }

    def follow_up_research(self, parent_task_id: str, query: str,
                           user_id: int, db: Session) -> str:
        """Start a follow-up research based on a previous task's context."""
        from app.models import ResearchTask

        # Get parent research context
        parent = db.query(ResearchTask).filter(ResearchTask.id == parent_task_id).first()
        if not parent or parent.status != "completed":
            raise ValueError("Parent research not found or not completed")

        # Build context from parent
        parent_context = {
            "parent_query": parent.query,
            "parent_knowledge": parent.result_knowledge or "",
            "parent_sources": json.loads(parent.result_sources) if parent.result_sources else [],
            "parent_strategy": parent.strategy or "source-based",
        }

        overrides = {"parent_context": parent_context}

        return self.start_research(
            query=query,
            strategy="enhanced-contextual-followup",
            user_id=user_id,
            db=db,
            research_mode="detailed",
            overrides=overrides,
        )

    def _notify(self, task_id: str, query: str, user_id: int,
                db: Session, status: str):
        """Send notification about research status."""
        try:
            from app.notification_service import get_notification_service
            notifier = get_notification_service()
            if notifier.available:
                from app.models import User
                user = db.query(User).filter(User.id == user_id).first()
                notifier.notify_research_complete(
                    task_id=task_id, query=query,
                    user_email=user.email if user else None,
                    status=status,
                )
        except Exception:
            pass

    def _track_tokens(self, task_id: str, user_id: int,
                      result: Any, db: Session):
        """Track token usage for the research task."""
        try:
            from app.token_tracker import get_token_tracker
            tracker = get_token_tracker()
            knowledge = ""
            if isinstance(result, dict):
                knowledge = result.get("summary", result.get("report", ""))
            elif isinstance(result, str):
                knowledge = result
            tracker.track_usage(
                db=db,
                user_id=user_id,
                model=OLLAMA_MODEL,
                input_text="x" * min(len(knowledge) // 4, 10000),
                output_text=knowledge[:5000] if knowledge else "",
                action="ldr_research",
                resource_id=task_id,
            )
        except Exception:
            pass

    def _update_task(self, db: Session, task_id: str, status: str = None,
                     progress: float = None, message: str = None):
        """Update task in DB and memory."""
        from app.models import ResearchTask
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
            logger.warning(f"Could not update task {task_id}: {e}")
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


# ==================== NEWS SERVICE ====================

class LDRNewsService:
    """
    News aggregation and subscription service powered by LDR.
    Provides news feeds, topic subscriptions, and news analysis.
    """

    def __init__(self):
        self._initialized = False

    def _ensure_init(self):
        if self._initialized:
            return True
        try:
            # Test if news module is available
            from app.local_deep_research.news import api as news_api
            self._news_api = news_api
            self._initialized = True
            return True
        except Exception:
            return False

    @property
    def available(self) -> bool:
        return self._ensure_init()

    def get_news_feed(self, topics: List[str] = None, limit: int = 20) -> List[Dict]:
        """Get news feed aggregated from multiple sources."""
        if not self.available:
            return []
        try:
            return self._news_api.get_news_feed(topics=topics, limit=limit)
        except Exception as e:
            logger.error(f"News feed error: {e}")
            return []

    def create_subscription(self, user_id: int, query: str,
                            sub_type: str = "search",
                            interval_hours: int = 24) -> Dict:
        """Create a news subscription."""
        return {
            "id": f"sub_{user_id}_{datetime.utcnow().timestamp():.0f}",
            "user_id": user_id,
            "query": query,
            "type": sub_type,
            "interval_hours": interval_hours,
            "created_at": datetime.utcnow().isoformat(),
            "status": "active",
        }


# ==================== SINGLETONS ====================

_ldr_service: Optional[LDRService] = None
_news_service: Optional[LDRNewsService] = None


def get_ldr_service() -> LDRService:
    global _ldr_service
    if _ldr_service is None:
        _ldr_service = LDRService()
    return _ldr_service


def get_news_service() -> LDRNewsService:
    global _news_service
    if _news_service is None:
        _news_service = LDRNewsService()
    return _news_service
