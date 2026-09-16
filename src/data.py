from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


VARIABLES = ["tas", "pr", "sfcWind", "hurs"]


@dataclass
class DatasetBundle:
    frame: pd.DataFrame
    source: str
    metadata: dict[str, str]


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
                tas = 288.0 + 8.0 * seasonal + 2.5 * spatial + rng.normal(0, 0.8)
                pr = max(0.0, 0.00001 * (1.0 + seasonal) + 0.000004 * spatial + rng.normal(0, 0.000002))
                wind = max(0.0, 7.0 - 1.3 * seasonal + rng.normal(0, 0.8))
                hurs = np.clip(72.0 + 8 * seasonal + rng.normal(0, 5), 10, 100)
                rows.append((date, x, y, tas, pr, wind, hurs))
    frame = pd.DataFrame(rows, columns=["time", "lon", "lat", *VARIABLES])
    return DatasetBundle(frame, "synthetic", {"seed": str(seed), "periods": str(periods)})


def load_local_netcdf(path: str | Path) -> DatasetBundle:
    """Load a local NetCDF without requiring a network download."""
    import xarray as xr

    ds = xr.open_dataset(path)
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
    return DatasetBundle(frame, str(path), {"variables": ",".join(available)})
