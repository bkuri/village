#!/usr/bin/env bash
# Village pre-commit hook
# Fast checks that run before every commit.
# Installed by: village up

set -euo pipefail

# Check if this is a Village-managed repo
GIT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
[ -d "$GIT_ROOT/.village" ] || exit 0

echo "Village pre-commit checks..."
echo ""

echo "  ruff check..."
if ! uv run ruff check .; then
    echo ""
    echo "  FAILED: ruff check found errors. Fix with 'uv run ruff check --fix .' or commit with --no-verify."
    exit 1
fi

echo "  ruff format..."
if ! uv run ruff format --check .; then
    echo ""
    echo "  FAILED: ruff format found issues. Fix with 'uv run ruff format .' or commit with --no-verify."
    exit 1
fi

echo ""
echo "Pre-commit checks passed."
