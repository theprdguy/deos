"""SSOT file readers and writers for devos/."""
from __future__ import annotations

import fcntl
import re
import shutil
from datetime import datetime
from pathlib import Path

import yaml


# ── QUEUE.yaml ─────────────────────────────────────────────────────────────

DEFAULT_QUEUE_PATH = Path("devos/tasks/QUEUE.yaml")
VALID_STATUSES = {"todo", "doing", "done", "blocked", "parked"}
VALID_TDD_VALUES = ("required", "skip", "self-evident")


class ValidationError(ValueError):
    """Raised when SSOT content violates queue schema expectations."""


class TicketResumeError(ValueError):
    """Raised when a ticket cannot be resumed from blocked status."""


class AmbiguousPlanMatchError(ValueError):
    """Raised when a plan selector matches multiple pending plans."""

    def __init__(self, selector: str, candidates: list[str]):
        self.selector = selector
        self.candidates = candidates
        super().__init__(self.format_message())

    def format_message(self) -> str:
        lines = [f"Ambiguous plan selector: {self.selector}", "Candidates:"]
        lines.extend(f"  - {candidate}" for candidate in self.candidates)
        return "\n".join(lines)


class QueueDumper(yaml.SafeDumper):
    """YAML dumper for QUEUE.yaml."""


def _represent_queue_string(dumper: yaml.SafeDumper, value: str) -> yaml.nodes.ScalarNode:
    """Keep multiline queue strings reload-safe without changing short scalar style."""
    style = "|" if "\n" in value else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


QueueDumper.add_representer(str, _represent_queue_string)


def _validate_ticket(ticket: dict) -> dict:
    """Return a normalized ticket with compatibility fallbacks applied."""
    normalized = dict(ticket)
    owner = normalized.get("owner")
    normalized["tdd"] = normalized.get("tdd", "skip")
    normalized["test_owner"] = normalized.get("test_owner", owner)
    normalized["impl_owner"] = normalized.get("impl_owner", owner)

    tdd = normalized["tdd"]
    if tdd not in VALID_TDD_VALUES:
        raise ValidationError(f"tdd must be one of [{', '.join(VALID_TDD_VALUES)}]")

    gates = normalized.get("gates")
    if gates is not None:
        if not isinstance(gates, list):
            raise ValidationError("gates must be a list of dicts or strings")
        for gate in gates:
            if not isinstance(gate, (dict, str)):
                raise ValidationError("gates must contain only dicts or strings")

    return normalized


def _validate_queue_data(data: dict) -> dict:
    """Return normalized queue data after validating ticket schema."""
    normalized = dict(data)
    tickets = normalized.get("tickets", [])
    normalized["tickets"] = [_validate_ticket(ticket) for ticket in tickets]
    return normalized


def read_queue(queue_path: Path | None = None) -> dict:
    """Read QUEUE.yaml, validate schema, and return normalized content."""
    queue_path = queue_path or DEFAULT_QUEUE_PATH
    if not queue_path.exists():
        return {"version": "3.0", "tickets": []}
    with open(queue_path) as f:
        data = yaml.safe_load(f) or {}
    if "tickets" not in data:
        data["tickets"] = []
    return _validate_queue_data(data)


def write_queue(queue_path: Path, data: dict) -> None:
    """Write QUEUE.yaml with file lock to prevent concurrent writes."""
    with open(queue_path, "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yaml.dump(
                data,
                f,
                Dumper=QueueDumper,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
            )
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def validate_queue_file(queue_path: Path) -> None:
    """Reload QUEUE.yaml after writes to catch serialization errors before dispatch."""
    read_queue(queue_path)


def get_tickets_by_owner(queue_path: Path, owner: str) -> list[dict]:
    """Get all tickets for a given owner."""
    data = read_queue(queue_path)
    return [t for t in data.get("tickets", []) if t.get("owner") == owner]


def get_tickets_by_status(queue_path: Path, status: str) -> list[dict]:
    """Get all tickets with a given status."""
    data = read_queue(queue_path)
    return [t for t in data.get("tickets", []) if t.get("status") == status]


