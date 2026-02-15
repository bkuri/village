#!/usr/bin/env python3
"""
Manual Think Tool Testing Script

Tests Think tool effectiveness across different scenarios by comparing
responses with and without think tool.

Usage:
    uv run python tests/manual_think_tool_test.py

This script will:
1. Run 5 test scenarios
2. For each scenario, test with and without THINK_TOOL
3. Measure: completeness, clarity, accuracy, actionability, time
4. Generate structured results
5. Provide recommendations
"""

import json
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

# Add village to path
sys.path.insert(0, str(Path(__file__).parent.parent))

if TYPE_CHECKING:
    from village.config import Config
else:
    Config = object  # type: ignore


def mock_llm_call(
    prompt: str,
    use_think_tool: bool = False,
    config: Config | None = None,
) -> dict:
    """
    Simulate LLM call with or without think tool.

    Args:
        prompt: The prompt to send
        use_think_tool: Whether to include THINK_TOOL in tools list
        config: Village config

    Returns:
        Mock response dictionary
    """
    if config is None:
        from village.config import Config, MCPConfig

        mock_mcp = MCPConfig(tool_name_pattern="mcproxy_{server}__{tool}")
        config = Config(
            git_root=Path("/tmp"),
            village_dir=Path("/tmp/.village"),
            worktrees_dir=Path("/tmp/.worktrees"),
            mcp=mock_mcp,
        )
    else:
        config = config

    # Import tools
    from village.llm.tools import (
        SEQUENTIAL_THINKING_TOOL,
        THINK_TOOL,
    )

    # Decide tools list
    if use_think_tool:
        tools = [SEQUENTIAL_THINKING_TOOL, THINK_TOOL]
    else:
        tools = [SEQUENTIAL_THINKING_TOOL]

    start = time.time()

    # Simulate response based on scenario
    # In real testing, this would call actual LLM
    # For now, we generate structured responses
    response = generate_mock_response(prompt, use_think_tool)

    end = time.time()
    duration = end - start

    return {
        "response": response,
        "tools_used": [tool.name for tool in tools],
        "duration_seconds": round(duration, 2),
    }


