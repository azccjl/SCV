from __future__ import annotations

import json
import os
from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

from src.actions import generate_actions
from src.data import (
    VARIABLE_LABELS,
    VARIABLE_UNITS,
    DatasetRecord,
    load_local_netcdf,
    scan_local_catalog,
    summarize_records,
    synthetic_bundle,
)
from src.evidence import compute_evidence
from src.ranking import rank_candidates
from src.state import AnalysisState


_default_data_dir = Path(__file__).resolve().parent / "data" / "local"
DATA_DIR = Path(os.environ.get("SCV_DATA_DIR", str(_default_data_dir)))
SCENARIO_LABELS = {"historical": "历史模拟", "ssp245": "SSP2-4.5", "ssp585": "SSP5-8.5"}
SCENARIO_COLORS = {"historical": "#60666b", "ssp245": "#16877c", "ssp585": "#c6503e"}

st.set_page_config(page_title="气候探索推荐器", page_icon="🌏", layout="wide")
st.markdown(
    """<style>
    .block-container {max-width: 1440px; padding-top: 1.6rem; padding-bottom: 3rem;}
    .app-head {padding: .45rem 0 1rem; border-bottom: 1px solid #d8dde1; margin-bottom: 1rem;}
    .app-head h1 {margin: 0 0 .3rem; font-size: 1.85rem; letter-spacing: 0;}
    .app-head p {margin: 0; color: #53616a;}
    .finding {padding: .8rem 1rem; background: #edf6f2; border-left: 4px solid #16877c; margin: .6rem 0 1rem;}
    .warning-note {padding: .75rem 1rem; background: #fff5e8; border-left: 4px solid #d18a2e; margin: .6rem 0 1rem;}
    div[data-testid="stMetric"] {border-top: 2px solid #d8dde1; padding-top: .55rem;}
    </style>""",
    unsafe_allow_html=True,
)
st.markdown(
    """<div class="app-head"><h1>气候探索推荐器</h1>
    <p>识别候选变化，解释情景与模型差异，再验证证据是否稳健。</p></div>""",
    unsafe_allow_html=True,
)


@st.cache_data(ttl=10, show_spinner=False)
def catalog() -> list[DatasetRecord]:
    return scan_local_catalog(DATA_DIR)


@st.cache_data(show_spinner=False)
def load_record(path: str):
    return load_local_netcdf(path)


@st.cache_data(ttl=30, show_spinner="正在汇总本地数据目录…")
def catalog_summary(signature: tuple[tuple[str, int, int], ...]) -> pd.DataFrame:
    by_path = {str(record.path): record for record in catalog()}
    chosen = [by_path[path] for path, _, _ in signature if path in by_path]
    return summarize_records(chosen)


def initial_state(frame: pd.DataFrame, record: DatasetRecord | None) -> AnalysisState:
    state = AnalysisState()
    state.time["start"] = str(pd.to_datetime(frame["time"]).min().date())
    state.time["end"] = str(pd.to_datetime(frame["time"]).max().date())
    state.region["lon"] = [float(frame["lon"].min()), float(frame["lon"].max())]
    state.region["lat"] = [float(frame["lat"].min()), float(frame["lat"].max())]
    state.variables = [name for name in ["tas", "pr"] if name in frame]
    if record:
        state.model, state.scenario = record.model, record.scenario
    return state


def filtered_frame(frame: pd.DataFrame, state: AnalysisState) -> pd.DataFrame:
    data = frame.copy()
    data["time"] = pd.to_datetime(data["time"])
    start, end = pd.to_datetime(state.time["start"]), pd.to_datetime(state.time["end"])
    lo, hi = state.region["lon"]
    la, lb = state.region["lat"]
    return data[data.time.between(start, end) & data.lon.between(lo, hi) & data.lat.between(la, lb)].copy()


