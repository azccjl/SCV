import json

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from src.data import load_local_netcdf, scan_local_catalog, summarize_records


def _write_subset(directory, model, scenario, year):
    path = directory / f"nex_{model}_{scenario}_{year}_subset.nc"
    ds = xr.Dataset(
        {
            "tas": (("time", "lat", "lon"), np.full((2, 2, 2), 300.0)),
            "pr": (("time", "lat", "lon"), np.full((2, 2, 2), 0.00001)),
        },
        coords={"time": pd.date_range(f"{year}-01-01", periods=2), "lat": [25.0, 26.0], "lon": [130.0, 131.0]},
    )
    ds.to_netcdf(path)
    manifest = {
        "model": model, "scenario": scenario, "year": year,
        "variables": ["tas", "pr"], "lon": [130, 131], "lat": [25, 26],
    }
    path.with_suffix(".json").write_text(json.dumps(manifest), encoding="utf-8")
    return path


def test_catalog_discovers_model_scenario_and_year(tmp_path):
    _write_subset(tmp_path, "MRI-ESM2-0", "historical", 2010)
    _write_subset(tmp_path, "GFDL-ESM4", "ssp245", 2035)

    records = scan_local_catalog(tmp_path)

    assert [(item.model, item.scenario, item.year) for item in records] == [
        ("GFDL-ESM4", "ssp245", 2035),
        ("MRI-ESM2-0", "historical", 2010),
    ]


def test_loading_normalizes_units_and_summary_stays_compact(tmp_path):
    path = _write_subset(tmp_path, "MRI-ESM2-0", "historical", 2010)
    bundle = load_local_netcdf(path)
    summary = summarize_records(scan_local_catalog(tmp_path))

    assert bundle.frame["tas"].mean() == pytest.approx(26.85)
    assert bundle.frame["pr"].mean() == pytest.approx(0.864)
    assert len(summary) == 1
    assert summary.loc[0, "tas_coverage"] == 1.0
