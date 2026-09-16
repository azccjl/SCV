"""Action model, legality checks, and deterministic candidate generation."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Iterable
import hashlib
import json
from .state import AnalysisState, DEFAULT_VARIABLES


STATISTICS = ("mean", "anomaly", "correlation", "lagged_correlation", "regression")


@dataclass(frozen=True)
class Action:
    kind: str
    parameters: dict[str, Any]

    @property
    def id(self) -> str:
        raw = json.dumps({"kind": self.kind, "parameters": self.parameters}, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()[:12]

    def validate(self, state: AnalysisState) -> None:
        if self.kind == "add_variable":
            v = self.parameters.get("variable")
            if v not in DEFAULT_VARIABLES or v in state.variables:
                raise ValueError("variable is unavailable or already selected")
        elif self.kind == "remove_variable":
            if self.parameters.get("variable") not in state.variables or len(state.variables) == 1:
                raise ValueError("cannot remove this variable")
        elif self.kind == "change_statistic":
            if self.parameters.get("operation") not in STATISTICS:
                raise ValueError("unsupported statistic")
        elif self.kind == "change_time_window":
            if self.parameters.get("aggregation") not in {"daily", "monthly", "seasonal", "annual"}:
                raise ValueError("unsupported aggregation")
        elif self.kind == "change_model":
            if not self.parameters.get("model"):
                raise ValueError("model is required")
        elif self.kind == "change_scenario":
            if not self.parameters.get("scenario"):
                raise ValueError("scenario is required")
        elif self.kind == "change_region":
            lon, lat = self.parameters.get("lon"), self.parameters.get("lat")
            AnalysisState._validate_range("lon", tuple(lon), -180, 360)
            AnalysisState._validate_range("lat", tuple(lat), -90, 90)
        else:
            raise ValueError(f"unsupported action kind: {self.kind}")

    def apply(self, state: AnalysisState) -> AnalysisState:
        self.validate(state)
        p = self.parameters
        if self.kind == "add_variable": return state.evolve(variables=tuple((*state.variables, p["variable"])))
        if self.kind == "remove_variable": return state.evolve(variables=tuple(v for v in state.variables if v != p["variable"]))
        if self.kind == "change_statistic": return state.evolve(operation=p["operation"])
        if self.kind == "change_time_window": return state.evolve(aggregation=p["aggregation"])
        if self.kind == "change_model": return state.evolve(model=p["model"])
        if self.kind == "change_scenario": return state.evolve(scenario=p["scenario"])
        return state.evolve(lon=tuple(p["lon"]), lat=tuple(p["lat"]))


@dataclass(frozen=True)
class Candidate:
    action: Action
    state_after: AnalysisState
    score: float = 0.0
    components: dict[str, float] | None = None
    reason: str = ""
    estimated_cost: float = 0.0
    evidence: dict[str, Any] | None = None


def generate_candidates(state: AnalysisState, limit: int = 3, explored: Iterable[str] = ()) -> list[Candidate]:
    """Generate a small, deterministic, legal action set for the current state."""
    explored = set(explored)
    pool = [Action("add_variable", {"variable": v}) for v in DEFAULT_VARIABLES if v not in state.variables]
    pool += [Action("change_statistic", {"operation": op}) for op in ("anomaly", "correlation", "lagged_correlation") if op != state.operation]
    pool += [Action("change_time_window", {"aggregation": a}) for a in ("seasonal", "annual") if a != state.aggregation]
    candidates = []
    for action in pool:
        if action.id in explored:
            continue
        try: after = action.apply(state)
        except ValueError: continue
        candidates.append(Candidate(action, after, reason=_reason(action), estimated_cost=_cost(state, after)))
    return candidates[:max(0, limit)]


def _reason(action: Action) -> str:
    p = action.parameters
    if action.kind == "add_variable": return f"增加 {p['variable']}，检验跨变量共同变化。"
    if action.kind == "change_statistic": return f"切换为 {p['operation']}，补充当前统计视角。"
    return f"切换时间聚合为 {p['aggregation']}，检查时间尺度敏感性。"


def _cost(before: AnalysisState, after: AnalysisState) -> float:
    area_before = (before.lon[1]-before.lon[0])*(before.lat[1]-before.lat[0])
    area_after = (after.lon[1]-after.lon[0])*(after.lat[1]-after.lat[0])
    return round(min(1.0, (area_after / area_before) * (len(after.variables) / len(before.variables))), 4)