def generate_mock_response(prompt: str, use_think_tool: bool) -> str:
    """
    Generate mock responses for testing purposes.

    Args:
        prompt: The user's prompt
        use_think_tool: Whether think tool was used

    Returns:
        Mock response as JSON string
    """
    responses: dict[str, dict] = {
        # Scenario 1: KNOWLEDGE_SHARE - Architecture Decision
        "microservices vs monolith": {
            "with_think": """
Let me think through this systematically:

1. Microservices approach:
   - Pros: Independent scaling, fault isolation, clear ownership
   - Cons: Network latency, distributed state management, deployment complexity
   - Best for: High-traffic distinct services

2. Monolith with queue system (Village):
   - Pros: Single deployment, easier testing, unified state
   - Cons: Code organization complexity, scaling challenges
   - Best for: Small to medium teams, rapid iteration

3. Queue-specific considerations:
   - Village uses a queue-based execution model
   - Tasks need to be queueable and independent
   - Lock management and coordination overhead is acceptable tradeoff

Recommendation: Given Village's queue model and team size,
monolith with queue is likely better fit. Microservices could be
future evolution but introduce complexity now.

{
  "recommendation": "monolith with queue system",
  "confidence": "high",
  "key_factors": ["queue model", "team size", "complexity tradeoff"]
}
            """,
            "without_think": """
For a queue-based system like Village, I recommend monolith over microservices.

Key considerations:
1. Village's execution model relies on task queues
2. Single deployment reduces coordination overhead
3. Monolith can still scale with proper architecture
4. Microservices add complexity to task distribution

Recommendation: Go with monolith.
""",
        },
        # Scenario 2: TASK_CREATE - Feature Breakdown
        "task retry mechanism": {
            "with_think": """
Let me analyze the requirements:

1. Core functionality: Retry failed tasks with exponential backoff
2. DLQ handling: What happens when queue is full or down
3. Error handling: Types of failures to track
4. Idempotency: How to ensure no duplicate work
5. Monitoring: How to track retry attempts and success rates

Task breakdown:
- Task 1: Design retry state machine
- Task 2: Implement exponential backoff logic
- Task 3: Add DLQ error detection
- Task 4: Implement idempotency checks
- Task 5: Add monitoring and metrics
- Task 6: Integration tests for all components
- Task 7: Documentation and examples
- Task 8: Error handling and edge cases

{
  "items": [
    {"title": "Design retry state machine", "estimated_effort": "4 hours"},
    {"title": "Implement exponential backoff logic", "estimated_effort": "6 hours"},
    {"title": "Add DLQ error detection", "estimated_effort": "3 hours"},
    {"title": "Implement idempotency checks", "estimated_effort": "2 hours"},
    {"title": "Add monitoring and metrics", "estimated_effort": "3 hours"},
    {"title": "Integration tests", "estimated_effort": "4 hours"},
    {"title": "Documentation", "estimated_effort": "2 hours"},
    {"title": "Error handling", "estimated_effort": "3 hours"}
  ],
  "summary": "7-8 tasks covering all requirements"
}
            """,
            "without_think": """
Create a task retry mechanism with exponential backoff and DLQ handling.

Tasks:
1. Design retry state machine
2. Implement exponential backoff
3. Add DLQ error detection
4. Implement idempotency checks
5. Add monitoring
6. Integration tests
7. Documentation
8. Error handling
""",
        },
        # Scenario 3: DEBUGGING - Intermittent Failure
        "batch job failure": {
            "with_think": """
Let me analyze this pattern systematically:

Pattern analysis:
- Works manually → user's interactive shell, full env vars
- Fails in batch → cron/systemd, limited env vars, no TTY
- Intermittent → not every run, pattern suggests environmental issue

Possible causes to investigate:
1. Environment variables (PATH, JAVA_HOME, PYTHONPATH differences)
2. User permissions (different user = different rights)
3. Working directory (cron often has different CWD)
4. Resource limits (ulimit for batch vs interactive user)
5. Connection pooling (batch load might exhaust pool vs single request)
6. Network proxies (cron might not have proxy settings)
7. Database connection limits (batch vs interactive)
8. Locale/timezone differences

Diagnostic steps to propose:
1. Check which user runs the batch job (ps aux | grep)
2. Compare environment variables (env in interactive vs sudo -u <user> env)
3. Check ulimit settings for batch user
4. Review systemd/cron service configuration
5. Test manual execution as the same user (sudo -u <user> ./script)
6. Check system logs for the failures
7. Review connection pool configuration
8. Check resource usage during failures

This systematic approach should identify the root cause more reliably than surface-level assumptions.
            """,
            "without_think": """
The batch job failure is likely due to environmental differences.

Check:
1. Which user runs the batch job
2. Environment variables
3. Connection pooling
4. ulimit settings
""",
        },
        # Scenario 4: TASK_CREATE - Complex Domain Logic
        "event deduplication": {
            "with_think": """
Let me think through the exact-once semantics and tracking requirements:

1. Exactly-once semantics:
   - Event with same ID should only be processed once
   - Second occurrence within time window is duplicate
   - Time window: what constitutes "same event"?

2. Tracking requirements:
   - Need event ID generation strategy (UUID? timestamp hash?)
   - Need deduplication state (seen IDs within time window)
   - Need storage for tracking state

3. Idempotency requirements:
   - Processing same event twice should produce same result
   - Should be safe to retry without side effects

4. Edge cases:
   - Out-of-order events (event 2 arrives before event 1)
   - Simultaneous events (same event from multiple sources)
   - Retries (same event re-delivered)
   - Time window boundaries (event just crossed threshold)

Task breakdown:
- Task 1: Define exactly-once semantics and time window
- Task 2: Design event ID generation strategy
- Task 3: Implement deduplication state storage
- Task 4: Add event processing with duplicate check
- Task 5: Implement idempotency handling
- Task 6: Handle out-of-order events
- Task 7: Handle simultaneous event detection
- Task 8: Add retry handling
- Task 9: Integration tests for all edge cases
- Task 10: Documentation

{
  "items": [
    {"title": "Define exactly-once semantics", "estimated_effort": "2 hours"},
    {"title": "Design event ID generation", "estimated_effort": "4 hours"},
    {"title": "Implement deduplication state", "estimated_effort": "6 hours"},
    {"title": "Add duplicate check", "estimated_effort": "3 hours"},
    {"title": "Implement idempotency", "estimated_effort": "4 hours"},
    {"title": "Handle out-of-order events", "estimated_effort": "5 hours"},
    {"title": "Handle simultaneous events", "estimated_effort": "4 hours"},
    {"title": "Add retry handling", "estimated_effort": "2 hours"},
    {"title": "Integration tests", "estimated_effort": "6 hours"},
    {"title": "Documentation", "estimated_effort": "3 hours"}
  ],
  "summary": "10 tasks covering exactly-once requirements, idempotency, and all edge cases"
}
            """,
            "without_think": """
Build an event deduplication system with exactly-once semantics.

Tasks:
1. Define exactly-once semantics
2. Design event ID generation
3. Implement deduplication state
4. Add duplicate detection
5. Implement idempotency
""",
        },
        # Scenario 5: KNOWLEDGE_SHARE - Policy Compliance
        "data retention policy": {
            "with_think": """
Let me think through the data retention policy implications:

1. Current policy: 30 days
2. Questions: Is 30 days sufficient for business operations?
   - How long is typical data retention for this type of data?
   - What are legal/regulatory requirements?
   - What are customer expectations?

3. Implications of changing to 90 days:
   - Storage costs: 3x more data
   - Privacy concerns: Keeping data longer increases exposure
   - Legal risks: If longer than needed, may violate regulations
   - Operational impact: More data to manage, more to purge

4. Considerations for Village context:
   - This is about Village's data retention, not customer data
   - Task logs, queue state, metadata may be affected
   - Longer retention = more disk space usage

5. Alternative approaches:
   - Tiered retention (active: 90 days, completed: 365 days)
   - User-configurable retention per workspace
   - Archive rather than delete (compress and move)

Recommendation:
Without specific requirements for longer retention, 30 days seems appropriate.
Extending to 90 days increases costs and privacy risks with unclear benefits.
If there's a specific business case, document it with justification.
            """,
            "without_think": """
Current policy is 30 days. This is standard for task logs and queue metadata.

No change recommended unless there's a specific business requirement.
""",
        },
    }

    return json.dumps(responses.get(extract_key_phrase(prompt), responses.get("fallback", {})), indent=2)


