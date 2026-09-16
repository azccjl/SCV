# SCV

研究计划：

- [面向科学数据探索的下一步推荐：基于 NEX-GDDP CMIP6 子集的原型方案](EXPLORATION_RECOMMENDATION_PLAN.md)
- [前三周实现总结](docs/WEEKS_1_3_IMPLEMENTATION.md)

## 本地运行

```powershell
python -m pip install -r requirements.txt
python run_demo.py
python -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501
```

程序会优先扫描 `D:\datatask\*.nc` 并使用第一个真实切片进行证据计算和候选排序；找不到切片时才使用确定性的本地合成样例。真实 NEX-GDDP NetCDF 也可通过 `src.data.load_local_netcdf` 接入；配置模板见 `data/manifest.example.yaml`。

页面支持连续多步探索。每次接受候选后，时间序列、变量关系散点图、空间分布图和选择前后指标都会按新状态重新计算；探索历史保留完整步骤，也可以逐步回退。

## 下载小范围真实数据

可以从 28 TB 数据中按变量、年份、经纬度拉取小切片，默认保存到 `D:\datatask`：

```powershell
python scripts/download_nex_subset.py --variables tas pr --model MRI-ESM2-0 --scenario historical --year 2010 --lon 130 150 --lat 25 40
```

脚本通过 Planetary Computer STAC 查询真实资产，由官方包自动申请短期 SAS 签名。为避免远程 NetCDF 随机读取卡死，它会临时下载所选变量的年度文件，在本地裁剪并校验后删除年度缓存；`D:\datatask` 最终只保留小切片，无需账号密码。若 `localhost` 无法访问，使用明确地址 `http://127.0.0.1:8501`；也可以运行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/check_local_app.ps1
```
