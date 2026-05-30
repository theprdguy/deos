"""Read-oriented projects registry for the host OS (replaces consumer_sync registry).

Tracks which projects the host knows about. Records live at
`devos/projects/<name>.md` with YAML frontmatter (name/repo_path/status).
No sync/apply logic — the host reads project state; it never pushes into projects.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


class RegistryError(RuntimeError):
    """Raised on invalid registry operations."""


def _registry_dir(host: Path) -> Path:
    return Path(host) / "devos" / "projects"


def register_project(
    host: Path, name: str, repo_path: str, *, status: str = "active"
) -> dict:
    """Create/overwrite a registry record for `name`. Returns the record dict."""
    if not _NAME_RE.fullmatch(name) or name in (".", ".."):
        raise RegistryError(f"invalid project name: {name!r}")
    record = {"name": name, "repo_path": repo_path, "status": status}
    reg = _registry_dir(host)
    reg.mkdir(parents=True, exist_ok=True)
    text = (
        "---\n"
        + yaml.safe_dump(record, allow_unicode=True, sort_keys=False)
        + "---\n"
        + f"# Project: {name}\n\nTracked by host OS projects registry (read-only).\n"
    )
    (reg / f"{name}.md").write_text(text, encoding="utf-8")
    return record


def list_projects(host: Path) -> list[dict]:
    """Return registered project records, sorted by file name."""
    reg = _registry_dir(host)
    if not reg.is_dir():
        return []
    out: list[dict] = []
    for path in sorted(reg.glob("*.md")):
        content = path.read_text(encoding="utf-8")
        if not content.startswith("---\n"):
            continue
        end = content.find("\n---\n", 4)
        if end == -1:
            continue
        data = yaml.safe_load(content[4:end]) or {}
        if isinstance(data, dict):  # ignore malformed/hand-edited frontmatter
            out.append(data)
    return out


# ── CLI handlers (registered by server/cli.py) ───────────────────────────────

def handle_register(args) -> int:
    from server.config import host_root
    try:
        rec = register_project(host_root(), args.name, args.repo_path, status=args.status)
    except RegistryError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"registered {rec['name']} -> {rec['repo_path']}")
    return 0


def handle_projects(args) -> int:
    from server.config import host_root
    rows = list_projects(host_root())
    if not rows:
        print("no projects registered")
        return 0
    print("name\tstatus\trepo_path")
    for r in rows:
        print(f"{r.get('name')}\t{r.get('status', '')}\t{r.get('repo_path', '')}")
    return 0
