"""
API Rate Limiter for LocalAIChatBox.
Per-user and per-IP rate limiting with configurable windows.
Inspired by local-deep-research's rate limiting system.
"""

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from threading import Lock
from typing import Dict, Optional, Tuple

from fastapi import HTTPException, Request, status

logger = logging.getLogger(__name__)


@dataclass
class RateWindow:
    """Sliding window rate counter."""
    requests: list = field(default_factory=list)
    lock: Lock = field(default_factory=Lock)

    def add_request(self, timestamp: float):
        with self.lock:
            self.requests.append(timestamp)

    def count_in_window(self, window_seconds: float) -> int:
        now = time.time()
        cutoff = now - window_seconds
        with self.lock:
            # Clean old entries
            self.requests = [t for t in self.requests if t > cutoff]
            return len(self.requests)


class RateLimiter:
    """In-memory rate limiter with per-user and per-IP tracking."""

    def __init__(self):
        self._user_windows: Dict[str, RateWindow] = defaultdict(RateWindow)
        self._ip_windows: Dict[str, RateWindow] = defaultdict(RateWindow)
        self._global_lock = Lock()

        # Default limits
        self.limits = {
            # endpoint_prefix: (max_requests, window_seconds)
            "chat": (30, 60),          # 30 requests per minute
            "research": (5, 300),       # 5 research tasks per 5 minutes
            "upload": (20, 60),         # 20 uploads per minute
            "auth": (10, 60),           # 10 auth attempts per minute
            "export": (10, 60),         # 10 exports per minute
            "admin": (60, 60),          # 60 admin requests per minute
            "default": (60, 60),        # 60 requests per minute default
        }

        # IP-based limits (stricter for unauthenticated)
        self.ip_limits = {
            "auth": (20, 300),          # 20 auth attempts per 5 minutes per IP
            "default": (120, 60),       # 120 requests per minute per IP
        }

    def check_rate_limit(self, request: Request, user_id: Optional[int] = None,
                         endpoint_type: str = "default") -> Tuple[bool, Dict]:
        """Check if the request is within rate limits.
        Returns (allowed, info_dict).
        """
        client_ip = self._get_client_ip(request)

        # Check IP-based limit
        ip_limit = self.ip_limits.get(endpoint_type, self.ip_limits["default"])
        ip_key = f"{client_ip}:{endpoint_type}"
        ip_window = self._ip_windows[ip_key]
        ip_count = ip_window.count_in_window(ip_limit[1])

        if ip_count >= ip_limit[0]:
            return False, {
                "type": "ip",
                "limit": ip_limit[0],
                "window": ip_limit[1],
                "current": ip_count,
                "retry_after": ip_limit[1],
            }

        # Check user-based limit
        if user_id:
            user_limit = self.limits.get(endpoint_type, self.limits["default"])
            user_key = f"user:{user_id}:{endpoint_type}"
            user_window = self._user_windows[user_key]
            user_count = user_window.count_in_window(user_limit[1])

            if user_count >= user_limit[0]:
                return False, {
                    "type": "user",
                    "limit": user_limit[0],
                    "window": user_limit[1],
                    "current": user_count,
                    "retry_after": user_limit[1],
                }

            user_window.add_request(time.time())

        ip_window.add_request(time.time())
        return True, {"allowed": True}

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request."""
        # Check forwarded headers (behind proxy)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        return request.client.host if request.client else "unknown"

    def get_stats(self) -> Dict:
        """Get rate limiter statistics."""
        return {
            "tracked_users": len(self._user_windows),
            "tracked_ips": len(self._ip_windows),
            "limits": self.limits,
            "ip_limits": self.ip_limits,
        }

    def cleanup(self):
        """Remove expired entries."""
        now = time.time()
        max_window = 600  # 10 minutes

        with self._global_lock:
            expired_users = [
                k for k, v in self._user_windows.items()
                if v.count_in_window(max_window) == 0
            ]
            for k in expired_users:
                del self._user_windows[k]

            expired_ips = [
                k for k, v in self._ip_windows.items()
                if v.count_in_window(max_window) == 0
            ]
            for k in expired_ips:
                del self._ip_windows[k]


# FastAPI dependency
def get_rate_limiter():
    return _rate_limiter


def check_rate_limit(endpoint_type: str = "default"):
    """Create a FastAPI dependency for rate limiting."""
    async def _check(request: Request):
        limiter = get_rate_limiter()
        # Try to extract user_id from auth header
        user_id = None
        try:
            from app.auth import get_current_user_optional
            # We don't block on auth failure here
        except Exception:
            pass

        allowed, info = limiter.check_rate_limit(request, user_id, endpoint_type)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Try again in {info.get('retry_after', 60)} seconds.",
                headers={"Retry-After": str(info.get("retry_after", 60))},
            )
    return _check


# Singleton
_rate_limiter = RateLimiter()
