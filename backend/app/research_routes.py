"""
Research API routes for deep research functionality.
Enhanced with SSE streaming, scheduler, multi-engine search, token tracking,
and PDF/DOCX export support.
"""
import json
import asyncio
import base64
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse, Response
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, Dict, List

from app.database import get_db
from app.models import User, ResearchTask, ScheduledResearch, TokenUsage
from app.auth import get_current_user, get_current_admin
from app.deep_research import get_research_service, STRATEGIES
from app.ldr_settings import get_all_settings, update_settings
from app.export_service import export_research_report

import logging
logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== SCHEMAS ====================

class ResearchStartRequest(BaseModel):
    query: str
    strategy: str = "source-based"
    overrides: Optional[Dict] = None


class ResearchStartResponse(BaseModel):
    task_id: str
    status: str
    message: str


class SettingsUpdateRequest(BaseModel):
    settings: Dict


class ScheduleCreateRequest(BaseModel):
    name: str
    query: str
    strategy: str = "source-based"
    interval_hours: int = 24


class ScheduleUpdateRequest(BaseModel):
    name: Optional[str] = None
    query: Optional[str] = None
    strategy: Optional[str] = None
    interval_hours: Optional[int] = None
    is_enabled: Optional[bool] = None


# ==================== RESEARCH ENDPOINTS ====================

