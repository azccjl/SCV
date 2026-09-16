from src.data import synthetic_bundle
from src.evidence import compute_evidence
from src.state import AnalysisState


def test_aggregation_changes_sample_count():
    bundle = synthetic_bundle(periods=24)
    state = AnalysisState()
    state.time["start"] = "2000-01-01"
    state.time["end"] = "2001-12-31"

    monthly = compute_evidence(bundle.frame, state)
    state.time["aggregation"] = "seasonal"
    seasonal = compute_evidence(bundle.frame, state)

    assert monthly.sample_count == 24
    assert seasonal.sample_count < monthly.sample_count


def test_lagged_operation_recomputes_correlation():
    bundle = synthetic_bundle(periods=24)
    state = AnalysisState()
    state.time["start"] = "2000-01-01"
    state.time["end"] = "2001-12-31"

    synchronous = compute_evidence(bundle.frame, state)
    state.operation = "lagged_correlation"
    lagged = compute_evidence(bundle.frame, state)

    assert lagged.metrics["correlation"] != synchronous.metrics["correlation"]
