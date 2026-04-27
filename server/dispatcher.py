"""Multi-agent dispatcher for os2-server.

Dispatches Claude 2, Codex, and Gemini for ticket execution.
Runs gate pipelines (tests, review) after completion.
Supports auto-retry on gate failure.
"""
from __future__ import annotations

import asyncio
import copy
import logging
import os
import re
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path

from .ssot import (
    TicketResumeError,
    ValidationError,
    block_ticket,
    get_recent_logs,
    read_queue,
    resume_blocked_ticket,
    update_ticket_fields,
    update_ticket_status,
)

logger = logging.getLogger(__name__)
DISPATCH_OUTPUT_TAIL_LINES = 30
QUOTA_EXHAUSTED_PATTERN = re.compile(
    r"usage limit|rate limit|quota exceeded|try again at \d+:\d+\s*(?:AM|PM)",
    re.IGNORECASE,
)
QUOTA_RESET_PATTERN = re.compile(
    r"try again at (?P<reset>\d+:\d+\s*(?:AM|PM))",
    re.IGNORECASE,
)
CLAUDE1_INTERACTIVE_MESSAGE = (
    "CLAUDE1 ticket {ticket_id} must be executed interactively (see CLAUDE.md)"
)
CLAUDE1_DISPATCH_ALL_SKIP_MESSAGE = (
    "Skipped CLAUDE1 ticket {ticket_id} — execute interactively"
)