@router.post("/api/research/start", response_model=ResearchStartResponse)
async def start_research(
    request: ResearchStartRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Start a new deep research task."""
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    valid_strategies = [s["id"] for s in STRATEGIES]
    if request.strategy not in valid_strategies:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid strategy. Valid options: {', '.join(valid_strategies)}"
        )

    service = get_research_service()
    task_id = service.start_research(
        query=request.query,
        strategy=request.strategy,
        user_id=current_user.id,
        db=db,
        overrides=request.overrides
    )

    return {
        "task_id": task_id,
        "status": "pending",
        "message": "Research task started"
    }


@router.get("/api/research/{task_id}/progress")
async def get_research_progress(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get the progress of a research task."""
    # Verify ownership
    task = db.query(ResearchTask).filter(ResearchTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Research task not found")
    if task.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")

    service = get_research_service()
    progress = service.get_progress(task_id, db)

    return {
        "task_id": task_id,
        "status": progress["status"],
        "progress": progress["progress"],
        "message": progress["message"]
    }


@router.get("/api/research/{task_id}/stream")
async def stream_research_progress(
    task_id: str,
    token: str = Query(None),
    db: Session = Depends(get_db)
):
    """Stream research progress via Server-Sent Events (SSE).
    Accepts token via query param since EventSource doesn't support headers.
    """
    # Auth via query param for SSE
    if not token:
        raise HTTPException(status_code=401, detail="Token required")

    from app.auth import decode_token
    try:
        payload = decode_token(token)
        username = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="Invalid token")
        current_user = db.query(User).filter(User.username == username).first()
        if not current_user:
            raise HTTPException(status_code=401, detail="User not found")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    task = db.query(ResearchTask).filter(ResearchTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Research task not found")
    if task.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")

    async def event_generator():
        service = get_research_service()
        last_progress = -1
        last_message = ""
        while True:
            try:
                from app.database import SessionLocal
                check_db = SessionLocal()
                try:
                    progress = service.get_progress(task_id, check_db)
                finally:
                    check_db.close()

                current_progress = progress.get("progress", 0)
                current_message = progress.get("message", "")
                current_status = progress.get("status", "unknown")

                # Send update if something changed
                if current_progress != last_progress or current_message != last_message:
                    data = json.dumps({
                        "task_id": task_id,
                        "status": current_status,
                        "progress": current_progress,
                        "message": current_message,
                    })
                    yield f"data: {data}\n\n"
                    last_progress = current_progress
                    last_message = current_message

                # Stop streaming if completed or failed
                if current_status in ("completed", "failed", "cancelled"):
                    final = json.dumps({
                        "task_id": task_id,
                        "status": current_status,
                        "progress": 100 if current_status == "completed" else current_progress,
                        "message": current_message,
                        "done": True,
                    })
                    yield f"data: {final}\n\n"
                    break

                await asyncio.sleep(1)
            except Exception as e:
                error = json.dumps({"error": str(e)})
                yield f"data: {error}\n\n"
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.get("/api/research/{task_id}/result")
async def get_research_result(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get the result of a completed research task."""
    task = db.query(ResearchTask).filter(ResearchTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Research task not found")
    if task.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")

    if task.status == "failed":
        return {
            "task_id": task_id,
            "status": "failed",
            "error": task.error_message
        }

    if task.status != "completed":
        return {
            "task_id": task_id,
            "status": task.status,
            "message": "Research not yet completed"
        }

    sources = []
    try:
        if task.result_sources:
            sources = json.loads(task.result_sources)
    except (json.JSONDecodeError, TypeError):
        pass

    metadata = {}
    try:
        if task.result_metadata:
            metadata = json.loads(task.result_metadata)
    except (json.JSONDecodeError, TypeError):
        pass

    return {
        "task_id": task_id,
        "status": "completed",
        "query": task.query,
        "strategy": task.strategy,
        "knowledge": task.result_knowledge,
        "report": task.result_report,
        "sources": sources,
        "metadata": metadata,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None
    }


@router.post("/api/research/{task_id}/report")
async def generate_report(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generate a detailed report from research findings."""
    task = db.query(ResearchTask).filter(ResearchTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Research task not found")
    if task.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")

    service = get_research_service()
    try:
        result = service.generate_report(task_id, db)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/api/research/history")
async def get_research_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = 20
):
    """Get research task history for the current user."""
    tasks = db.query(ResearchTask)\
        .filter(ResearchTask.user_id == current_user.id)\
        .order_by(ResearchTask.created_at.desc())\
        .limit(limit)\
        .all()

    return {
        "total": len(tasks),
        "tasks": [
            {
                "id": t.id,
                "query": t.query,
                "strategy": t.strategy,
                "status": t.status,
                "progress": t.progress,
                "progress_message": t.progress_message,
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "completed_at": t.completed_at.isoformat() if t.completed_at else None
            }
            for t in tasks
        ]
    }


@router.delete("/api/research/{task_id}")
async def delete_research(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a research task."""
    task = db.query(ResearchTask).filter(ResearchTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Research task not found")
    if task.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Cancel if running
    if task.status in ("pending", "running"):
        service = get_research_service()
        service.cancel_task(task_id, db)

    db.delete(task)
    db.commit()

    return {"message": "Research task deleted"}


@router.get("/api/research/strategies")
async def get_strategies(
    current_user: User = Depends(get_current_user)
):
    """Get available research strategies."""
    return {"strategies": STRATEGIES}


# ==================== SETTINGS ENDPOINTS ====================

@router.get("/api/settings/ldr")
async def get_ldr_settings(
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Get all LDR settings (admin only)."""
    settings = get_all_settings(db)
    return {"settings": settings}


@router.put("/api/settings/ldr")
async def update_ldr_settings(
    request: SettingsUpdateRequest,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Update LDR settings (admin only)."""
    updated = update_settings(db, request.settings)
    return {"settings": updated, "message": "Settings updated successfully"}


# ==================== EXPORT ENDPOINTS ====================

@router.get("/api/research/{task_id}/export")
async def export_research(
    task_id: str,
    format: str = Query("markdown", regex="^(markdown|json|pdf|docx)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Export a research report in various formats (markdown, json, pdf, docx)."""
    try:
        result = export_research_report(db, task_id, current_user.id, format=format)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not result:
        raise HTTPException(status_code=404, detail="Research task not found")

    if result.get("is_binary"):
        content = base64.b64decode(result["content"])
        return Response(
            content=content,
            media_type=result["content_type"],
            headers={
                "Content-Disposition": f'attachment; filename="{result["filename"]}"'
            }
        )

    return Response(
        content=result["content"],
        media_type=result["content_type"],
        headers={
            "Content-Disposition": f'attachment; filename="{result["filename"]}"'
        }
    )


# ==================== SEARCH ENGINE ENDPOINTS ====================

@router.get("/api/search/engines")
async def get_search_engines(
    current_user: User = Depends(get_current_user),
):
    """Get available search engines and their status."""
    try:
        from app.search_engines import get_meta_search_engine
        meta = get_meta_search_engine()
        engines = []
        for name, engine in meta.engines.items():
            engines.append({
                "name": name,
                "available": engine.available,
                "requires_api_key": hasattr(engine, 'api_key') and engine.api_key is None,
            })
        return {"engines": engines}
    except Exception as e:
        return {"engines": [], "error": str(e)}


@router.post("/api/search/test")
async def test_search(
    query: str = Query(..., min_length=1),
    engine: str = Query("auto"),
    current_user: User = Depends(get_current_user),
):
    """Test a search query across engines."""
    try:
        from app.search_engines import get_meta_search_engine
        meta = get_meta_search_engine()
        results = meta.search(query, max_results=5)
        return {
            "query": query,
            "engine": engine,
            "results": [
                {
                    "title": r.title,
                    "url": r.url,
                    "snippet": r.snippet[:200] if r.snippet else "",
                    "source": r.source,
                    "relevance": r.relevance_score,
                }
                for r in results
            ],
            "total": len(results),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== TOKEN USAGE ENDPOINTS ====================

@router.get("/api/tokens/stats")
async def get_token_stats(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get token usage statistics for the current user."""
    try:
        from app.token_tracker import get_token_tracker
        tracker = get_token_tracker()
        stats = tracker.get_usage_stats(db, current_user.id, days)
        return stats
    except Exception as e:
        return {"error": str(e), "total_tokens": 0, "estimated_cost": 0}


@router.get("/api/tokens/stats/all")
async def get_all_token_stats(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Get token usage statistics for all users (admin only)."""
    try:
        from app.token_tracker import get_token_tracker
        tracker = get_token_tracker()
        stats = tracker.get_usage_stats(db, user_id=None, days=days)
        return stats
    except Exception as e:
        return {"error": str(e), "total_tokens": 0, "estimated_cost": 0}


# ==================== SCHEDULER ENDPOINTS ====================

@router.post("/api/research/schedules")
async def create_schedule(
    request: ScheduleCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a scheduled research task."""
    try:
        from app.research_scheduler import get_research_scheduler
        scheduler = get_research_scheduler()
        schedule = scheduler.add_schedule(
            user_id=current_user.id,
            name=request.name,
            query=request.query,
            strategy=request.strategy,
            interval_hours=request.interval_hours,
            db=db
        )
        return {"message": "Schedule created", "schedule_id": schedule.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/research/schedules")
async def get_schedules(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all scheduled research tasks for current user."""
    schedules = db.query(ScheduledResearch)\
        .filter(ScheduledResearch.user_id == current_user.id)\
        .order_by(ScheduledResearch.created_at.desc())\
        .all()

    return {
        "schedules": [
            {
                "id": s.id,
                "name": s.name,
                "query": s.query,
                "strategy": s.strategy,
                "interval_hours": s.interval_hours,
                "is_enabled": s.is_enabled,
                "last_run_at": s.last_run_at.isoformat() if s.last_run_at else None,
                "next_run_at": s.next_run_at.isoformat() if s.next_run_at else None,
                "run_count": s.run_count,
                "created_at": s.created_at.isoformat(),
            }
            for s in schedules
        ]
    }


@router.put("/api/research/schedules/{schedule_id}")
async def update_schedule(
    schedule_id: str,
    request: ScheduleUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a scheduled research task."""
    schedule = db.query(ScheduledResearch).filter(
        ScheduledResearch.id == schedule_id,
        ScheduledResearch.user_id == current_user.id
    ).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    if request.name is not None:
        schedule.name = request.name
    if request.query is not None:
        schedule.query = request.query
    if request.strategy is not None:
        schedule.strategy = request.strategy
    if request.interval_hours is not None:
        schedule.interval_hours = request.interval_hours
    if request.is_enabled is not None:
        schedule.is_enabled = request.is_enabled

    db.commit()
    return {"message": "Schedule updated"}


@router.delete("/api/research/schedules/{schedule_id}")
async def delete_schedule(
    schedule_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a scheduled research task."""
    schedule = db.query(ScheduledResearch).filter(
        ScheduledResearch.id == schedule_id,
        ScheduledResearch.user_id == current_user.id
    ).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    try:
        from app.research_scheduler import get_research_scheduler
        scheduler = get_research_scheduler()
        scheduler.remove_schedule(schedule_id, db)
    except Exception:
        pass

    db.delete(schedule)
    db.commit()
    return {"message": "Schedule deleted"}
