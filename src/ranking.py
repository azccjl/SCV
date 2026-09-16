from __future__ import annotations

from dataclasses import dataclass

from .actions import Action
from .data import DatasetBundle
from .evidence import compute_evidence
from .state import AnalysisState, Evidence


@dataclass
class Candidate:
    action: Action
    state: AnalysisState
    evidence: Evidence
    scores: dict[str, float]
    score: float
    reason: str


def rank_candidates(bundle: DatasetBundle, state: AnalysisState, actions: list[Action] | None = None) -> list[Candidate]:
    current = compute_evidence(bundle.frame, state)
    candidates = []
    for action in actions or []:
        next_state = action.apply(state)
        evidence = compute_evidence(bundle.frame, next_state)
        relevance = 0.9 if action.kind in {"add_variable", "change_statistic"} else 0.65
        information = min(1.0, abs(evidence.metrics.get("correlation", 0) - current.metrics.get("correlation", 0)) + 0.2)
        novelty = 0.8 if action.kind in {"change_region", "change_time_window"} else 0.55
        stability = max(0.0, 1.0 - evidence.missing_fraction) * (1.0 if evidence.sample_count >= 12 else 0.5)
        cost = min(1.0, (evidence.sample_count * max(1, len(next_state.variables))) / 30000)
        scores = {"relevance": relevance, "information_gain": information, "novelty": novelty, "evidence_stability": stability, "normalized_cost": cost}
        score = 0.30 * relevance + 0.25 * information + 0.15 * novelty + 0.15 * stability + 0.15 * (1 - cost)
        reason = f"{action.label}；相关性 {relevance:.2f}，证据稳定性 {stability:.2f}，预估成本 {cost:.2f}"
        candidates.append(Candidate(action, next_state, evidence, scores, score, reason))
    return sorted(candidates, key=lambda item: item.score, reverse=True)
