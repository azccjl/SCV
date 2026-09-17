from scripts.download_nex_batch import ANCHOR_PERIODS, MODELS, PERIODS, build_tasks


def test_anchor_plan_covers_each_model_and_scenario_once():
    tasks = build_tasks(MODELS, ["tas", "pr"], ANCHOR_PERIODS)

    assert len(tasks) == 9
    assert {(task["model"], task["scenario"]) for task in tasks} == {
        (model, scenario) for model in MODELS for scenario in ANCHOR_PERIODS
    }


def test_full_plan_keeps_expected_225_regional_slices():
    tasks = build_tasks(MODELS, ["tas", "pr"], PERIODS)

    assert len(tasks) == 225
    assert all(task["variables"] == ["tas", "pr"] for task in tasks)
