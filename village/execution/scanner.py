"""Content scanner — content, filename, and TDD rule enforcement.

Scans file contents for forbidden patterns, validates filename casing,
and enforces test-driven development (TDD) rules.
"""

import fnmatch
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from village.rules.schema import FilenameConfig, RulesConfig, TddConfig

logger = logging.getLogger(__name__)


@dataclass
class ScanViolation:
    """A single rule violation found during scanning."""

    rule: str  # "content" | "filename" | "tdd"
    message: str
    file_path: Path | None = None
    line: int | None = None
    pattern: str | None = None  # which pattern matched


@dataclass
class ScanResult:
    """Aggregated scan result with all violations."""

    passed: bool
    violations: list[ScanViolation] = field(default_factory=list)


# Regex patterns for filename casing validation
_SNAKE_CASE_RE = re.compile(r"^[a-z][a-z0-9]*(_[a-z0-9]+)*(\.[a-z]+)?$")
_KEBAB_CASE_RE = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*(\.[a-z]+)?$")
_CAMEL_CASE_RE = re.compile(r"^[a-z][a-zA-Z0-9]*(\.[a-zA-Z0-9]+)?$")

# Extensions that require test files (source code)
_SOURCE_EXTENSIONS: set[str] = {".py", ".ts", ".js", ".tsx", ".jsx", ".go", ".rs", ".java", ".rb"}


def _path_matches_globs(path: Path, globs: list[str] | None) -> bool:
    """Check if a path matches any of the given gitignore-style glob patterns.

    Supports ``**`` for recursive matching and ``!`` prefix for exclusion.
    If *globs* is None or empty, all paths match.
    """
    if not globs:
        return True

    path_str = str(path.as_posix())
    excluded = False

    for glob_pattern in globs:
        if glob_pattern.startswith("!"):
            # Exclusion pattern
            if fnmatch.fnmatch(path_str, glob_pattern[1:]):
                excluded = True
        else:
            if fnmatch.fnmatch(path_str, glob_pattern):
                return not excluded

    return excluded


def _get_test_candidates(stem: str, suffix: str, test_dir: Path) -> list[Path]:
    """Generate candidate test filenames for a given source filename."""
    return [
        test_dir / f"test_{stem}{suffix}",
        test_dir / f"{stem}_test{suffix}",
    ]


def _get_test_paths(source_path: Path, test_dirs: list[str]) -> list[Path]:
    """Get expected test file paths for a given source file.

    For ``src/foo.py``, generates candidates relative to the source's
    ancestor directories, trying ``tests/test_foo.py``,
    ``tests/foo_test.py``, and mirrored subdirectory paths.

    If the source path is absolute, candidates are resolved relative to
    each ancestor up to the filesystem root, so the correct project root
    is discovered regardless of CWD.
    """
    stem = source_path.stem
    suffix = source_path.suffix

    candidates: list[Path] = []

    for test_dir_raw in test_dirs:
        test_dir_path = Path(test_dir_raw)

        # Base candidates (relative or absolute)
        candidates.extend(_get_test_candidates(stem, suffix, test_dir_path))

        # Mirror hierarchy: if source is src/utils/helper.py, also check
        # tests/utils/test_helper.py
        rel_parts = _source_relative_parts(source_path)
        if rel_parts:
            for td in test_dirs:
                mirror_root = Path(td) / rel_parts
                candidates.extend(_get_test_candidates(stem, suffix, mirror_root))

        # If source path is absolute, resolve test dirs relative to each
        # ancestor of the source path (to find the project root)
        if source_path.is_absolute():
            # Walk up from source's parent to root
            ancestor = source_path.parent
            while ancestor != ancestor.parent:  # stop at filesystem root
                for td in test_dirs:
                    resolved = ancestor / td
                    candidates.extend(_get_test_candidates(stem, suffix, resolved))
                ancestor = ancestor.parent

    return candidates


def _source_relative_parts(source_path: Path) -> Path | None:
    """Extract the relative subdirectory parts of a source path.

    For ``src/utils/helper.py``, returns ``utils``.
    For ``helper.py``, returns None.
    """
    parts = source_path.parts
    if len(parts) < 2:
        return None
    # For absolute paths, skip the root '/'
    # For relative paths, everything except the filename
    if source_path.is_absolute():
        rel = parts[1:-1]  # skip root, skip filename
    else:
        rel = parts[:-1]  # skip filename
    if not rel:
        return None
    return Path(*rel)


