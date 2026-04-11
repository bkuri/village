"""Spec-driven autonomous build loop.

Implements the Ralph Wiggum methodology: iterate over numbered markdown specs,
spawn an agent to implement each one, verify completion, and retry on failure.
"""

import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from village.config import Config, get_config
from village.contracts import generate_spec_contract
from village.locks import Lock, write_lock
from village.probes.tmux import capture_pane, pane_exists
from village.resume import _create_resume_window, _inject_contract
from village.worktrees import create_worktree

logger = logging.getLogger(__name__)

SPEC_COMPLETE_RE = re.compile(r"^(#{1,3} )?(\*\*)?Status(\*\*)?:\s+COMPLETE", re.IGNORECASE | re.MULTILINE)
PROMISE_DONE_RE = re.compile(r"<promise>(ALL_)?DONE</promise>")
MAX_CONSECUTIVE_FAILURES = 3
DEFAULT_RETRY_DELAY = 3


@dataclass
class SpecInfo:
    path: Path
    name: str
    is_complete: bool


@dataclass
class LoopIteration:
    iteration: int
    spec_name: str
    success: bool
    promise_detected: bool
    verified_complete: bool
    started_at: datetime
    finished_at: datetime
    pane_id: str = ""
    error: str = ""


@dataclass
class LoopResult:
    total_specs: int
    completed_specs: int
    iterations: int
    details: list[LoopIteration] = field(default_factory=list)
    remaining: list[str] = field(default_factory=list)


def find_specs(specs_dir: Path) -> list[SpecInfo]:
    if not specs_dir.is_dir():
        return []
    specs = sorted(specs_dir.glob("*.md"))
    return [SpecInfo(path=s, name=s.name, is_complete=check_spec_completion(s)) for s in specs]


def find_incomplete_specs(specs_dir: Path) -> list[SpecInfo]:
    return [s for s in find_specs(specs_dir) if not s.is_complete]


def check_spec_completion(spec_path: Path) -> bool:
    if not spec_path.exists():
        return False
    try:
        content = spec_path.read_text(encoding="utf-8")
        return bool(SPEC_COMPLETE_RE.search(content))
    except (IOError, OSError):
        return False


def detect_promise(text: str) -> str | None:
    match = PROMISE_DONE_RE.search(text)
    if match:
        return match.group(0)
    return None


def monitor_pane(
    session_name: str,
    pane_id: str,
    timeout: int = 3600,
    poll_interval: float = 5.0,
) -> tuple[bool, str]:
    """Monitor a tmux pane for completion or timeout.

    Returns:
        (completed, output) where completed is True if pane exited
        and output is the captured pane content at the end.
    """
    start = time.time()
    output = ""
    while time.time() - start < timeout:
        if not pane_exists(session_name, pane_id, force_refresh=True):
            logger.info(f"Pane {pane_id} exited")
            return True, output
        try:
            output = capture_pane(session_name, pane_id, limit=5000)
            if detect_promise(output):
                logger.info(f"Promise signal detected in pane {pane_id}")
                return True, output
        except Exception as e:
            logger.debug(f"Error capturing pane {pane_id}: {e}")
        time.sleep(poll_interval)
    logger.warning(f"Timeout monitoring pane {pane_id} after {timeout}s")
    return False, output


