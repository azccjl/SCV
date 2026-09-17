"""Download and locally subset selected NEX-GDDP CMIP6 variables."""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import planetary_computer
import requests
import xarray as xr

STAC = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
CHUNK_SIZE = 8 * 1024 * 1024


def find_asset(model: str, scenario: str, year: int, variable: str) -> str:
    response = requests.post(
        STAC,
        json={"collections": ["nasa-nex-gddp-cmip6"], "ids": [f"{model}.{scenario}.{year}"], "limit": 1},
        timeout=60,
    )
    response.raise_for_status()
    features = response.json().get("features", [])
    if not features or variable not in features[0]["assets"]:
        raise ValueError(f"未找到 {model}/{scenario}/{year}/{variable}")
    return features[0]["assets"][variable]["href"]


def download_file(url: str, destination: Path, retries: int = 3) -> None:
    partial = destination.with_suffix(destination.suffix + ".partial")
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            existing = partial.stat().st_size if partial.exists() else 0
            headers = {"Range": f"bytes={existing}-"} if existing else {}
            with requests.get(
                planetary_computer.sign(url), headers=headers, stream=True, timeout=(30, 180)
            ) as response:
                response.raise_for_status()
                resumed = existing > 0 and response.status_code == 206
                if existing and not resumed:
                    existing = 0
                remaining = int(response.headers.get("content-length", 0))
                expected = existing + remaining if remaining else 0
                received = existing
                mode = "ab" if resumed else "wb"
                with partial.open(mode) as handle:
                    for chunk in response.iter_content(CHUNK_SIZE):
                        if not chunk:
                            continue
                        handle.write(chunk)
                        received += len(chunk)
                        if expected:
                            print(
                                f"  {received / 1024**2:.1f}/{expected / 1024**2:.1f} MiB",
                                end="\r",
                                flush=True,
                            )
                if expected and received != expected:
                    raise IOError(f"下载不完整：应为 {expected} 字节，实际 {received} 字节")
            os.replace(partial, destination)
            print(f"  下载完成：{destination.name} ({received / 1024**2:.1f} MiB)", flush=True)
            return
        except (OSError, requests.RequestException) as exc:
            last_error = exc
            if attempt == retries:
                break
            delay = min(10 * attempt, 30)
            print(f"  第 {attempt} 次下载中断，{delay} 秒后从断点继续：{exc}", flush=True)
            time.sleep(delay)
    raise RuntimeError(f"下载失败，已尝试 {retries} 次：{destination.name}") from last_error


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variables", nargs="+", default=["tas", "pr"])
    parser.add_argument("--model", default="MRI-ESM2-0")
    parser.add_argument("--scenario", default="historical")
    parser.add_argument("--year", type=int, default=2010)
    parser.add_argument("--lon", nargs=2, type=float, default=[130, 150])
    parser.add_argument("--lat", nargs=2, type=float, default=[25, 40])
    parser.add_argument("--start", default=None)
    parser.add_argument("--end", default=None)
    parser.add_argument("--out-dir", default=r"D:\datatask")
    parser.add_argument("--retries", type=int, default=3)
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    cache_dir = out_dir / ".cache"
    out_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)
    start = args.start or f"{args.year}-01-01"
    end = args.end or f"{args.year}-12-31"
    subsets = []
    sources = {}

    for variable in args.variables:
        url = find_asset(args.model, args.scenario, args.year, variable)
        sources[variable] = url
        annual = cache_dir / Path(url).name
        if annual.exists():
            print(f"复用已下载缓存：{annual.name}", flush=True)
        else:
            print(f"下载 {variable} 年度文件（裁剪后会自动删除）...", flush=True)
            download_file(url, annual, retries=args.retries)
        with xr.open_dataset(annual, engine="netcdf4", decode_times=True) as ds:
            subset = ds[[variable]].sel(
                time=slice(start, end),
                lat=slice(min(args.lat), max(args.lat)),
                lon=slice(min(args.lon), max(args.lon)),
            ).load()
        if not all(subset.sizes.get(name, 0) for name in ("time", "lat", "lon")):
            raise ValueError(f"{variable} 裁剪结果为空，请检查经纬度和时间")
        subsets.append(subset)
        annual.unlink(missing_ok=True)

    combined = xr.merge(subsets, compat="override")
    output = out_dir / f"nex_{args.model}_{args.scenario}_{args.year}_subset.nc"
    partial_output = output.with_suffix(".partial.nc")
    encoding = {name: {"zlib": True, "complevel": 4} for name in args.variables}
    combined.to_netcdf(partial_output, engine="netcdf4", encoding=encoding)
    with xr.open_dataset(partial_output) as check:
        missing = [name for name in args.variables if name not in check]
        if missing:
            raise ValueError(f"输出校验失败，缺少变量：{missing}")
        sizes = {key: int(value) for key, value in check.sizes.items()}
    os.replace(partial_output, output)
    manifest = {
        "sources": sources,
        "variables": args.variables,
        "model": args.model,
        "scenario": args.scenario,
        "year": args.year,
        "time": [start, end],
        "lon": args.lon,
        "lat": args.lat,
        "output": str(output),
        "sizes": sizes,
    }
    output.with_suffix(".json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
