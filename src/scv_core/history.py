"""Append-only JSONL history suitable for replay and audit."""
from __future__ import annotations
from pathlib import Path
from typing import Any, Iterator, Mapping
import json
from datetime import datetime, timezone
from .state import AnalysisState
from .actions import Action, Candidate


class HistoryLog:
    def __init__(self, path: str | Path): self.path = Path(path)

    def append(self, state_before: AnalysisState, action: Action, state_after: AnalysisState,
               candidate: Candidate | None = None, user_choice: str | None = None,
               rejection_reason: str | None = None, elapsed_seconds: float | None = None) -> None:
        record = {"timestamp": datetime.now(timezone.utc).isoformat(), "state_before": state_before.to_dict(),
                  "action": {"id": action.id, "kind": action.kind, "parameters": action.parameters},
                  "state_after": state_after.to_dict(), "candidate": None if candidate is None else {
                      "score": candidate.score, "components": candidate.components, "reason": candidate.reason,
                      "estimated_cost": candidate.estimated_cost, "evidence": candidate.evidence},
                  "user_choice": user_choice, "rejection_reason": rejection_reason, "elapsed_seconds": elapsed_seconds}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")

    def records(self) -> Iterator[dict[str, Any]]:
        if not self.path.exists(): return
        with self.path.open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip(): yield json.loads(line)

    def replay(self, initial: AnalysisState | None = None) -> AnalysisState | None:
        state = initial
        for record in self.records():
            state = AnalysisState.from_dict(record["state_after"])
        return state
