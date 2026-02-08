"""
Token & Cost Tracker for LocalAIChatBox.
Tracks LLM token usage, estimated costs, and provides analytics.
Inspired by local-deep-research's TokenCounter and pricing system.
"""

import logging
import os
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import Column, Integer, String, Float, DateTime, Text, func, and_
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Approximate token estimation (4 chars ≈ 1 token for English)
CHARS_PER_TOKEN = 4

# Model pricing per 1M tokens (input/output)
MODEL_PRICING = {
    # Local models (free)
    "llama3.1": {"input": 0.0, "output": 0.0},
    "llama3.2": {"input": 0.0, "output": 0.0},
    "llava": {"input": 0.0, "output": 0.0},
    "mistral": {"input": 0.0, "output": 0.0},
    "mixtral": {"input": 0.0, "output": 0.0},
    "phi3": {"input": 0.0, "output": 0.0},
    "gemma2": {"input": 0.0, "output": 0.0},
    "qwen2": {"input": 0.0, "output": 0.0},
    "deepseek-r1": {"input": 0.0, "output": 0.0},
    # Cloud models (for reference)
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4.1": {"input": 2.00, "output": 8.00},
    "gpt-4.1-mini": {"input": 0.40, "output": 1.60},
    "claude-3.5-sonnet": {"input": 3.00, "output": 15.00},
    "claude-3.5-haiku": {"input": 0.80, "output": 4.00},
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    "gemini-1.5-pro": {"input": 1.25, "output": 5.00},
}


def estimate_tokens(text: str) -> int:
    """Estimate token count from text."""
    if not text:
        return 0
    return max(1, len(text) // CHARS_PER_TOKEN)


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate cost in USD for a given model and token counts."""
    pricing = MODEL_PRICING.get(model, {"input": 0.0, "output": 0.0})
    # Handle partial model name matches (e.g., "llama3.1:latest")
    if pricing["input"] == 0.0 and pricing["output"] == 0.0:
        for key in MODEL_PRICING:
            if key in model.lower():
                pricing = MODEL_PRICING[key]
                break

    cost = (input_tokens / 1_000_000) * pricing["input"] + \
           (output_tokens / 1_000_000) * pricing["output"]
    return round(cost, 6)


class TokenTracker:
    """Track token usage and costs."""

    def __init__(self):
        self._session_tokens = {
            "total_input": 0,
            "total_output": 0,
            "total_cost": 0.0,
            "calls": 0,
        }

    def track_usage(self, db: Session, user_id: int, model: str,
                    input_text: str, output_text: str,
                    action: str = "chat", resource_id: str = None) -> Dict:
        """Track a single LLM call's token usage."""
        input_tokens = estimate_tokens(input_text)
        output_tokens = estimate_tokens(output_text)
        cost = estimate_cost(model, input_tokens, output_tokens)

        # Update session stats
        self._session_tokens["total_input"] += input_tokens
        self._session_tokens["total_output"] += output_tokens
        self._session_tokens["total_cost"] += cost
        self._session_tokens["calls"] += 1

        # Save to database
        try:
            from app.models import TokenUsage
            usage = TokenUsage(
                user_id=user_id,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
                estimated_cost=cost,
                action=action,
                resource_id=resource_id,
            )
            db.add(usage)
            db.commit()
        except Exception as e:
            logger.warning(f"Failed to save token usage: {e}")
            try:
                db.rollback()
            except Exception:
                pass

        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "estimated_cost": cost,
            "model": model,
        }

    def get_usage_stats(self, db: Session, user_id: int = None,
                        days: int = 30) -> Dict:
        """Get token usage statistics."""
        try:
            from app.models import TokenUsage
            since = datetime.utcnow() - timedelta(days=days)
            query = db.query(TokenUsage).filter(TokenUsage.created_at >= since)

            if user_id:
                query = query.filter(TokenUsage.user_id == user_id)

            # Aggregate stats
            stats = query.with_entities(
                func.sum(TokenUsage.input_tokens).label("total_input"),
                func.sum(TokenUsage.output_tokens).label("total_output"),
                func.sum(TokenUsage.total_tokens).label("total_tokens"),
                func.sum(TokenUsage.estimated_cost).label("total_cost"),
                func.count(TokenUsage.id).label("total_calls"),
            ).first()

            # By model
            by_model = query.with_entities(
                TokenUsage.model,
                func.sum(TokenUsage.total_tokens).label("tokens"),
                func.sum(TokenUsage.estimated_cost).label("cost"),
                func.count(TokenUsage.id).label("calls"),
            ).group_by(TokenUsage.model).all()

            # By action
            by_action = query.with_entities(
                TokenUsage.action,
                func.sum(TokenUsage.total_tokens).label("tokens"),
                func.count(TokenUsage.id).label("calls"),
            ).group_by(TokenUsage.action).all()

            # Daily usage
            from sqlalchemy import cast, Date
            daily = query.with_entities(
                cast(TokenUsage.created_at, Date).label("date"),
                func.sum(TokenUsage.total_tokens).label("tokens"),
                func.sum(TokenUsage.estimated_cost).label("cost"),
            ).group_by(
                cast(TokenUsage.created_at, Date)
            ).order_by(
                cast(TokenUsage.created_at, Date)
            ).all()

            return {
                "period_days": days,
                "total_input_tokens": stats.total_input or 0,
                "total_output_tokens": stats.total_output or 0,
                "total_tokens": stats.total_tokens or 0,
                "total_cost_usd": round(float(stats.total_cost or 0), 4),
                "total_calls": stats.total_calls or 0,
                "by_model": [
                    {"model": m.model, "tokens": m.tokens or 0,
                     "cost": round(float(m.cost or 0), 4), "calls": m.calls}
                    for m in by_model
                ],
                "by_action": [
                    {"action": a.action, "tokens": a.tokens or 0, "calls": a.calls}
                    for a in by_action
                ],
                "daily_usage": [
                    {"date": d.date.isoformat() if hasattr(d.date, 'isoformat') else str(d.date),
                     "tokens": d.tokens or 0,
                     "cost": round(float(d.cost or 0), 4)}
                    for d in daily
                ],
                "session_stats": dict(self._session_tokens),
            }
        except Exception as e:
            logger.warning(f"Failed to get token stats: {e}")
            return {
                "period_days": days,
                "total_tokens": 0,
                "total_cost_usd": 0,
                "error": str(e),
                "session_stats": dict(self._session_tokens),
            }

    def get_session_stats(self) -> Dict:
        """Get current session stats."""
        return dict(self._session_tokens)


# Singleton
_token_tracker: Optional[TokenTracker] = None


def get_token_tracker() -> TokenTracker:
    global _token_tracker
    if _token_tracker is None:
        _token_tracker = TokenTracker()
    return _token_tracker
