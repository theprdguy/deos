"""Claude 1 pipe-mode wrapper.

Invokes `claude -p` with SSOT context for PRD decomposition and planning.
Used by the dispatcher for agent-review gates and by CLI for plan operations.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path


SYSTEM_PROMPT_TEMPLATE = """
You are Claude 1, the Planner + Researcher + SSOT Manager for this project.

Your current SSOT state:

## .claude/CLAUDE.md (Your Operating Rules)
{claude_md}

## devos/PROJECT_STATE.md
{project_state}

## devos/CONTEXT.md
{context}

## devos/tasks/QUEUE.yaml
{queue}

## devos/questions/QUEUE.md
{questions}

## Recent Session Logs
{recent_logs}

---
RULES:
1. Do NOT write implementation code.
2. If decomposing a PRD: output a JSON block with tickets (see format below).
3. If answering a question: respond concisely.
4. Update SSOT files if needed (you have filesystem access).
5. The user will approve plans before dispatch begins.

When decomposing a PRD, output tickets in this JSON format inside a ```json block:
{{
  "plan_summary": "Brief description of the plan",
  "tickets": [
    {{
      "id": "T-001",
      "owner": "CLAUDE2",
      "status": "todo",
      "priority": "high",
      "goal": "What to build",
      "context": "Why + research context",
      "constraints": ["constraint 1"],
      "dod": ["acceptance criterion"],
      "files": ["apps/api/src/feature.ts"],
      "verify": "make pr-check",
      "deps": [],
      "contract_impact": "none"
    }}
  ]
}}
"""


def _load_ssot_context(devos_path: Path, claude_md_path: Path) -> dict:
    """Load SSOT files for system prompt context."""

    def read_or(path: Path, default: str = "(not found)") -> str:
        try:
            content = path.read_text()
            return content[:3000]  # Truncate to save tokens
        except Exception:
            return default

    # Read recent logs (last 3)
    logs_path = devos_path / "logs"
    recent_logs = "(no logs yet)"
    if logs_path.exists():
        log_files = sorted(
            [f for f in logs_path.iterdir() if f.suffix == ".md" and f.name != "README.md"],
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )[:3]
        if log_files:
            recent_logs = "\n---\n".join(f.read_text()[:500] for f in log_files)

    return {
        "claude_md": read_or(claude_md_path),
        "project_state": read_or(devos_path / "PROJECT_STATE.md"),
        "context": read_or(devos_path / "CONTEXT.md"),
        "queue": read_or(devos_path / "tasks" / "QUEUE.yaml"),
        "questions": read_or(devos_path / "questions" / "QUEUE.md"),
        "recent_logs": recent_logs,
    }


def invoke_claude1(
    user_message: str,
    devos_path: Path,
    claude_md_path: Path,
    timeout: int = 300,
) -> str:
    """
    Invoke Claude 1 via `claude -p` pipe mode.
    Returns the response text.
    """
    ssot = _load_ssot_context(devos_path, claude_md_path)
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(**ssot)

    full_prompt = f"{system_prompt}\n\n---\n\nUser message:\n{user_message}"

    try:
        result = subprocess.run(
            ["claude", "-p", full_prompt],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(devos_path.parent),  # project root
        )
        if result.returncode != 0:
            return f"Claude 1 error (exit {result.returncode}):\n{result.stderr[:500]}"
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        return f"Claude 1 timed out after {timeout}s."
    except FileNotFoundError:
        return "Error: `claude` CLI not found. Is Claude Code installed?"


def extract_tickets_from_response(response: str) -> list[dict] | None:
    """
    Parse ticket JSON from Claude 1's PRD decomposition response.
    Returns list of tickets or None if no JSON block found.
    """
    import json
    import re

    match = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL)
    if not match:
        return None

    try:
        data = json.loads(match.group(1))
        return data.get("tickets")
    except json.JSONDecodeError:
        return None


def extract_plan_summary(response: str) -> str:
    """Extract the plan summary from Claude 1's response."""
    import json
    import re

    match = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL)
    if not match:
        return "(no summary)"
    try:
        data = json.loads(match.group(1))
        return data.get("plan_summary", "(no summary)")
    except json.JSONDecodeError:
        return "(parse error)"