def update_ticket_status(queue_path: Path, ticket_id: str, status: str) -> bool:
    """Update the status of a ticket. Returns True if found and updated."""
    data = read_queue(queue_path)
    for ticket in data.get("tickets", []):
        if ticket.get("id") == ticket_id:
            ticket["status"] = status
            write_queue(queue_path, data)
            return True
    return False


def update_ticket_fields(queue_path: Path, ticket_id: str, updates: dict) -> bool:
    """Update arbitrary ticket fields. Returns True if found and updated."""
    data = read_queue(queue_path)
    for ticket in data.get("tickets", []):
        if ticket.get("id") != ticket_id:
            continue
        ticket.update(updates)
        write_queue(queue_path, data)
        return True
    return False


def block_ticket(queue_path: Path, ticket_id: str, reason: str, log_path: str) -> bool:
    """Mark a ticket blocked with dispatch failure metadata."""
    return update_ticket_fields(
        queue_path,
        ticket_id,
        {
            "status": "blocked",
            "_blocked_reason": reason,
            "_blocked_log": log_path,
        },
    )


def resume_blocked_ticket(queue_path: Path, ticket_id: str) -> dict:
    """Move a blocked ticket back to todo and archive blocked metadata."""
    data = read_queue(queue_path)
    for ticket in data.get("tickets", []):
        if ticket.get("id") != ticket_id:
            continue

        status = ticket.get("status")
        if status != "blocked":
            raise TicketResumeError(f"{ticket_id} is `{status}`, cannot resume")

        if "_blocked_reason" in ticket:
            ticket["_prev_blocked_reason"] = ticket.pop("_blocked_reason")
        if "_blocked_log" in ticket:
            ticket["_prev_blocked_log"] = ticket.pop("_blocked_log")
        ticket.pop("_retries", None)
        ticket["status"] = "todo"
        write_queue(queue_path, data)
        return ticket

    raise TicketResumeError(f"Ticket `{ticket_id}` not found in queue.")


def append_tickets(queue_path: Path, new_tickets: list[dict]) -> None:
    """Append new tickets to QUEUE.yaml."""
    for ticket in new_tickets:
        status = ticket.get("status")
        if status not in VALID_STATUSES:
            raise ValueError(
                f"Ticket '{ticket.get('id')}' has invalid status '{status}'. "
                f"New tickets must use status 'todo'. Valid values: {sorted(VALID_STATUSES)}"
            )
    data = read_queue(queue_path)
    data["tickets"].extend(new_tickets)
    write_queue(queue_path, data)


def format_queue_summary(queue_path: Path) -> str:
    """Format queue as a readable summary."""
    data = read_queue(queue_path)
    tickets = data.get("tickets", [])
    if not tickets:
        return "Queue: Empty — no tickets yet."

    lines = ["Ticket Queue\n"]
    by_status: dict[str, list] = {}
    for t in tickets:
        s = t.get("status", "unknown")
        by_status.setdefault(s, []).append(t)

    for status in ["doing", "todo", "blocked", "parked", "done"]:
        if status not in by_status:
            continue
        lines.append(f"\n[{status.upper()}]")
        for t in by_status[status]:
            owner = t.get("owner", "?")
            tdd = t.get("tdd", "skip")
            test_owner = t.get("test_owner", owner)
            impl_owner = t.get("impl_owner", owner)
            goal_preview = str(t.get("goal", ""))[:60].strip()
            lines.append(
                f"  {t['id']} [{owner}] tdd={tdd} test_owner={test_owner} "
                f"impl_owner={impl_owner} {goal_preview}"
            )

    return "\n".join(lines)


# ── PROJECT_STATE.md ────────────────────────────────────────────────────────

def read_project_state(devos_path: Path) -> str:
    """Read PROJECT_STATE.md and return content."""
    state_file = devos_path / "PROJECT_STATE.md"
    if not state_file.exists():
        return "(PROJECT_STATE.md not found)"
    return state_file.read_text()