def monthly_series(frame: pd.DataFrame, variables: list[str]) -> pd.DataFrame:
    data = frame.groupby("time", as_index=False)[variables].mean(numeric_only=True).set_index("time")
    data = data.resample("MS").mean().reset_index()
    return data.melt("time", var_name="variable", value_name="value").dropna()


def half_year_change(frame: pd.DataFrame, variable: str) -> tuple[float, float, float]:
    values = frame.groupby("time", as_index=False)[variable].mean().dropna().sort_values("time")
    if len(values) < 2:
        return np.nan, np.nan, np.nan
    midpoint = len(values) // 2
    before = float(values.iloc[:midpoint][variable].mean())
    after = float(values.iloc[midpoint:][variable].mean())
    return before, after, after - before


def batch_progress() -> tuple[int, int, str | None]:
    ledger = DATA_DIR / "batch_anchors_status.json"
    if not ledger.exists():
        return 0, 0, None
    try:
        plan = json.loads(ledger.read_text(encoding="utf-8")).get("plan", [])
    except (OSError, json.JSONDecodeError):
        return 0, 0, None
    completed = 0
    current = None
    for item in plan:
        output = DATA_DIR / f"nex_{item['model']}_{item['scenario']}_{item['year']}_subset.nc"
        if output.exists():
            completed += 1
        elif current is None:
            current = f"{item['model']} · {SCENARIO_LABELS.get(item['scenario'], item['scenario'])} · {item['year']}"
    return completed, len(plan), current


records = catalog()
using_synthetic = not records

with st.sidebar:
    st.header("数据与问题")
    if records:
        models = sorted({record.model for record in records})
        selected_model = st.selectbox("气候模式", models)
        model_records = [record for record in records if record.model == selected_model]
        scenarios = sorted({record.scenario for record in model_records}, key=lambda value: ["historical", "ssp245", "ssp585"].index(value))
        selected_scenario = st.selectbox("情景", scenarios, format_func=lambda value: SCENARIO_LABELS.get(value, value))
        scenario_records = [record for record in model_records if record.scenario == selected_scenario]
        years = sorted(record.year for record in scenario_records)
        selected_year = st.selectbox("详细查看年份", years, index=len(years) - 1)
        selected_record = next(record for record in scenario_records if record.year == selected_year)
        bundle = load_record(str(selected_record.path))
    else:
        selected_record = None
        bundle = synthetic_bundle()
        st.warning("没有发现本地 NetCDF，暂时使用合成数据。")

    available_variables = [name for name in VARIABLE_LABELS if name in bundle.frame]
    selected_variable = st.selectbox("主要变量", available_variables, format_func=lambda value: VARIABLE_LABELS[value])
    st.caption("所有筛选都会重算图表与证据；投影情景不是天气预测。")
    completed_downloads, planned_downloads, current_download = batch_progress()
    if planned_downloads:
        st.divider()
        st.caption("锚点数据下载")
        st.progress(completed_downloads / planned_downloads, text=f"已就绪 {completed_downloads}/{planned_downloads} 个切片")
        if current_download:
            st.caption(f"下一项：{current_download}")
        if st.button("刷新数据目录", icon=":material/refresh:", width="stretch"):
            catalog.clear()
            catalog_summary.clear()
            st.rerun()

dataset_key = str(selected_record.path) if selected_record else "synthetic"
if st.session_state.get("dataset_key") != dataset_key:
    st.session_state.dataset_key = dataset_key
    st.session_state.state = initial_state(bundle.frame, selected_record)
    st.session_state.history = []
state: AnalysisState = st.session_state.state
state.variables = [selected_variable] + [name for name in state.variables if name != selected_variable and name in bundle.frame]
if len(state.variables) == 1:
    secondaries = [name for name in available_variables if name != selected_variable]
    if secondaries:
        state.variables.append(secondaries[0])

total_size = sum(record.size_bytes for record in records)
inventory = st.columns(4)
inventory[0].metric("本地切片", len(records))
inventory[1].metric("模式", len({record.model for record in records}) if records else 0)
inventory[2].metric("情景", len({record.scenario for record in records}) if records else 0)
inventory[3].metric("占用空间", f"{total_size / 1024**2:.1f} MB")