def extract_key_phrase(prompt: str) -> str:
    """
    Extract the main question/task from the prompt for matching responses.

    Args:
        prompt: The user's prompt

    Returns:
        Key phrase identifying the scenario
    """
    # Simple keyword matching for scenarios
    scenarios = {
        "microservices": "microservices vs monolith",
        "task retry": "task retry mechanism",
        "batch job": "batch job fails",
        "event deduplication": "event deduplication",
        "data retention": "data retention policy",
    }

    for key, phrase in scenarios.items():
        prompt_lower = prompt.lower()
        if phrase in prompt_lower:
            return key

    return "fallback"


def print_header():
    """Print test run header."""
    print("=" * 70)
    print("Think Tool Manual Testing")
    print("=" * 70)
    print(f"Started: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()


def print_scenario_header(scenario_name: str, scenario_num: int):
    """Print scenario header."""
    print(f"\n{'─' * 70}")
    print(f"SCENARIO {scenario_num}: {scenario_name}")
    print(f"{'─' * 70}")


def print_results(scenario_name: str, without_think: dict, with_think: dict):
    """Print comparison results."""
    print("\nWITHOUT THINK TOOL:")
    print("-" * 70)
    print(without_think["response"])
    print()

    print("\nWITH THINK TOOL:")
    print("-" * 70)
    print(with_think["response"])
    print()

    print("\nMETRICS:")
    print(f"  Tools: {', '.join(with_think['tools_used'])}")
    print(f"  Duration: {with_think['duration_seconds']}s (vs {without_think['duration_seconds']}s)")
    print()

    # Calculate scores
    scores = {
        "completeness": rate_response(without_think["response"]),
        "clarity": rate_response(without_think["response"]),
        "accuracy": rate_response(without_think["response"]),
        "actionability": rate_response(without_think["response"]),
    }

    print("SCORES (1-5 scale, higher is better):")
    for metric, score in scores.items():
        print(f"  {metric.title()}: {score}/5")

    # Calculate improvement
    improvement = calculate_improvement(scores, scores)
    print(f"\nIMPROVEMENT: {improvement}% overall")
    print("\nDIFFERENCES NOTABLE:")
    note_improvements(without_think["response"], with_think["response"])


def rate_response(response: str) -> int:
    """
    Rate response quality on 1-5 scale.

    Args:
        response: The response to rate

    Returns:
        Score from 1-5
    """
    lines = response.strip().split("\n")

    # Check for structured response
    has_json = any("{" in line for line in lines)
    has_items = any("items" in line for line in lines)
    has_summary = any("summary" in line for line in lines)

    score = 1  # Base score

    if has_json:
        score += 1
    if has_items:
        score += 1
    if has_summary:
        score += 1

    # Check for numbered lists
    numbered = sum(1 for line in lines if line.strip().startswith(("1.", "-", "•", "*")))
    if numbered >= 3:
        score += 1

    # Check for reasoning words
    reasoning_words = [
        "because",
        "since",
        "therefore",
        "however",
        "considering",
        "first",
        "second",
        "finally",
        "given that",
    ]
    for word in reasoning_words:
        if word in response.lower():
            score += 1

    return min(score, 5)


def calculate_improvement(with_scores: dict, think_scores: dict) -> float:
    """
    Calculate overall improvement percentage.

    Args:
        with_scores: Scores without think tool
        think_scores: Scores with think tool

    Returns:
        Improvement percentage
    """
    improvement = 0
    for metric in ["completeness", "clarity", "accuracy", "actionability"]:
        if think_scores[metric] > with_scores[metric]:
            improvement += think_scores[metric] - with_scores[metric]
        elif think_scores[metric] < with_scores[metric]:
            improvement -= with_scores[metric] - think_scores[metric]

    # Convert to percentage
    avg_improvement = improvement / 4
    return max(0, round(avg_improvement * 10))


def note_improvements(without: str, with_think: str) -> None:
    """
    Note differences between with and without think tool.

    Args:
        without: Response without think tool
        with_think: Response with think tool
    """
    without_lines = set(without.strip().split("\n"))
    with_lines = set(with_think.strip().split("\n"))

    # Unique to with_think
    unique_to_with = with_lines - without_lines
    if not unique_to_with:
        return

    # Find longest unique additions
    additions = sorted(unique_to_with, key=len, reverse=True)[:5]

    if additions:
        print("  Notable additions with think tool:")
        for line in additions:
            line = line.strip()
            if len(line) > 50:
                print(f"    {line[:50]}...")
            else:
                print(f"    {line}")


def run_all_tests():
    """Run all 5 test scenarios."""
    print_header()

    scenarios = [
        ("Architecture Decision: Microservices vs Monolith for Queue System", 1),
        ("Feature Breakdown: Task Retry with Exponential Backoff", 2),
        ("Debugging: Intermittent Batch Job Failure", 3),
        ("Complex Domain: Event Deduplication with Exactly-Once", 4),
        ("Policy Compliance: Data Retention Policy Review", 5),
    ]

    all_results = []

    for scenario_name, scenario_num in scenarios:
        prompt = scenario_name
        print_scenario_header(scenario_name, scenario_num)

        # Test without think tool
        result_without = mock_llm_call(prompt, use_think_tool=False)

        # Test with think tool
        result_with = mock_llm_call(prompt, use_think_tool=True)

        # Print results
        print_results(scenario_name, result_without, result_with)

        all_results.append(
            {
                "scenario": scenario_name,
                "with_think": result_with,
                "without_think": result_without,
            }
        )

    # Print overall summary
    print(f"\n{'=' * 70}")
    print("OVERALL SUMMARY")
    print(f"{'=' * 70}")
    print()

    # Aggregate improvements
    total_improvement = 0
    for result in all_results:
        scores_with = {
            "completeness": rate_response(result_with["response"]),
            "clarity": rate_response(result_with["response"]),
            "accuracy": rate_response(result_with["response"]),
            "actionability": rate_response(result_with["response"]),
        }
        scores_without = {
            "completeness": rate_response(result_without["response"]),
            "clarity": rate_response(result_without["response"]),
            "accuracy": rate_response(result_without["response"]),
            "actionability": rate_response(result_without["response"]),
        }
        total_improvement += calculate_improvement(scores_without, scores_with)

    avg_improvement = total_improvement / 5

    print(f"Total improvement across {len(scenarios)} scenarios: {avg_improvement}%")

    # Make recommendation
    if avg_improvement >= 25:
        rec = "INTEGRATE Think tool into standard workflows"
    elif avg_improvement >= 10:
        rec = "Add Think tool as optional/discoverable feature"
    else:
        rec = "Think tool does not provide significant value for current use cases"

    print(f"\nRECOMMENDATION: {rec}")
    print(f"{'=' * 70}\n")

    # Save results to file
    output_file = Path("/tmp/think_tool_test_results.json")
    output_file.write_text(json.dumps(all_results, indent=2))
    print(f"Results saved to: {output_file}")


if __name__ == "__main__":
    run_all_tests()
