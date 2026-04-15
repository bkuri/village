"""Core stack data models."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Layer:
    """A layer in the stack (one PR)."""

    layer_number: int
    tasks: list[str] = field(default_factory=list)
    group_name: str | None = None

    def __hash__(self) -> int:
        return hash(self.layer_number)


@dataclass
class StackGroup:
    """A group of tasks that become one PR."""

    name: str | None
    tasks: list[str] = field(default_factory=list)
    layer: int = 1

    def __hash__(self) -> int:
        return hash(self.name)


@dataclass
class Stack:
    """A complete stack of PRs."""

    trunk: str = "main"
    groups: list[StackGroup] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def layers(self) -> list[Layer]:
        """Get layers ordered by layer number."""
        by_layer: dict[int, list[str]] = {}
        for group in self.groups:
            by_layer.setdefault(group.layer, []).extend(group.tasks)

        layers = []
        for layer_num in sorted(by_layer.keys()):
            layers.append(
                Layer(
                    layer_number=layer_num,
                    tasks=by_layer[layer_num],
                )
            )
        return layers

    def add_group(self, group: StackGroup) -> None:
        """Add a group to the stack."""
        self.groups.append(group)

    def get_layer(self, layer_num: int) -> Layer | None:
        """Get a specific layer."""
        for layer in self.layers:
            if layer.layer_number == layer_num:
                return layer
        return None