class ContentScanner:
    """Scans file content, filenames, and TDD compliance against rules.

    Args:
        rules: Optional :class:`RulesConfig` to load rules from. If omitted,
            scanning methods will return empty results for content/filename/TDD checks.
    """

    def __init__(self, rules: RulesConfig | None = None) -> None:
        self.rules = rules

    # ── Content scanning ──────────────────────────────────────────────

    def scan_file(self, path: Path, content: str | None = None) -> list[ScanViolation]:
        """Check a single file's content against forbidden patterns.

        Reads the file from disk if *content* is not provided.
        Respects gitignore-style path scoping via
        :attr:`ForbiddenContentRule.paths`.

        Args:
            path: Path to the file to scan.
            content: Optional pre-read file content. If omitted, the file is
                read from disk.

        Returns:
            A list of violations found (empty if clean).
        """
        violations: list[ScanViolation] = []

        if self.rules is None or not self.rules.content_rules:
            return violations

        if content is None:
            try:
                content = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as e:
                logger.debug("Could not read %s: %s", path, e)
                return violations

        lines = content.splitlines()

        for rule in self.rules.content_rules:
            if not _path_matches_globs(path, rule.paths):
                continue

            pattern = rule.match
            # Try as regex first
            try:
                compiled = re.compile(pattern)
                for line_no, line in enumerate(lines, start=1):
                    if compiled.search(line):
                        violations.append(
                            ScanViolation(
                                rule="content",
                                message=rule.reason or f"Match of forbidden pattern: {pattern}",
                                file_path=path,
                                line=line_no,
                                pattern=pattern,
                            )
                        )
            except re.error:
                # Treat as literal substring match
                for line_no, line in enumerate(lines, start=1):
                    if pattern in line:
                        violations.append(
                            ScanViolation(
                                rule="content",
                                message=rule.reason or f"Match of forbidden pattern: {pattern}",
                                file_path=path,
                                line=line_no,
                                pattern=pattern,
                            )
                        )

        return violations

    # ── Filename scanning ─────────────────────────────────────────────

    def scan_filename(self, path: Path, casing: str | None = None) -> list[ScanViolation]:
        """Check filename matches configured casing.

        Supports ``snake_case``, ``kebab-case``, and ``camelCase``.
        Respects path scoping from :attr:`FilenameConfig.paths`.

        Args:
            path: Path to the file whose name to validate.
            casing: Override casing style. If omitted, uses
                :attr:`RulesConfig.filename.casing`.

        Returns:
            A list of violations (empty if filename is valid).
        """
        violations: list[ScanViolation] = []

        if self.rules is None:
            return violations

        filename_config: FilenameConfig | None = self.rules.filename
        if filename_config is None:
            return violations

        effective_casing = casing or filename_config.casing
        if effective_casing is None:
            return violations

        # Check path scoping
        if not _path_matches_globs(path, filename_config.paths):
            return violations

        name = path.name

        # Pick the regex for the configured casing
        if effective_casing == "snake_case":
            valid = bool(_SNAKE_CASE_RE.match(name))
            label = "snake_case (e.g. my_file.py)"
        elif effective_casing == "kebab-case":
            valid = bool(_KEBAB_CASE_RE.match(name))
            label = "kebab-case (e.g. my-file.py)"
        elif effective_casing == "camelCase":
            valid = bool(_CAMEL_CASE_RE.match(name))
            label = "camelCase (e.g. myFile.py)"
        else:
            logger.debug("Unknown casing style: %s, skipping", effective_casing)
            return violations

        if not valid:
            violations.append(
                ScanViolation(
                    rule="filename",
                    message=f"Filename '{name}' does not match {label}",
                    file_path=path,
                    pattern=effective_casing,
                )
            )

        return violations

    # ── TDD enforcement ───────────────────────────────────────────────

    def check_tdd(
        self,
        changed_files: list[Path],
        test_dirs: list[str] | None = None,
    ) -> list[ScanViolation]:
        """Verify that every new source file has a corresponding test file.

        Checks files with extensions in ``{'.py', '.ts', '.js', '.tsx', '.jsx',
        '.go', '.rs', '.java', '.rb'}``.

        Args:
            changed_files: List of file paths that were added or modified.
            test_dirs: Directories to search for test files (e.g.
                ``["tests/", "test/"]``). Falls back to
                :attr:`TddConfig.test_dirs` or ``["tests/"]``.

        Returns:
            A list of violations (empty if TDD is satisfied).
        """
        violations: list[ScanViolation] = []

        if self.rules is None:
            return violations

        tdd_config: TddConfig | None = self.rules.tdd
        if tdd_config is None or not tdd_config.enabled:
            return violations

        effective_test_dirs = test_dirs or tdd_config.test_dirs or ["tests/"]

        for file_path in changed_files:
            if file_path.suffix not in _SOURCE_EXTENSIONS:
                continue

            # Skip test files themselves
            if any(file_path.as_posix().startswith(td) for td in effective_test_dirs):
                continue

            # Skip __init__.py and similar
            if file_path.name.startswith("__") and file_path.name.endswith("__"):
                continue

            candidates = _get_test_paths(file_path, effective_test_dirs)
            found = any(c.exists() for c in candidates)

            if not found:
                candidate_names = ", ".join(c.name for c in set(candidates))
                violations.append(
                    ScanViolation(
                        rule="tdd",
                        message=(f"No test file found for '{file_path.name}'. Expected one of: {candidate_names}"),
                        file_path=file_path,
                    )
                )

        return violations

    # ── Tree scanning ─────────────────────────────────────────────────

    def scan_tree(self, tree_path: Path) -> list[ScanViolation]:
        """Recursively scan all files in a directory.

        Performs content scanning and filename validation on every
        file under *tree_path*.

        Args:
            tree_path: Root directory to scan recursively.

        Returns:
            Aggregated list of violations from content and filename checks.
        """
        all_violations: list[ScanViolation] = []

        if not tree_path.is_dir():
            logger.debug("scan_tree: %s is not a directory, skipping", tree_path)
            return all_violations

        for entry in sorted(tree_path.rglob("*")):
            if not entry.is_file():
                continue
            # Skip hidden files and common ignores
            if any(part.startswith(".") for part in entry.parts):
                continue
            if entry.name in ("__pycache__", ".DS_Store"):
                continue

            all_violations.extend(self.scan_file(entry))
            all_violations.extend(self.scan_filename(entry))

        return all_violations
