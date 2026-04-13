"""Configuration loader for os2-server."""
from __future__ import annotations

from pathlib import Path

import yaml


def load_config(config_path: str = "os2.yaml") -> dict:
    """Load os2.yaml configuration."""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with open(path) as f:
        return yaml.safe_load(f)


def get_paths(config: dict) -> dict:
    """Get key file paths from config."""
    root = Path(config.get("project_root", "."))
    return {
        "root": root,
        "devos": root / config.get("devos_dir", "devos"),
        "queue": root / config.get("queue_file", "devos/tasks/QUEUE.yaml"),
        "plans": root / config.get("plans_dir", "devos/plans"),
        "logs": root / config.get("logs_dir", "devos/logs"),
    }