class Dispatcher:
    """Dispatches builder agents for ticket execution."""

    def __init__(self, config: dict, paths: dict, notify_callback=None):
        """
        notify_callback: async callable(message: str) for completion notifications.
        """
        self.config = config
        self.paths = paths
        self.notify = notify_callback
        self.agent_configs = config.get("agents", {})
        self._running: dict[str, subprocess.Popen] = {}  # ticket_id -> process
        self._threads: dict[str, threading.Thread] = {}  # ticket_id -> thread
        self._preflight_cache: dict[str, tuple[bool, str]] = {}
        self._dispatch_failures: dict[str, str] = {}
        self._dispatch_start_failed = False
        self._quota_exhausted = False
        self._quota_reset: str | None = None
        self._state_lock = threading.RLock()

    # ── Public API ──────────────────────────────────────────────────────────

    def dispatch(self, ticket_id: str, *, fatal_status_mismatch: bool = True) -> tuple[bool, str]:
        """
        Dispatch a single ticket to its assigned agent.
        Returns (success, message).
        """
        with self._state_lock:
            try:
                data = read_queue(self.paths["queue"])
            except ValidationError as exc:
                return self._dispatch_error(f"ValidationError: {exc}")
            ticket = next((t for t in data.get("tickets", []) if t.get("id") == ticket_id), None)

            if not ticket:
                return self._dispatch_error(f"Ticket `{ticket_id}` not found in queue.")

            if self._quota_exhausted:
                return self._dispatch_error(self._format_quota_stop_message(), fatal=False)

            status = ticket.get("status")
            if status not in ("todo",):
                return self._dispatch_error(
                    f"Ticket `{ticket_id}` is `{status}`, not `todo`. Cannot dispatch.",
                    fatal=fatal_status_mismatch,
                )

            owner = ticket.get("owner")
            target_owner = ticket.get("impl_owner") or owner
            if self._is_claude1_interactive_ticket(ticket):
                msg = CLAUDE1_INTERACTIVE_MESSAGE.format(ticket_id=ticket_id)
                print(msg, file=sys.stderr)
                return self._dispatch_error(msg)
            if target_owner not in self.agent_configs:
                return self._dispatch_error(f"Unknown owner `{target_owner}` for ticket `{ticket_id}`.")

            dispatch_snapshot_sha = self._capture_dispatch_snapshot(ticket_id)
            if dispatch_snapshot_sha is None:
                return self._dispatch_error(
                    f"Could not capture dispatch snapshot for ticket `{ticket_id}`."
                )

            # Fallback: if agent not available, use fallback agent
            resolved_owner, fallback_reason = self._resolve_agent(target_owner)

            # Check dependencies
            deps = ticket.get("deps", [])
            if deps:
                blocked_by = self._check_deps(data, deps)
                if blocked_by:
                    return self._dispatch_error(
                        f"Ticket `{ticket_id}` blocked by: {', '.join(blocked_by)}",
                        fatal=False,
                    )

            # Check concurrent limit
            max_concurrent = self.config.get("dispatch", {}).get("max_concurrent", 2)
            if len(self._running) >= max_concurrent:
                return self._dispatch_error(
                    f"At capacity ({max_concurrent} agents running). Wait for completion.",
                    fatal=False,
                )

            # Check scope overlap (if scope_check enabled)
            if self.config.get("dispatch", {}).get("scope_check", True):
                conflict = self._check_scope_conflict(ticket, data)
                if conflict:
                    return self._dispatch_error(
                        f"Ticket `{ticket_id}` file scope conflicts with running ticket `{conflict}`.",
                        fatal=False,
                    )

            try:
                self._resolve_gates(ticket)
            except ValidationError as exc:
                return self._dispatch_error(f"ValidationError: {exc}")

            preflight_ok, preflight_msg = self._run_preflight(resolved_owner)
            if not preflight_ok:
                print(preflight_msg, file=sys.stderr)
                return self._dispatch_error(preflight_msg)

            if fallback_reason:
                update_ticket_fields(
                    self.paths["queue"],
                    ticket_id,
                    {
                        "_dispatch_owner": resolved_owner,
                        "_original_impl_owner": ticket.get("_original_impl_owner", target_owner),
                        "_fallback_reason": fallback_reason,
                    },
                )

            # Dispatch
            update_ticket_status(self.paths["queue"], ticket_id, "doing")
            runtime_ticket = self._build_runtime_ticket(ticket, resolved_owner)
            thread = threading.Thread(
                target=self._run_agent,
                args=(runtime_ticket, dispatch_snapshot_sha),
                daemon=False,
            )
            self._running[ticket_id] = None  # Mark as running before releasing dispatch lock.
            self._threads[ticket_id] = thread
            thread.start()
            return True, f"Dispatched `{ticket_id}` to {resolved_owner}."

    def dispatch_all_todo(self) -> list[tuple[str, str]]:
        """
        Dispatch all tickets that are todo (deps satisfied).
        Blocks until all dispatched agents finish (required for CLI mode).
        Returns list of (ticket_id, message).
        """
        try:
            data = read_queue(self.paths["queue"])
        except ValidationError as exc:
            msg = f"ValidationError: {exc}"
            print(msg, file=sys.stderr)
            self._dispatch_error(msg)
            self.wait_all()
            return [("QUEUE", msg)]

        preflight_ok, preflight_msg = self._run_dispatch_all_preflight(data)
        if not preflight_ok:
            print(preflight_msg, file=sys.stderr)
            self._dispatch_error(preflight_msg)
            self.wait_all()
            return [("PREFLIGHT", preflight_msg)]

        results = []
        for ticket in data.get("tickets", []):
            if ticket.get("status") != "todo":
                continue
            if self._quota_exhausted:
                results.append((ticket["id"], self._format_quota_stop_message()))
                break
            if self._is_claude1_interactive_ticket(ticket):
                results.append((ticket["id"], self._format_claude1_dispatch_all_skip(ticket)))
                continue
            ok, msg = self.dispatch(ticket["id"])
            results.append((ticket["id"], msg))
        self.wait_all()
        return results

    def resume(self, ticket_id: str) -> tuple[bool, str]:
        """Resume a blocked ticket, then immediately dispatch it."""
        try:
            resume_blocked_ticket(self.paths["queue"], ticket_id)
        except TicketResumeError as exc:
            return self._dispatch_error(str(exc))

        print(
            f"Resumed `{ticket_id}`. Confirm the blocked cause is resolved; "
            "dispatch may fail again for the same reason."
        )
        return self.dispatch(ticket_id)

    def wait_all(self) -> None:
        """Block until all running agent threads have finished."""
        while True:
            with self._state_lock:
                threads = list(self._threads.values())
            if not threads:
                with self._state_lock:
                    failures = dict(self._dispatch_failures)
                    self._dispatch_failures.clear()
                    dispatch_start_failed = self._dispatch_start_failed
                    self._dispatch_start_failed = False
                if failures:
                    for message in failures.values():
                        print(message)
                    raise SystemExit(1)
                if dispatch_start_failed:
                    raise SystemExit(1)
                return
            for thread in threads:
                thread.join()

    def get_running(self) -> list[str]:
        """Return list of currently running ticket IDs."""
        with self._state_lock:
            return list(self._running.keys())

    # ── Internal ─────────────────────────────────────────────────────────────

    def _dispatch_error(self, message: str, *, fatal: bool = True) -> tuple[bool, str]:
        """Return a dispatch failure, recording fatal start failures for CLI exit."""
        if fatal:
            with self._state_lock:
                self._dispatch_start_failed = True
        return False, message

    def _is_claude1_interactive_ticket(self, ticket: dict) -> bool:
        """Return whether a ticket is owned by CLAUDE1 and must not be subprocess-dispatched."""
        return ticket.get("owner") == "CLAUDE1"

    def _format_claude1_dispatch_all_skip(self, ticket: dict) -> str:
        """Return the dispatch-all reminder for a CLAUDE1-owned ticket."""
        return CLAUDE1_DISPATCH_ALL_SKIP_MESSAGE.format(ticket_id=ticket.get("id"))

    def _detect_quota_reset(self, stderr: str) -> str | None:
        """Return the quota reset time when stderr contains a Codex quota error."""
        if not QUOTA_EXHAUSTED_PATTERN.search(stderr or ""):
            return None
        reset_match = QUOTA_RESET_PATTERN.search(stderr or "")
        if not reset_match:
            return "unknown"
        return re.sub(r"\s+", " ", reset_match.group("reset").strip()).upper()

    def _format_quota_stop_message(self, reset: str | None = None) -> str:
        """Return the standardized quota exhaustion message for CLI output."""
        reset_value = reset if reset is not None else self._quota_reset
        if reset_value and reset_value != "unknown":
            return f"Codex quota exhausted, reset at {reset_value}"
        return "Codex quota exhausted, reset unknown"

    def _format_quota_blocked_reason(self, reason: str, reset: str) -> str:
        """Return the blocked reason prefix while preserving the original reason."""
        if reset == "unknown":
            return f"quota_exhausted (reset unknown); {reason}"
        return f"quota_exhausted: {reset}; {reason}"

    def _record_quota_exhausted(self, reset: str) -> str:
        """Remember quota exhaustion and emit the standardized stderr notice."""
        with self._state_lock:
            self._quota_exhausted = True
            self._quota_reset = reset
        message = self._format_quota_stop_message(reset)
        print(message, file=sys.stderr)
        return message

    def _is_agent_available(self, agent_name: str) -> bool:
        """Check if an agent is configured and available to run."""
        agent_cfg = self.agent_configs.get(agent_name, {})
        config_dir = agent_cfg.get("config_dir")
        if config_dir:
            # Agent requires a config directory (e.g. .claude-b) — check credentials exist
            creds = Path(config_dir) / ".claude.json"
            if not creds.exists():
                logger.info(f"{agent_name} not available: {creds} not found")
                return False
        return True

    def _resolve_agent(self, owner: str) -> tuple[str, str | None]:
        """Resolve agent, returning (owner, fallback_reason)."""
        if self._is_agent_available(owner):
            return owner, None
        fallback = self.agent_configs.get(owner, {}).get("fallback")
        if fallback:
            reason = f"{owner} unavailable"
            logger.warning(f"{owner} not available — falling back to {fallback}")
            return fallback, reason
        return owner, None

    def _run_preflight(self, owner: str) -> tuple[bool, str]:
        """Run target-agent preflight before mutating ticket status."""
        if owner in self._preflight_cache:
            return self._preflight_cache[owner]

        scripts = {
            "CODEX": "scripts/preflight-codex.sh",
            "CLAUDE2": "scripts/preflight-claude2.sh",
        }
        script = scripts.get(owner)
        if not script:
            result = (True, "preflight skipped")
            self._preflight_cache[owner] = result
            return result

        script_path = self.paths["root"] / script
        try:
            result = subprocess.run(
                ["bash", str(script_path)],
                capture_output=True,
                text=True,
                timeout=5,
                cwd=str(self.paths["root"]),
            )
        except subprocess.TimeoutExpired:
            result = (False, f"[preflight] {owner.lower()} preflight timed out")
            self._preflight_cache[owner] = result
            return result

        if result.returncode == 0:
            preflight_result = (True, "preflight passed")
            self._preflight_cache[owner] = preflight_result
            return preflight_result

        output = (result.stderr or result.stdout or f"[preflight] {owner.lower()} preflight failed").strip()
        preflight_result = (False, output)
        self._preflight_cache[owner] = preflight_result
        return preflight_result

    def _run_dispatch_all_preflight(self, data: dict) -> tuple[bool, str]:
        """Preflight each eligible dispatch target once before dispatch-all starts."""
        owners: list[str] = []
        for ticket in data.get("tickets", []):
            if ticket.get("status") != "todo":
                continue
            if self._is_claude1_interactive_ticket(ticket):
                continue
            if self._check_deps(data, ticket.get("deps", [])):
                continue

            target_owner = ticket.get("impl_owner") or ticket.get("owner")
            if target_owner not in self.agent_configs:
                return False, f"Unknown owner `{target_owner}` for ticket `{ticket.get('id')}`."

            resolved_owner, _fallback_reason = self._resolve_agent(target_owner)
            if resolved_owner not in owners:
                owners.append(resolved_owner)

        for owner in owners:
            ok, msg = self._run_preflight(owner)
            if not ok:
                return False, msg

        return True, "preflight passed"

    def _capture_dispatch_snapshot(self, ticket_id: str) -> str | None:
        """Return the HEAD SHA used as this dispatch's diff baseline."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(self.paths["root"]),
            )
        except Exception as exc:
            logger.error("Could not capture dispatch snapshot for %s: %s", ticket_id, exc)
            return None

        if result.returncode != 0:
            error_output = (result.stderr or result.stdout or "git rev-parse failed").strip()
            logger.error("Could not capture dispatch snapshot for %s: %s", ticket_id, error_output)
            return None

        snapshot_sha = result.stdout.strip()
        if not snapshot_sha:
            logger.error("Could not capture dispatch snapshot for %s: empty HEAD SHA", ticket_id)
            return None
        return snapshot_sha

    def _check_deps(self, data: dict, deps: list[str]) -> list[str]:
        """Return list of unfinished dependency ticket IDs."""
        tickets_by_id = {t["id"]: t for t in data.get("tickets", [])}
        return [d for d in deps if tickets_by_id.get(d, {}).get("status") != "done"]

    def _check_scope_conflict(self, ticket: dict, data: dict) -> str | None:
        """Return conflicting ticket_id if file scope overlaps with a running ticket."""
        my_files = set(ticket.get("files", []))
        for running_id in list(self._running):
            running_ticket = next(
                (t for t in data.get("tickets", []) if t.get("id") == running_id), None
            )
            if not running_ticket:
                continue
            their_files = set(running_ticket.get("files", []))
            if my_files & their_files:
                return running_id
        return None

    def _build_runtime_ticket(self, ticket: dict, owner: str) -> dict:
        """Return an execution-local ticket copy with the resolved owner."""
        runtime_ticket = copy.deepcopy(ticket)
        runtime_ticket["owner"] = owner
        return runtime_ticket

    def _auto_chain_enabled(self) -> bool:
        """Return whether post-completion dispatch chaining is enabled."""
        return bool(self.config.get("dispatch", {}).get("auto_chain", False))

    def _dispatch_auto_chain_todo(self) -> list[tuple[str, str]]:
        """
        Dispatch todo tickets after a completion when auto_chain is enabled.

        This re-scans the queue so downstream tickets unlocked by a `done` status,
        and tickets previously skipped due to capacity, can start without manual re-run.
        """
        if not self._auto_chain_enabled():
            return []

        try:
            with self._state_lock:
                data = read_queue(self.paths["queue"])
        except ValidationError as exc:
            return [("QUEUE", f"ValidationError: {exc}")]
        results: list[tuple[str, str]] = []
        for ticket in data.get("tickets", []):
            if ticket.get("status") != "todo":
                continue
            if self._quota_exhausted:
                break
            if self._is_claude1_interactive_ticket(ticket):
                results.append((ticket["id"], self._format_claude1_dispatch_all_skip(ticket)))
                continue
            if self._check_deps(data, ticket.get("deps", [])):
                continue

            ok, msg = self.dispatch(ticket["id"], fatal_status_mismatch=False)
            results.append((ticket["id"], msg))
            if "At capacity" in msg:
                break

        return results

    def _run_agent(self, ticket: dict, dispatch_snapshot_sha: str) -> None:
        """Run an agent for a ticket in a background thread."""
        ticket_id = ticket["id"]
        owner = ticket["owner"]
        agent_cfg = self.agent_configs.get(owner, {})
        mode = agent_cfg.get("mode", "subprocess")
        completed_done = False
        auto_chain_results: list[tuple[str, str]] = []

        logger.info(f"Starting {owner} for {ticket_id} (mode: {mode})")

        try:
            if mode in ("subprocess", "pipe"):
                success, failure = self._run_subprocess(ticket, agent_cfg)
            else:
                logger.error(f"Unknown mode {mode} for {owner}")
                success = False
                failure = {"reason": f"unknown mode {mode}"}

            if not success:
                failure_msg = self._handle_dispatch_failure(ticket, owner, failure)
                log_summary = self._get_agent_log(owner, ticket_id)
                msg = f"{failure_msg}\n{log_summary}".strip()
                if self.notify:
                    asyncio.run(self._send_notify(msg))
                return

            no_diff_failure = self._detect_no_ticket_file_diff(
                ticket,
                failure,
                dispatch_snapshot_sha,
            )
            if no_diff_failure:
                failure_msg = self._handle_dispatch_failure(ticket, owner, no_diff_failure)
                log_summary = self._get_agent_log(owner, ticket_id)
                msg = f"{failure_msg}\n{log_summary}".strip()
                if self.notify:
                    asyncio.run(self._send_notify(msg))
                return

            # Agent succeeded — run gate pipeline
            gates_passed, gate_msg = self._run_gates(ticket, dispatch_snapshot_sha)

            if gates_passed:
                with self._state_lock:
                    update_ticket_status(self.paths["queue"], ticket_id, "done")
                completed_done = True
                log_summary = self._get_agent_log(owner, ticket_id)
                msg = f"[DONE] {ticket_id} completed by {owner} (gates passed)\n{log_summary}"
            else:
                # Gates failed — attempt retry
                logger.warning(f"Gates failed for {ticket_id}: {gate_msg}")
                retry_success = self._attempt_retry(ticket, gate_msg, dispatch_snapshot_sha)

                if retry_success:
                    # Re-run gates after retry
                    gates_passed_2, gate_msg_2 = self._run_gates(ticket, dispatch_snapshot_sha)
                    if gates_passed_2:
                        with self._state_lock:
                            update_ticket_status(self.paths["queue"], ticket_id, "done")
                        completed_done = True
                        msg = f"[DONE] {ticket_id} completed by {owner} (passed after retry)\n{gate_msg_2}"
                    else:
                        with self._state_lock:
                            update_ticket_status(self.paths["queue"], ticket_id, "blocked")
                        msg = f"[BLOCKED] {ticket_id} gates still failing after retry: {gate_msg_2}"
                else:
                    with self._state_lock:
                        update_ticket_status(self.paths["queue"], ticket_id, "blocked")
                    msg = f"[BLOCKED] {ticket_id} gates failed: {gate_msg}"

            if self.notify:
                asyncio.run(self._send_notify(msg))

        except Exception as e:
            logger.exception(f"Error running {owner} for {ticket_id}: {e}")
            self._handle_dispatch_failure(
                ticket,
                owner,
                {
                    "reason": f"dispatcher error: {e}",
                    "stdout": "",
                    "stderr": "",
                    "returncode": None,
                },
            )
            if self.notify:
                asyncio.run(self._send_notify(f"❌ `{ticket_id}` error: {e}"))
        finally:
            with self._state_lock:
                self._running.pop(ticket_id, None)
                self._threads.pop(ticket_id, None)
            if completed_done:
                auto_chain_results = self._dispatch_auto_chain_todo()
                if auto_chain_results:
                    auto_chain_lines = "\n".join(
                        f"- {downstream_id}: {downstream_msg}"
                        for downstream_id, downstream_msg in auto_chain_results
                    )
                    logger.info(f"Auto-chain results after {ticket_id}:\n{auto_chain_lines}")

    def _build_prompt(self, ticket: dict) -> str:
        """Build the prompt string for an agent.

        Note: Agent instructions (CLAUDE.md) are loaded automatically by
        claude -p via CLAUDE_CONFIG_DIR. We only pass the ticket here.
        """
        return f"""Work on this ticket:

