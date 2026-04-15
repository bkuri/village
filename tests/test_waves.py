"""Tests for wave-based label evolution."""

from village.stack.waves import (
    analyze_task_complexity,
    apply_proposals,
    evaluate_wave,
    format_wave_summary,
    suggest_group_assignment,
)


def test_analyze_task_no_deps():
    task = {"id": "t1", "title": "Add feature", "labels": [], "depends_on": []}
    layer = analyze_task_complexity(task, [task])
    assert layer == 1


def test_analyze_task_with_deps():
    task = {"id": "t1", "title": "Add feature", "labels": ["stack:layer:1"], "depends_on": ["t0"]}
    layer = analyze_task_complexity(task, [task])
    assert layer == 2


def test_suggest_group_auth():
    task = {"id": "t1", "title": "Add login feature", "labels": []}
    group = suggest_group_assignment(task, [])
    assert group == "auth"


def test_suggest_group_api():
    task = {"id": "t1", "title": "Create API endpoint", "labels": []}
    group = suggest_group_assignment(task, [])
    assert group == "api"


def test_suggest_group_no_match():
    task = {"id": "t1", "title": "Do something unique", "labels": []}
    group = suggest_group_assignment(task, [])
    assert group is None


def test_evaluate_wave_no_changes():
    tasks = [
        {"id": "t1", "title": "Add login", "labels": ["stack:layer:1", "stack:group:auth"], "depends_on": []},
    ]
    wave = evaluate_wave(tasks)
    assert len(wave.proposals) == 0


def test_evaluate_wave_suggests_layer_change():
    tasks = [
        {"id": "t1", "title": "Add login", "labels": ["stack:layer:1"], "depends_on": ["t0"]},
    ]
    wave = evaluate_wave(tasks)
    assert len(wave.proposals) == 1
    assert wave.proposals[0].layer_change == 1


def test_evaluate_wave_suggests_group():
    tasks = [
        {"id": "t1", "title": "Add login feature", "labels": ["stack:layer:1"], "depends_on": []},
    ]
    wave = evaluate_wave(tasks)
    assert len(wave.proposals) == 1
    assert wave.proposals[0].group_change == "auth"


def test_apply_proposals():
    tasks = [
        {"id": "t1", "title": "Add login", "labels": ["stack:layer:1"], "depends_on": ["t0"]},
    ]
    wave = evaluate_wave(tasks)
    updated = apply_proposals(tasks, wave.proposals)
    assert "stack:layer:2" in updated[0]["labels"]


def test_format_wave_summary():
    wave = evaluate_wave(
        [
            {"id": "t1", "title": "Add login", "labels": ["stack:layer:1"], "depends_on": []},
        ]
    )
    summary = format_wave_summary(wave)
    assert "Wave 1" in summary
    assert "t1" in summary
