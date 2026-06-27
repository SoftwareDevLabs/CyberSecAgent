from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ToolResult:
    stdout: str
    stderr: str
    returncode: int


def run_tool(
    command: list[str],
    *,
    cwd: Path | None = None,
    timeout_seconds: int = 300,
    env_overrides: dict[str, str] | None = None,
) -> ToolResult:
    """Run an external tool as a subprocess.

    All external tool invocations in the pipeline go through this function —
    never call subprocess.run directly from stage modules. This makes it
    trivial to mock the runner in tests.

    Does NOT raise on non-zero exit codes — callers decide whether a non-zero
    exit is fatal based on context.
    """
    import os

    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd else None,
        timeout=timeout_seconds,
        env=env,
    )
    return ToolResult(
        stdout=result.stdout,
        stderr=result.stderr,
        returncode=result.returncode,
    )
