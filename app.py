from __future__ import annotations

import streamlit as st
import pandas as pd
import altair as alt

from src.actions import generate_actions
from src.data import find_local_bundle, synthetic_bundle
from src.evidence import compute_evidence
from src.ranking import rank_candidates
from src.state import AnalysisState

st.set_page_config(page_title="Scientific Exploration Recommender", layout="wide")
st.title("Scientific Exploration Recommender")
st.caption("NEX-GDDP 原型：优先使用 D:\\datatask 中经过校验的真实气候数据切片。")

bundle = find_local_bundle()
if bundle is None:
    bundle = synthetic_bundle()
    st.warning("未找到同时包含 tas 和 pr 的有效本地切片，当前使用合成样例。")
else:
    st.success(f"数据源：本地真实切片 `{bundle.source}`")


def initial_state() -> AnalysisState:
    state = AnalysisState()
    if bundle.source != "synthetic":
        state.time["start"] = str(bundle.frame["time"].min().date())
        state.time["end"] = str(bundle.frame["time"].max().date())
        state.region["lon"] = [float(bundle.frame["lon"].min()), float(bundle.frame["lon"].max())]
        state.region["lat"] = [float(bundle.frame["lat"].min()), float(bundle.frame["lat"].max())]
    return state


def chart_frame(frame: pd.DataFrame, state: AnalysisState) -> pd.DataFrame:
    data = frame.copy()
    data["time"] = pd.to_datetime(data["time"])
    start = pd.to_datetime(state.time["start"])
    end = pd.to_datetime(state.time["end"])
    lo, hi = state.region["lon"]
    la, lb = state.region["lat"]
    data = data[data.time.between(start, end) & data.lon.between(lo, hi) & data.lat.between(la, lb)]
    series = data.groupby("time", as_index=False)[state.variables].mean(numeric_only=True).set_index("time")
    if state.time.get("aggregation") == "monthly":
        series = series.resample("MS").mean()
    elif state.time.get("aggregation") == "seasonal":
        series = series.resample("QS-DEC").mean()
    return series.reset_index().melt("time", var_name="variable", value_name="value").dropna()


def relationship_frame(frame: pd.DataFrame, state: AnalysisState) -> pd.DataFrame:
    wide = chart_frame(frame, state).pivot(index="time", columns="variable", values="value").reset_index()
    if len(state.variables) < 2 or not set(state.variables[:2]).issubset(wide.columns):
        return pd.DataFrame()
    left, right = state.variables[:2]
    if state.operation == "lagged_correlation":
        wide[right] = wide[right].shift(1)
    return wide[["time", left, right]].dropna()


def spatial_frame(frame: pd.DataFrame, state: AnalysisState) -> pd.DataFrame:
    data = frame.copy()
    data["time"] = pd.to_datetime(data["time"])
    start = pd.to_datetime(state.time["start"])
    end = pd.to_datetime(state.time["end"])
    lo, hi = state.region["lon"]
    la, lb = state.region["lat"]
    data = data[data.time.between(start, end) & data.lon.between(lo, hi) & data.lat.between(la, lb)]
    latest = data["time"].max()
    data = data[data.time == latest]
    return data.groupby(["lon", "lat"], as_index=False)[state.variables[0]].mean().dropna()

if "state" not in st.session_state:
    st.session_state.state = initial_state()
if "history" not in st.session_state:
    st.session_state.history = []

state: AnalysisState = st.session_state.state

with st.sidebar:
    st.header("当前分析状态")
    state.goal = st.text_input("科学目标", state.goal)
    operations = ["anomaly_and_correlation", "lagged_correlation", "mean_compare"]
    state.operation = st.selectbox("统计操作", operations, index=operations.index(state.operation) if state.operation in operations else 0)
    st.write("变量：", ", ".join(state.variables))
    if st.button("重置状态"):
        st.session_state.state = initial_state()
        st.session_state.history = []
        st.rerun()

current = compute_evidence(bundle.frame, state)
st.subheader("当前证据")
cols = st.columns(4)
cols[0].metric("样本周期", current.sample_count)
cols[1].metric("相关系数", f"{current.metrics.get('correlation', 0):.3f}")
cols[2].metric("缺测比例", f"{current.missing_fraction:.1%}")
cols[3].metric("计算耗时", f"{current.runtime_ms:.1f} ms")
for warning in current.warnings:
    st.warning(warning)

