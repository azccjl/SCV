from __future__ import annotations

from dataclasses import dataclass

from .state import AnalysisState


@dataclass
class Action:
    kind: str
    label: str
    parameters: dict

    def apply(self, state: AnalysisState) -> AnalysisState:
        values = state.to_dict()
        if self.kind == "add_variable":
            variable = self.parameters["variable"]
            if variable not in values["variables"]:
                values["variables"].append(variable)
        elif self.kind == "change_time_window":
            values["time"].update(self.parameters)
        elif self.kind == "change_region":
            values["region"].update(self.parameters)
        elif self.kind == "change_statistic":
            values["operation"] = self.parameters["operation"]
        elif self.kind == "change_model":
            values["model"] = self.parameters["model"]
        else:
            raise ValueError(f"Unsupported action: {self.kind}")
        return AnalysisState(**values)


def generate_actions(state: AnalysisState) -> list[Action]:
    actions = []
    if "sfcWind" not in state.variables:
        actions.append(Action("add_variable", "加入近地面风速", {"variable": "sfcWind"}))
    if "hurs" not in state.variables:
        actions.append(Action("add_variable", "加入相对湿度", {"variable": "hurs"}))
    actions.extend(
        [
            Action("change_time_window", "改用季节聚合", {"aggregation": "seasonal"}),
            Action("change_region", "缩小到黑潮核心区域", {"lon": [135.0, 145.0], "lat": [28.0, 37.0]}),
            Action("change_region", "扩大空间范围", {"lon": [125.0, 155.0], "lat": [20.0, 45.0]}),
            Action("change_statistic", "改用滞后相关", {"operation": "lagged_correlation"}),
            Action("change_model", "比较 GFDL-ESM4", {"model": "GFDL-ESM4"}),
        ]
    )
    return actions
