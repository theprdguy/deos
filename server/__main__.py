"""os2-server CLI entry point.

Usage:
    python3 -m server dispatch T-001
    python3 -m server dispatch-all
    python3 -m server approve [plan-id]
    python3 -m server reject "reason" [plan-id]
    python3 -m server status
    python3 -m server queue
    python3 -m server logs
    python3 -m server pending
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from server.approval import ApprovalManager
from server.config import get_paths, load_config
from server.dispatcher import Dispatcher
from server.ssot import format_logs_summary, format_queue_summary, format_status_summary

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("os2")
DEFAULT_LOG_FILE = ".os2-server.log"


def get_log_file_path(config: dict) -> str:
    """Return the configured server log file path with a safe fallback."""
    server_config = (config or {}).get("server") or {}
    return server_config.get("log_file") or DEFAULT_LOG_FILE


def main() -> None:
    config_path = Path("os2.yaml")
    if not config_path.exists():
        logger.error("os2.yaml not found. Run from project root.")
        sys.exit(1)

    config = load_config()
    paths = get_paths(config)

    args = sys.argv[1:]
    if not args:
        print(f"Log file: {get_log_file_path(config)}")
        print(__doc__)
        sys.exit(0)

    cmd = args[0]

    # Status queries (no LLM, no dispatcher needed)
    if cmd == "status":
        print(format_status_summary(paths["devos"]))
        return
    if cmd == "queue":
        print(format_queue_summary(paths["queue"]))
        return
    if cmd == "logs":
        print(format_logs_summary(paths["logs"]))
        return
    if cmd == "pending":
        approval = ApprovalManager(paths["plans"], paths["queue"])
        print(approval.format_pending_summary())
        return

    # Approval workflow
    if cmd == "approve":
        approval = ApprovalManager(paths["plans"], paths["queue"])
        plan_id = args[1] if len(args) > 1 else None
        success, msg = approval.approve(plan_id)
        print(msg)
        if success:
            dispatcher = Dispatcher(config=config, paths=paths)
            results = dispatcher.dispatch_all_todo()
            for tid, msg in results:
                print(f"  {tid}: {msg}")
        return

    if cmd == "reject":
        if len(args) < 2:
            print("Usage: python3 -m server reject 'reason' [plan-id]")
            sys.exit(1)
        approval = ApprovalManager(paths["plans"], paths["queue"])
        reason = args[1]
        plan_id = args[2] if len(args) > 2 else None
        success, msg = approval.reject(reason, plan_id)
        print(msg)
        return

    # Dispatch
    if cmd == "dispatch":
        if len(args) < 2:
            print("Usage: python3 -m server dispatch T-001")
            sys.exit(1)
        dispatcher = Dispatcher(config=config, paths=paths)
        ticket_id = args[1]
        success, msg = dispatcher.dispatch(ticket_id)
        print(msg)
        dispatcher.wait_all()
        return

    if cmd == "dispatch-all":
        dispatcher = Dispatcher(config=config, paths=paths)
        results = dispatcher.dispatch_all_todo()
        if not results:
            print("No todo tickets to dispatch.")
        for tid, msg in results:
            print(f"  {tid}: {msg}")
        return

    print(f"Unknown command: {cmd}")
    print(__doc__)
    sys.exit(1)


if __name__ == "__main__":
    main()
