"""Analyzer for required dependencies (PPC, API keys)."""

import json
import os
from pathlib import Path

import click

from village.doctor.base import Analyzer, AnalyzerResult, Finding
from village.ppc import require_ppc

PPC_INSTALL_URL = "https://github.com/bkuri/ppc"


class RequirementsAnalyzer(Analyzer):
    """Check that required tools and credentials are present."""

    name = "requirements"
    description = "Check PPC binary and provider API keys"
    category = "requirements"

    def run(self) -> AnalyzerResult:
        findings = []

        # Check PPC binary
        findings.extend(self._check_ppc())

        # Check pi API keys
        findings.extend(self._check_pi_auth())

        return AnalyzerResult(
            analyzer_name=self.name,
            analyzer_description=self.description,
            findings=findings,
        )

    def _check_ppc(self) -> list[Finding]:
        try:
            require_ppc()
            return []
        except click.ClickException:
            return [
                Finding(
                    id="ppc-not-found",
                    title="PPC binary not found on PATH",
                    description=(
                        f"PPC is required but not installed. Install from: {PPC_INSTALL_URL}\n\n"
                        f"PPC is a Go CLI tool that generates system prompts. "
                        f"Without it, village cannot start agents."
                    ),
                    severity="high",
                    category="requirements",
                    metadata={"url": PPC_INSTALL_URL},
                )
            ]

    def _check_pi_auth(self) -> list[Finding]:
        findings: list[Finding] = []

        # Check environment variable first (takes precedence)
        zai_key = os.environ.get("ZAI_API_KEY")
        if zai_key:
            return findings  # Env var overrides auth.json

        # Check auth.json
        auth_path = Path.home() / ".pi" / "agent" / "auth.json"
        if not auth_path.exists():
            findings.append(
                Finding(
                    id="pi-auth-missing",
                    title="pi agent auth file not found",
                    description=(
                        f"No auth file found at {auth_path}. "
                        f"The pi agent needs API keys to make LLM calls.\n\n"
                        f"Set ZAI_API_KEY env var or create {auth_path} "
                        f"with provider API keys.\n\n"
                        f"Example auth.json:\n"
                        f'{{"zai":"your-zai-api-key"}}'
                    ),
                    severity="high",
                    category="requirements",
                    metadata={"path": str(auth_path)},
                )
            )
            return findings

        try:
            auth_data = json.loads(auth_path.read_text())
        except (json.JSONDecodeError, OSError):
            findings.append(
                Finding(
                    id="pi-auth-invalid",
                    title="pi agent auth file is invalid",
                    description=f"Could not parse auth file at {auth_path}. Check that it contains valid JSON.",
                    severity="high",
                    category="requirements",
                    metadata={"path": str(auth_path)},
                )
            )
            return findings

        if not auth_data:
            findings.append(
                Finding(
                    id="pi-auth-empty",
                    title="pi agent auth file is empty",
                    description=(
                        f"Auth file at {auth_path} exists but is empty. "
                        f"Add API keys for your providers.\n\n"
                        f"Example: {auth_path}\n"
                        f'{{"zai":"your-zai-api-key"}}'
                    ),
                    severity="high",
                    category="requirements",
                    metadata={"path": str(auth_path)},
                )
            )

        return findings
