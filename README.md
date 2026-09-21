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

程序会扫描 `D:\datatask\*.nc` 及配套 JSON 清单，自动建立“模式 - 情景 - 年份 - 变量”目录。侧栏可以选择详细切片，“解释差异”页会汇总全部已下载数据；找不到切片时才使用确定性的本地合成样例。温度统一显示为摄氏度，降水统一显示为 mm/day。

界面按照“识别 - 解释 - 验证”组织：先查看单个切片的时间与空间结构，再比较历史、SSP2-4.5、SSP5-8.5及多模式分歧，最后核查数据覆盖、参数敏感性和探索历史。单年内的前后半年差异明确标为季节差异，不作为长期趋势。

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

## 第二阶段批量数据

可续传批量脚本默认计划下载 3 个模式、历史 2000-2014、SSP2-4.5 与 SSP5-8.5 的 2030-2044 和 2081-2095，共 225 个区域年度切片。每个年度变量先下载、裁剪、校验，再删除年度缓存；状态保存在 `D:\datatask\batch_full_status.json`。

```powershell
python scripts/download_nex_batch.py --variables tas pr --models MRI-ESM2-0 GFDL-ESM4 MIROC6
```

使用 `--max-files 6` 可先验证小批量。最终区域切片预计远小于 2 GB；空间占用小并不表示样本少，原始全球数据不会整库复制到本机。

推荐先运行覆盖优先的锚点批次。它为每个模式下载 2010 历史基准、2035 SSP2-4.5 和 2035 SSP5-8.5，共 9 个切片；原始传输量约数 GB，裁剪后的长期占用只有十几 MB：

```powershell
python scripts/download_nex_batch.py --profile anchors --variables tas pr --models MRI-ESM2-0 GFDL-ESM4 MIROC6
```

需要连续数十年样本时，可下载单个模式的紧凑年代方案：历史期 2000–2014、SSP2-4.5 与 SSP5-8.5 的 2030–2044。45 个年度切片最终约占 75–90 MB，但源文件总传输量约 16–18 GB：

```powershell
python scripts/download_nex_batch.py --profile decades --variables tas pr --models MRI-ESM2-0
```

下载器会保留未完成的 `.partial` 文件并使用 HTTP Range 续传。每个任务有独立超时与重试，进度账本写入 `D:\datatask\batch_anchors_status.json`。
