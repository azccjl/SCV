"""Resumable batch download plan for compact NEX-GDDP regional subsets."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path


MODELS = ["MRI-ESM2-0", "GFDL-ESM4", "MIROC6"]
PERIODS = {
    "historical": range(2000, 2015),
    "ssp245": [*range(2030, 2045), *range(2081, 2096)],
    "ssp585": [*range(2030, 2045), *range(2081, 2096)],
}
ANCHOR_PERIODS = {
    "historical": [2010],
    "ssp245": [2035],
    "ssp585": [2035],
}


def build_tasks(models: list[str], variables: list[str], periods: dict[str, object] | None = None) -> list[dict[str, object]]:
    periods = periods or PERIODS
    return [
        {"model": model, "scenario": scenario, "year": year, "variables": variables}
        for model in models
        for scenario, years in periods.items()
        for year in years
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", nargs="+", default=MODELS)
    parser.add_argument("--variables", nargs="+", default=["tas", "pr"])
    parser.add_argument("--lon", nargs=2, type=float, default=[130, 150])
    parser.add_argument("--lat", nargs=2, type=float, default=[25, 40])
    parser.add_argument("--out-dir", default=r"D:\datatask")
    parser.add_argument("--max-files", type=int, default=0, help="0 means run the full 225-file phase-two plan")
    parser.add_argument("--retry-delay", type=int, default=20)
    parser.add_argument("--retries", type=int, default=2, help="Retries for each model/scenario/year task")
    parser.add_argument("--timeout-minutes", type=int, default=30)
    parser.add_argument("--profile", choices=["full", "anchors"], default="full")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = out_dir / f"batch_{args.profile}_status.json"
    periods = ANCHOR_PERIODS if args.profile == "anchors" else PERIODS
    tasks = build_tasks(args.models, args.variables, periods)
    if args.max_files:
        tasks = tasks[: args.max_files]
    status = {"plan": tasks, "completed": [], "failed": [], "updated_at": None}
    if ledger_path.exists():
        try:
            previous = json.loads(ledger_path.read_text(encoding="utf-8"))
            status["completed"] = previous.get("completed", [])
            status["failed"] = previous.get("failed", [])
        except (OSError, json.JSONDecodeError):
            pass

    completed = {(item["model"], item["scenario"], int(item["year"])) for item in status["completed"]}
    downloader = Path(__file__).with_name("download_nex_subset.py")
    for index, task in enumerate(tasks, 1):
        key = (task["model"], task["scenario"], int(task["year"]))
        output = out_dir / f"nex_{key[0]}_{key[1]}_{key[2]}_subset.nc"
        if key in completed or output.exists():
            print(f"[{index}/{len(tasks)}] skip {key}: already present", flush=True)
            continue
        command = [
            sys.executable, str(downloader), "--variables", *args.variables,
            "--model", str(key[0]), "--scenario", str(key[1]), "--year", str(key[2]),
            "--lon", *(str(value) for value in args.lon),
            "--lat", *(str(value) for value in args.lat), "--out-dir", str(out_dir),
        ]
        print(f"[{index}/{len(tasks)}] download {key}", flush=True)
        returncode = 1
        for attempt in range(1, args.retries + 1):
            try:
                result = subprocess.run(command, check=False, timeout=args.timeout_minutes * 60)
                returncode = result.returncode
            except subprocess.TimeoutExpired:
                returncode = 124
                print(f"  task timed out after {args.timeout_minutes} minutes", flush=True)
            if returncode == 0:
                break
            if attempt < args.retries:
                print(f"  retry {attempt + 1}/{args.retries} after {args.retry_delay}s", flush=True)
                time.sleep(args.retry_delay)
        entry = {"model": key[0], "scenario": key[1], "year": key[2]}
        if returncode == 0:
            status["completed"].append(entry)
            completed.add(key)
        else:
            status["failed"] = [item for item in status["failed"] if not all(item.get(k) == v for k, v in entry.items())]
            status["failed"].append({**entry, "returncode": returncode})
        status["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        ledger_path.write_text(json.dumps(status, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
