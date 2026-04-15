"""Tests for stack label system."""

from village.stack.core import Stack
from village.stack.labels import (
    create_pr_specs,
    group_tasks_by_label,
    parse_stack_labels,
    resolve_stack_order,
)


def test_parse_layer_label():
    info = parse_stack_labels("task1", ["stack:layer:2"])
    assert info.layer == 2
    assert info.group_name is None
    assert not info.is_flat


def test_parse_group_label():
    info = parse_stack_labels("task1", ["stack:group:auth"])
    assert info.group_name == "auth"
    assert info.layer == 1


def test_parse_combined_labels():
    info = parse_stack_labels("task1", ["stack:layer:3", "stack:group:api"])
    assert info.layer == 3
    assert info.group_name == "api"


def test_parse_flat_label():
    info = parse_stack_labels("task1", ["stack:flat"])
    assert info.is_flat
    assert info.layer == 1


def test_parse_multiple_labels():
    info = parse_stack_labels(
        "task1",
        [
            "stack:layer:2",
            "stack:group:auth",
            "stack:flat",
            "bump:minor",
        ],
    )
    assert info.layer == 2
    assert info.group_name == "auth"
    assert info.is_flat


def test_group_tasks_single():
    tasks = [
        {"id": "task1", "labels": ["stack:layer:1", "stack:group:auth"]},
        {"id": "task2", "labels": ["stack:layer:1", "stack:group:auth"]},
    ]
    stack = group_tasks_by_label(tasks)
    assert len(stack.groups) == 1
    assert len(stack.groups[0].tasks) == 2


def test_group_tasks_multiple_layers():
    tasks = [
        {"id": "task1", "labels": ["stack:layer:1"]},
        {"id": "task2", "labels": ["stack:layer:2"]},
    ]
    stack = group_tasks_by_label(tasks)
    assert len(stack.groups) == 2
    layers = stack.layers
    assert layers[0].layer_number == 1
    assert layers[1].layer_number == 2


def test_group_tasks_flat():
    tasks = [
        {"id": "task1", "labels": []},
        {"id": "task2", "labels": []},
    ]
    stack = group_tasks_by_label(tasks, flat_override=True)
    assert len(stack.groups) == 1
    assert len(stack.groups[0].tasks) == 2
    assert stack.groups[0].name is None


def test_resolve_stack_order():
    stack = Stack()
    from village.stack.core import StackGroup

    stack.add_group(StackGroup(name="b", layer=2))
    stack.add_group(StackGroup(name="a", layer=1))
    ordered = resolve_stack_order(stack)
    assert ordered[0].name == "a"
    assert ordered[1].name == "b"


def test_create_pr_specs():
    tasks = [
        {"id": "task1", "labels": ["stack:layer:1", "stack:group:core"]},
        {"id": "task2", "labels": ["stack:layer:2", "stack:group:api"]},
    ]
    specs = create_pr_specs(tasks, "my-feature")
    assert len(specs) == 2
    assert specs[0]["layer"] == 1
    assert specs[1]["layer"] == 2


def test_create_pr_specs_flat():
    tasks = [
        {"id": "task1", "labels": []},
        {"id": "task2", "labels": []},
    ]
    specs = create_pr_specs(tasks, "my-feature", flat=True)
    assert len(specs) == 1
    assert len(specs[0]["tasks"]) == 2
