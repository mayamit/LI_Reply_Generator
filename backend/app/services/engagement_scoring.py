"""Deterministic engagement scoring for LinkedIn post authors.

Combines follower count, like/comment/repost counts, and historical
interaction count into a normalized 0–100 score using capped log scaling.

Formula
-------
For each signal *s* with raw value *v*, weight *w*, and cap *c*:

    normalized(v, c) = min(log2(v + 1) / log2(c + 1), 1.0)
    component(s) = w * normalized(v, c)

Final score = round(sum(component(s) for all s) * 100), clamped to [0, 100].
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Constants – single source of truth for weights and caps
# ---------------------------------------------------------------------------

WEIGHTS: dict[str, float] = {
    "follower_count": 0.25,
    "like_count": 0.20,
    "comment_count": 0.30,
    "repost_count": 0.15,
    "interaction_count": 0.10,
}

CAPS: dict[str, int] = {
    "follower_count": 100_000,
    "like_count": 1_000,
    "comment_count": 1_000,
    "repost_count": 1_000,
    "interaction_count": 50,
}


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EngagementScore:
    """Engagement score with per-signal breakdown for explainability.

    Attributes:
        score: Normalized integer score in [0, 100].
        breakdown: Mapping of signal name → weighted contribution (0.0–weight).
    """

    score: int
    breakdown: dict[str, float]


# ---------------------------------------------------------------------------
# Scoring function
# ---------------------------------------------------------------------------

def _normalize(value: int, cap: int) -> float:
    """Log-scale a raw value against a cap, returning a float in [0.0, 1.0]."""
    if value <= 0 or cap <= 0:
        return 0.0
    return min(math.log2(value + 1) / math.log2(cap + 1), 1.0)


def compute_engagement_score(
    *,
    follower_count: int | None = None,
    like_count: int | None = None,
    comment_count: int | None = None,
    repost_count: int | None = None,
    interaction_count: int | None = None,
) -> EngagementScore:
    """Compute a deterministic engagement score from raw signals.

    All parameters are optional; missing (``None``) values contribute zero.
    Negative values are treated as zero defensively.

    Returns an :class:`EngagementScore` with the integer score and a breakdown
    dict showing each signal's weighted contribution.
    """
    raw: dict[str, int] = {
        "follower_count": follower_count if follower_count is not None else 0,
        "like_count": like_count if like_count is not None else 0,
        "comment_count": comment_count if comment_count is not None else 0,
        "repost_count": repost_count if repost_count is not None else 0,
        "interaction_count": interaction_count if interaction_count is not None else 0,
    }

    breakdown: dict[str, float] = {}
    weighted_sum = 0.0

    for signal, weight in WEIGHTS.items():
        norm = _normalize(raw[signal], CAPS[signal])
        contribution = weight * norm
        breakdown[signal] = contribution
        weighted_sum += contribution

    score = min(max(round(weighted_sum * 100), 0), 100)

    return EngagementScore(score=score, breakdown=breakdown)