def format_status_summary(devos_path: Path) -> str:
    """Format a concise status summary."""
    content = read_project_state(devos_path)

    lines = content.split("\n")
    summary_lines = ["Project Status\n"]

    in_section = None
    for line in lines:
        if line.startswith("## North Star"):
            in_section = "north_star"
        elif line.startswith("## Current Milestone"):
            in_section = "milestone"
        elif line.startswith("## Agent Status"):
            in_section = "agents"
        elif line.startswith("## In progress"):
            in_section = "progress"
        elif line.startswith("## Blockers"):
            in_section = "blockers"
        elif line.startswith("## "):
            in_section = None

        if in_section in ("north_star", "milestone", "progress", "blockers") and line.strip():
            summary_lines.append(line)

    return "\n".join(summary_lines[:30])


# ── Session Logs ─────────────────────────────────────────────────────────────

def get_recent_logs(logs_path: Path, limit: int = 5) -> list[Path]:
    """Get the most recent session log files."""
    if not logs_path.exists():
        return []
    logs = [f for f in logs_path.iterdir() if f.suffix == ".md" and f.name != "README.md"]
    logs.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    return logs[:limit]


def format_logs_summary(logs_path: Path) -> str:
    """Format recent logs as a readable summary."""
    recent = get_recent_logs(logs_path)
    if not recent:
        return "Logs: No session logs yet."

    lines = ["Recent Session Logs\n"]
    for log_file in recent:
        content = log_file.read_text()
        # Extract Summary section
        match = re.search(r"## Summary\n(.*?)(?=\n##|\Z)", content, re.DOTALL)
        summary = match.group(1).strip()[:200] if match else "(no summary)"
        lines.append(f"\n{log_file.name}")
        lines.append(summary)

    return "\n".join(lines)


# ── Plans ────────────────────────────────────────────────────────────────────

def list_pending_plans(plans_path: Path) -> list[Path]:
    """List plans awaiting approval."""
    pending = plans_path / "pending"
    if not pending.exists():
        return []
    return sorted([
        f
        for f in pending.iterdir()
        if f.suffix == ".yaml" and not f.name.endswith("-tickets.yaml")
    ])


def read_plan(plan_path: Path) -> dict:
    """Read a plan YAML file."""
    with open(plan_path) as f:
        return yaml.safe_load(f) or {}


def _format_plan_candidate(plan_file: Path, plan: dict) -> str:
    """Format a pending plan candidate for ambiguity errors."""
    plan_id = plan.get("id") or "(no id)"
    return f"{plan_file.stem} (id: {plan_id})"


def _pending_plan_candidates(plans_path: Path) -> list[tuple[Path, dict]]:
    """Read pending plan files with their parsed metadata."""
    return [(plan_file, read_plan(plan_file)) for plan_file in list_pending_plans(plans_path)]


def _unique_candidates(candidates: list[tuple[Path, dict]]) -> list[tuple[Path, dict]]:
    """Deduplicate candidates by file path while preserving match order."""
    seen = set()
    unique = []
    for plan_file, plan in candidates:
        if plan_file in seen:
            continue
        seen.add(plan_file)
        unique.append((plan_file, plan))
    return unique


def _resolve_pending_plan_file(plans_path: Path, selector: str) -> Path | None:
    """
    Resolve a pending plan selector by filename stem, plan id, then partial matches.

    Match priority:
    1. exact filename stem
    2. exact plan id field
    3. partial filename stem or plan id field
    """
    candidates = _pending_plan_candidates(plans_path)

    exact_filename = [(path, plan) for path, plan in candidates if path.stem == selector]
    if len(exact_filename) == 1:
        return exact_filename[0][0]
    if len(exact_filename) > 1:
        raise AmbiguousPlanMatchError(
            selector,
            [_format_plan_candidate(path, plan) for path, plan in exact_filename],
        )

    exact_id = [(path, plan) for path, plan in candidates if str(plan.get("id", "")) == selector]
    if len(exact_id) == 1:
        return exact_id[0][0]
    if len(exact_id) > 1:
        raise AmbiguousPlanMatchError(
            selector,
            [_format_plan_candidate(path, plan) for path, plan in exact_id],
        )

    partial = _unique_candidates([
        (path, plan)
        for path, plan in candidates
        if selector in path.stem or selector in str(plan.get("id", ""))
    ])
    if len(partial) == 1:
        return partial[0][0]
    if len(partial) > 1:
        raise AmbiguousPlanMatchError(
            selector,
            [_format_plan_candidate(path, plan) for path, plan in partial],
        )

    return None


