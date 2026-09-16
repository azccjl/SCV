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

## 下载小范围真实数据

可以从 28 TB 数据中按变量、年份、经纬度拉取小切片，默认保存到 `D:\datatask`：

```powershell
python scripts/download_nex_subset.py --variable tas --model MRI-ESM2-0 --scenario historical --year 2010 --lon 130 150 --lat 25 40
```

脚本通过 Planetary Computer STAC 查询真实资产，并用 xarray 只写入指定切片；不会自动保存完整年度文件。若 `localhost` 无法访问，先确认终端仍在运行 Streamlit，然后使用明确地址 `http://127.0.0.1:8501`；也可以运行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/check_local_app.ps1
```
