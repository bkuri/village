"""Pure rendering functions for task specs and breakdowns."""

from village.chat.sequential_thinking import TaskBreakdown
from village.chat.task_spec import TaskSpec


def render_task_spec(spec: TaskSpec, refinement_count: int = 0) -> str:
    """Render task specification as ASCII box with dependencies."""
    box_width = 46
    lines = []

    lines.append("┌" + "─" * box_width + "┐")
    title_display = f"{spec.title} (Refinement #{refinement_count})" if refinement_count > 0 else spec.title
    lines.append("│" + f" TASK: {title_display[:38]} " + " " * (box_width - 39) + "│")
    lines.append("├" + "─" * box_width + "┤")
    lines.append("│" + f" Title: {spec.title[:35]} " + " " * (box_width - 35) + "│")
    lines.append("│" + f" Scope: {spec.scope:<35} " + " " * (box_width - 35) + "│")
    lines.append("│" + f" Estimate: {spec.estimate:<31} " + " " * (box_width - 31) + "│")
    lines.append("├" + "─" * box_width + "┤")

    if spec.has_dependencies():
        lines.append("│" + " DEPENDENCIES: " + " " * (box_width - 13) + "│")

        if spec.blocked_by:
            blocked_str = ", ".join(spec.blocked_by)[:30]
            lines.append("│" + f"   ⬇ BLOCKED BY: {blocked_str} " + " " * (box_width - 42) + "│")
        else:
            lines.append("│" + " " * box_width + "│")

        if spec.blocks:
            blocks_str = ", ".join(spec.blocks)[:33]
            lines.append("│" + f"   ⬇ BLOCKS: {blocks_str} " + " " * (box_width - 41) + "│")
        else:
            lines.append("│" + " " * box_width + "│")
    else:
        lines.append("│" + " DEPENDENCIES: (none) " + " " * (box_width - 19) + "│")

    lines.append("├" + "─" * box_width + "┤")
    lines.append("│" + f" SUCCESS CRITERIA ({len(spec.success_criteria)}): " + " " * (box_width - 23) + "│")

    for i, criterion in enumerate(spec.success_criteria, 1):
        lines.append("│" + f"   {i}. {criterion[:40]} " + " " * (box_width - 41) + "│")

    lines.append("├" + "─" * box_width + "┤")

    confidence_emoji = {"high": "🟢", "medium": "🟡", "low": "🔴"}
    emoji = confidence_emoji[spec.confidence]
    lines.append("│" + f" Confidence: {emoji} {spec.confidence.upper():<30} " + " " * (box_width - 41) + "│")
    lines.append("├" + "─" * box_width + "┤")

    lines.append("│" + " /refine /revise <clarification> - Revise this task      " + " " * (box_width - 55) + "│")
    lines.append("│" + " /undo - Revert to previous version                     " + " " * (box_width - 50) + "│")
    lines.append("│" + " /confirm - Queue this task                              " + " " * (box_width - 50) + "│")
    lines.append("│" + " /discard - Cancel                                       " + " " * (box_width - 43) + "│")
    lines.append("└" + "─" * box_width + "┘")

    return "\n".join(lines)


def render_breakdown(breakdown: TaskBreakdown) -> str:
    """Render TaskBreakdown as ASCII table."""
    box_width = 46
    lines = []

    title_display = breakdown.title_original or "Untitled"
    if breakdown.title_suggested:
        title_display += f" → {breakdown.title_suggested}"

    lines.append("┌" + "─" * box_width + "┐")
    lines.append("│" + f" BREAKDOWN: {title_display[:40]} " + " " * (box_width - 49) + "│")
    lines.append("├" + "─" * box_width + "┤")

    index_to_title = {i: item.title for i, item in enumerate(breakdown.items)}

    for i, item in enumerate(breakdown.items, 1):
        if item.dependencies:
            deps_str = ", ".join(index_to_title.get(d, f"#{d}") for d in item.dependencies)
        else:
            deps_str = "none"

        title_short = item.title[:35]

        lines.append("│" + f" {i}. {title_short}" + " " * (box_width - 40) + "│")

        desc_words = item.description.split()[:8]
        desc_short = " ".join(desc_words)
        lines.append("│" + f"    {desc_short}" + " " * (box_width - 45) + "│")

        lines.append("│" + f"    [depends: {deps_str}]" + " " * (box_width - 22) + "│")
        lines.append("│" + f"    [effort: {item.estimated_effort}]" + " " * (box_width - 20) + "│")

        if i < len(breakdown.items):
            lines.append("│" + " " * box_width + "│")

    lines.append("└" + "─" * box_width + "┘")

    lines.append("")
    lines.append("Actions:")
    lines.append("  /confirm   Create all subtasks in task store")
    lines.append("  /edit      Refine entire breakdown")
    lines.append("  /discard    Cancel this breakdown")

    return "\n".join(lines)


def render_decomposition_error(
    error_message: str,
    task_info: str | None = None,
    breakdown: str | None = None,
    offer_retry: bool = True,
) -> str:
    """Render decomposition error with full context."""
    lines = ["❌ ERROR: Decomposition Failed", ""]
    lines.append(error_message)
    lines.append("")

    if task_info:
        lines.append("Task Information:")
        lines.append(task_info)
        lines.append("")

    if breakdown:
        lines.append("Generated Breakdown (partial or invalid):")
        breakdown_display = breakdown[:500] if len(breakdown) > 500 else breakdown
        lines.append(breakdown_display)
        if len(breakdown) > 500:
            lines.append(f"[... {len(breakdown) - 500} more characters truncated]")
        lines.append("")

    if offer_retry:
        lines.append("Actions:")
        lines.append("  /retry      Try decomposition again")
        lines.append("  /discard    Cancel and try simpler task")
        lines.append("  /confirm-simple  Create as single task (without breakdown)")

    return "\n".join(lines)


def task_spec_to_text(spec: TaskSpec) -> str:
    """Convert TaskSpec to text for LLM prompt."""
    lines = [
        f"Title: {spec.title}",
        f"Description: {spec.description}",
        f"Scope: {spec.scope}",
        f"Blocks: {', '.join(spec.blocks) if spec.blocks else '(none)'}",
        f"Blocked by: {', '.join(spec.blocked_by) if spec.blocked_by else '(none)'}",
        f"Success Criteria: {', '.join(spec.success_criteria) if spec.success_criteria else '(none)'}",
    ]
    if spec.search_hints:
        hints_parts = []
        for key, values in spec.search_hints.items():
            if values:
                hints_parts.append(f"{key}: {', '.join(values)}")
        if hints_parts:
            lines.append(f"Search Hints: {'; '.join(hints_parts)}")
    return "\n".join(lines)


def breakdown_to_text(breakdown: TaskBreakdown) -> str:
    """Convert TaskBreakdown to text for LLM prompt."""
    lines = [f"Title: {breakdown.title_original or 'Untitled'}"]

    if breakdown.summary:
        lines.append(f"Summary: {breakdown.summary}")

    lines.append("Subtasks:")
    for i, item in enumerate(breakdown.items, 1):
        deps_str = ", ".join(str(d) for d in item.dependencies) if item.dependencies else "none"
        lines.append(f"  {i}. {item.title}")
        lines.append(f"     {item.description}")
        lines.append(f"     [depends: {deps_str}] [effort: {item.estimated_effort}]")

    return "\n".join(lines)
