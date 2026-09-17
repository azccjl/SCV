from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


VARIABLES = ["tas", "tasmax", "tasmin", "pr", "sfcWind", "hurs", "rsds", "rlds"]
VARIABLE_LABELS = {
    "tas": "近地面气温", "tasmax": "日最高气温", "tasmin": "日最低气温",
    "pr": "降水", "sfcWind": "近地面风速", "hurs": "相对湿度",
    "rsds": "向下短波辐射", "rlds": "向下长波辐射",
}
VARIABLE_UNITS = {
    "tas": "°C", "tasmax": "°C", "tasmin": "°C", "pr": "mm/day",
    "sfcWind": "m/s", "hurs": "%", "rsds": "W/m²", "rlds": "W/m²",
}
_FILENAME = re.compile(r"^nex_(?P<model>.+)_(?P<scenario>historical|ssp245|ssp585)_(?P<year>\d{4})_subset\.nc$")


@dataclass
class DatasetBundle:
    frame: pd.DataFrame
    source: str
    metadata: dict[str, object]


@dataclass(frozen=True)
class DatasetRecord:
    path: Path
    model: str
    scenario: str
    year: int
    variables: tuple[str, ...]
    lon: tuple[float, float] | None = None
    lat: tuple[float, float] | None = None
    size_bytes: int = 0

    @property
    def label(self) -> str:
        return f"{self.model} · {self.scenario} · {self.year}"