st.subheader("选择产生了什么变化")
series = chart_frame(bundle.frame, state)
if not series.empty:
    line = alt.Chart(series).mark_line(point=True).encode(
        x=alt.X("time:T", title="时间"),
        y=alt.Y("value:Q", title="区域平均值"),
        color=alt.Color("variable:N", title="变量"),
        tooltip=[alt.Tooltip("time:T", title="时间"), "variable:N", alt.Tooltip("value:Q", format=".4g")],
    ).properties(height=150).facet(row=alt.Row("variable:N", title=None)).resolve_scale(y="independent")
    st.altair_chart(line, width="stretch")
    st.caption("该图按当前区域、时间范围和聚合方式重新计算；缺测值保留为空，不做插值。")

    relation = relationship_frame(bundle.frame, state)
    if not relation.empty:
        left, right = state.variables[:2]
        relation_title = "前一期降水与当前温度" if state.operation == "lagged_correlation" else "同期温度与降水"
        scatter = alt.Chart(relation).mark_circle(size=90, opacity=0.8).encode(
            x=alt.X(f"{left}:Q", title=f"{left}（K）", scale=alt.Scale(zero=False)),
            y=alt.Y(f"{right}:Q", title=f"{right}（kg m⁻² s⁻¹）", scale=alt.Scale(zero=False)),
            color=alt.Color("month(time):O", title="月份"),
            tooltip=[alt.Tooltip("time:T", title="时间"), alt.Tooltip(f"{left}:Q", format=".3f"), alt.Tooltip(f"{right}:Q", format=".4g")],
        ).properties(title=relation_title, height=280)
        st.altair_chart(scatter, width="stretch")

    map_data = spatial_frame(bundle.frame, state)
    if not map_data.empty:
        heat = alt.Chart(map_data).mark_rect().encode(
            x=alt.X("lon:O", title="经度"),
            y=alt.Y("lat:O", title="纬度"),
            color=alt.Color(f"{state.variables[0]}:Q", title=state.variables[0]),
            tooltip=["lon:Q", "lat:Q", alt.Tooltip(f"{state.variables[0]}:Q", format=".4g")],
        ).properties(height=260)
        st.altair_chart(heat, width="stretch")
        st.caption(f"上图显示最新时刻的 {state.variables[0]} 空间分布；灰色/空白网格表示没有有效观测。")

if st.session_state.history:
    previous = st.session_state.history[-1]["before_state"]
    previous_evidence = compute_evidence(bundle.frame, AnalysisState(**previous))
    comparison = pd.DataFrame(
        {
            "指标": ["样本周期", "相关系数", "缺测比例"],
            "选择前": [previous_evidence.sample_count, previous_evidence.metrics.get("correlation", 0), previous_evidence.missing_fraction],
            "选择后": [current.sample_count, current.metrics.get("correlation", 0), current.missing_fraction],
        }
    )
    st.dataframe(comparison, hide_index=True, width="stretch")
    comparison_long = comparison.melt("指标", var_name="阶段", value_name="值")
    change_chart = alt.Chart(comparison_long).mark_bar().encode(
        x=alt.X("阶段:N", title=None),
        y=alt.Y("值:Q", title=None),
        color=alt.Color("阶段:N", title=None),
        tooltip=["指标:N", "阶段:N", alt.Tooltip("值:Q", format=".4g")],
    ).properties(height=120).facet(column=alt.Column("指标:N", title=None)).resolve_scale(y="independent")
    st.altair_chart(change_chart, width="stretch")

st.subheader("下一步值得探索")
actions = [
    action for action in generate_actions(state)
    if (action.kind != "add_variable" or action.parameters["variable"] in bundle.frame.columns)
    and action.kind != "change_model"
]
actions = [action for action in actions if action.apply(state).to_dict() != state.to_dict()]
visited_keys = {AnalysisState(**item["before_state"]).key() for item in st.session_state.history}
actions = [action for action in actions if action.apply(state).key() not in visited_keys]
candidates = rank_candidates(bundle, state, actions)
for index, candidate in enumerate(candidates[:3]):
    with st.container(border=True):
        st.markdown(f"**{index + 1}. {candidate.action.label}**")
        st.write(candidate.reason)
        delta = candidate.evidence.metrics.get("correlation", 0) - current.metrics.get("correlation", 0)
        st.caption(
            f"若选择：样本周期 {current.sample_count} → {candidate.evidence.sample_count}；"
            f"相关系数 {current.metrics.get('correlation', 0):.3f} → "
            f"{candidate.evidence.metrics.get('correlation', 0):.3f}（变化 {delta:+.3f}）"
        )
        st.json(candidate.scores)
        if st.button("接受此候选", key=f"accept-{index}"):
            st.session_state.history.append({"before_state": state.to_dict(), "action": candidate.action.label, "score": candidate.score})
            st.session_state.state = candidate.state
            st.rerun()

if st.session_state.history and st.button("回退上一步"):
    last = st.session_state.history.pop()
    st.session_state.state = AnalysisState(**last["before_state"])
    st.rerun()

st.subheader("探索历史")
if st.session_state.history:
    history_rows = [
        {"步骤": index, "选择": item["action"], "推荐分数": round(item["score"], 3)}
        for index, item in enumerate(st.session_state.history, 1)
    ]
    st.dataframe(history_rows, hide_index=True, width="stretch")
else:
    st.info("尚未接受候选。")
