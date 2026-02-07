"""
Research API routes for deep research functionality.
"""
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, Dict

from app.database import get_db
from app.models import User, ResearchTask
from app.auth import get_current_user, get_current_admin
from app.deep_research import get_research_service, STRATEGIES
from app.ldr_settings import get_all_settings, update_settings

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