```yaml
{self._ticket_to_yaml(ticket)}
```

After completing:
1. Run the verify command in the ticket
2. Write a session log to devos/logs/
3. Output the 4-line handoff format
"""

    def _ticket_to_yaml(self, ticket: dict) -> str:
        import yaml
        return yaml.dump(ticket, allow_unicode=True)

    def _tail_lines(self, text: str, limit: int = DISPATCH_OUTPUT_TAIL_LINES) -> str:
        """Return the last non-empty output lines for immediate failure summaries."""
        lines = (text or "").splitlines()
        return "\n".join(lines[-limit:])

    def _relative_log_path(self, path: Path) -> str:
        """Return a project-relative path when possible."""
        try:
            return str(path.relative_to(self.paths["root"]))
        except ValueError:
            return str(path)

    def _write_dispatch_failure_log(
        self,
        ticket_id: str,
        owner: str,
        reason: str,
        stdout: str,
        stderr: str,
        returncode: int | None,
    ) -> str:
        """Persist full subprocess output for a failed dispatch."""
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        log_dir = self.paths["logs"] / "dispatch"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"{ticket_id}-{timestamp}.log"
        log_file.write_text(
            "\n".join(
                [
                    f"ticket: {ticket_id}",
                    f"owner: {owner}",
                    f"returncode: {returncode}",
                    f"reason: {reason}",
                    "",
                    "===== STDOUT =====",
                    stdout or "",
                    "",
                    "===== STDERR =====",
                    stderr or "",
                    "",
                ]
            )
        )
        return self._relative_log_path(log_file)

    def _format_dispatch_failure_message(
        self,
        reason: str,
        stdout: str,
        stderr: str,
        log_path: str,
    ) -> str:
        """Format the immediate failure summary printed by CLI dispatch."""
        lines = [f"✗ Dispatch failed: {reason}"]
        stderr_tail = self._tail_lines(stderr)
        stdout_tail = self._tail_lines(stdout)

        if stderr_tail:
            lines.extend(
                [
                    f"stderr (last {DISPATCH_OUTPUT_TAIL_LINES} lines):",
                    stderr_tail,
                ]
            )
        if stdout_tail:
            lines.extend(
                [
                    f"stdout (last {DISPATCH_OUTPUT_TAIL_LINES} lines):",
                    stdout_tail,
                ]
            )
        lines.append(f"Full log: {log_path}")
        return "\n".join(lines)

    def _handle_dispatch_failure(self, ticket: dict, owner: str, failure: dict) -> str:
        """Mark a failed subprocess dispatch blocked and surface captured output."""
        ticket_id = ticket["id"]
        reason = failure.get("reason") or "agent failed"
        stdout = failure.get("stdout") or ""
        stderr = failure.get("stderr") or ""
        returncode = failure.get("returncode")
        quota_reset = self._detect_quota_reset(stderr) if owner == "CODEX" else None
        if quota_reset is not None:
            reason = self._format_quota_blocked_reason(reason, quota_reset)
            self._record_quota_exhausted(quota_reset)
        log_path = self._write_dispatch_failure_log(
            ticket_id=ticket_id,
            owner=owner,
            reason=reason,
            stdout=stdout,
            stderr=stderr,
            returncode=returncode,
        )
        blocked_reason = f"{reason}; log: {log_path}"
        with self._state_lock:
            block_ticket(self.paths["queue"], ticket_id, blocked_reason, log_path)
        message = self._format_dispatch_failure_message(reason, stdout, stderr, log_path)
        with self._state_lock:
            self._dispatch_failures[ticket_id] = message
        return message

    def _detect_no_ticket_file_diff(
        self,
        ticket: dict,
        subprocess_result: dict,
        dispatch_snapshot_sha: str,
    ) -> dict | None:
        """Return a synthetic failure when a successful agent produced no scoped diff."""
        files = ticket.get("files") or []
        if not files:
            return None

        diff_cmd = ["git", "diff", "--name-only", dispatch_snapshot_sha, "--", *files]
        try:
            diff_result = subprocess.run(
                diff_cmd,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(self.paths["root"]),
            )
        except Exception as exc:
            logger.warning(
                "Could not check ticket-file diff for %s before gates: %s",
                ticket.get("id"),
                exc,
            )
            return None

        if diff_result.returncode != 0:
            error_output = (diff_result.stderr or diff_result.stdout or "git diff failed").strip()
            logger.warning(
                "Could not check ticket-file diff for %s before gates: %s",
                ticket.get("id"),
                error_output,
            )
            return None

        if diff_result.stdout.strip():
            return None

        return {
            "reason": (
                "agent_runtime_failure: subprocess returned 0 but produced no diff "
                "— check session log"
            ),
            "stdout": subprocess_result.get("stdout") or "",
            "stderr": subprocess_result.get("stderr") or "",
            "returncode": subprocess_result.get("returncode", 0),
        }

    def _run_subprocess(self, ticket: dict, agent_cfg: dict) -> tuple[bool, dict]:
        """Run agent as subprocess (Claude 2 or Codex)."""
        command = agent_cfg.get("command", ["claude", "-p"])
        timeout = agent_cfg.get("timeout", 600)
        env = {**os.environ, **agent_cfg.get("env", {})}

        # Set config dir for Claude 2
        config_dir = agent_cfg.get("config_dir")
        if config_dir:
            env["CLAUDE_CONFIG_DIR"] = config_dir

        prompt = self._build_prompt(ticket)

        try:
            result = subprocess.run(
                command,
                input=prompt,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
                cwd=str(self.paths["root"]),
            )
            if result.returncode != 0:
                logger.error(f"Agent failed: {result.stderr[:500]}")
                reason = f"agent exited with code {result.returncode}"
                return False, {
                    "reason": reason,
                    "stdout": result.stdout or "",
                    "stderr": result.stderr or "",
                    "returncode": result.returncode,
                }
            return True, {
                "stdout": result.stdout or "",
                "stderr": result.stderr or "",
                "returncode": result.returncode,
            }
        except subprocess.TimeoutExpired as exc:
            logger.error(f"Agent timed out after {timeout}s")
            return False, {
                "reason": f"agent timed out after {timeout}s",
                "stdout": exc.stdout or "",
                "stderr": exc.stderr or "",
                "returncode": None,
            }
        except FileNotFoundError as exc:
            logger.error(f"Agent command not found: {exc}")
            return False, {
                "reason": f"agent command not found: {exc.filename}",
                "stdout": "",
                "stderr": str(exc),
                "returncode": None,
            }

    # ── Gate Pipeline ─────────────────────────────────────────────────────────

    def _resolve_gates(self, ticket: dict) -> list[dict]:
        """Resolve gates for a ticket: ticket-level gates override defaults."""
        gates_config = self.config.get("gates", {})
        defaults = list(gates_config.get("defaults", []))
        ticket_gates = ticket.get("gates")
        if ticket_gates:
            return self._normalize_gates(ticket_gates, defaults)

        # Use defaults from os2.yaml
        gates = [copy.deepcopy(gate) for gate in defaults]

        # Add tag-based gates
        tags = ticket.get("tags", [])
        by_tag = gates_config.get("by_tag", {})
        for tag in tags:
            if tag in by_tag:
                gates.extend(by_tag[tag])

        return gates

    def _gate_default_lookup(self, defaults: list[dict]) -> dict[str, dict]:
        """Build lookup for string gate names from configured defaults."""
        lookup = {
            str(gate["name"]): gate
            for gate in defaults
            if isinstance(gate, dict) and gate.get("name")
        }
        types: dict[str, list[dict]] = {}
        for gate in defaults:
            if not isinstance(gate, dict):
                continue
            gate_type = gate.get("type")
            if gate_type:
                types.setdefault(str(gate_type), []).append(gate)
        for gate_type, matches in types.items():
            if len(matches) == 1:
                lookup.setdefault(gate_type, matches[0])
        return lookup

    def _normalize_gates(self, gates: list, defaults: list[dict]) -> list[dict]:
        """Resolve string gate references to default gate dicts."""
        lookup = self._gate_default_lookup(defaults)
        normalized = []
        for gate in gates:
            if isinstance(gate, dict):
                normalized.append(copy.deepcopy(gate))
                continue
            if isinstance(gate, str):
                default_gate = lookup.get(gate)
                if default_gate is None:
                    raise ValidationError(
                        f"unknown gate name: '{gate}', see os2.yaml gates.defaults"
                    )
                normalized.append(copy.deepcopy(default_gate))
                continue
            raise ValidationError("gates must contain only dicts or strings")
        return normalized

    def _run_command_gate(self, gate: dict) -> tuple[bool, str]:
        """Run a command gate (e.g. make test). Returns (passed, output)."""
        cmd = gate.get("run", "")
        if not cmd:
            return True, "no command"

        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=gate.get("timeout", 120),
                cwd=str(self.paths["root"]),
            )
            if result.returncode == 0:
                return True, result.stdout[-500:] if result.stdout else "ok"
            return False, (result.stderr or result.stdout)[-500:]
        except subprocess.TimeoutExpired:
            return False, f"gate timed out after {gate.get('timeout', 120)}s"

    def _run_agent_review(self, ticket: dict, dispatch_snapshot_sha: str) -> tuple[bool, str]:
        """Run agent-review gate: Claude 1 reviews diff against DOD."""
        review_cfg = self.config.get("gates", {}).get("agent_review", {})
        max_diff = review_cfg.get("max_diff_lines", 500)

        # Get git diff for the ticket's files
        files = ticket.get("files", [])
        diff_cmd = (
            ["git", "diff", dispatch_snapshot_sha, "--"] + files
            if files
            else ["git", "diff", dispatch_snapshot_sha]
        )
        try:
            diff_result = subprocess.run(
                diff_cmd,
                capture_output=True, text=True, timeout=30,
                cwd=str(self.paths["root"]),
            )
            diff_text = diff_result.stdout
            if len(diff_text.splitlines()) > max_diff:
                diff_text = "\n".join(diff_text.splitlines()[:max_diff]) + "\n... (truncated)"
        except Exception:
            diff_text = "(could not get diff)"

        # Build review prompt
        import yaml
        dod = ticket.get("dod", [])
        review_prompt = f"""You are reviewing a completed ticket. Check if the diff satisfies the DOD.

