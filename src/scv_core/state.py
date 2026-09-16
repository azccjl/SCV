"""Immutable analysis state and validation helpers."""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date
from typing import Any, Mapping
import hashlib
import json


DEFAULT_VARIABLES = ("tas", "pr", "sfcWind", "hurs")


@dataclass(frozen=True)
class AnalysisState:
    variables: tuple[str, ...] = ("tas",)
    lon: tuple[float, float] = (130.0, 150.0)
    lat: tuple[float, float] = (25.0, 40.0)
    start: str = "2000-01-01"
    end: str = "2010-12-31"
    aggregation: str = "monthly"
    model: str = "MRI-ESM2-0"
    scenario: str = "historical"
    operation: str = "mean"
    goal: str = "探索变量之间的共同变化"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        variables = tuple(dict.fromkeys(self.variables))
        if not variables:
            raise ValueError("variables must contain at least one variable")
        if any(not isinstance(v, str) or not v.strip() for v in variables):
            raise ValueError("variables must be non-empty strings")
        object.__setattr__(self, "variables", variables)
        self._validate_range("lon", self.lon, -180, 360)
        self._validate_range("lat", self.lat, -90, 90)
        try:
            start, end = date.fromisoformat(self.start), date.fromisoformat(self.end)
        except ValueError as exc:
            raise ValueError("start/end must be ISO dates (YYYY-MM-DD)") from exc
        if start > end:
            raise ValueError("start must not be after end")
        if self.aggregation not in {"daily", "monthly", "seasonal", "annual"}:
            raise ValueError("unsupported aggregation")

    @staticmethod
    def _validate_range(name: str, value: tuple[float, float], low: float, high: float) -> None:
        if len(value) != 2 or value[0] >= value[1] or value[0] < low or value[1] > high:
            raise ValueError(f"{name} must be an increasing pair in [{low}, {high}]")

    def to_dict(self) -> dict[str, Any]:
        return {
            "variables": list(self.variables), "region": {"lon": list(self.lon), "lat": list(self.lat)},
            "time": {"start": self.start, "end": self.end, "aggregation": self.aggregation},
            "model": self.model, "scenario": self.scenario, "operation": self.operation,
            "goal": self.goal, "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "AnalysisState":
        region, time = value.get("region", {}), value.get("time", {})
        return cls(variables=tuple(value.get("variables", ("tas",))), lon=tuple(region.get("lon", (130, 150))),
                   lat=tuple(region.get("lat", (25, 40))), start=time.get("start", "2000-01-01"),
                   end=time.get("end", "2010-12-31"), aggregation=time.get("aggregation", "monthly"),
                   model=value.get("model", "MRI-ESM2-0"), scenario=value.get("scenario", "historical"),
                   operation=value.get("operation", "mean"), goal=value.get("goal", ""),
                   metadata=value.get("metadata", {}))

    @property
    def cache_key(self) -> str:
        payload = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    def evolve(self, **changes: Any) -> "AnalysisState":
        return replace(self, **changes)
