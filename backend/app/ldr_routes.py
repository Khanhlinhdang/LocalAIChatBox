"""
LDR (Local Deep Research) API routes for LocalAIChatBox.
Adds 30+ strategies, multi-engine search, follow-up research,
news subscriptions, and advanced analytics endpoints.
"""
import json
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, Dict, List

from app.database import get_db
from app.models import User, ResearchTask
from app.auth import get_current_user, get_current_admin
from app.ldr_service import (
    get_ldr_service, get_news_service,
    LDR_STRATEGIES, LDR_SEARCH_ENGINES,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== SCHEMAS ====================

class LDRResearchRequest(BaseModel):
    query: str
    strategy: str = "source-based"
    research_mode: str = "detailed"  # quick | detailed | report
    search_engine: str = "auto"
    iterations: int = 3
    questions_per_iteration: int = 3
    overrides: Optional[Dict] = None


class LDRFollowUpRequest(BaseModel):
    parent_task_id: str
    query: str


class NewsSubscriptionRequest(BaseModel):
    query: str
    sub_type: str = "search"
    interval_hours: int = 24


# ==================== HEALTH & INFO ====================

@router.get("/api/ldr/health")
async def ldr_health():
    """Check LDR engine health and status."""
    service = get_ldr_service()
    return service.get_health()


@router.get("/api/ldr/strategies")
async def ldr_strategies(
    category: Optional[str] = Query(None, description="Filter by category"),
):
    """Get all LDR strategies with metadata."""
    strategies = LDR_STRATEGIES
    if category:
        strategies = [s for s in strategies if s.get("category") == category]
    return {
        "strategies": strategies,
        "total": len(strategies),
        "categories": list(set(s.get("category", "general") for s in LDR_STRATEGIES)),
    }


@router.get("/api/ldr/search-engines")
async def ldr_search_engines():
    """Get all available LDR search engines."""
    return {
        "engines": LDR_SEARCH_ENGINES,
        "total": len(LDR_SEARCH_ENGINES),
    }


# ==================== RESEARCH ====================

@router.post("/api/ldr/research/start")
async def ldr_start_research(
    request: LDRResearchRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Start an LDR-powered research task."""
    service = get_ldr_service()

    if not service.available:
        raise HTTPException(
            status_code=503,
            detail="LDR engine is not available. Check health endpoint for details."
        )

    # Validate strategy
    valid_strategies = [s["id"] for s in LDR_STRATEGIES]
    if request.strategy not in valid_strategies:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid strategy: {request.strategy}. Valid: {valid_strategies}"
        )

    task_id = service.start_research(
        query=request.query,
        strategy=request.strategy,
        user_id=user.id,
        db=db,
        research_mode=request.research_mode,
        search_engine=request.search_engine,
        iterations=request.iterations,
        questions_per_iteration=request.questions_per_iteration,
        overrides=request.overrides,
    )

    return {
        "task_id": task_id,
        "status": "pending",
        "message": f"LDR research started with {request.strategy} strategy",
        "engine": "ldr",
    }


@router.get("/api/ldr/research/{task_id}/progress")
async def ldr_research_progress(
    task_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get LDR research progress."""
    service = get_ldr_service()
    return service.get_progress(task_id, db)


@router.get("/api/ldr/research/{task_id}/result")
async def ldr_research_result(
    task_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get completed LDR research result."""
    task = db.query(ResearchTask).filter(
        ResearchTask.id == task_id
    ).first()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Task not completed (status: {task.status})"
        )

    # Parse metadata
    metadata = {}
    try:
        metadata = json.loads(task.result_metadata) if task.result_metadata else {}
    except (json.JSONDecodeError, TypeError):
        pass

    # Parse sources
    sources = []
    try:
        sources = json.loads(task.result_sources) if task.result_sources else []
    except (json.JSONDecodeError, TypeError):
        pass

    return {
        "task_id": task_id,
        "query": task.query,
        "status": task.status,
        "engine": "ldr",
        "strategy": metadata.get("strategy", task.strategy),
        "research_mode": metadata.get("research_mode", "detailed"),
        "knowledge": task.result_knowledge or "",
        "report": task.result_report or "",
        "sources": sources,
        "metadata": metadata,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "duration_seconds": metadata.get("duration_seconds", 0),
    }


# ==================== FOLLOW-UP RESEARCH ====================

@router.post("/api/ldr/research/follow-up")
async def ldr_follow_up(
    request: LDRFollowUpRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Start follow-up research based on a previous task."""
    service = get_ldr_service()

    if not service.available:
        raise HTTPException(status_code=503, detail="LDR engine not available")

    try:
        task_id = service.follow_up_research(
            parent_task_id=request.parent_task_id,
            query=request.query,
            user_id=user.id,
            db=db,
        )
        return {
            "task_id": task_id,
            "status": "pending",
            "message": "Follow-up research started",
            "parent_task_id": request.parent_task_id,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==================== NEWS & SUBSCRIPTIONS ====================

@router.get("/api/ldr/news/feed")
async def ldr_news_feed(
    topics: Optional[str] = Query(None, description="Comma-separated topics"),
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
):
    """Get news feed from multiple sources."""
    service = get_news_service()
    topic_list = topics.split(",") if topics else None
    feed = service.get_news_feed(topics=topic_list, limit=limit)
    return {"items": feed, "total": len(feed)}


@router.post("/api/ldr/news/subscriptions")
async def create_subscription(
    request: NewsSubscriptionRequest,
    user: User = Depends(get_current_user),
):
    """Create a news subscription."""
    service = get_news_service()
    sub = service.create_subscription(
        user_id=user.id,
        query=request.query,
        sub_type=request.sub_type,
        interval_hours=request.interval_hours,
    )
    return sub


# ==================== LDR ANALYTICS ====================

@router.get("/api/ldr/analytics/strategies")
async def ldr_strategy_analytics(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get analytics on LDR strategy usage."""
    tasks = db.query(ResearchTask).filter(
        ResearchTask.strategy.like("ldr:%")
    ).all()

    stats = {}
    for task in tasks:
        strategy = task.strategy.replace("ldr:", "") if task.strategy else "unknown"
        if strategy not in stats:
            stats[strategy] = {"count": 0, "completed": 0, "failed": 0, "avg_duration": 0, "durations": []}
        stats[strategy]["count"] += 1
        if task.status == "completed":
            stats[strategy]["completed"] += 1
            try:
                meta = json.loads(task.result_metadata) if task.result_metadata else {}
                dur = meta.get("duration_seconds", 0)
                if dur:
                    stats[strategy]["durations"].append(dur)
            except Exception:
                pass
        elif task.status == "failed":
            stats[strategy]["failed"] += 1

    # Calculate averages
    for s in stats:
        durations = stats[s].pop("durations", [])
        stats[s]["avg_duration"] = round(sum(durations) / len(durations)) if durations else 0

    return {
        "strategies": stats,
        "total_ldr_tasks": len(tasks),
    }


@router.get("/api/ldr/analytics/engines")
async def ldr_engine_analytics(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get analytics on search engine usage."""
    tasks = db.query(ResearchTask).filter(
        ResearchTask.strategy.like("ldr:%")
    ).all()

    engine_stats = {}
    for task in tasks:
        try:
            meta = json.loads(task.result_metadata) if task.result_metadata else {}
            engine = meta.get("search_engine", "auto")
            if engine not in engine_stats:
                engine_stats[engine] = {"count": 0, "completed": 0}
            engine_stats[engine]["count"] += 1
            if task.status == "completed":
                engine_stats[engine]["completed"] += 1
        except Exception:
            pass

    return {"engines": engine_stats}