## Ticket
```yaml
{yaml.dump(ticket, allow_unicode=True)}
```

## DOD Checklist
{chr(10).join(f'- [ ] {item}' for item in dod)}

## Diff
```diff
{diff_text}
```

Respond with EXACTLY one of:
- PASS: <one-line summary>
- FAIL: <what's missing or wrong>
"""

        try:
            result = subprocess.run(
                ["claude", "-p"],
                input=review_prompt,
                capture_output=True, text=True,
                timeout=review_cfg.get("timeout", 120),
                cwd=str(self.paths["root"]),
            )
            if result.returncode != 0:
                error_output = (result.stderr or result.stdout or "agent review command failed").strip()
                return False, error_output[-500:]

            response = result.stdout.strip()
            ansi_pattern = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
            verdict_pattern = re.compile(r"(?im)^[^\S\r\n]*(PASS|FAIL):[^\n\r]*")

            cleaned_response = ansi_pattern.sub("", response)
            verdict_match = verdict_pattern.search(cleaned_response)
            if verdict_match:
                verdict_line = verdict_match.group(0).strip()
                return verdict_line.upper().startswith("PASS:"), verdict_line

            preview = cleaned_response.replace("\r", " ").replace("\n", " ").strip()
            preview = preview[:200] if preview else "(empty response)"
            return False, f"no verdict in response: {preview}"
        except subprocess.TimeoutExpired:
            return False, "agent review timed out"
        except FileNotFoundError:
            logger.warning("claude CLI not found for agent-review gate, skipping")
            return True, "skipped (claude not found)"

    def _run_ticket_verify(self, ticket: dict) -> tuple[bool, str]:
        """Run ticket-level verify command(s). Returns (passed, message)."""
        verify = ticket.get("verify")
        if not verify:
            return True, "skipped (no verify)"

        commands = verify if isinstance(verify, list) else [verify]
        timeout = self.config.get("gates", {}).get("verify_timeout", 120)

        for raw_cmd in commands:
            cmd, expect_nonzero = self._normalize_verify_command(str(raw_cmd).strip())
            if not cmd:
                continue

            try:
                result = subprocess.run(
                    cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=str(self.paths["root"]),
                )
            except subprocess.TimeoutExpired as exc:
                output = ((exc.stderr or "") + (exc.stdout or "")).strip() or "(no output)"
                return False, f"verify failed: {cmd}\n{output}\n(timed out after {timeout}s)"

            stdout = (result.stdout or "").strip()
            stderr = (result.stderr or "").strip()
            output = (stderr or stdout) or "(no output)"
            if expect_nonzero:
                if result.returncode != 0:
                    continue
                return False, f"verify failed: {cmd}\nexpected non-zero exit code, got 0"
            if result.returncode != 0:
                return False, f"verify failed: {cmd}\n{output}"
            if "wc -l" in cmd and stdout.isdigit() and int(stdout) != 0:
                return False, f"verify failed: {cmd}\n{stdout}"

        return True, "verify passed"

    def _normalize_verify_command(self, raw_cmd: str) -> tuple[str, bool]:
        """Convert simple natural-language verify specs into shell commands."""
        cmd = raw_cmd
        expect_nonzero = False

        nonzero_markers = ("의 exit code != 0", " exit code != 0")
        for marker in nonzero_markers:
            if marker in cmd:
                cmd = cmd.split(marker, 1)[0].strip()
                expect_nonzero = True
                break

        output_markers = (" 가 해당 ticket entry 출력", "가 해당 ticket entry 출력")
        for marker in output_markers:
            if marker in cmd:
                cmd = cmd.split(marker, 1)[0].strip()
                break

        if "<known-failing-ticket>" in cmd:
            cmd = cmd.replace("<known-failing-ticket>", self._known_failing_ticket_id())

        return cmd, expect_nonzero

    def _known_failing_ticket_id(self) -> str:
        """Resolve the placeholder used by some human-readable verify specs."""
        try:
            data = read_queue(self.paths["queue"])
        except ValidationError:
            return "T-X"

        blocked = [
            ticket
            for ticket in data.get("tickets", [])
            if ticket.get("status") == "blocked"
            and ticket.get("_blocked_reason")
            and ticket.get("_blocked_log")
        ]
        for ticket in blocked:
            ticket_id = str(ticket.get("id", ""))
            if ticket_id.startswith("T-X"):
                return ticket_id
        if blocked:
            return str(blocked[0].get("id"))
        return "T-X"

    def _run_gates(self, ticket: dict, dispatch_snapshot_sha: str) -> tuple[bool, str]:
        """Run the full gate pipeline. Returns (all_passed, failure_message)."""
        gates = self._resolve_gates(ticket)
        for gate in gates:
            gate_name = gate.get("name", "unnamed")
            logger.info(f"Running gate '{gate_name}' for {ticket['id']}")

            if gate.get("type") == "agent-review":
                passed, msg = self._run_agent_review(ticket, dispatch_snapshot_sha)
            else:
                passed, msg = self._run_command_gate(gate)

            if not passed:
                logger.warning(f"Gate '{gate_name}' failed for {ticket['id']}: {msg}")
                return False, f"{gate_name}: {msg}"

            logger.info(f"Gate '{gate_name}' passed for {ticket['id']}")

        logger.info(f"Running gate 'verify' for {ticket['id']}")
        verify_passed, verify_msg = self._run_ticket_verify(ticket)
        if not verify_passed:
            logger.warning(f"Gate 'verify' failed for {ticket['id']}: {verify_msg}")
            return False, f"verify: {verify_msg}"
        logger.info(f"Gate 'verify' passed for {ticket['id']}: {verify_msg}")

        if not gates and not ticket.get("verify"):
            return True, "no gates configured"

        return True, "all gates passed"

    def _rollback_retry_files(self, ticket_id: str, files: list[str]) -> bool:
        """Restore retry scope files to HEAD and confirm they are clean."""
        if not files:
            return True

        root = str(self.paths["root"])
        failed_files: list[str] = []

        for file_path in files:
            tracked_cmd = ["git", "ls-files", "--error-unmatch", "--", file_path]
            try:
                tracked_result = subprocess.run(
                    tracked_cmd,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    cwd=root,
                )
            except (subprocess.TimeoutExpired, Exception) as exc:
                logger.error(f"Rollback failed for {ticket_id} on {file_path}: {exc}")
                failed_files.append(file_path)
                continue

            target_path = Path(root) / file_path
            if tracked_result.returncode == 0:
                rollback_cmd = ["git", "restore", "--worktree", "--source=HEAD", "--", file_path]
            elif target_path.exists():
                rollback_cmd = ["git", "clean", "-f", "--", file_path]
            else:
                continue

            try:
                rollback_result = subprocess.run(
                    rollback_cmd,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    cwd=root,
                )
            except (subprocess.TimeoutExpired, Exception) as exc:
                logger.error(f"Rollback failed for {ticket_id} on {file_path}: {exc}")
                failed_files.append(file_path)
                continue

            if rollback_result.returncode != 0:
                error_output = (
                    rollback_result.stderr
                    or rollback_result.stdout
                    or f"{rollback_cmd[1]} failed"
                ).strip()
                logger.error(f"Rollback failed for {ticket_id} on {file_path}: {error_output}")
                failed_files.append(file_path)

        status_cmd = ["git", "status", "--short", "--", *files]
        try:
            status_result = subprocess.run(
                status_cmd,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=root,
            )
        except (subprocess.TimeoutExpired, Exception) as exc:
            logger.error(f"Rollback status check failed for {ticket_id}: {exc}")
            return False

        if status_result.returncode != 0:
            error_output = (status_result.stderr or status_result.stdout or "git status failed").strip()
            logger.error(f"Rollback status check failed for {ticket_id}: {error_output}")
            return False

        remaining = status_result.stdout.strip()
        if remaining:
            logger.error(f"Rollback left scope dirty for {ticket_id}: {remaining}")
            for line in remaining.splitlines():
                dirty_path = line[3:].strip()
                if dirty_path and dirty_path not in failed_files:
                    failed_files.append(dirty_path)

        if failed_files:
            logger.error(
                "Rollback incomplete for %s; failed files: %s",
                ticket_id,
                ", ".join(failed_files),
            )
            return False

        return True

    def _get_max_retries_for_ticket(self, ticket: dict) -> int:
        """Resolve retry limit using retry_policy with max_retries fallback."""
        retry_cfg = self.config.get("gates", {}).get("auto_retry", {})
        default_max_retries = retry_cfg.get("max_retries", 1)
        priority = ticket.get("priority")
        if not priority:
            return default_max_retries

        retry_policy = retry_cfg.get("retry_policy", {})
        priority_limit = retry_policy.get(priority)
        if priority_limit is None:
            return default_max_retries

        try:
            return int(priority_limit)
        except (TypeError, ValueError):
            logger.warning(
                "Invalid retry_policy for priority '%s': %r; using default max_retries=%s",
                priority,
                priority_limit,
                default_max_retries,
            )
            return default_max_retries

    def _attempt_retry(
        self,
        ticket: dict,
        gate_output: str,
        dispatch_snapshot_sha: str,
    ) -> bool:
        """Re-dispatch builder with gate failure context. Returns success."""
        retry_cfg = self.config.get("gates", {}).get("auto_retry", {})
        if not retry_cfg.get("enabled", False):
            return False

        ticket_id = ticket["id"]
        max_retries = self._get_max_retries_for_ticket(ticket)

        # Track retries via ticket metadata
        retries = ticket.get("_retries", 0)
        if retries >= max_retries:
            logger.info(f"Max retries ({max_retries}) reached for {ticket_id}")
            return False

        # Get diff for context
        files = ticket.get("files", [])
        diff_cmd = (
            ["git", "diff", dispatch_snapshot_sha, "--"] + files
            if files
            else ["git", "diff", dispatch_snapshot_sha]
        )
        try:
            diff_result = subprocess.run(
                diff_cmd, capture_output=True, text=True, timeout=30,
                cwd=str(self.paths["root"]),
            )
            diff_text = diff_result.stdout[-3000:]
        except Exception:
            diff_text = "(could not get diff)"

        retry_ticket = copy.deepcopy(ticket)
        retry_ticket["_retries"] = retries + 1

        owner = retry_ticket["owner"]
        agent_cfg = self.agent_configs.get(owner, {})

        logger.info(f"Retrying {ticket_id} (attempt {retries + 1}/{max_retries})")

        if not self._rollback_retry_files(ticket_id, files):
            logger.error(f"Retry aborted for {ticket_id}: rollback failed")
            return False

        # Build retry prompt with gate context
        import yaml
        retry_prompt = f"""Your previous attempt on this ticket failed gate checks. Fix the issues.

