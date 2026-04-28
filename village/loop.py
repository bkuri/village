"""Spec-driven autonomous build loop.

Implements the Ralph Wiggum methodology: iterate over numbered markdown specs,
spawn an agent to implement each one, verify completion, and retry on failure.
"""

import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import click

from village.builder_state import BuildRunState, BuildRunStatus, generate_run_id
from village.config import Config, get_config
from village.contracts import generate_spec_contract
from village.execution.manifest import ManifestStore
from village.execution.refs import freeze_build_commit
from village.execution.verify import inject_violation_notes, run_verification
from village.locks import Lock, write_lock
from village.probes.tmux import capture_pane, pane_exists
from village.resume import _create_resume_window, _inject_contract
from village.rules.loader import load_rules
from village.worktrees import create_worktree

logger = logging.getLogger(__name__)


def check_and_trigger_wave(config: Any) -> bool:
    """Check if a wave should be triggered (task completed).

    Returns True if wave was triggered.
    """
    from village.stack.waves import evaluate_wave, format_wave_summary
    from village.tasks import get_task_store
    from village.tasks.models import TaskUpdate

    store = get_task_store()

    done_tasks = store.list_tasks(status="done")
    if not done_tasks:
        return False

    task_dicts = [{"id": t.id, "title": t.title, "labels": t.labels, "depends_on": []} for t in done_tasks]

    wave = evaluate_wave(task_dicts)
    if not wave.proposals:
        return False

    click.echo(format_wave_summary(wave))

    try:
        response = input("Accept proposals? (yes/no): ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        click.echo("")
        return False
    if response == "yes":
        from village.stack.waves import apply_proposals

        updated = apply_proposals(task_dicts, wave.proposals)
        done_labels = set(done_tasks[0].labels) if done_tasks else set()
        for task_dict in updated:
            new_labels = [label for label in task_dict["labels"] if label not in done_labels]
            store.update_task(
                task_dict["id"],
                TaskUpdate(add_labels=new_labels),
            )
        click.echo("Proposals accepted.")
        return True
    else:
        try:
            reason = input("Explain why (or 'cant-continue' to abort): ").strip()
        except (EOFError, KeyboardInterrupt):
            click.echo("")
            return False
        if reason.lower() == "cant-continue":
            raise RuntimeError("User rejected wave proposals without alternative")
        click.echo(f"Proposals rejected: {reason}")
        return False


def check_landing_trigger(
    config: Any,
    plan_slug: str | None = None,
    landing_dry_run: bool = False,
) -> bool:
    """Check if all tasks are done and trigger landing.

    Args:
        config: Village configuration
        plan_slug: Optional plan slug to update state after landing
        landing_dry_run: If True, simulate landing without creating PRs

    Returns True if landing was triggered.
    """
    from village.builder.arrange import arrange_landing
    from village.plans.models import PlanState
    from village.plans.store import FilePlanStore
    from village.tasks import get_task_store

    store = get_task_store()
    all_tasks = store.list_tasks()

    if not all_tasks:
        return False

    done_ids = {t.id for t in store.list_tasks(status="done")}
    all_ids = {t.id for t in all_tasks}

    if done_ids == all_ids and done_ids:
        click.echo("\nAll tasks completed! Triggering landing...")
        try:
            arrange_landing(dry_run=landing_dry_run)

            # Update plan state to LANDED if we have a plan slug
            if plan_slug:
                try:
                    plans_dir = config.git_root / ".village" / "plans"
                    plan_store = FilePlanStore(plans_dir)
                    plan = plan_store.get(plan_slug)
                    plan.state = PlanState.LANDED
                    plan_store.update(plan)
                    logger.info(f"Plan '{plan_slug}' state updated to LANDED")
                    click.echo(f"Plan '{plan_slug}' marked as LANDED")
                except Exception as e:
                    logger.warning(f"Failed to update plan state: {e}")

            if landing_dry_run:
                click.echo("Landing dry-run complete!")
            else:
                click.echo("Landing complete!")
            return True
        except Exception as e:
            logger.error(f"Landing failed: {e}")
            click.echo(f"Landing failed: {e}", err=True)

            # Update plan state to indicate landing failure (record error in metadata)
            if plan_slug:
                try:
                    plans_dir = config.git_root / ".village" / "plans"
                    plan_store = FilePlanStore(plans_dir)
                    plan = plan_store.get(plan_slug)
                    plan.metadata["landing_error"] = str(e)
                    plan_store.update(plan)
                    logger.info(f"Plan '{plan_slug}' landing failure recorded")
                except Exception:
                    pass

            return False

    return False


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


def _execute_spec(
    spec: SpecInfo,
    iteration_num: int,
    agent: str,
    model: str | None,
    config: Config,
    session_name: str,
    build_commit: str | None = None,
    dry_run: bool = False,
) -> LoopIteration:
    """Execute a single spec in its own worktree/tmux pane.

    This function is safe to call from a thread. Each invocation
    operates on an independent worktree and tmux window.
    """
    started_at = datetime.now()
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
        logger.info(f"[parallel] Dry run: would process spec {spec.name}")
        iter_result.success = True
        iter_result.finished_at = datetime.now()
        return iter_result

    try:
        spec_content = spec.path.read_text(encoding="utf-8")
        task_id = spec.path.stem
        window_name = f"builder-{iteration_num}-{task_id}"

        # Tamper-proof config loading from git commit
        rules = load_rules(
            path=config.village_dir / "rules.yaml",
            git_root=config.git_root,
            commit=build_commit,
        )
        manifest_store = ManifestStore(config.git_root / ".village" / "approvals")
        _manifest = (
            manifest_store.load_from_git(task_id, build_commit) if build_commit else manifest_store.load(task_id)
        )

        worktree_path = config.worktrees_dir / task_id
        if not worktree_path.exists():
            try:
                create_worktree(task_id, session_name, config)
            except Exception as e:
                logger.error(f"Failed to create worktree for {spec.name}: {e}")
                iter_result.error = str(e)
                iter_result.finished_at = datetime.now()
                return iter_result

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

        logger.info(f"[parallel] Agent spawned in pane {pane_id} for {spec.name}, monitoring...")
        completed, output = monitor_pane(session_name, pane_id)

        promise = detect_promise(output)
        if promise:
            iter_result.promise_detected = True
            logger.info(f"[parallel] Promise detected for {spec.name}: {promise}")

            # Post-hoc verification gate — run checks before marking complete
            verification = run_verification(
                worktree_path,
                spec.name,
                rules=rules,
            )
            violations = [v for v in verification if not v.passed]

            if violations:
                # Collect all ScanViolations from all failed checks
                all_violations: list[Any] = []
                for v in violations:
                    all_violations.extend(v.violations)
                if all_violations:
                    inject_violation_notes(spec.path, all_violations)
                logger.warning(f"[parallel] Spec {spec.name} failed verification: {len(violations)} check(s) failed")
                # Do NOT mark complete — agent will see violations on retry
            elif check_spec_completion(spec.path):
                iter_result.verified_complete = True
                iter_result.success = True
                logger.info(f"[parallel] Spec {spec.name} marked COMPLETE")
            else:
                logger.warning(f"[parallel] Promise found but {spec.name} not marked complete after verification")
        else:
            logger.warning(f"[parallel] No completion signal for {spec.name}")

    except Exception as e:
        logger.error(f"[parallel] Iteration {iteration_num} ({spec.name}) failed: {e}")
        iter_result.error = str(e)

    iter_result.finished_at = datetime.now()
    return iter_result


def _run_parallel_batch(
    specs: list[SpecInfo],
    base_iteration: int,
    agent: str,
    model: str | None,
    config: Config,
    parallel: int,
    build_commit: str | None = None,
    dry_run: bool = False,
) -> list[LoopIteration]:
    """Execute a batch of specs in parallel using a thread pool.

    Each spec gets its own worktree and tmux pane. The number of
    concurrent workers is capped at `parallel`.
    """
    session_name = config.tmux_session
    results: list[LoopIteration] = []

    with ThreadPoolExecutor(max_workers=parallel, thread_name_prefix="village-par") as executor:
        future_to_spec: dict[Any, tuple[SpecInfo, int]] = {}
        for i, spec in enumerate(specs):
            iteration_num = base_iteration + i
            future = executor.submit(
                _execute_spec,
                spec,
                iteration_num,
                agent,
                model,
                config,
                session_name,
                build_commit=build_commit,
                dry_run=dry_run,
            )
            future_to_spec[future] = (spec, iteration_num)

        for future in as_completed(future_to_spec):
            spec, _ = future_to_spec[future]
            try:
                result = future.result()
                results.append(result)
                status = "COMPLETE" if result.success else "FAILED"
                logger.info(f"[parallel] {spec.name}: {status}")
            except Exception as e:
                logger.error(f"[parallel] {spec.name} raised exception: {e}")
                results.append(
                    LoopIteration(
                        iteration=base_iteration,
                        spec_name=spec.name,
                        success=False,
                        promise_detected=False,
                        verified_complete=False,
                        started_at=datetime.now(),
                        finished_at=datetime.now(),
                        error=str(e),
                    )
                )

    return results


def run_loop(
    specs_dir: Path,
    agent: str = "worker",
    model: str | None = None,
    max_iterations: int | None = None,
    retry_delay: float = DEFAULT_RETRY_DELAY,
    dry_run: bool = False,
    config: Config | None = None,
    parallel: int = 1,
    wave_enabled: bool = True,
    plan_slug: str | None = None,
    landing_dry_run: bool = False,
    run_id: str | None = None,
    skip_specs: set[str] | None = None,
) -> LoopResult:
    if config is None:
        config = get_config()

    # Freeze build commit at the very start — all config reads during
    # this build use this commit hash for tamper-proofing
    build_commit: str | None = None
    try:
        build_commit = freeze_build_commit(config.git_root)
    except RuntimeError as e:
        logger.warning("Could not freeze build commit: %s", e)
        # Non-fatal — continue with disk-based reads

    if run_id is None:
        run_id = generate_run_id()

    build_state = BuildRunState(config.village_dir / "builds")
    build_state.create_run(run_id, str(specs_dir), total_specs=len(find_specs(specs_dir)) if specs_dir.is_dir() else 0)

    if parallel > 1:
        logger.info(f"Parallel execution enabled with {parallel} workers")

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
        build_state.update_run(run_id, status=BuildRunStatus.COMPLETED)
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
    completed_spec_names: set[str] = set(skip_specs) if skip_specs else set()

    if parallel > 1:
        while True:
            if max_iterations is not None and iteration_num >= max_iterations:
                logger.info(f"Reached max iterations: {max_iterations}")
                break

            incomplete = find_incomplete_specs(specs_dir)
            if not incomplete:
                logger.info("All specs are COMPLETE")
                break

            batch = incomplete[:parallel]
            logger.info(f"Launching parallel batch: {[s.name for s in batch]}")

            batch_results = _run_parallel_batch(
                specs=batch,
                base_iteration=iteration_num + 1,
                agent=agent,
                model=model,
                config=config,
                parallel=parallel,
                build_commit=build_commit,
                dry_run=dry_run,
            )

            batch_completed = 0
            for result in batch_results:
                iteration_num += 1
                result.iteration = iteration_num
                iterations.append(result)

                if result.success:
                    completed_count += 1
                    batch_completed += 1
                    consecutive_failures = 0
                    completed_spec_names.add(result.spec_name)
                else:
                    consecutive_failures += 1

            build_state.update_run(
                run_id,
                iteration_count=iteration_num,
                completed_specs=sorted(completed_spec_names),
            )

            logger.info(f"Parallel batch complete: {batch_completed}/{len(batch)} succeeded")

            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                logger.warning(
                    f"{MAX_CONSECUTIVE_FAILURES} consecutive failures. "
                    f"Consider checking logs, simplifying specs, or changing model."
                )
                consecutive_failures = 0

            if wave_enabled:
                try:
                    check_and_trigger_wave(config)
                except RuntimeError as e:
                    if "cant-continue" in str(e):
                        logger.info("Wave evaluation rejected. Stopping build.")
                        break
                    raise
                except Exception as e:
                    logger.warning(f"Wave evaluation failed: {e}")

            try:
                if check_landing_trigger(config, plan_slug, landing_dry_run):
                    logger.info("All tasks completed. Landing triggered.")
                    break
            except Exception as e:
                logger.error(f"Landing check failed: {e}")

            if not dry_run:
                logger.info(f"Waiting {retry_delay}s before next batch...")
                time.sleep(retry_delay)

        final_incomplete = find_incomplete_specs(specs_dir)
        final_status = BuildRunStatus.COMPLETED if not final_incomplete else BuildRunStatus.STOPPED
        build_state.update_run(run_id, status=final_status, completed_specs=sorted(completed_spec_names))
        return LoopResult(
            total_specs=total_specs,
            completed_specs=total_specs - len(final_incomplete),
            iterations=len(iterations),
            details=iterations,
            remaining=[s.name for s in final_incomplete],
        )

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

            # Tamper-proof config loading from git commit
            rules = load_rules(
                path=config.village_dir / "rules.yaml",
                git_root=config.git_root,
                commit=build_commit,
            )
            manifest_store = ManifestStore(config.git_root / ".village" / "approvals")
            _manifest = (
                manifest_store.load_from_git(task_id, build_commit) if build_commit else manifest_store.load(task_id)
            )

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

                # Post-hoc verification gate — run checks before marking complete
                verification = run_verification(
                    worktree_path,
                    spec.name,
                    rules=rules,
                )
                violations = [v for v in verification if not v.passed]

                if violations:
                    # Collect all ScanViolations from all failed checks
                    all_violations: list[Any] = []
                    for v in violations:
                        all_violations.extend(v.violations)
                    if all_violations:
                        inject_violation_notes(spec.path, all_violations)
                    logger.warning(f"Spec {spec.name} failed verification: {len(violations)} check(s) failed")
                    # Do NOT mark complete — agent will see violations on retry
                    consecutive_failures += 1
                elif check_spec_completion(spec.path):
                    iter_result.verified_complete = True
                    iter_result.success = True
                    completed_count += 1
                    consecutive_failures = 0
                    completed_spec_names.add(spec.name)
                    logger.info(f"Spec {spec.name} marked COMPLETE")

                    # After task is marked done, trigger wave evaluation
                    if wave_enabled:
                        try:
                            check_and_trigger_wave(config)
                        except RuntimeError as e:
                            if "cant-continue" in str(e):
                                logger.info("Wave evaluation rejected. Stopping build.")
                                break
                            raise
                        except Exception as e:
                            logger.warning(f"Wave evaluation failed: {e}")

                    # After task is marked done, check if landing is triggered
                    try:
                        if check_landing_trigger(config, plan_slug, landing_dry_run):
                            logger.info("All tasks completed. Landing triggered.")
                            break
                    except Exception as e:
                        logger.error(f"Landing check failed: {e}")
                else:
                    logger.warning("Promise found but spec not marked complete after verification")
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

        build_state.update_run(
            run_id,
            iteration_count=iteration_num,
            completed_specs=sorted(completed_spec_names),
        )

        logger.info(f"Waiting {retry_delay}s before next iteration...")
        time.sleep(retry_delay)

    final_incomplete = find_incomplete_specs(specs_dir)
    final_status = BuildRunStatus.COMPLETED if not final_incomplete else BuildRunStatus.STOPPED
    build_state.update_run(run_id, status=final_status, completed_specs=sorted(completed_spec_names))
    return LoopResult(
        total_specs=total_specs,
        completed_specs=total_specs - len(final_incomplete),
        iterations=len(iterations),
        details=iterations,
        remaining=[s.name for s in final_incomplete],
    )
