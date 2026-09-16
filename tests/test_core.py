import json
from scv_core import AnalysisState, Action, HistoryLog, compute_evidence, generate_candidates, score_candidate


def test_action_candidate_and_score():
    state = AnalysisState(goal="寻找滞后响应")
    candidates = generate_candidates(state)
    assert len(candidates) == 3
    action = Action("change_statistic", {"operation": "lagged_correlation"})
    after = action.apply(state)
    candidate = next(c for c in generate_candidates(state, 20) if c.action == action)
    scored = score_candidate(candidate, compute_evidence(candidate, metrics={"information_gain": .8, "stability": .9}))
    assert after.operation == "lagged_correlation"
    assert 0 <= scored.score <= 1


def test_history_jsonl(tmp_path):
    path = tmp_path / "history.jsonl"
    state = AnalysisState()
    action = Action("add_variable", {"variable": "pr"})
    after = action.apply(state)
    log = HistoryLog(path)
    log.append(state, action, after, user_choice="accepted")
    assert len(list(log.records())) == 1
    assert log.replay().variables == ("tas", "pr")
