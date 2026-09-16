"""Evidence and transparent candidate scoring; accepts precomputed numeric metrics."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any, Mapping
from .actions import Candidate


@dataclass(frozen=True)
class Evidence:
    relevance: float = 0.0
    information_gain: float = 0.0
    novelty: float = 0.0
    stability: float = 0.0
    normalized_cost: float = 0.0
    sample_count: int = 0
    missing_fraction: float = 0.0
    basis: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        for name in ("relevance", "information_gain", "novelty", "stability", "normalized_cost", "missing_fraction"):
            value = getattr(self, name)
            if not 0 <= value <= 1: raise ValueError(f"{name} must be in [0, 1]")

    def to_dict(self) -> dict[str, Any]: return asdict(self)


def compute_evidence(candidate: Candidate, *, metrics: Mapping[str, float] | None = None, sample_count: int = 0,
                     missing_fraction: float = 0.0, basis: Mapping[str, Any] | None = None) -> Evidence:
    """Build evidence from deterministic metrics computed by a data adapter."""
    m = metrics or {}
    return Evidence(relevance=float(m.get("relevance", _goal_relevance(candidate))),
                    information_gain=float(m.get("information_gain", 0.0)),
                    novelty=float(m.get("novelty", 1.0)), stability=float(m.get("stability", 0.0)),
                    normalized_cost=max(0.0, min(1.0, float(m.get("normalized_cost", candidate.estimated_cost)))),
                    sample_count=sample_count, missing_fraction=missing_fraction, basis=basis or {})


def score_candidate(candidate: Candidate, evidence: Evidence) -> Candidate:
    score = (0.30*evidence.relevance + 0.25*evidence.information_gain + 0.15*evidence.novelty +
             0.15*evidence.stability + 0.15*(1-evidence.normalized_cost))
    return Candidate(candidate.action, candidate.state_after, round(score, 6),
                     {"relevance": evidence.relevance, "information_gain": evidence.information_gain,
                      "novelty": evidence.novelty, "stability": evidence.stability,
                      "normalized_cost": evidence.normalized_cost}, candidate.reason,
                     candidate.estimated_cost, evidence.to_dict())


def _goal_relevance(candidate: Candidate) -> float:
    goal = candidate.state_after.goal.lower()
    if "滞后" in goal or "lag" in goal: return 0.9 if candidate.action.parameters.get("operation") == "lagged_correlation" else 0.4
    if "相关" in goal or "correlation" in goal: return 0.8 if candidate.action.parameters.get("operation") in {"correlation", "lagged_correlation"} else 0.4
    return 0.5