def run_loop(
    specs_dir: Path,
    agent: str = "worker",
    model: str | None = None,
    max_iterations: int | None = None,
    retry_delay: float = DEFAULT_RETRY_DELAY,
    dry_run: bool = False,
    config: Config | None = None,
    parallel: int = 1,
) -> LoopResult:
    if config is None:
        config = get_config()

    if parallel > 1:
        logger.warning(f"Parallel execution requested ({parallel}) but not yet implemented. Running sequentially.")

    if not specs_dir.is_dir():
        raise FileNotFoundError(f"Specs directory not found: {specs_dir}")

    all_specs = find_specs(specs_dir)
    if not all_specs:
        raise ValueError("No specs found in specs directory")

    total_specs = len(all_specs)
    incomplete = find_incomplete_specs(specs_dir)
    completed_count = total_specs - len(incomplete)

    if not incomplete:
        logger.info(f"All {total_specs} specs are COMPLETE")
        return LoopResult(
            total_specs=total_specs,
            completed_specs=completed_count,
            iterations=0,
            remaining=[],
        )

    logger.info(f"Found {total_specs} specs, {len(incomplete)} incomplete")
    logger.info(f"Next spec: {incomplete[0].name}")

    session_name = config.tmux_session
    iterations: list[LoopIteration] = []
    consecutive_failures = 0
    iteration_num = 0

    while True:
        if max_iterations is not None and iteration_num >= max_iterations:
            logger.info(f"Reached max iterations: {max_iterations}")
            break

        incomplete = find_incomplete_specs(specs_dir)
        if not incomplete:
            logger.info("All specs are COMPLETE")
            break

        spec = incomplete[0]
        iteration_num += 1
        started_at = datetime.now()

        logger.info(f"Iteration {iteration_num}: {spec.name}")
        iter_result = LoopIteration(
            iteration=iteration_num,
            spec_name=spec.name,
            success=False,
            promise_detected=False,
            verified_complete=False,
            started_at=started_at,
            finished_at=started_at,
        )

        if dry_run:
            logger.info(f"Dry run: would process spec {spec.name}")
            iter_result.success = True
            iter_result.finished_at = datetime.now()
            iterations.append(iter_result)
            continue

        try:
            spec_content = spec.path.read_text(encoding="utf-8")
            task_id = spec.path.stem
            window_name = f"builder-{iteration_num}-{task_id}"

            worktree_path = config.worktrees_dir / task_id
            if not worktree_path.exists():
                try:
                    create_worktree(task_id, session_name, config)
                except Exception as e:
                    logger.error(f"Failed to create worktree: {e}")
                    iter_result.error = str(e)
                    consecutive_failures += 1
                    iterations.append(iter_result)
                    time.sleep(retry_delay)
                    continue

            pane_id = _create_resume_window(session_name, window_name, dry_run=False)
            if not pane_id:
                raise RuntimeError(f"Failed to create tmux window '{window_name}'")
            iter_result.pane_id = pane_id

            lock = Lock(
                task_id=task_id,
                pane_id=pane_id,
                window=window_name,
                agent=agent,
                claimed_at=datetime.now(),
            )
            write_lock(lock)

            contract = generate_spec_contract(
                spec_path=spec.path,
                spec_content=spec_content,
                agent=agent,
                worktree_path=worktree_path,
                window_name=window_name,
                model=model,
                config=config,
            )
            agent_type = config.agents[agent].type if agent in config.agents else "opencode"
            _inject_contract(
                session_name,
                pane_id,
                contract,
                dry_run=False,
                agent_type=agent_type,
                traces_dir=config.traces_dir,
            )

            logger.info(f"Agent spawned in pane {pane_id}, monitoring...")
            completed, output = monitor_pane(session_name, pane_id)

            promise = detect_promise(output)
            if promise:
                iter_result.promise_detected = True
                logger.info(f"Promise detected: {promise}")

                if check_spec_completion(spec.path):
                    iter_result.verified_complete = True
                    iter_result.success = True
                    completed_count += 1
                    consecutive_failures = 0
                    logger.info(f"Spec {spec.name} marked COMPLETE")
                else:
                    logger.warning("Promise found but spec not marked complete")
                    consecutive_failures += 1
            else:
                logger.warning(f"No completion signal for {spec.name}")
                consecutive_failures += 1

                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    logger.warning(
                        f"{MAX_CONSECUTIVE_FAILURES} consecutive failures. "
                        f"Consider checking logs, simplifying specs, or changing model."
                    )
                    consecutive_failures = 0

        except Exception as e:
            logger.error(f"Iteration {iteration_num} failed: {e}")
            iter_result.error = str(e)
            consecutive_failures += 1

        iter_result.finished_at = datetime.now()
        iterations.append(iter_result)

        logger.info(f"Waiting {retry_delay}s before next iteration...")
        time.sleep(retry_delay)

    final_incomplete = find_incomplete_specs(specs_dir)
    return LoopResult(
        total_specs=total_specs,
        completed_specs=total_specs - len(final_incomplete),
        iterations=len(iterations),
        details=iterations,
        remaining=[s.name for s in final_incomplete],
    )