if records:
    st.success(f"当前详细数据：{selected_record.label}；{', '.join(selected_record.variables)}")
    if selected_record.scenario != "historical":
        st.markdown('<div class="warning-note"><strong>阅读提示：</strong>SSP 是条件性气候投影，不是对某一年天气的确定预测。结论应同时查看多个模式与历史基准。</div>', unsafe_allow_html=True)

tab_identify, tab_interpret, tab_validate, tab_next = st.tabs(["识别变化", "解释差异", "验证稳健性", "下一步推荐"])

with tab_identify:
    st.subheader("当前切片里发生了什么")
    current_frame = filtered_frame(bundle.frame, state)
    primary_label = VARIABLE_LABELS[selected_variable]
    unit = VARIABLE_UNITS[selected_variable]
    before, after, delta = half_year_change(current_frame, selected_variable)
    coverage = float(current_frame[selected_variable].notna().mean()) if len(current_frame) else 0.0
    if selected_record and selected_record.year == pd.to_datetime(current_frame.time).dt.year.min():
        message = (
            f"{selected_record.year} 年内后半年相对前半年的{primary_label}差值为 {delta:+.2f} {unit}。"
            "这是季节差异，不能解释为长期气候趋势。"
        )
    else:
        message = f"当前时间窗口内后半段相对前半段的{primary_label}差值为 {delta:+.2f} {unit}。"
    st.markdown(f'<div class="finding"><strong>当前读数：</strong>{message}</div>', unsafe_allow_html=True)
    metrics = st.columns(4)
    metrics[0].metric("前半段平均", f"{before:.2f} {unit}")
    metrics[1].metric("后半段平均", f"{after:.2f} {unit}", f"{delta:+.2f} {unit}")
    metrics[2].metric("有效格点比例", f"{coverage:.1%}")
    metrics[3].metric("日样本", current_frame["time"].nunique())
    if coverage < 0.5:
        st.warning("当前区域有效格点不足一半。该范围包含大量海洋格点，而 NEX-GDDP 在这里存在明显缺测；不要把空白区解释为没有变化。")

    series = monthly_series(current_frame, state.variables)
    if not series.empty:
        series["label"] = series["variable"].map(VARIABLE_LABELS)
        line = alt.Chart(series).mark_line(point=True).encode(
            x=alt.X("time:T", title="时间"), y=alt.Y("value:Q", title=None, scale=alt.Scale(zero=False)),
            color=alt.Color("label:N", title=None),
            tooltip=[alt.Tooltip("time:T", title="月份"), alt.Tooltip("label:N", title="变量"), alt.Tooltip("value:Q", title="区域平均", format=".3f")],
        ).properties(height=180).facet(row=alt.Row("label:N", title=None)).resolve_scale(y="independent")
        st.altair_chart(line, width="stretch")
        st.caption("月平均保留季节循环。不同变量使用独立纵轴，不能用线条高度直接比较量级。")

    spatial = current_frame.groupby(["lon", "lat"], as_index=False)[selected_variable].mean().dropna()
    if not spatial.empty:
        spatial_chart = alt.Chart(spatial).mark_rect().encode(
            x=alt.X("lon:O", title="经度"), y=alt.Y("lat:O", title="纬度"),
            color=alt.Color(f"{selected_variable}:Q", title=f"{primary_label} ({unit})", scale=alt.Scale(scheme="viridis")),
            tooltip=[alt.Tooltip("lon:Q", title="经度"), alt.Tooltip("lat:Q", title="纬度"), alt.Tooltip(f"{selected_variable}:Q", title=primary_label, format=".3f")],
        ).properties(height=340)
        st.altair_chart(spatial_chart, width="stretch")
        st.caption("全年平均空间分布；空白是缺测，不代表零值。")

    if records:
        availability = pd.DataFrame([{"model": r.model, "scenario": SCENARIO_LABELS.get(r.scenario, r.scenario), "year": r.year} for r in records])
        availability["dataset"] = availability["model"] + " · " + availability["scenario"]
        availability_chart = alt.Chart(availability).mark_rect().encode(
            x=alt.X("year:O", title="年份"), y=alt.Y("dataset:N", title=None),
            color=alt.Color("count():Q", legend=None, scale=alt.Scale(range=["#e8ecee", "#236b5d"])),
            tooltip=[alt.Tooltip("dataset:N", title="数据组"), alt.Tooltip("year:O", title="年份")],
        ).properties(title="本地数据覆盖", height=max(100, 28 * availability.dataset.nunique()))
        st.altair_chart(availability_chart, width="stretch")

