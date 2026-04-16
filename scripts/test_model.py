#!/usr/bin/env python3
"""Quick model tester for interview-style Q&A."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import click

from village.llm.providers.openrouter import OpenRouterClient

INTERVIEW_PROMPT = """You are conducting an adaptive onboarding interview. Your goal is to gather information about a software project.

Rules:
- Ask ONE question at a time
- After the user answers, ask ONE follow-up based on their response
- After 3 questions total, provide a 2-3 sentence summary of what you learned
- Keep questions short and focused

Start with your first question."""


@click.command()
@click.argument('model')
@click.option('--api-key', default=None, help='OpenRouter API key (or use OPENROUTER_API_KEY env)')
def main(model: str, api_key: str | None) -> None:
    api_key = api_key or os.getenv('OPENROUTER_API_KEY')
    if not api_key:
        click.echo('Error: API key required. Set OPENROUTER_API_KEY or use --api-key')
        sys.exit(1)

    # Handle both 'zai/glm-5-turbo' and 'openrouter/zai/glm-5-turbo' formats
    model_id = model.replace('openrouter/', '') if model.startswith('openrouter/') else model

    client = OpenRouterClient(api_key=api_key, model=model_id)

    click.echo(f'Model: {model}')
    click.echo('Type /exit to quit\n')

    response = client.call(prompt=INTERVIEW_PROMPT, system_prompt='You are a helpful assistant.')
    click.echo(f'Assistant: {response}\n')

    while True:
        user_input = click.prompt('You')
        if user_input.lower() in ['/exit', '/quit']:
            break

        response = client.call(prompt=user_input)
        click.echo(f'Assistant: {response}\n')


if __name__ == '__main__':
    main()