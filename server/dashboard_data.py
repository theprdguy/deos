"""Read-only ticket aggregation for the local dashboard."""
from __future__ import annotations

from pathlib import Path

from server.projects_registry import list_projects
from server.ssot import find_ticket, read_queue_with_archive

BOARD_STATUSES = (
    "todo",
    "doing",
    "code_ready",
    "needs_pm",
    "blocked",
    "parked",
    "done",
)
UNKNOWN_STATUS = "unknown"
DEFAULT_DONE_LIMIT = 30


def _queue_path(root: Path) -> Path:
    return root / "devos" / "tasks" / "QUEUE.yaml"


def _resolve_root(host: Path, repo_path: object) -> Path:
    root = Path(str(repo_path or ""))
    if root.is_absolute():
        return root
    return host / root


def _project_specs(host: Path) -> list[dict]:
    host = Path(host)
    specs = [{"name": "dev-os", "repo_path": str(host), "root": host}]
    for record in list_projects(host):
        repo_path = record.get("repo_path", "")
        specs.append(
            {
                "name": record.get("name", "?"),
                "repo_path": str(repo_path),
                "root": _resolve_root(host, repo_path),
            }
        )
    return specs


def _project_spec(host: Path, name: str) -> dict | None:
    for spec in _project_specs(host):
        if spec["name"] == name:
            return spec
    return None


def _read_project_tickets(spec: dict) -> list[dict]:
    queue_path = _queue_path(spec["root"])
    if not queue_path.is_file():
        raise FileNotFoundError(f"QUEUE.yaml not found: {queue_path}")
    return list(read_queue_with_archive(queue_path).get("tickets", []))


def _bucket_status(ticket: dict) -> str:
    status = ticket.get("status")
    if status in BOARD_STATUSES:
        return str(status)
    return UNKNOWN_STATUS


def _display_status(ticket: dict) -> str:
    status = ticket.get("status")
    if isinstance(status, str) and status.strip():
        return status
    return UNKNOWN_STATUS


def _empty_counts() -> dict:
    return {status: 0 for status in BOARD_STATUSES}


def _counts(tickets: list[dict]) -> dict:
    counts = _empty_counts()
    unknown = 0
    for ticket in tickets:
        bucket = _bucket_status(ticket)
        if bucket == UNKNOWN_STATUS:
            unknown += 1
        else:
            counts[bucket] += 1
    if unknown:
        counts[UNKNOWN_STATUS] = unknown
    return counts


def _goal_summary(ticket: dict) -> str:
    for line in str(ticket.get("goal") or "").splitlines():
        summary = line.strip()
        if summary:
            return summary
    return ""


def _card(ticket: dict) -> dict:
    return {
        "id": ticket.get("id"),
        "owner": ticket.get("owner"),
        "status": _display_status(ticket),
        "priority": ticket.get("priority"),
        "goal_summary": _goal_summary(ticket),
    }


def _error_summary(spec: dict, exc: Exception) -> dict:
    return {
        "name": spec["name"],
        "repo_path": spec["repo_path"],
        "ok": False,
        "error": str(exc) or exc.__class__.__name__,
        "counts": _empty_counts(),
        "total": 0,
    }


def list_dashboard_projects(host: Path) -> list[dict]:
    """Return project summaries for the host followed by registry projects."""
    rows: list[dict] = []
    for spec in _project_specs(Path(host)):
        try:
            tickets = _read_project_tickets(spec)
        except Exception as exc:
            rows.append(_error_summary(spec, exc))
            continue
        rows.append(
            {
                "name": spec["name"],
                "repo_path": spec["repo_path"],
                "ok": True,
                "error": None,
                "counts": _counts(tickets),
                "total": len(tickets),
            }
        )
    return rows


def load_project_board(host: Path, name: str, *, done_limit: int = DEFAULT_DONE_LIMIT) -> dict | None:
    """Return status-grouped dashboard cards for one project."""
    spec = _project_spec(Path(host), name)
    if spec is None:
        return None

    try:
        tickets = _read_project_tickets(spec)
    except Exception as exc:
        return {
            "name": spec["name"],
            "ok": False,
            "error": str(exc) or exc.__class__.__name__,
            "columns": [],
        }

    grouped = {status: [] for status in BOARD_STATUSES}
    unknown: list[dict] = []
    for ticket in tickets:
        card = _card(ticket)
        bucket = _bucket_status(ticket)
        if bucket == UNKNOWN_STATUS:
            unknown.append(card)
        else:
            grouped[bucket].append(card)

    columns: list[dict] = []
    limit = max(done_limit, 0)
    for status in BOARD_STATUSES:
        cards = grouped[status]
        column = {"status": status, "tickets": cards}
        if status == "done":
            omitted = max(len(cards) - limit, 0)
            column["done_truncated"] = omitted
            if omitted:
                column["tickets"] = cards[-limit:] if limit else []
        columns.append(column)
    if unknown:
        columns.append({"status": UNKNOWN_STATUS, "tickets": unknown})

    return {"name": spec["name"], "ok": True, "error": None, "columns": columns}


def load_ticket_detail(host: Path, name: str, ticket_id: str) -> dict | None:
    """Return a full ticket dict from QUEUE or ARCHIVE, or None when absent."""
    spec = _project_spec(Path(host), name)
    if spec is None:
        return None
    queue_path = _queue_path(spec["root"])
    if not queue_path.is_file():
        return None
    ticket, _source = find_ticket(queue_path, ticket_id)
    return ticket
