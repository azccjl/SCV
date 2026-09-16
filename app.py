from __future__ import annotations

import streamlit as st

from src.actions import generate_actions
from src.data import synthetic_bundle
from src.evidence import compute_evidence
from src.ranking import rank_candidates
from src.state import AnalysisState

st.set_page_config(page_title="Scientific Exploration Recommender", layout="wide")
st.title("Scientific Exploration Recommender")
st.caption("NEX-GDDP 原型：使用确定性本地样例演示 one-step-ahead 推荐，不会自动下载大文件。")

if "state" not in st.session_state:
    st.session_state.state = AnalysisState()
if "history" not in st.session_state:
    st.session_state.history = []

state: AnalysisState = st.session_state.state
bundle = synthetic_bundle()

with st.sidebar:
    st.header("当前分析状态")
    state.goal = st.text_input("科学目标", state.goal)
    operations = ["anomaly_and_correlation", "lagged_correlation", "mean_compare"]
    state.operation = st.selectbox("统计操作", operations, index=operations.index(state.operation) if state.operation in operations else 0)
    st.write("变量：", ", ".join(state.variables))
    if st.button("重置状态"):
        st.session_state.state = AnalysisState()
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

st.subheader("下一步值得探索")
actions = generate_actions(state)
candidates = rank_candidates(bundle, state, actions)
for index, candidate in enumerate(candidates[:3]):
    with st.container(border=True):
        st.markdown(f"**{index + 1}. {candidate.action.label}**")
        st.write(candidate.reason)
        st.json(candidate.scores)
        if st.button("接受此候选", key=f"accept-{index}"):
            st.session_state.history.append({"before": state.to_dict(), "action": candidate.action.label, "score": candidate.score})
            st.session_state.state = candidate.state
            st.rerun()

st.subheader("探索历史")
if st.session_state.history:
    st.dataframe(st.session_state.history, use_container_width=True)
else:
    st.info("尚未接受候选。")