def _standardize_units(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    for variable in ("tas", "tasmax", "tasmin"):
        values = frame[variable].dropna() if variable in frame else pd.Series(dtype=float)
        if not values.empty and values.median() > 100:
            frame[variable] = frame[variable] - 273.15
    values = frame["pr"].dropna() if "pr" in frame else pd.Series(dtype=float)
    if not values.empty and values.median() < 0.1:
        frame["pr"] = frame["pr"] * 86400.0
    return frame


def synthetic_bundle(seed: int = 7, periods: int = 132) -> DatasetBundle:
    """Create a deterministic, small climate-like dataset for local demos/tests."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2000-01-01", periods=periods, freq="MS")
    lon = np.linspace(130, 150, 12)
    lat = np.linspace(25, 40, 10)
    rows = []
    for i, date in enumerate(dates):
        seasonal = np.sin(2 * np.pi * i / 12)
        for x in lon:
            for y in lat:
                spatial = 0.25 * np.sin((x - 130) / 4) + 0.15 * np.cos((y - 25) / 3)
                tas = 15.0 + 8.0 * seasonal + 2.5 * spatial + rng.normal(0, 0.8)
                pr = max(0.0, 0.86 * (1.0 + seasonal) + 0.35 * spatial + rng.normal(0, 0.17))
                wind = max(0.0, 7.0 - 1.3 * seasonal + rng.normal(0, 0.8))
                hurs = np.clip(72.0 + 8 * seasonal + rng.normal(0, 5), 10, 100)
                rows.append((date, x, y, tas, pr, wind, hurs))
    frame = pd.DataFrame(rows, columns=["time", "lon", "lat", "tas", "pr", "sfcWind", "hurs"])
    return DatasetBundle(frame, "synthetic", {"seed": seed, "periods": periods, "variables": ["tas", "pr", "sfcWind", "hurs"]})


def _read_manifest(path: Path) -> dict[str, object]:
    manifest_path = path.with_suffix(".json")
    if not manifest_path.exists():
        return {}
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def scan_local_catalog(directory: str | Path = r"D:\datatask") -> list[DatasetRecord]:
    """Discover subset files without loading their gridded values."""
    records: list[DatasetRecord] = []
    for path in sorted(Path(directory).glob("nex_*_subset.nc")):
        manifest = _read_manifest(path)
        match = _FILENAME.match(path.name)
        if not manifest and not match:
            continue
        model = str(manifest.get("model") or match.group("model"))
        scenario = str(manifest.get("scenario") or match.group("scenario"))
        year = int(manifest.get("year") or match.group("year"))
        variables = tuple(str(item) for item in manifest.get("variables", ()))
        if not variables:
            try:
                import xarray as xr
                with xr.open_dataset(path) as ds:
                    variables = tuple(name for name in VARIABLES if name in ds)
            except OSError:
                continue
        lon, lat = manifest.get("lon"), manifest.get("lat")
        records.append(DatasetRecord(
            path=path, model=model, scenario=scenario, year=year, variables=variables,
            lon=tuple(float(v) for v in lon) if isinstance(lon, list) and len(lon) == 2 else None,
            lat=tuple(float(v) for v in lat) if isinstance(lat, list) and len(lat) == 2 else None,
            size_bytes=path.stat().st_size,
        ))
    return records


def load_local_netcdf(path: str | Path) -> DatasetBundle:
    """Load one local subset and normalize common climate units for display."""
    import xarray as xr
    path = Path(path)
    manifest = _read_manifest(path)
    with xr.open_dataset(path) as ds:
        available = [v for v in VARIABLES if v in ds]
        if not available:
            raise ValueError(f"No supported variables found in {path}; expected one of {VARIABLES}")
        frame = ds[available].to_dataframe().reset_index()
    for col in ["time", "lon", "lat"]:
        if col not in frame:
            aliases = {"lon": "longitude", "lat": "latitude"}
            if aliases.get(col) in frame:
                frame[col] = frame[aliases[col]]
            else:
                raise ValueError(f"NetCDF is missing coordinate {col}")
    frame = _standardize_units(frame)
    metadata: dict[str, object] = {"variables": available, "units": {v: VARIABLE_UNITS[v] for v in available}}
    metadata.update(manifest)
    return DatasetBundle(frame, str(path), metadata)


def load_records(records: Iterable[DatasetRecord]) -> DatasetBundle:
    selected = list(records)
    if not selected:
        raise ValueError("No dataset records selected")
    bundles = [load_local_netcdf(record.path) for record in selected]
    frame = pd.concat([bundle.frame for bundle in bundles], ignore_index=True)
    common = set(selected[0].variables).intersection(*(set(record.variables) for record in selected[1:]))
    return DatasetBundle(frame, f"{len(selected)} local subsets", {
        "models": sorted({record.model for record in selected}),
        "scenarios": sorted({record.scenario for record in selected}),
        "years": sorted({record.year for record in selected}), "variables": sorted(common),
    })


def summarize_records(records: Iterable[DatasetRecord]) -> pd.DataFrame:
    """Compute one spatial-temporal mean row per file, keeping memory bounded."""
    import xarray as xr

    rows: list[dict[str, object]] = []
    for record in records:
        try:
            with xr.open_dataset(record.path) as ds:
                row: dict[str, object] = {
                    "model": record.model, "scenario": record.scenario,
                    "year": record.year, "size_bytes": record.size_bytes,
                }
                for variable in record.variables:
                    if variable not in ds:
                        continue
                    value = float(ds[variable].mean(skipna=True).compute())
                    coverage = float(ds[variable].notnull().mean().compute())
                    if variable in ("tas", "tasmax", "tasmin") and value > 100:
                        value -= 273.15
                    if variable == "pr" and value < 0.1:
                        value *= 86400.0
                    row[variable] = value
                    row[f"{variable}_coverage"] = coverage
        except (OSError, ValueError):
            continue
        rows.append(row)
    return pd.DataFrame(rows)


def find_local_bundle(directory: str | Path = r"D:\datatask") -> DatasetBundle | None:
    """Return the newest readable local file containing both core variables."""
    records = sorted(scan_local_catalog(directory), key=lambda item: item.path.stat().st_mtime, reverse=True)
    for record in records:
        if not {"tas", "pr"}.issubset(record.variables):
            continue
        try:
            return load_local_netcdf(record.path)
        except (OSError, ValueError):
            continue
    return None
