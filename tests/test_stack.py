"""Tests for stack module."""

from village.stack.core import Layer, Stack, StackGroup
from village.stack.git_backend import GitStackBackend


def test_layer_creation():
    layer = Layer(layer_number=1, tasks=["task1", "task2"])
    assert layer.layer_number == 1
    assert len(layer.tasks) == 2


def test_stack_group():
    group = StackGroup(name="auth", tasks=["task1", "task2"], layer=1)
    assert group.name == "auth"
    assert group.layer == 1


def test_stack_add_group():
    stack = Stack(trunk="main")
    stack.add_group(StackGroup(name="auth", layer=1))
    stack.add_group(StackGroup(name="api", layer=2))
    assert len(stack.groups) == 2


def test_stack_layers():
    stack = Stack(trunk="main")
    stack.add_group(StackGroup(name="core", tasks=["t1"], layer=1))
    stack.add_group(StackGroup(name="api", tasks=["t2"], layer=2))
    layers = stack.layers
    assert len(layers) == 2
    assert layers[0].layer_number == 1
    assert layers[1].layer_number == 2


def test_stack_get_layer():
    stack = Stack(trunk="main")
    stack.add_group(StackGroup(name="auth", layer=1))
    assert stack.get_layer(1) is not None
    assert stack.get_layer(999) is None


def test_git_backend_init(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import subprocess

    subprocess.run(["git", "init"], capture_output=True)
    backend = GitStackBackend()
    assert backend.repo_root == tmp_path
