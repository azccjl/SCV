"""Lightweight, dependency-free exploration recommendation core."""

from .state import AnalysisState
from .actions import Action, Candidate, generate_candidates
from .evidence import Evidence, compute_evidence, score_candidate
from .history import HistoryLog

__all__ = [
    "AnalysisState", "Action", "Candidate", "generate_candidates",
    "Evidence", "compute_evidence", "score_candidate", "HistoryLog",
]
