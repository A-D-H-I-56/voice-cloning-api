"""
Security middleware: API key authentication and rate limiting.
"""

import logging
import time
from collections import defaultdict
from typing import Optional

from fastapi import HTTPException, Request, status
from app.config import settings

logger = logging.getLogger(__name__)


class RateLimiter:
    """Simple in-memory rate limiter — counts requests per IP."""

    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, client_ip: str) -> bool:
        """Check if client_ip is within rate limit."""
        now = time.time()

        # Clean old requests outside the window
        self.requests[client_ip] = [
            req_time
            for req_time in self.requests[client_ip]
            if now - req_time < self.window_seconds
        ]

        # Check if under limit
        if len(self.requests[client_ip]) < self.max_requests:
            self.requests[client_ip].append(now)
            return True

        return False

    def get_reset_time(self, client_ip: str) -> int:
        """Get seconds until rate limit resets."""
        if not self.requests[client_ip]:
            return 0
        oldest_request = min(self.requests[client_ip])
        reset_time = int(oldest_request + self.window_seconds - time.time())
        return max(0, reset_time)


# Global rate limiter instance
rate_limiter = RateLimiter(
    max_requests=settings.rate_limit_requests,
    window_seconds=settings.rate_limit_window,
)


async def verify_api_key(request: Request) -> None:
    """Verify API key in Authorization header."""
    auth_header = request.headers.get("Authorization", "")

    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header. Use: Authorization: Bearer <api_key>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    api_key = auth_header.replace("Bearer ", "", 1)

    if api_key != settings.api_key:
        logger.warning("Failed API authentication from %s", request.client.host)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def check_rate_limit(request: Request) -> None:
    """Check if client IP is within rate limit."""
    client_ip = request.client.host if request.client else "unknown"

    if not rate_limiter.is_allowed(client_ip):
        reset_in = rate_limiter.get_reset_time(client_ip)
        logger.warning(
            "Rate limit exceeded for %s (reset in %d seconds)",
            client_ip,
            reset_in,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Try again in {reset_in} seconds.",
            headers={"Retry-After": str(reset_in)},
        )


def get_client_ip(request: Request) -> str:
    """Get client IP, accounting for proxies."""
    # Check X-Forwarded-For header (from reverse proxy/load balancer)
    x_forwarded_for = request.headers.get("X-Forwarded-For")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()

    return request.client.host if request.client else "unknown"
