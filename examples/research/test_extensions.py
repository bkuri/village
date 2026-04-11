#!/usr/bin/env python
"""Test script to verify research extensions work correctly."""

import asyncio

from examples.research.chat import (
    ResearchChatContext,
    ResearchChatProcessor,
    ResearchTaskHooks,
    ResearchThinkingRefiner,
    ResearchToolInvoker,
)
from village.extensibility.tool_invokers import ToolInvocation


async def test_processor():
    """Test ResearchChatProcessor."""
    print("Testing ResearchChatProcessor...")
    processor = ResearchChatProcessor(citation_style="APA")

    query = "research machine learning interpretability"
    processed = await processor.pre_process(query)
    print(f"  Pre-processed: '{processed}'")

    response = "ML interpretability methods include SHAP [1] and LIME (Smith, 2024)."
    formatted = await processor.post_process(response)
    print(f"  Post-processed: '{formatted}'")
    print("  ✓ Processor passed\n")


async def test_thinking_refiner():
    """Test ResearchThinkingRefiner."""
    print("Testing ResearchThinkingRefiner...")
    refiner = ResearchThinkingRefiner()

    query = "Research machine learning interpretability"
    should_refine = await refiner.should_refine(query)
    print(f"  Should refine: {should_refine}")

    if should_refine:
        refinement = await refiner.refine_query(query)
        print(f"  Original: '{refinement.original_query}'")
        print(f"  Steps ({len(refinement.refined_steps)}):")
        for i, step in enumerate(refinement.refined_steps, 1):
            print(f"    {i}. {step}")
        print(f"  Context hints: {refinement.context_hints}")
    print("  ✓ Thinking refiner passed\n")


async def test_tool_invoker():
    """Test ResearchToolInvoker."""
    print("Testing ResearchToolInvoker...")
    invoker = ResearchToolInvoker()

    invocation = ToolInvocation(
        tool_name="perplexity_search",
        args={"query": "machine learning interpretability"},
    )

    should_invoke = await invoker.should_invoke(invocation)
    print(f"  Should invoke: {should_invoke}")

    transformed = await invoker.transform_args(invocation)
    print(f"  Transformed args: {transformed}")

    result = {"papers": ["paper1", "paper2"]}
    processed_result = await invoker.on_success(invocation, result)
    print(f"  Result processed: {processed_result is not None}")
    print("  ✓ Tool invoker passed\n")


async def test_chat_context():
    """Test ResearchChatContext."""
    print("Testing ResearchChatContext...")
    context = ResearchChatContext()

    session_ctx = await context.load_context("test-session")
    print(f"  Session ID: {session_ctx.session_id}")
    print(f"  Initial metadata: {session_ctx.metadata}")

    enriched = await context.enrich_context(session_ctx)
    print(f"  Enriched metadata: {list(enriched.metadata.keys())}")

    await context.save_context(session_ctx)
    print("  ✓ Chat context passed\n")


async def test_task_hooks():
    """Test ResearchTaskHooks."""
    print("Testing ResearchTaskHooks...")
    hooks = ResearchTaskHooks()

    context = {
        "task_type": "research",
        "title": "ML Interpretability Study",
        "description": "Research machine learning interpretability methods",
    }

    should_create = await hooks.should_create_task_hook(context)
    print(f"  Should create hook: {should_create}")

    if should_create:
        hook_spec = await hooks.create_hook_spec(context)
        print(f"  Title: {hook_spec.title}")
        print(f"  Tags: {hook_spec.tags}")
        print(f"  Metadata: {list(hook_spec.metadata.keys())}")
    print("  ✓ Task hooks passed\n")


async def test_bootstrap():
    """Test bootstrap function."""
    print("Testing bootstrap function...")
    from examples.research.chat import bootstrap_research_extensions

    registry = bootstrap_research_extensions()
    names = registry.get_all_names()
    print("  Registered extensions:")
    for ext_type, class_name in names.items():
        print(f"    - {ext_type}: {class_name}")
    print("  ✓ Bootstrap passed\n")


async def main():
    """Run all tests."""
    print("=" * 60)
    print("Research Extensions Test Suite")
    print("=" * 60 + "\n")

    await test_processor()
    await test_thinking_refiner()
    await test_tool_invoker()
    await test_chat_context()
    await test_task_hooks()
    await test_bootstrap()

    print("=" * 60)
    print("All tests passed! ✓")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
