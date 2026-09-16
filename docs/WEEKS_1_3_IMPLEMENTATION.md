# 前三周实现记录

本记录对应 `EXPLORATION_RECOMMENDATION_PLAN.md` 的阶段 A-C 中可在无原始 28 TB 数据条件下先完成的核心部分。

## 已完成

- `src/scv_core/state.py`：不可变 `AnalysisState`，包括变量、经纬度范围、ISO 日期、聚合尺度、模型/情景、统计操作、目标、稳定缓存键和 JSON 互转。
- `src/scv_core/actions.py`：`Action`、`Candidate`、动作合法性检查、动作应用、确定性候选生成。默认最多返回 3 个候选，支持增加/移除变量、统计量、时间聚合、模型、情景和区域动作。
- `src/scv_core/evidence.py`：证据结构和计划中的透明加权评分：
  `0.30*Relevance + 0.25*InformationGain + 0.15*Novelty + 0.15*Stability + 0.15*(1-Cost)`。
  数据适配器可以传入预先计算的统计量、样本数、缺测比例和证据依据。
- `src/scv_core/history.py`：追加式 JSONL 日志，保存状态转移、动作 ID、候选分数、用户选择、拒绝原因和耗时，并支持回放最后状态。
- `tests/test_core.py`：核心动作/评分和 JSONL 回放测试。
- `pyproject.toml`：最小可编辑安装配置；运行时只依赖 Python 标准库。

## 本地运行

在仓库根目录：

```powershell
python -m pip install -e .
python -c "from scv_core import AnalysisState, generate_candidates; print(generate_candidates(AnalysisState()))"
```

测试需要 pytest：

```powershell
python -m pip install pytest
python -m pytest -q
```

当前环境已成功完成 `pip install -e .` 和标准库 smoke test；由于环境原先没有 pytest，测试命令需先安装该开发依赖。

## 与真实数据适配器的接口约定

真实 NetCDF/Zarr 读取器不应放进核心状态模块。读取器执行候选动作后，将相关性、信息增益、稳定性、成本等归一化到 `[0,1]`，调用 `compute_evidence(candidate, metrics=...)`，再调用 `score_candidate`。这样可以保持 data3 小样例和后续 data2/OpenVisus 适配器的推荐接口一致。

## 仍待完成

前三周中尚未加入 UI、图形证据预览、真实 data3 下载清单和缺测/空切片质量警告；这些属于主任务的适配器和交互层，核心 API 已预留 `Evidence.sample_count`、`missing_fraction`、`basis` 字段。
