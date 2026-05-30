#!/usr/bin/env bash

set -euo pipefail

# Cross-test author map. Edit these grep-friendly lines if local git author
# names/emails change; matching is case-insensitive substring matching.
# AUTHOR_MAP_CLAUDE2="Claude|claude2"
# AUTHOR_MAP_CODEX="codex|Codex"
# AUTHOR_MAP_CLAUDE1="hoanshin|Hoan Shin"

printf '[6/6] cross-test\n'
printf 'author map: CLAUDE2=(Claude|claude2), CODEX=(codex|Codex), CLAUDE1=(hoanshin|Hoan Shin)\n'

if [ ! -f "devos/tasks/QUEUE.yaml" ]; then
  echo "skipped (queue missing)"
  exit 0
fi

python3 - "$@" <<'PY'
from __future__ import annotations

import sys
import subprocess
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    print("skipped (pyyaml missing)")
    raise SystemExit(0)

AUTHOR_MAP = {
    "CLAUDE2": ["Claude", "claude2"],
    "CODEX": ["codex", "Codex"],
    "CLAUDE1": ["hoanshin", "Hoan Shin"],
}


def load_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text()) or {}
    except Exception:
        return {}


def iter_ticket_dicts(value: Any) -> list[dict[str, Any]]:
    tickets: list[dict[str, Any]] = []
    if isinstance(value, dict):
        nested = value.get("tickets")
        if isinstance(nested, list):
            tickets.extend(item for item in nested if isinstance(item, dict))
        for child in value.values():
            tickets.extend(iter_ticket_dicts(child))
    elif isinstance(value, list):
        for child in value:
            tickets.extend(iter_ticket_dicts(child))
    return tickets


def find_ticket(ticket_id: str) -> dict[str, Any] | None:
    queue = load_yaml(Path("devos/tasks/QUEUE.yaml"))
    for ticket in iter_ticket_dicts(queue):
        if str(ticket.get("id", "")).strip() == ticket_id:
            return ticket

    approved_dir = Path("devos/plans/approved")
    for path in sorted(approved_dir.glob("*.yaml")) + sorted(approved_dir.glob("*.yml")):
        for ticket in iter_ticket_dicts(load_yaml(path)):
            if str(ticket.get("id", "")).strip() == ticket_id:
                return ticket
    return None


def active_ticket_ids() -> list[str]:
    queue = load_yaml(Path("devos/tasks/QUEUE.yaml"))
    ids: list[str] = []
    for ticket in iter_ticket_dicts(queue):
        if str(ticket.get("status", "")).strip() == "doing":
            ticket_id = str(ticket.get("id", "")).strip()
            if ticket_id:
                ids.append(ticket_id)
    return ids


def is_test_file(path_text: str) -> bool:
    path = Path(path_text)
    normalized = path.as_posix()
    name = path.name
    return (
        normalized.startswith("tests/")
        or "_test." in name
        or ".test." in name
        or ".spec." in name
    )


def ticket_test_files(ticket: dict[str, Any]) -> list[str]:
    files = ticket.get("files") or []
    if isinstance(files, str):
        files = [files]
    if not isinstance(files, list):
        return []
    return [str(path).strip() for path in files if is_test_file(str(path).strip())]


def first_added_author(path_text: str) -> str:
    proc = subprocess.run(
        [
            "git",
            "log",
            "--reverse",
            "--diff-filter=A",
            "--format=%an <%ae>",
            "--",
            path_text,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    for line in proc.stdout.splitlines():
        author = line.strip()
        if author:
            return author
    return ""


def author_matches(owner: str, author: str) -> bool:
    patterns = AUTHOR_MAP.get(owner.upper())
    if not patterns:
        return True
    author_lower = author.lower()
    return any(pattern.lower() in author_lower for pattern in patterns)


def check_ticket(ticket_id: str) -> bool:
    ticket = find_ticket(ticket_id)
    if ticket is None:
        print(f"{ticket_id}: skipped (ticket not found)")
        return True

    if "test_owner" not in ticket:
        print(f"{ticket_id}: skipped (no test_owner)")
        return True

    test_owner = str(ticket.get("test_owner") or "").strip()
    if not test_owner:
        print(f"{ticket_id}: skipped (no test_owner)")
        return True

    test_files = ticket_test_files(ticket)
    if not test_files:
        print(f"{ticket_id}: skipped (no test files)")
        return True

    added_authors = [(path, first_added_author(path)) for path in test_files]
    added_authors = [(path, author) for path, author in added_authors if author]
    if not added_authors:
        print(f"{ticket_id}: skipped (no test first-commit)")
        return True

    for path, author in added_authors:
        if not author_matches(test_owner, author):
            print(
                f"cross-test policy violation: {ticket_id} expected test_owner={test_owner} "
                f"but first-commit author={author}",
                file=sys.stderr,
            )
            return False
        print(f"{ticket_id}: OK {path} first-commit author={author}")

    return True


ticket_ids = [arg.strip() for arg in sys.argv[1:] if arg.strip()]
if not ticket_ids:
    ticket_ids = active_ticket_ids()

if not ticket_ids:
    print("OK cross-test: no active ticket")
    raise SystemExit(0)

failed = False
for ticket_id in ticket_ids:
    if not check_ticket(ticket_id):
        failed = True

raise SystemExit(1 if failed else 0)
PY
