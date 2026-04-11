#!/usr/bin/env bash
# Village prepare-commit-msg hook
# Appends task ID reference to commit messages when working in worktrees.
# Installed by: village up

COMMIT_MSG_FILE="$1"

# Find git root
GIT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0

# Check if village is initialized
VILLAGE_DIR="$GIT_ROOT/.village"
[ -d "$VILLAGE_DIR" ] || exit 0

# Check if we're in a worktree
WORKTREE_DIR="$GIT_ROOT/.worktrees"
[ -d "$WORKTREE_DIR" ] || exit 0

# Get the current worktree path (relative to .worktrees/)
# In a worktree, git rev-parse --show-toplevel returns the worktree path
CURRENT_PATH=$(git rev-parse --show-toplevel 2>/dev/null)
WORKTREE_NAME=$(basename "$CURRENT_PATH")

# Check if the worktree name matches task ID pattern (bd-xxxx or similar)
if echo "$WORKTREE_NAME" | grep -qE '^[a-z]+-[a-f0-9]{4}$'; then
    TASK_ID="$WORKTREE_NAME"
    # Check if task ID is already referenced in the commit message
    if ! grep -q "$TASK_ID" "$COMMIT_MSG_FILE" 2>/dev/null; then
        echo "" >> "$COMMIT_MSG_FILE"
        echo "Refs: $TASK_ID" >> "$COMMIT_MSG_FILE"
    fi
fi

exit 0
