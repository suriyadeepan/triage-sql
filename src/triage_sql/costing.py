"""Token usage cost estimates based on a run-recorded model rate card."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TokenRateCard:
    model: str
    input_usd_per_million: float
    output_usd_per_million: float
    source_url: str
    checked_at: str
    pricing_tier: str = "standard"
    cached_input_usd_per_million: float | None = None

    def __post_init__(self) -> None:
        if not self.model or not self.source_url or not self.checked_at:
            raise ValueError("rate card requires model, source URL, and checked-at date")
        if self.input_usd_per_million < 0 or self.output_usd_per_million < 0:
            raise ValueError("token rates cannot be negative")
        if self.cached_input_usd_per_million is not None and self.cached_input_usd_per_million < 0:
            raise ValueError("cached input rate cannot be negative")


def estimate_token_cost_usd(
    rate_card: TokenRateCard,
    input_tokens: int | None,
    output_tokens: int | None,
    cached_input_tokens: int | None = None,
) -> float | None:
    """Estimate input/output charges; reasoning tokens are included in output tokens."""
    if input_tokens is None or output_tokens is None:
        return None
    if input_tokens < 0 or output_tokens < 0:
        raise ValueError("token counts cannot be negative")

    cached_rate = (
        rate_card.cached_input_usd_per_million
        if rate_card.cached_input_usd_per_million is not None
        else rate_card.input_usd_per_million
    )
    cached = min(input_tokens, max(0, cached_input_tokens or 0))
    uncached = input_tokens - cached
    return (
        uncached * rate_card.input_usd_per_million
        + cached * cached_rate
        + output_tokens * rate_card.output_usd_per_million
    ) / 1_000_000