with tab_interpret:
    st.subheader("情景与模式差异")
    if records:
        signature = tuple((str(r.path), r.size_bytes, int(r.path.stat().st_mtime)) for r in records)
        summary = catalog_summary(signature)
    else:
        summary = pd.DataFrame()
    if summary.empty or selected_variable not in summary:
        st.info("还没有足够的本地数据形成跨年或跨情景比较。批量下载完成后这里会自动出现。")
    else:
        summary["scenario_label"] = summary["scenario"].map(SCENARIO_LABELS)
        historical = summary[summary.scenario == "historical"].groupby("model")[selected_variable].mean().rename("baseline")
        summary = summary.join(historical, on="model")
        summary["anomaly"] = summary[selected_variable] - summary["baseline"]
        annual = alt.Chart(summary.dropna(subset=[selected_variable])).mark_line(point=True).encode(
            x=alt.X("year:Q", title="年份", axis=alt.Axis(format="d")),
            y=alt.Y(f"{selected_variable}:Q", title=f"区域年平均 {primary_label} ({unit})", scale=alt.Scale(zero=False)),
            color=alt.Color("scenario:N", title="情景", scale=alt.Scale(domain=list(SCENARIO_COLORS), range=list(SCENARIO_COLORS.values())), legend=alt.Legend(labelExpr="datum.label == 'historical' ? '历史模拟' : datum.label == 'ssp245' ? 'SSP2-4.5' : 'SSP5-8.5'")),
            strokeDash=alt.StrokeDash("model:N", title="模式"),
            tooltip=["model:N", alt.Tooltip("scenario_label:N", title="情景"), alt.Tooltip("year:Q", title="年份", format="d"), alt.Tooltip(f"{selected_variable}:Q", title=primary_label, format=".3f")],
        ).properties(height=360)
        st.altair_chart(annual, width="stretch")
        st.caption("每条线代表一个气候模式。跨模式结论应关注方向是否一致，而不只看集合平均。")

        future = summary[(summary.scenario != "historical") & summary.anomaly.notna()].copy()
        if future.empty:
            st.info("当前只有历史切片。至少下载同一模式的历史期和未来 SSP 切片后，才能计算相对历史基准的变化。")
        else:
            agreement = future.groupby(["scenario", "year"], as_index=False).agg(
                median=("anomaly", "median"), q1=("anomaly", lambda values: values.quantile(.25)),
                q3=("anomaly", lambda values: values.quantile(.75)), models=("model", "nunique"),
                positive=("anomaly", lambda values: float((values > 0).mean())),
            )
            agreement["scenario_label"] = agreement["scenario"].map(SCENARIO_LABELS)
            band = alt.Chart(agreement).mark_area(opacity=.18).encode(
                x=alt.X("year:Q", title="年份", axis=alt.Axis(format="d")), y=alt.Y("q1:Q", title=f"相对历史基准变化 ({unit})"), y2="q3:Q",
                color=alt.Color("scenario:N", scale=alt.Scale(domain=list(SCENARIO_COLORS), range=list(SCENARIO_COLORS.values())), legend=None),
            )
            median = alt.Chart(agreement).mark_line(point=True, strokeWidth=3).encode(
                x="year:Q", y="median:Q", color=alt.Color("scenario:N", scale=alt.Scale(domain=list(SCENARIO_COLORS), range=list(SCENARIO_COLORS.values())), legend=None),
                tooltip=[alt.Tooltip("scenario_label:N", title="情景"), alt.Tooltip("year:Q", title="年份", format="d"), alt.Tooltip("median:Q", title="中位变化", format="+.3f"), alt.Tooltip("positive:Q", title="正变化模式比例", format=".0%"), alt.Tooltip("models:Q", title="模式数")],
            )
            st.altair_chart((band + median).properties(height=300), width="stretch")
            st.caption("实线是跨模式中位数，带状区是四分位范围。同向模式比例越高，方向性证据越一致；这仍不消除情景与模型不确定性。")
            st.download_button("下载当前比较表", summary.to_csv(index=False).encode("utf-8-sig"), "scv_comparison.csv", "text/csv")

