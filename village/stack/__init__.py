"""Stack management for VCS-agnostic PR stacking."""

from village.stack.backend import StackBackend
from village.stack.core import Layer, Stack, StackGroup
from village.stack.factory import get_stack_backend

__all__ = [
    "StackBackend",
    "Stack",
    "Layer",
    "StackGroup",
    "get_stack_backend",
]
