# SCV

研究计划：

- [面向科学数据探索的下一步推荐：基于 NEX-GDDP CMIP6 子集的原型方案](EXPLORATION_RECOMMENDATION_PLAN.md)
- [前三周实现总结](docs/WEEKS_1_3_IMPLEMENTATION.md)

## 本地运行

```powershell
python -m pip install -r requirements.txt
python run_demo.py
python -m streamlit run app.py
```

默认使用确定性的本地合成样例，不会自动下载赛事数据。真实 NEX-GDDP NetCDF 可通过 `src.data.load_local_netcdf` 接入；配置模板见 `data/manifest.example.yaml`。
