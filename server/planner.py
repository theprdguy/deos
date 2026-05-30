"""Planner response parser utilities.

A `claude -p` pipe-mode wrapper previously lived here; it was removed in
T-OSN-TOKEN-PHASE-0A (2026-05-14) because:
- No callers existed in server/, bin/, scripts/, or tests/ (dead code).
- 2026-06-15 Anthropic Agent SDK billing split makes accidental `claude -p`
  invocations more impactful — removing dead code avoids future risk.

The parsing helpers below are retained for potential plan-decomposition reuse.
"""
from __future__ import annotations


def extract_tickets_from_response(response: str) -> list[dict] | None:
    """
    Parse ticket JSON from a planner response.
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
    """Extract the plan summary from a planner response."""
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
