"""Post-hoc verification — run checks after agent signals completion.

Verification runs *after* the agent outputs ``<promise>DONE</promise>`` but
*before* the spec is marked as complete.  If verification fails, violations
are written into the spec as "Inspect Notes" so the agent can fix them on
retry.
"""

from __future__ import annotations

import logging
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from village.execution.scanner import ContentScanner, ScanViolation
from village.rules.schema import RulesConfig

logger = logging.getLogger(__name__)


@dataclass
class VerificationResult:
    """Outcome of a single verification check."""

    passed: bool
    rule_name: str
    message: str = ""
    violations: list[ScanViolation] = field(default_factory=list)


@dataclass
class VerificationViolation:
    """A single violation with file path and description for inspect notes."""

    file_path: Path
    message: str
    rule: str


def run_verification(
    worktree: Path,
    spec_id: str,
    rules: RulesConfig | None,
    manifest_store: Any | None = None,
    build_commit: str | None = None,
) -> list[VerificationResult]:
    """Run all post-hoc verification checks on a completed spec.

    Checks performed:

    1. **Content scan** — no forbidden patterns in new/modified files
    2. **Filename casing** — new files match configured casing
    3. **TDD** — test files exist for new source files

    Args:
        worktree: Path to the worktree directory containing agent changes.
        spec_id: The spec identifier (stem of the spec filename).
        rules: Loaded :class:`RulesConfig` (may be None to skip all checks).
        manifest_store: Reserved for future manifest-compliance checks.
        build_commit: The build commit hash (reserved for future use).

    Returns:
        A list of :class:`VerificationResult` objects.  All-passing results
        are included so callers can differentiate "no rules configured" from
        "all checks passed".
    """
    results: list[VerificationResult] = []
    scanner = ContentScanner(rules)

    if not rules:
        return results

    # 1. Scan all files in worktree for forbidden content
    violations = scanner.scan_tree(worktree)
    if violations:
        results.append(
            VerificationResult(
                passed=False,
                rule_name="content_rules",
                message=f"Found {len(violations)} content violations",
                violations=violations,
            )
        )
    else:
        results.append(
            VerificationResult(
                passed=True,
                rule_name="content_rules",
                message="No content violations found",
            )
        )

    # 2. TDD check: for each new source file, verify a test file exists
    if rules.tdd and rules.tdd.enabled:
        new_files = _get_new_files(worktree)
        tdd_violations = scanner.check_tdd(new_files, rules.tdd.test_dirs)
        if tdd_violations:
            results.append(
                VerificationResult(
                    passed=False,
                    rule_name="tdd",
                    message=f"TDD violations: {len(tdd_violations)} source files without tests",
                    violations=tdd_violations,
                )
            )
        else:
            results.append(
                VerificationResult(
                    passed=True,
                    rule_name="tdd",
                    message="All source files have corresponding tests",
                )
            )

    # 3. Filename casing
    if rules.filename and rules.filename.casing:
        new_files = _get_new_files(worktree)
        casing_violations: list[ScanViolation] = []
        for f in new_files:
            casing_violations.extend(scanner.scan_filename(f, rules.filename.casing))
        if casing_violations:
            results.append(
                VerificationResult(
                    passed=False,
                    rule_name="filename_casing",
                    message=f"Filename casing violations: {len(casing_violations)}",
                    violations=casing_violations,
                )
            )
        else:
            results.append(
                VerificationResult(
                    passed=True,
                    rule_name="filename_casing",
                    message="All filenames match configured casing",
                )
            )

    return results


def format_violations_for_inspect(violations: list[ScanViolation]) -> str:
    """Format scan violations into an inspect notes section for the spec.

    The formatted notes are appended to the spec file so the agent sees
    what failed on the next attempt.

    Args:
        violations: List of :class:`ScanViolation` found during verification.

    Returns:
        A markdown-formatted string suitable for appending to a spec file.
    """
    lines = [
        "## Inspect Notes",
        "",
        "The following verification violations were found. Fix them and retry:",
        "",
    ]
    for v in violations:
        file_str = f" in `{v.file_path}`" if v.file_path else ""
        line_str = f" (line {v.line})" if v.line is not None else ""
        pattern_str = f" [pattern: {v.pattern}]" if v.pattern else ""
        lines.append(f"- **{v.rule}**{file_str}{line_str}: {v.message}{pattern_str}")

    lines.append("")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def inject_violation_notes(spec_path: Path, violations: list[ScanViolation]) -> None:
    """Append verification violations as inspect notes in the spec file.

    The spec content is modified in-place.  Violations are written after
    the existing content so the agent sees them on the next retry.

    Args:
        spec_path: Path to the spec file to modify.
        violations: List of :class:`ScanViolation` found during verification.
    """
    if not spec_path.exists():
        logger.warning("Cannot inject violation notes: spec %s does not exist", spec_path)
        return

    try:
        existing = spec_path.read_text(encoding="utf-8")
        notes = format_violations_for_inspect(violations)

        # Avoid duplicate inspect notes — replace existing section if present
        inspect_pattern = re.compile(r"^## Inspect Notes\n.*?\n---\n", re.DOTALL | re.MULTILINE)
        if inspect_pattern.search(existing):
            existing = inspect_pattern.sub("", existing).rstrip("\n") + "\n\n"

        updated = existing.rstrip("\n") + "\n\n" + notes + "\n"
        spec_path.write_text(updated, encoding="utf-8")
        logger.info("Injected %d violation note(s) into %s", len(violations), spec_path.name)
    except (IOError, OSError) as e:
        logger.warning("Failed to inject violation notes into %s: %s", spec_path, e)


def _get_new_files(worktree: Path) -> list[Path]:
    """Get list of files added or modified in the worktree.

    Uses ``git diff --name-only --diff-filter=AMR HEAD`` relative to the
    worktree's HEAD.

    Args:
        worktree: The worktree directory to scan.

    Returns:
        A list of absolute :class:`Path` objects for changed files.
        Returns an empty list if git diff fails or the worktree has no HEAD.
    """
    if not worktree.is_dir():
        return []

    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=AMR", "HEAD"],
            capture_output=True,
            text=True,
            cwd=worktree,
        )
        if result.returncode != 0:
            logger.debug("git diff failed for %s: %s", worktree, result.stderr.strip())
            return []
        lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        return [worktree / f for f in lines]
    except (OSError, subprocess.SubprocessError) as e:
        logger.debug("Failed to get new files for %s: %s", worktree, e)
        return []
