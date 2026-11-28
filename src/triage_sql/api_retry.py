"""Explicit retry limits and transient OpenAI API error classification for FS-03."""

from __future__ import annotations

from dataclasses import dataclass, field


MAX_RETRIES_PER_REQUEST = 2
MAX_RETRIES_PER_EXPERIMENT = 50
LUNA_MODEL = "gpt-6-luna"
LUNA_REASONING_EFFORT = "high"


def require_luna_high_configuration(generator) -> None:
    """Fail before any request unless the explicit experiment model and effort match."""
    if getattr(generator, "model", None) != LUNA_MODEL:
        raise ValueError(f"FS-03 requires OPENAI_MODEL={LUNA_MODEL}")
    if getattr(generator, "reasoning_effort", None) != LUNA_REASONING_EFFORT:
        raise ValueError("FS-03 requires OPENAI_REASONING_EFFORT=high")


@dataclass
class RetryBudget:
    """Track retry allowances by logical generation and across the whole run."""

    per_request_limit: int = MAX_RETRIES_PER_REQUEST
    total_limit: int = MAX_RETRIES_PER_EXPERIMENT
    total_used: int = 0
    used_by_request: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.per_request_limit < 0 or self.total_limit < 0 or self.total_used < 0:
            raise ValueError("retry limits and counts cannot be negative")
        if self.total_used > self.total_limit:
            raise ValueError("retry count cannot exceed the global retry limit")
        if any(count < 0 or count > self.per_request_limit for count in self.used_by_request.values()):
            raise ValueError("per-request retry count is outside its configured limit")
        if sum(self.used_by_request.values()) != self.total_used:
            raise ValueError("global retry count must equal the sum of per-request counts")

    def can_retry(self, request_key: str) -> bool:
        return (
            bool(request_key)
            and self.used_by_request.get(request_key, 0) < self.per_request_limit
            and self.total_used < self.total_limit
        )

    def claim_retry(self, request_key: str) -> int:
        if not self.can_retry(request_key):
            raise RuntimeError("retry budget exhausted for request or experiment")
        count = self.used_by_request.get(request_key, 0) + 1
        self.used_by_request[request_key] = count
        self.total_used += 1
        return count

    def to_dict(self) -> dict:
        return {
            "per_request_limit": self.per_request_limit,
            "total_limit": self.total_limit,
            "total_used": self.total_used,
            "used_by_request": dict(sorted(self.used_by_request.items())),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RetryBudget":
        return cls(
            per_request_limit=data["per_request_limit"],
            total_limit=data["total_limit"],
            total_used=data["total_used"],
            used_by_request=dict(data["used_by_request"]),
        )


def is_transient_openai_error(error: BaseException) -> bool:
    """Return true only for retryable OpenAI connection/timeouts and transient statuses."""
    try:
        import openai
    except ImportError:
        return False

    if isinstance(error, (openai.APIConnectionError, openai.APITimeoutError)):
        return True
    if isinstance(error, openai.APIStatusError):
        status = error.status_code
        return status in {408, 409, 429} or status >= 500
    return False
