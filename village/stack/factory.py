"""Stack backend factory."""

from village.stack.backend import StackBackend
from village.stack.git_backend import GitStackBackend
from village.stack.jj_backend import JJStackBackend


def get_stack_backend() -> StackBackend:
    """Detect VCS and return appropriate stack backend."""
    import subprocess

    try:
        subprocess.run(["jj", "log"], capture_output=True, check=True)
        return JJStackBackend()
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    try:
        subprocess.run(["git", "rev-parse"], capture_output=True, check=True)
        return GitStackBackend()
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    raise RuntimeError("No supported VCS found (git or jj)")
