"""Repository-level conftest.

Ensures host tests resolve `from server import ...` when pytest is invoked
without explicit PYTHONPATH (e.g., dispatch gate, fresh CI shell, IDE runner).

The host repo also contains independent consumer repos under projects/. If a
consumer without its own pytest root marker runs bare `pytest`, pytest discovers
this host config. In that case this conftest must stand down: host sys.path
cleanup and host package guards are only valid for host collection targets.
"""
from __future__ import annotations

import sys
from pathlib import Path

_repo_root = Path(__file__).resolve().parent
_projects_root = _repo_root / "projects"

_PYTEST_DEFAULT_NORECURSEDIRS = [
    "*.egg",
    ".*",
    "_darcs",
    "build",
    "CVS",
    "dist",
    "node_modules",
    "venv",
    "{arch}",
]


def _safe_resolve(path: str | Path) -> Path | None:
    try:
        return Path(path).resolve()
    except (OSError, RuntimeError, TypeError):
        return None


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _sys_path_entry_path(entry: str) -> Path | None:
    if entry == "":
        return _safe_resolve(Path.cwd())
    return _safe_resolve(entry)


def _is_sys_path_entry_under(entry: str, parent: Path) -> bool:
    path = _sys_path_entry_path(entry)
    return path is not None and _is_relative_to(path, parent)


def _is_sys_path_entry(entry: str, target: Path) -> bool:
    path = _sys_path_entry_path(entry)
    return path == target


def _activate_host_sys_path() -> None:
    """Put host root first and remove stale projects/ entries for host tests."""
    sys.path = [p for p in sys.path if not _is_sys_path_entry_under(p, _projects_root)]

    repo_root_str = str(_repo_root)
    sys.path = [p for p in sys.path if not _is_sys_path_entry(p, _repo_root)]
    sys.path.insert(0, repo_root_str)


def _disable_host_surface_for_project_collection(config) -> None:
    """Undo host-only config effects when pytest was invoked inside projects/."""
    sys.path = [p for p in sys.path if not _is_sys_path_entry(p, _repo_root)]

    cache = getattr(config, "_inicache", None)
    if isinstance(cache, dict):
        cache["testpaths"] = []
        cache["norecursedirs"] = list(_PYTEST_DEFAULT_NORECURSEDIRS)

    inicfg = getattr(config, "inicfg", None)
    if isinstance(inicfg, dict):
        inicfg["testpaths"] = ""
        inicfg["norecursedirs"] = "\n".join(_PYTEST_DEFAULT_NORECURSEDIRS)


def _invocation_dir(config) -> Path:
    invocation_params = getattr(config, "invocation_params", None)
    value = getattr(invocation_params, "dir", None)
    return _safe_resolve(value) if value is not None else Path.cwd().resolve()


def _invocation_args(config) -> tuple[str, ...]:
    invocation_params = getattr(config, "invocation_params", None)
    args = getattr(invocation_params, "args", None)
    if args is None:
        args = getattr(config, "args", ())
    return tuple(str(arg) for arg in (args or ()))


def _collection_arg_paths(config, invocation_dir: Path) -> list[Path]:
    paths: list[Path] = []
    for arg in _invocation_args(config):
        if arg.startswith("-"):
            continue
        raw_path = arg.split("::", 1)[0]
        if not raw_path:
            continue
        path = Path(raw_path)
        if not path.is_absolute():
            path = invocation_dir / path
        resolved = _safe_resolve(path)
        if resolved is not None:
            paths.append(resolved)
    return paths


def _is_projects_collection(config) -> bool:
    invocation_dir = _invocation_dir(config)
    if _is_relative_to(invocation_dir, _projects_root):
        return True
    return any(
        _is_relative_to(path, _projects_root)
        for path in _collection_arg_paths(config, invocation_dir)
    )


def pytest_configure(config):
    """Regression guard: verify that 'server' resolves to the host repo root,
    not to any projects/ sub-tree.

    This runs once per session and fails early (before any test is collected)
    if the sys.path ordering is wrong — giving a clear diagnostic rather than
    mysterious ImportErrors deep in the test run.
    """
    if _is_projects_collection(config):
        _disable_host_surface_for_project_collection(config)
        return

    _activate_host_sys_path()

    import importlib.util
    spec = importlib.util.find_spec("server")
    if spec is None:
        raise RuntimeError(
            "pytest_configure: 'server' package not found on sys.path. "
            f"sys.path={sys.path!r}"
        )
    if spec.origin is None:
        locations = [
            str(_safe_resolve(location) or location)
            for location in (spec.submodule_search_locations or ())
        ]
        raise RuntimeError(
            "pytest_configure: 'server' resolves as a namespace package; "
            "spec.origin is None. Expected the concrete host package at "
            f"{_repo_root / 'server'}. locations={locations!r}; "
            f"sys.path={sys.path!r}"
        )
    server_origin = Path(spec.origin).resolve()
    if not server_origin.is_relative_to(_repo_root):
        raise RuntimeError(
            f"pytest_configure: 'server' resolves to {server_origin}, "
            f"which is OUTSIDE the host repo root {_repo_root}. "
            "A projects/ sub-tree is shadowing the host server package. "
            f"sys.path={sys.path!r}"
        )
    # Confirm it is not inside projects/
    if server_origin.is_relative_to(_projects_root):
        raise RuntimeError(
            f"pytest_configure: 'server' resolves to {server_origin}, "
            f"which is inside projects/. "
            "This would cause collection ImportErrors for host tests. "
            f"sys.path={sys.path!r}"
        )
