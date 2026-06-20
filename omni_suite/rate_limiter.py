"""Token bucket rate limiter for MCP server DoS protection.

Thread-safe token bucket implementation that limits request rates.
Configurable via environment variables:

- OMNI_RATE_LIMIT_RPM: requests per minute (default: 60, 0 = disabled)
- OMNI_RATE_LIMIT_BURST: max burst size (default: 10)

Usage:
    from omni_suite.rate_limiter import rate_limiter

    ok, err = rate_limiter.check_rate()
    if not ok:
        return {"success": False, "error": err}
"""

from __future__ import annotations

import os
import threading
import time

__all__ = ["TokenBucket", "rate_limiter", "check_rate_limit"]


class TokenBucket:
    """Thread-safe token bucket rate limiter.

    Attributes:
        rate: Tokens added per second (derived from rpm / 60).
        burst: Maximum token count the bucket can hold.
        tokens: Current available tokens.
        last_refill: Timestamp of last token refill.
    """

    def __init__(self, rpm: int = 60, burst: int = 10) -> None:
        if rpm < 0:
            rpm = 0
        if burst < 1:
            burst = 1
        self.rate: float = rpm / 60.0
        self.burst: int = burst
        self.tokens: float = float(burst)
        self.last_refill: float = time.monotonic()
        self._lock = threading.Lock()

    def _refill(self) -> None:
        """Add tokens based on elapsed time since last refill."""
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(float(self.burst), self.tokens + elapsed * self.rate)
        self.last_refill = now

    def consume(self, tokens: int = 1) -> bool:
        """Consume *tokens* from the bucket.

        Returns True if allowed, False if rate limited.
        """
        if self.rate <= 0:
            return True  # disabled
        with self._lock:
            self._refill()
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

    @property
    def wait_seconds(self) -> float:
        """Estimated seconds until at least one token is available."""
        if self.rate <= 0:
            return 0.0
        with self._lock:
            self._refill()
            if self.tokens >= 1.0:
                return 0.0
            return (1.0 - self.tokens) / self.rate


def check_rate_limit(
    rpm: int | None = None,
    burst: int | None = None,
) -> tuple[bool, str | None]:
    """Convenience: check rate limit using env-var-configured defaults.

    Returns:
        (True, None) if allowed.
        (False, error_message) if rate limited.
    """
    if rpm is None:
        rpm = int(os.environ.get("OMNI_RATE_LIMIT_RPM", "60"))
    if burst is None:
        burst = int(os.environ.get("OMNI_RATE_LIMIT_BURST", "10"))

    global _bucket
    if _bucket is None:
        _bucket = TokenBucket(rpm=rpm, burst=burst)

    if not _bucket.consume():
        wait = _bucket.wait_seconds
        return (
            False,
            f"RATE_LIMITED: too many requests. Retry in {wait:.1f}s.",
        )
    return True, None


def rate_limit_failure_response() -> dict:
    """Standard error response for rate limited requests."""
    return {
        "success": False,
        "error_code": "RATE_LIMITED",
        "message": "Rate limit exceeded. Please reduce request frequency and retry.",
    }


# Module-level singleton initialized lazily on first call.
_bucket: TokenBucket | None = None
rate_limiter = check_rate_limit  # convenience alias