with tab_validate:
    st.subheader("证据是否经得起替换设置")
    evidence = compute_evidence(bundle.frame, state)
    checks = st.columns(4)
    checks[0].metric("聚合周期", evidence.sample_count)
    checks[1].metric("变量相关", f"{evidence.metrics.get('correlation', 0):.3f}")
    checks[2].metric("缺测比例", f"{evidence.missing_fraction:.1%}")
    checks[3].metric("计算耗时", f"{evidence.runtime_ms:.0f} ms")
    for warning in evidence.warnings:
        st.warning(warning)
    st.markdown(
        """
        **验证清单**

        1. 用至少两个未来情景检查方向是否一致，并明确情景之间何时分叉。
        2. 用多个模式检查结论是否由单一模式驱动，同时报告中位数、离散范围和同向比例。
        3. 更换历史基准期、季节和空间范围，确认结论不是参数选择造成。
        4. 回到日尺度或格点尺度核查极端事件，避免把年均变化等同于风险变化。
        """
    )
    if not summary.empty:
        display_columns = [name for name in ["model", "scenario_label", "year", selected_variable, f"{selected_variable}_coverage"] if name in summary]
        st.dataframe(summary[display_columns].sort_values(["model", "year"]), hide_index=True, width="stretch")

with tab_next:
    st.subheader("下一步值得探索什么")
    actions = [
        action for action in generate_actions(state)
        if (action.kind != "add_variable" or action.parameters["variable"] in bundle.frame.columns)
        and action.kind != "change_model"
    ]
    actions = [action for action in actions if action.apply(state).to_dict() != state.to_dict()]
    visited = {AnalysisState(**item["before_state"]).key() for item in st.session_state.history}
    actions = [action for action in actions if action.apply(state).key() not in visited]
    candidates = rank_candidates(bundle, state, actions)
    for index, candidate in enumerate(candidates[:3]):
        with st.container(border=True):
            st.markdown(f"**{index + 1}. {candidate.action.label}**")
            st.write(candidate.reason)
            st.caption(f"选择后预计有 {candidate.evidence.sample_count} 个聚合周期，缺测比例 {candidate.evidence.missing_fraction:.1%}。推荐分数是排序线索，不是科学真值。")
            if st.button("采用并重新计算", key=f"accept-{index}"):
                st.session_state.history.append({"before_state": state.to_dict(), "action": candidate.action.label, "score": candidate.score})
                st.session_state.state = candidate.state
                st.rerun()
    if st.session_state.history:
        history = pd.DataFrame([{"步骤": i, "选择": item["action"], "推荐分数": round(item["score"], 3)} for i, item in enumerate(st.session_state.history, 1)])
        st.dataframe(history, hide_index=True, width="stretch")
        if st.button("回退上一步"):
            last = st.session_state.history.pop()
            st.session_state.state = AnalysisState(**last["before_state"])
            st.rerun()
    else:
        st.info("还没有采用推荐。系统只给出少量候选，最终选择保留给分析者。")
