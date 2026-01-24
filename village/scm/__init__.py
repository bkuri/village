"""SCM abstraction layer."""

from village.scm.git import GitSCM
from village.scm.protocol import SCM, WorkspaceInfo
from village.scm.utils import (
    generate_window_name,
    increment_task_id,
    parse_window_name,
    resolve_task_id,
)

__all__ = [
    "SCM",
    "WorkspaceInfo",
    "generate_window_name",
    "increment_task_id",
    "parse_window_name",
    "resolve_task_id",
    "GitSCM",
]