def _read_split_ticket_file(ticket_file: Path) -> list[dict]:
    """Read tickets from a sibling split-ticket YAML file."""
    data = read_plan(ticket_file)
    return data.get("tickets", [])


def _read_ticket_directory(ticket_dir: Path) -> list[dict]:
    """Read tickets from a plan-id/tickets/*.yaml directory."""
    tickets = []
    for ticket_file in sorted(ticket_dir.glob("*.yaml")):
        data = read_plan(ticket_file)
        if isinstance(data, list):
            tickets.extend(data)
        elif isinstance(data, dict) and "tickets" in data:
            tickets.extend(data.get("tickets", []))
        elif isinstance(data, dict) and data.get("id"):
            tickets.append(data)
        else:
            raise ValueError(f"Invalid ticket file: {ticket_file}")
    return tickets


def _resolve_plan_tickets(plans_path: Path, plan_id: str, plan: dict) -> tuple[list[dict], list[Path]]:
    """
    Resolve tickets for single-file or split-mode plans.

    Priority:
    1. tickets key in the plan file
    2. sibling {plan-id}-tickets.yaml
    3. {plan-id}/tickets/*.yaml directory
    """
    if "tickets" in plan:
        return plan.get("tickets", []), []

    pending = plans_path / "pending"
    sibling_tickets = pending / f"{plan_id}-tickets.yaml"
    if sibling_tickets.exists():
        return _read_split_ticket_file(sibling_tickets), [sibling_tickets]

    ticket_dir_root = pending / plan_id
    ticket_dir = ticket_dir_root / "tickets"
    if ticket_dir.exists() and any(ticket_dir.glob("*.yaml")):
        return _read_ticket_directory(ticket_dir), [ticket_dir_root]

    raise FileNotFoundError("split-mode: tickets file not found")


def _move_plan_artifacts_to_approved(
    pending_file: Path,
    approved_dir: Path,
    plan_id: str,
    artifacts: list[Path],
) -> None:
    """Move the approved plan and any split-mode artifacts out of pending."""
    pending_file.rename(approved_dir / f"{plan_id}.yaml")
    for artifact in artifacts:
        shutil.move(str(artifact), str(approved_dir / artifact.name))


def _timestamped_rejected_artifact_path(base_path: Path) -> Path:
    """Return a non-conflicting rejected artifact path with a timestamp suffix."""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    candidate = base_path.with_name(f"{base_path.name}-{timestamp}")
    if not candidate.exists():
        return candidate

    microsecond_timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    return base_path.with_name(f"{base_path.name}-{microsecond_timestamp}")


def _move_plan_artifacts_to_rejected(
    pending_file: Path,
    rejected_dir: Path,
    plan_id: str,
) -> None:
    """Move split-mode plan artifacts out of pending during rejection."""
    sibling_tickets = pending_file.parent / f"{plan_id}-tickets.yaml"
    if sibling_tickets.exists():
        shutil.move(str(sibling_tickets), str(rejected_dir / sibling_tickets.name))

    ticket_dir_root = pending_file.parent / plan_id
    if ticket_dir_root.exists():
        target = rejected_dir / ticket_dir_root.name
        if target.exists():
            target = _timestamped_rejected_artifact_path(target)
        shutil.move(str(ticket_dir_root), str(target))


