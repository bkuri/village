from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class StepType(str, Enum):
    PROMPT = "prompt"
    CRITIQUE = "critique"
    DECOMPOSE = "decompose"
    RESEARCH = "research"
    SYNTHESIZE = "synthesize"
    BEADS = "beads"


STEP_PRESETS: dict[StepType, dict[str, Any]] = {
    StepType.PROMPT: {
        "tools": [],
        "traits": {},
    },
    StepType.CRITIQUE: {
        "tools": ["sequential_thinking"],
        "traits": {"style": "critical", "approach": "probing"},
    },
    StepType.DECOMPOSE: {
        "tools": ["sequential_thinking"],
        "traits": {"style": "analytical"},
        "target": "beads",
    },
    StepType.RESEARCH: {
        "tools": ["perplexity"],
        "traits": {},
        "retry": {"max_attempts": 3, "backoff_seconds": 2.0},
    },
    StepType.SYNTHESIZE: {
        "tools": [],
        "traits": {"style": "synthesizing"},
    },
    StepType.BEADS: {
        "tools": [],
        "traits": {},
        "target": "beads",
    },
}


@dataclass
class RetryConfig:
    max_attempts: int = 1
    backoff_seconds: float = 1.0


@dataclass
class StepConfig:
    name: str
    type: StepType
    prompt: str | None = None
    policy: str | None = None
    traits: dict[str, str] = field(default_factory=dict)
    tools: list[str] = field(default_factory=list)
    target: str | None = None
    input_from: list[str] | None = None
    async_exec: bool = False
    retry: RetryConfig = field(default_factory=RetryConfig)

    def resolve(self) -> "StepConfig":
        preset = STEP_PRESETS.get(self.type, {})
        merged = StepConfig(
            name=self.name,
            type=self.type,
            prompt=self.prompt,
            policy=self.policy,
            traits={**preset.get("traits", {}), **self.traits},
            tools=self.tools or preset.get("tools", []),
            target=self.target or preset.get("target"),
            input_from=self.input_from,
            async_exec=self.async_exec,
            retry=self.retry,
        )
        preset_retry = preset.get("retry")
        if preset_retry and merged.retry.max_attempts == 1:
            merged.retry = RetryConfig(**preset_retry)
        return merged


@dataclass
class WorkflowSchema:
    name: str
    description: str
    steps: list[StepConfig] = field(default_factory=list)
    inputs: list[str] = field(default_factory=list)
    version: int = 1

    def resolve_steps(self) -> list[StepConfig]:
        return [step.resolve() for step in self.steps]