## Gate Failure
{gate_output}

## Your Previous Diff
```diff
{diff_text}
```

## Original Ticket
```yaml
{yaml.dump(retry_ticket, allow_unicode=True)}
```

이전 시도의 변경은 롤백됨, 원본 코드 기준으로 작업.

Fix the issues identified in the gate failure, then:
1. Run the verify command in the ticket
2. Write a session log to devos/logs/
3. Output the 4-line handoff format
"""

        # Run the agent with retry prompt
        mode = agent_cfg.get("mode", "subprocess")
        if mode in ("subprocess", "pipe"):
            command = agent_cfg.get("command", ["claude", "-p"])
            timeout = agent_cfg.get("timeout", 600)
            env = {**os.environ, **agent_cfg.get("env", {})}
            config_dir = agent_cfg.get("config_dir")
            if config_dir:
                env["CLAUDE_CONFIG_DIR"] = config_dir

            try:
                result = subprocess.run(
                    command, input=retry_prompt,
                    capture_output=True, text=True,
                    timeout=timeout, env=env,
                    cwd=str(self.paths["root"]),
                )
                return result.returncode == 0
            except (subprocess.TimeoutExpired, Exception) as e:
                logger.error(f"Retry failed for {ticket_id}: {e}")
                return False
        else:
            logger.warning(f"Retry not supported for mode '{mode}'")
            return False

    def _get_agent_log(self, owner: str, ticket_id: str) -> str:
        """Get summary from the agent's session log."""
        import re
        logs_path = self.paths["logs"]
        agent_name = owner.lower().replace("1", "1").replace("2", "2")
        # Find most recent log for this agent/ticket
        recent = get_recent_logs(logs_path, limit=10)
        for log_file in recent:
            if agent_name in log_file.name.lower() and ticket_id in log_file.name:
                content = log_file.read_text()
                match = re.search(r"## Summary\n(.*?)(?=\n##|\Z)", content, re.DOTALL)
                if match:
                    return match.group(1).strip()[:200]
        return ""

    async def _send_notify(self, message: str) -> None:
        """Send notification via callback."""
        if self.notify:
            try:
                await self.notify(message)
            except Exception as e:
                logger.error(f"Failed to send notification: {e}")
