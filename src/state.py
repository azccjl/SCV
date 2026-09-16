from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class AnalysisState:
    variables: list[str] = field(default_factory=lambda: ["tas", "pr"])
    region: dict[str, list[float]] = field(
        default_factory=lambda: {"lon": [130.0, 150.0], "lat": [25.0, 40.0]}
    )
    time: dict[str, str] = field(
        default_factory=lambda: {
            "start": "2000-01-01",
            "end": "2010-12-31",
            "aggregation": "monthly",
        }
    )
    model: str = "MRI-ESM2-0"
    scenario: str = "historical"
    operation: str = "anomaly_and_correlation"
    goal: str = "寻找黑潮区域的温度-降水共同变化"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def key(self) -> str:
        import json

        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True)


@dataclass
class Evidence:
    metrics: dict[str, float]
    sample_count: int
    missing_fraction: float
    runtime_ms: float
    warnings: list[str] = field(default_factory=list)