def _load_gate_defaults(queue_path: Path) -> list[dict]:
    """Load os2.yaml gate defaults for plan approval validation."""
    root = queue_path.parent.parent.parent
    config_path = root / "os2.yaml"
    if not config_path.exists():
        return []
    with open(config_path) as f:
        config = yaml.safe_load(f) or {}
    defaults = config.get("gates", {}).get("defaults", [])
    return [gate for gate in defaults if isinstance(gate, dict)]


def _gate_default_lookup(defaults: list[dict]) -> dict[str, dict]:
    """Build the supported string-gate lookup table from defaults."""
    lookup = {
        str(gate["name"]): gate
        for gate in defaults
        if gate.get("name")
    }
    types: dict[str, list[dict]] = {}
    for gate in defaults:
        gate_type = gate.get("type")
        if gate_type:
            types.setdefault(str(gate_type), []).append(gate)
    for gate_type, matches in types.items():
        if len(matches) == 1:
            lookup.setdefault(gate_type, matches[0])
    return lookup


def _validate_gate_names(tickets: list[dict], defaults: list[dict]) -> None:
    """Reject unknown string gate names before approving a plan."""
    lookup = _gate_default_lookup(defaults)
    for ticket in tickets:
        gates = ticket.get("gates")
        if not gates:
            continue
        if not isinstance(gates, list):
            raise ValidationError("gates must be a list of dicts or strings")
        for gate in gates:
            if isinstance(gate, str) and gate not in lookup:
                raise ValidationError(
                    f"unknown gate name: '{gate}', see os2.yaml gates.defaults"
                )
            if not isinstance(gate, (dict, str)):
                raise ValidationError("gates must contain only dicts or strings")


def approve_plan(plans_path: Path, plan_id: str, queue_path: Path) -> bool:
    """Move plan from pending to approved and write tickets to QUEUE.yaml."""
    pending_file = _resolve_pending_plan_file(plans_path, plan_id)
    if pending_file is None:
        return False

    resolved_plan_id = pending_file.stem
    plan = read_plan(pending_file)
    tickets, split_artifacts = _resolve_plan_tickets(plans_path, resolved_plan_id, plan)
    _validate_gate_names(tickets, _load_gate_defaults(queue_path))

    # Write tickets to queue
    append_tickets(queue_path, tickets)

    # Move plan to approved
    approved_dir = plans_path / "approved"
    approved_dir.mkdir(exist_ok=True)
    _move_plan_artifacts_to_approved(pending_file, approved_dir, resolved_plan_id, split_artifacts)

    return True


def reject_plan(plans_path: Path, plan_id: str, reason: str) -> bool:
    """Move plan from pending to rejected with reason."""
    pending_file = _resolve_pending_plan_file(plans_path, plan_id)
    if pending_file is None:
        return False

    resolved_plan_id = pending_file.stem
    plan = read_plan(pending_file)
    plan["rejection_reason"] = reason
    plan["rejected_at"] = datetime.now().isoformat()

    # Move to rejected
    rejected_dir = plans_path / "rejected"
    rejected_dir.mkdir(exist_ok=True)
    rejected_file = rejected_dir / f"{resolved_plan_id}.yaml"
    with open(rejected_file, "w") as f:
        yaml.dump(plan, f, allow_unicode=True)

    _move_plan_artifacts_to_rejected(pending_file, rejected_dir, resolved_plan_id)

    pending_file.unlink()
    return True


def format_plan_summary(plan: dict) -> str:
    """Format a plan for approval review."""
    lines = [
        "Plan Ready for Approval",
        f"ID: {plan.get('id', 'unknown')}",
        f"Source: {plan.get('source', 'PRD')}",
        f"\nTickets ({len(plan.get('tickets', []))} total):",
    ]
    for ticket in plan.get("tickets", []):
        owner = ticket.get("owner", "?")
        goal = str(ticket.get("goal", ""))[:80].strip()
        lines.append(f"  {ticket.get('id', '?')} [{owner}] {goal}")

    lines.extend([
        "\nActions:",
        "  make approve           — start work",
        "  make reject R='reason' — revise plan",
    ])
    return "\n".join(lines)
