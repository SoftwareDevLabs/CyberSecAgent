"""Unit tests for pipeline.runner."""
from __future__ import annotations

import sys

import pytest

from pipeline.runner import ToolResult, run_tool


def test_run_tool_captures_stdout() -> None:
    result = run_tool([sys.executable, "-c", "print('hello')"])
    assert result.returncode == 0
    assert result.stdout.strip() == "hello"
    assert result.stderr == ""


def test_run_tool_captures_stderr() -> None:
    result = run_tool([sys.executable, "-c", "import sys; sys.stderr.write('err')"])
    assert result.returncode == 0
    assert result.stderr == "err"


def test_run_tool_non_zero_exit_does_not_raise() -> None:
    # The runner returns the result — it's the stage's job to decide if failure is fatal
    result = run_tool([sys.executable, "-c", "raise SystemExit(1)"])
    assert result.returncode == 1


def test_run_tool_env_override() -> None:
    result = run_tool(
        [sys.executable, "-c", "import os; print(os.environ['TEST_VAR'])"],
        env_overrides={"TEST_VAR": "cyberguard"},
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "cyberguard"


def test_run_tool_timeout_raises() -> None:
    with pytest.raises(Exception):
        run_tool(
            [sys.executable, "-c", "import time; time.sleep(10)"],
            timeout_seconds=1,
        )


def test_tool_result_fields() -> None:
    result = ToolResult(stdout="out", stderr="err", returncode=0)
    assert result.stdout == "out"
    assert result.stderr == "err"
    assert result.returncode == 0
