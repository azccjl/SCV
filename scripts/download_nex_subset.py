"""Download a small NEX-GDDP CMIP6 NetCDF subset to D:\\datatask.

The STAC asset is streamed through xarray and only the requested spatial/time
slice is written locally. The source yearly file is never saved in full.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import requests
import xarray as xr

STAC = "https://planetarycomputer.microsoft.com/api/stac/v1/search"


def find_asset(model: str, scenario: str, year: int, variable: str) -> str:
    query = {
        "collections": ["nasa-nex-gddp-cmip6"],
        "ids": [f"{model}.{scenario}.{year}"],
        "limit": 1,
    }
    response = requests.post(STAC, json=query, timeout=60)
    response.raise_for_status()
    features = response.json().get("features", [])
    if not features or variable not in features[0]["assets"]:
        raise ValueError("未找到对应 STAC 条目或变量，请检查 model/scenario/year/variable")
    return features[0]["assets"][variable]["href"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variable", default="tas", choices=["tas", "pr", "sfcWind", "hurs"])
    parser.add_argument("--model", default="MRI-ESM2-0")
    parser.add_argument("--scenario", default="historical")
    parser.add_argument("--year", type=int, default=2010)
    parser.add_argument("--lon", nargs=2, type=float, default=[130, 150])
    parser.add_argument("--lat", nargs=2, type=float, default=[25, 40])
    parser.add_argument("--start", default=None, help="ISO date, defaults to year-01-01")
    parser.add_argument("--end", default=None, help="ISO date, defaults to year-12-31")
    parser.add_argument("--out-dir", default=r"D:\datatask")
    parser.add_argument("--local-file", default=None, help="已授权下载的本地年度 NetCDF；只从它导出切片")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    start = args.start or f"{args.year}-01-01"
    end = args.end or f"{args.year}-12-31"
    url = find_asset(args.model, args.scenario, args.year, args.variable)
    print(f"读取远程资产: {url}")
    print("仅读取目标区域和时间范围，不保存完整年度文件。")
    source = args.local_file or url
    try:
        ds = xr.open_dataset(source, engine="netcdf4", decode_times=True)
    except Exception as exc:
        raise RuntimeError(
            "远程 Blob 当前拒绝匿名访问。请从 Planetary Computer/赛事授权入口获取文件，"
            "然后用 --local-file 指向本地年度 NetCDF。原始错误: " + str(exc)
        ) from exc
    subset = ds[[args.variable]].sel(
        time=slice(start, end),
        lat=slice(min(args.lat), max(args.lat)),
        lon=slice(min(args.lon), max(args.lon)),
    )
    output = out_dir / f"nex_{args.variable}_{args.model}_{args.scenario}_{args.year}_subset.nc"
    subset.to_netcdf(output)
    manifest = {
        "source": url,
        "variable": args.variable,
        "model": args.model,
        "scenario": args.scenario,
        "year": args.year,
        "time": [start, end],
        "lon": args.lon,
        "lat": args.lat,
        "output": str(output),
        "sizes": {k: int(v) for k, v in subset.sizes.items()},
    }
    (out_dir / (output.stem + ".json")).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
