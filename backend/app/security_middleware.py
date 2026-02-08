"""
Security Middleware for LocalAIChatBox.
Adds security headers, input sanitization, and SSRF protection.
Inspired by local-deep-research's security architecture.
"""

import ipaddress
import logging
import re
from typing import Optional
from urllib.parse import urlparse

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


# ==================== SECURITY HEADERS MIDDLEWARE ====================

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "SAMEORIGIN"

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # XSS Protection (legacy browsers)
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Referrer policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions policy
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), "
            "payment=(), usb=(), magnetometer=()"
        )

        # Content Security Policy (relaxed for API + SPA)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob: https:; "
            "font-src 'self' data:; "
            "connect-src 'self' http: https: ws: wss:; "
            "frame-ancestors 'self'"
        )

        # Strict Transport Security (for HTTPS deployments)
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )

        return response


# ==================== INPUT SANITIZATION ====================

class InputSanitizer:
    """Sanitize user inputs to prevent XSS, injection, etc."""

    # Dangerous HTML tags
    DANGEROUS_TAGS = re.compile(
        r'<\s*(?:script|iframe|object|embed|form|input|button|textarea|'
        r'link|meta|base|applet|style\s+[^>]*expression)[^>]*>',
        re.IGNORECASE
    )

    # Event handlers
    EVENT_HANDLERS = re.compile(
        r'\bon\w+\s*=\s*["\']?[^"\']*["\']?',
        re.IGNORECASE
    )

    # JavaScript protocol
    JS_PROTOCOL = re.compile(
        r'javascript\s*:',
        re.IGNORECASE
    )

    # Data URI with script
    DATA_SCRIPT = re.compile(
        r'data\s*:\s*text/html',
        re.IGNORECASE
    )

    # SQL injection patterns
    SQL_INJECTION = re.compile(
        r"(?:--|;|'|\b(?:DROP|DELETE|INSERT|UPDATE|ALTER|CREATE|EXEC|UNION|SELECT)\b\s+\b(?:TABLE|FROM|INTO|SET|WHERE|ALL)\b)",
        re.IGNORECASE
    )

    @classmethod
    def sanitize_text(cls, text: str) -> str:
        """Sanitize text input, removing dangerous content."""
        if not text:
            return text

        # Remove dangerous HTML tags
        cleaned = cls.DANGEROUS_TAGS.sub('', text)

        # Remove event handlers
        cleaned = cls.EVENT_HANDLERS.sub('', cleaned)

        # Remove JavaScript protocol
        cleaned = cls.JS_PROTOCOL.sub('', cleaned)

        # Remove data URI scripts
        cleaned = cls.DATA_SCRIPT.sub('', cleaned)

        return cleaned.strip()

    @classmethod
    def sanitize_filename(cls, filename: str) -> str:
        """Sanitize a filename to prevent path traversal."""
        if not filename:
            return "unnamed"

        # Remove path separators
        filename = filename.replace("/", "_").replace("\\", "_")

        # Remove null bytes
        filename = filename.replace("\x00", "")

        # Remove parent directory references
        filename = filename.replace("..", "_")

        # Keep only safe characters
        filename = re.sub(r'[^\w\s\-\.\(\)]', '_', filename)

        # Limit length
        if len(filename) > 255:
            name, ext = filename[:200], filename[-50:]
            filename = name + ext

        return filename or "unnamed"

    @classmethod
    def is_safe_query(cls, query: str) -> bool:
        """Check if a query string appears safe (no SQL injection)."""
        if not query:
            return True
        return not cls.SQL_INJECTION.search(query)

    @classmethod
    def sanitize_html(cls, html: str) -> str:
        """Remove all HTML tags from text."""
        if not html:
            return ""
        return re.sub(r'<[^>]+>', '', html)


# ==================== SSRF PROTECTION ====================

class SSRFProtection:
    """Prevent Server-Side Request Forgery attacks."""

    # Private/internal IP ranges
    PRIVATE_RANGES = [
        ipaddress.ip_network("10.0.0.0/8"),
        ipaddress.ip_network("172.16.0.0/12"),
        ipaddress.ip_network("192.168.0.0/16"),
        ipaddress.ip_network("127.0.0.0/8"),
        ipaddress.ip_network("169.254.0.0/16"),  # Link-local
        ipaddress.ip_network("0.0.0.0/8"),
        ipaddress.ip_network("::1/128"),  # IPv6 loopback
        ipaddress.ip_network("fc00::/7"),  # IPv6 private
        ipaddress.ip_network("fe80::/10"),  # IPv6 link-local
    ]

    # Allowed internal hostnames (for Docker services)
    ALLOWED_INTERNAL = {
        "ollama", "searxng", "postgres", "backend", "frontend", "nginx",
        "localhost",
    }

    @classmethod
    def is_safe_url(cls, url: str, allow_internal: bool = False) -> bool:
        """Check if a URL is safe to request (not targeting internal services)."""
        if not url:
            return False

        try:
            parsed = urlparse(url)

            # Only allow http/https
            if parsed.scheme not in ("http", "https"):
                return False

            hostname = parsed.hostname
            if not hostname:
                return False

            # Check allowed internal services
            if allow_internal and hostname.lower() in cls.ALLOWED_INTERNAL:
                return True

            # Block private IPs
            try:
                ip = ipaddress.ip_address(hostname)
                for network in cls.PRIVATE_RANGES:
                    if ip in network:
                        logger.warning(f"SSRF blocked: {url} -> private IP {ip}")
                        return False
            except ValueError:
                # Not an IP, it's a hostname - that's fine
                pass

            # Block Docker internal hostnames
            if not allow_internal and hostname.lower() in cls.ALLOWED_INTERNAL:
                return False

            return True

        except Exception as e:
            logger.warning(f"URL validation error: {e}")
            return False

    @classmethod
    def validate_webhook_url(cls, url: str) -> bool:
        """Validate a webhook URL (must be external)."""
        return cls.is_safe_url(url, allow_internal=False)


# ==================== REQUEST VALIDATION MIDDLEWARE ====================

class RequestValidationMiddleware(BaseHTTPMiddleware):
    """Validate and sanitize incoming requests."""

    # Max request body size (10MB)
    MAX_BODY_SIZE = 10 * 1024 * 1024

    async def dispatch(self, request: Request, call_next):
        # Check content length
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.MAX_BODY_SIZE:
            return Response(
                content='{"detail": "Request body too large"}',
                status_code=413,
                media_type="application/json",
            )

        response = await call_next(request)
        return response
