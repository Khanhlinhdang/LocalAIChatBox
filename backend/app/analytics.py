"""
Usage Analytics Service for LocalAIChatBox.
Tracks user actions and provides analytics data for dashboards.
Inspired by LightRAG's document status tracking and RAG-Anything's batch processing stats.
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from sqlalchemy import func, and_, cast, Date
from sqlalchemy.orm import Session
from app.models import UsageLog, User, Document, Conversation, ChatSession, ResearchTask


def log_usage(db: Session, user_id: int, action: str,
              resource_type: str = None, resource_id: str = None,
              metadata: dict = None):
    """Log a user action for analytics."""
    try:
        log = UsageLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            metadata_json=json.dumps(metadata, default=str) if metadata else None,
        )
        db.add(log)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Analytics logging error (non-fatal): {e}")


def get_usage_overview(db: Session, days: int = 30) -> Dict:
    """Get overall usage statistics for the analytics dashboard."""
    since = datetime.utcnow() - timedelta(days=days)

    # Total counts
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active == True).count()
    total_documents = db.query(Document).count()
    total_conversations = db.query(Conversation).count()
    total_sessions = db.query(ChatSession).count()
    total_research = db.query(ResearchTask).count()

    # Period counts
    period_queries = db.query(UsageLog).filter(
        and_(UsageLog.action == "query", UsageLog.created_at >= since)
    ).count()
    period_uploads = db.query(UsageLog).filter(
        and_(UsageLog.action == "upload", UsageLog.created_at >= since)
    ).count()
    period_research = db.query(UsageLog).filter(
        and_(UsageLog.action == "research", UsageLog.created_at >= since)
    ).count()
    period_logins = db.query(UsageLog).filter(
        and_(UsageLog.action == "login", UsageLog.created_at >= since)
    ).count()

    return {
        "total_users": total_users,
        "active_users": active_users,
        "total_documents": total_documents,
        "total_conversations": total_conversations,
        "total_sessions": total_sessions,
        "total_research": total_research,
        "period_days": days,
        "period_queries": period_queries,
        "period_uploads": period_uploads,
        "period_research": period_research,
        "period_logins": period_logins,
    }


def get_daily_activity(db: Session, days: int = 30) -> List[Dict]:
    """Get daily activity counts for charting."""
    since = datetime.utcnow() - timedelta(days=days)

    results = db.query(
        cast(UsageLog.created_at, Date).label("date"),
        UsageLog.action,
        func.count(UsageLog.id).label("count")
    ).filter(
        UsageLog.created_at >= since
    ).group_by(
        cast(UsageLog.created_at, Date),
        UsageLog.action
    ).order_by(
        cast(UsageLog.created_at, Date)
    ).all()

    # Build daily activity map
    daily = {}
    for row in results:
        date_str = row.date.isoformat() if hasattr(row.date, 'isoformat') else str(row.date)
        if date_str not in daily:
            daily[date_str] = {"date": date_str, "queries": 0, "uploads": 0, "research": 0, "logins": 0, "exports": 0}
        if row.action in daily[date_str]:
            daily[date_str][row.action + "s" if not row.action.endswith("s") else row.action] = row.count
        elif row.action == "query":
            daily[date_str]["queries"] = row.count
        elif row.action == "upload":
            daily[date_str]["uploads"] = row.count
        elif row.action == "research":
            daily[date_str]["research"] = row.count
        elif row.action == "login":
            daily[date_str]["logins"] = row.count
        elif row.action == "export":
            daily[date_str]["exports"] = row.count

    # Fill in missing days
    result_list = []
    for i in range(days):
        d = (datetime.utcnow() - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d")
        if d in daily:
            result_list.append(daily[d])
        else:
            result_list.append({"date": d, "queries": 0, "uploads": 0, "research": 0, "logins": 0, "exports": 0})

    return result_list


def get_top_users(db: Session, days: int = 30, limit: int = 10) -> List[Dict]:
    """Get most active users by query count."""
    since = datetime.utcnow() - timedelta(days=days)

    results = db.query(
        UsageLog.user_id,
        User.username,
        User.full_name,
        func.count(UsageLog.id).label("actions")
    ).join(
        User, UsageLog.user_id == User.id
    ).filter(
        UsageLog.created_at >= since
    ).group_by(
        UsageLog.user_id, User.username, User.full_name
    ).order_by(
        func.count(UsageLog.id).desc()
    ).limit(limit).all()

    return [
        {"user_id": r.user_id, "username": r.username, "full_name": r.full_name, "actions": r.actions}
        for r in results
    ]


def get_popular_queries(db: Session, days: int = 30, limit: int = 20) -> List[Dict]:
    """Get most common queries."""
    since = datetime.utcnow() - timedelta(days=days)

    results = db.query(
        Conversation.question,
        func.count(Conversation.id).label("count")
    ).filter(
        Conversation.created_at >= since
    ).group_by(
        Conversation.question
    ).order_by(
        func.count(Conversation.id).desc()
    ).limit(limit).all()

    return [{"question": r.question, "count": r.count} for r in results]


def get_document_stats(db: Session) -> Dict:
    """Get document statistics by type, user, and date."""
    # By file type
    by_type = db.query(
        Document.file_type,
        func.count(Document.id).label("count"),
        func.sum(Document.num_chunks).label("total_chunks")
    ).group_by(Document.file_type).all()

    # By user
    by_user = db.query(
        User.username,
        func.count(Document.id).label("count")
    ).join(
        Document, Document.uploaded_by == User.id
    ).group_by(User.username).order_by(
        func.count(Document.id).desc()
    ).limit(10).all()

    return {
        "by_type": [
            {"type": r.file_type or "unknown", "count": r.count, "total_chunks": r.total_chunks or 0}
            for r in by_type
        ],
        "by_user": [
            {"username": r.username, "count": r.count}
            for r in by_user
        ],
    }


def get_action_breakdown(db: Session, days: int = 30) -> Dict:
    """Get action type breakdown for the period."""
    since = datetime.utcnow() - timedelta(days=days)

    results = db.query(
        UsageLog.action,
        func.count(UsageLog.id).label("count")
    ).filter(
        UsageLog.created_at >= since
    ).group_by(
        UsageLog.action
    ).all()

    return {r.action: r.count for r in results}
