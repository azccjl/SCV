from __future__ import annotations

import time

import numpy as np
import pandas as pd

from .state import AnalysisState, Evidence


def _safe_corr(left: pd.Series, right: pd.Series) -> float:
    value = left.corr(right)
    return 0.0 if pd.isna(value) else float(value)


def compute_evidence(frame: pd.DataFrame, state: AnalysisState) -> Evidence:
    started = time.perf_counter()
    data = frame.copy()
    data["time"] = pd.to_datetime(data["time"])
    start, end = pd.to_datetime(state.time["start"]), pd.to_datetime(state.time["end"])
    lo, hi = state.region["lon"]
    la, lb = state.region["lat"]
    data = data[data.time.between(start, end) & data.lon.between(lo, hi) & data.lat.between(la, lb)]
    group = data.groupby("time", as_index=False)[state.variables].mean(numeric_only=True)
    group = group.set_index("time").sort_index()
    if state.time.get("aggregation") == "monthly":
        group = group.resample("MS").mean()
    elif state.time.get("aggregation") == "seasonal":
        group = group.resample("QS-DEC").mean()
    group = group.reset_index()
    for variable in state.variables:
        group[f"{variable}_anomaly"] = group[variable] - group[variable].mean()
    metrics: dict[str, float] = {"mean_abs_anomaly": 0.0, "correlation": 0.0}
    if state.variables:
        metrics["mean_abs_anomaly"] = float(group[f"{state.variables[0]}_anomaly"].abs().mean())
    if len(state.variables) >= 2:
        if state.operation == "lagged_correlation":
            metrics["correlation"] = _safe_corr(group[state.variables[0]], group[state.variables[1]].shift(1))
        else:
            metrics["correlation"] = _safe_corr(group[state.variables[0]], group[state.variables[1]])
    missing = float(data[state.variables].isna().mean().mean()) if len(data) else 1.0
    warnings = []
    if len(group) < 12:
        warnings.append("时间样本少于 12 个聚合周期")
    if missing > 0.1:
        warnings.append("缺测比例超过 10%")
    if not len(data):
        warnings.append("当前空间/时间切片没有数据")
    return Evidence(metrics, int(len(group)), missing, (time.perf_counter() - started) * 1000, warnings)
