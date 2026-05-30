"""Gemini Plan B handoff/ingest — T-OSN-W7-GEMINI-02.

Manual escape hatch for visual Gemini review when Plan A (gemini_dispatcher.py)
fails or is unavailable.

R6 (Phase 0): Make targets removed — python3 CLI only (R5 Make interface sunset).
- python3 -m server.gemini_handoff pending     — list pending tickets
- python3 -m server.gemini_handoff next        — pick oldest pending, write active.lock, print guidance
- python3 -m server.gemini_handoff ingest-stdin — read stdin, match active.lock, store log

RCE surface: structural zero — no Make variable channel exists for Plan B.

Security guarantees (preserved from R1-R4):
- ticket_id validated against strict regex before any file I/O (path traversal guard)
- stdout never contains raw shell metacharacters: .sh script written to .cache/,
  stdout only prints the script path (shlex.quote used throughout)
- ingest response stored as plain text only; never eval/exec'd
- ingest rejects responses > 100 KB (paste error / corruption guard)
- flag file path derived from validated ticket_id only (no traversal)
- devos/state/ auto-created with parents=True
- active.lock read from devos/state/ — no user-controlled path component
"""

from __future__ import annotations

import shlex
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

# W1 fix (T-OSN-W7-GEMINI-02 R2): import shared regex from _ticket_id.py.
# Previously this module had its own ^T-[A-Z0-9]+(-[A-Z0-9]+)*$ regex that
# lacked the trailing [a-z]? suffix, causing sub-ticket ids like T-...-01a
# to be rejected in Plan B fallback.
from server._ticket_id import TICKET_ID_RE as _TICKET_ID_RE
from server._ticket_id import TicketIdError, validate_ticket_id as _validate_ticket_id

# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

INGEST_MAX_BYTES: int = 100 * 1024  # 100 KB cap on paste response
GEMINI_DEFAULT_MODEL: str = "gemini-3.1-pro-preview"
ACTIVE_LOCK_FILENAME: str = "gemini_active.lock"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class HandoffError(RuntimeError):
    """Raised when handoff() cannot complete (e.g. bad ticket_id, I/O error)."""


class IngestError(RuntimeError):
    """Raised when ingest() cannot complete (missing flag, oversized response, etc.)."""


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------


class GeminiHandoff:
    """Plan B: manual Gemini visual review handoff + ingest infrastructure.

    R6 python CLI interface (Make targets removed — R5/R6 history: Make interface sunset):
        python3 -m server.gemini_handoff pending      →  list pending flags
        python3 -m server.gemini_handoff next         →  pick oldest pending → print guidance + write active.lock
        python3 -m server.gemini_handoff ingest-stdin →  read stdin → match active.lock → store log + cleanup
    """

    def __init__(
        self,
        *,
        project_root: Path,
        model: str = GEMINI_DEFAULT_MODEL,
    ) -> None:
        self.project_root = project_root.resolve()
        self.model = model
        self._cache_dir = self.project_root / ".cache"
        self._state_dir = self.project_root / "devos" / "state"
        self._log_dir = self.project_root / "devos" / "logs" / "gemini"
        # Ensure required dirs exist
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._state_dir.mkdir(parents=True, exist_ok=True)
        self._log_dir.mkdir(parents=True, exist_ok=True)

    # -----------------------------------------------------------------------
    # handoff() — internal API used by dispatcher.handoff_fallback()
    # -----------------------------------------------------------------------

    def handoff(
        self,
        *,
        ticket_id: str,
        prompt: str,
        image_paths: List[str],
    ) -> None:
        """Print manual paste instructions and create pending flag.

        INTERNAL API: called by dispatcher.handoff_fallback() when Plan A fails.
        Not exposed via Make user-facing targets in R5 (queue-only).

        Security: all shell values written to the .sh script via shlex.quote.
        stdout only prints the .sh script path — never raw prompt or image paths.

        Steps:
        1. Validate ticket_id (path traversal guard).
        2. Write .cache/gemini-handoff-{T}.sh (quoted, executable).
        3. Create devos/state/gemini_pending_{T}.flag.
        4. Print guidance to stdout: "use python3 -m server.gemini_handoff next to process".

        Args:
            ticket_id: validated ticket identifier.
            prompt: review prompt text (never printed raw to stdout).
            image_paths: list of image paths to attach (never printed raw to stdout).
        """
        # Purge stale handoff scripts (WARNING R3 — non-fatal cleanup)
        self._purge_old_handoffs()

        _validate_ticket_id(ticket_id)

        script_path = self._write_handoff_script(
            ticket_id=ticket_id,
            prompt=prompt,
            image_paths=image_paths,
        )

        # Create pending flag
        flag_path = self._flag_path(ticket_id)
        try:
            flag_path.write_text(
                f"pending\nticket={ticket_id}\nts={datetime.now(tz=timezone.utc).isoformat()}\n",
                encoding="utf-8",
            )
        except OSError as exc:
            raise HandoffError(
                f"Could not create pending flag for {ticket_id}: {exc}"
            ) from exc

        # R7: stdout guidance — python3 CLI only (Make gemini-* removed in R6)
        print(
            f"\n[gemini-handoff] Plan A failed — pending flag created for {ticket_id}\n"
            f"{'=' * 60}\n\n"
            f"Script written to: {script_path}\n\n"
            f"Next step:\n"
            f"  python3 -m server.gemini_handoff next\n\n"
            f"  (This will pick the oldest pending ticket, print the run command,\n"
            f"   and create gemini_active.lock for ingest matching.)\n\n"
            f"Flag created: {flag_path}\n",
            file=sys.stdout,
            flush=True,
        )

    # -----------------------------------------------------------------------
    # pending() — list all pending flags
    # -----------------------------------------------------------------------

    def pending(self) -> int:
        """List all pending Gemini handoff tickets.

        Scans devos/state/gemini_pending_*.flag, sorts by mtime (oldest first),
        prints each with timestamp and ticket_id.

        Returns exit code (0 always — informational).
        """
        flags = sorted(
            self._state_dir.glob("gemini_pending_*.flag"),
            key=lambda p: p.stat().st_mtime,
        )
        if not flags:
            print("[gemini-pending] No pending Gemini handoff tickets.", file=sys.stdout)
            return 0

        print(f"[gemini-pending] {len(flags)} pending ticket(s):", file=sys.stdout)
        for flag in flags:
            ticket_id = self._ticket_id_from_flag(flag)
            mtime = datetime.fromtimestamp(flag.stat().st_mtime, tz=timezone.utc).isoformat()
            print(f"  {mtime}  {ticket_id}", file=sys.stdout)
        return 0

    # -----------------------------------------------------------------------
    # next() — pick oldest pending, write active.lock, print guidance
    # -----------------------------------------------------------------------

    def next_pending(self) -> int:
        """Pick the oldest pending ticket, write active.lock, print handoff guidance.

        Steps:
        1. Scan devos/state/gemini_pending_*.flag (mtime sort — oldest first).
        2. Select the oldest flag; extract ticket_id (regex-validated).
        3. Write devos/state/gemini_active.lock with the ticket_id.
        4. Print the handoff script path + guidance.

        Returns: 0 on success, 1 on error (no pending / lock conflict).
        """
        flags = sorted(
            self._state_dir.glob("gemini_pending_*.flag"),
            key=lambda p: p.stat().st_mtime,
        )
        if not flags:
            print(
                "[gemini-next] No pending Gemini handoff tickets.\n"
                "  Run `python3 -m server.gemini_dispatcher dispatch-env` to trigger Plan A,\n"
                "  or wait for Plan A to fall back to Plan B.",
                file=sys.stdout,
            )
            return 0

        oldest = flags[0]
        ticket_id = self._ticket_id_from_flag(oldest)

        # Validate extracted ticket_id (path traversal guard)
        try:
            _validate_ticket_id(ticket_id)
        except TicketIdError as exc:
            print(
                f"[gemini-next] ERROR: Invalid ticket_id extracted from flag {oldest.name!r}: {exc}",
                file=sys.stderr,
            )
            return 1

        # Write active.lock
        lock_path = self._active_lock_path()
        try:
            lock_path.write_text(
                f"{ticket_id}\nts={datetime.now(tz=timezone.utc).isoformat()}\n",
                encoding="utf-8",
            )
        except OSError as exc:
            print(
                f"[gemini-next] ERROR: Could not write active.lock: {exc}",
                file=sys.stderr,
            )
            return 1

        # Look up handoff script
        script_path = self._cache_dir / f"gemini-handoff-{ticket_id}.sh"
        if script_path.exists():
            script_note = (
                f"Run the generated script:\n\n"
                f"  bash {script_path}\n\n"
                f"Then paste the JSON response using:\n\n"
                f"  python3 -m server.gemini_handoff ingest-stdin\n\n"
                f"  (or pipe directly: gemini ... | python3 -m server.gemini_handoff ingest-stdin)"
            )
        else:
            script_note = (
                f"No pre-generated script found for {ticket_id}.\n"
                f"Check .cache/ for gemini-handoff-{ticket_id}.sh.\n\n"
                f"After running manually, paste via:\n\n"
                f"  python3 -m server.gemini_handoff ingest-stdin"
            )

        print(
            f"\n[gemini-next] Processing ticket: {ticket_id}\n"
            f"{'=' * 60}\n\n"
            f"{script_note}\n\n"
            f"Active lock: {lock_path}\n"
            f"Pending flag: {oldest}\n",
            file=sys.stdout,
            flush=True,
        )
        return 0

    # -----------------------------------------------------------------------
    # ingest_stdin() — read stdin, match active.lock, store log
    # -----------------------------------------------------------------------

    def ingest_stdin(self) -> int:
        """Read Gemini response from stdin, match active.lock, store log, cleanup.

        Steps:
        1. Read active.lock → get ticket_id.
        2. Read stdin (100KB cap, plain text).
        3. Write devos/logs/gemini/{date}-{T}.md (redaction applied).
        4. Delete pending flag + active.lock.

        Returns: 0 on success, 1 on error.

        Security:
        - ticket_id comes from active.lock (server-written), NOT from user input.
        - stdin stored as plain text only; never eval/exec'd.
        - 100 KB cap prevents degenerate inputs.
        """
        # Step 1: read active.lock
        lock_path = self._active_lock_path()
        if not lock_path.exists():
            print(
                "[gemini-ingest] ERROR: No active lock found.\n"
                "  Run `python3 -m server.gemini_handoff next` first to select a pending ticket.",
                file=sys.stderr,
            )
            return 1

        lock_content = lock_path.read_text(encoding="utf-8").strip()
        # First line is the ticket_id
        ticket_id = lock_content.splitlines()[0].strip()

        # Validate ticket_id from lock (should always be valid but guard defensively)
        try:
            _validate_ticket_id(ticket_id)
        except TicketIdError as exc:
            print(
                f"[gemini-ingest] ERROR: ticket_id in active.lock is invalid: {exc}",
                file=sys.stderr,
            )
            return 1

        # Step 2: read stdin
        try:
            response = sys.stdin.read()
        except Exception as exc:
            print(
                f"[gemini-ingest] ERROR: Could not read stdin: {exc}",
                file=sys.stderr,
            )
            return 1

        # Empty response check
        if not response.strip():
            print(
                "[gemini-ingest] ERROR: Response is empty. Did you forget to paste the Gemini output?\n"
                "  Run `python3 -m server.gemini_handoff next` to retry.",
                file=sys.stderr,
            )
            return 1

        # Length cap
        response_bytes = len(response.encode("utf-8"))
        if response_bytes > INGEST_MAX_BYTES:
            print(
                f"[gemini-ingest] ERROR: Response too large: {response_bytes} bytes "
                f"(maximum: {INGEST_MAX_BYTES} bytes = 100 KB). "
                f"Trim or split before ingesting.",
                file=sys.stderr,
            )
            return 1

        # Step 3: write log
        try:
            log_path = self._write_ingest_log(ticket_id=ticket_id, response=response)
        except OSError as exc:
            print(
                f"[gemini-ingest] ERROR: Could not write ingest log: {exc}",
                file=sys.stderr,
            )
            return 1

        # Step 4: cleanup — remove pending flag and active.lock
        flag_path = self._flag_path(ticket_id)
        for path in (flag_path, lock_path):
            if path.exists():
                try:
                    path.unlink()
                except OSError as exc:
                    print(
                        f"[gemini-ingest] WARNING: Could not remove {path}: {exc}",
                        file=sys.stderr,
                    )

        print(
            f"[gemini-ingest] Response saved: {log_path}\n"
            f"[gemini-ingest] Ticket {ticket_id} ingest complete.\n"
            f"[gemini-ingest] Cleaned up: pending flag + active.lock",
            file=sys.stdout,
        )
        return 0

    # -----------------------------------------------------------------------
    # ingest() — internal API (called by tests and dispatcher integration)
    # -----------------------------------------------------------------------

    def ingest(
        self,
        *,
        ticket_id: str,
        response: str,
    ) -> Path:
        """Store pasted Gemini response as plain text log; remove pending flag.

        INTERNAL API: preserved for backward compatibility with existing tests
        and dispatcher integration. In R6 python CLI interface, users use
        ingest_stdin() (called by `python3 -m server.gemini_handoff ingest-stdin`).

        Security guarantees:
        - ticket_id validated (path traversal guard).
        - response length checked against INGEST_MAX_BYTES.
        - response stored as plain text ONLY — never eval/exec'd.
        - @./ tokens in response are harmless (not passed to gemini; stored verbatim).
        - flag must exist; missing flag raises IngestError.

        Args:
            ticket_id: validated ticket identifier.
            response: pasted response text from external Gemini session.

        Returns:
            Path to the written log file.

        Raises:
            TicketIdError: invalid ticket_id.
            IngestError: missing flag, oversized response, or I/O error.
        """
        _validate_ticket_id(ticket_id)

        # Verify pending flag exists (user must have run handoff first)
        flag_path = self._flag_path(ticket_id)
        if not flag_path.exists():
            raise IngestError(
                f"No pending flag found for {ticket_id}. "
                f"Expected: {flag_path}\n"
                f"Run `python3 -m server.gemini_handoff next` to select a pending ticket."
            )

        # Empty response check (W5 fix): empty string signals user forgot to paste.
        if not response.strip():
            raise IngestError(
                "Response is empty. Did you forget to paste the Gemini output? "
                "Run `python3 -m server.gemini_handoff next` and copy the full response before ingesting."
            )

        # Length cap: reject oversized responses
        response_bytes = len(response.encode("utf-8"))
        if response_bytes > INGEST_MAX_BYTES:
            raise IngestError(
                f"Response too large: {response_bytes} bytes "
                f"(maximum allowed: {INGEST_MAX_BYTES} bytes = 100 KB). "
                f"Trim or split the response before ingesting."
            )

        # Write plain-text log (NEVER eval/exec the content)
        log_path = self._write_ingest_log(ticket_id=ticket_id, response=response)

        # Remove pending flag
        try:
            flag_path.unlink()
        except OSError as exc:
            # Log removal failure is non-fatal — log was already written
            print(
                f"[gemini-ingest] WARNING: could not remove flag {flag_path}: {exc}",
                file=sys.stderr,
            )

        print(
            f"[gemini-ingest] Response saved: {log_path}\n"
            f"[gemini-ingest] Flag removed: {flag_path}\n"
            f"[gemini-ingest] Ticket {ticket_id} ingest complete.",
            file=sys.stdout,
        )
        return log_path

    # -----------------------------------------------------------------------
    # Handoff cache maintenance (WARNING — R3)
    # -----------------------------------------------------------------------

    def _purge_old_handoffs(self, max_age_days: int = 7) -> None:
        """Delete .cache/gemini-handoff-*.sh files older than max_age_days.

        Mirrors GeminiDispatcher._purge_old_handoffs (T-OSN-W7-GEMINI-01a R2).
        Without cleanup, stale handoff scripts accumulate in .cache/ and can
        mislead operators who tab-complete to an outdated handoff prompt for
        an already-dispatched ticket.

        Only removes files matching 'gemini-handoff-*.sh' (Plan B handoff
        scripts).  Other cache files (smoke caches, arg tmp files, etc.) are
        left untouched.

        Called once at the start of handoff() — non-fatal: any OSError is
        logged to stderr and the purge is skipped silently.
        """
        import time

        cutoff = time.time() - max_age_days * 86400
        try:
            for script in self._cache_dir.glob("gemini-handoff-*.sh"):
                try:
                    if script.stat().st_mtime < cutoff:
                        script.unlink()
                except OSError:
                    pass  # non-fatal
        except OSError:
            pass  # non-fatal — cache dir may not exist yet

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    def _active_lock_path(self) -> Path:
        """Return the active lock file path (no ticket_id component — not user-controlled)."""
        return self._state_dir / ACTIVE_LOCK_FILENAME

    def _flag_path(self, ticket_id: str) -> Path:
        """Return the flag file path for a (validated) ticket_id.

        ticket_id must already be validated before calling this method.
        The resulting path is guaranteed to stay inside devos/state/.
        """
        return self._state_dir / f"gemini_pending_{ticket_id}.flag"

    def _ticket_id_from_flag(self, flag_path: Path) -> str:
        """Extract ticket_id from a flag filename.

        Flag filename format: gemini_pending_{ticket_id}.flag
        Returns the ticket_id substring (not yet validated — caller must validate).
        """
        name = flag_path.stem  # e.g. gemini_pending_T-OSN-W7-001
        prefix = "gemini_pending_"
        if name.startswith(prefix):
            return name[len(prefix):]
        return name  # fallback — will fail validation

    def _write_handoff_script(
        self,
        *,
        ticket_id: str,
        prompt: str,
        image_paths: List[str],
    ) -> Path:
        """Write a quoted shell script to .cache/gemini-handoff-{T}.sh.

        All user-controlled values (prompt, image_paths, model, ticket_id) are
        passed through shlex.quote before being written to the file.
        stdout only prints the path to this script — never its contents.
        """
        script_path = self._cache_dir / f"gemini-handoff-{ticket_id}.sh"
        model_q = shlex.quote(self.model)
        prompt_q = shlex.quote(prompt)

        # Build image argument list: @./path format, each shlex-quoted
        image_args_parts: List[str] = []
        for img_path in image_paths:
            # Use as-is display path with @./ prefix; quote entire token
            token = f"@./{img_path}" if not img_path.startswith("/") else f"@{img_path}"
            image_args_parts.append(shlex.quote(token))

        image_args_q = " ".join(image_args_parts)
        prompt_with_images = (
            f"{image_args_q} {prompt_q}" if image_args_q else prompt_q
        )

        script_content = (
            "#!/usr/bin/env bash\n"
            f"# Auto-generated handoff script for {shlex.quote(ticket_id)}\n"
            f"# Run from the project root.\n"
            f"# Generated: {datetime.now(tz=timezone.utc).isoformat()}\n"
            f"gemini -m {model_q} --sandbox "
            f"-p {prompt_with_images} "
            f"--output-format json\n"
        )

        script_path.write_text(script_content, encoding="utf-8")
        # W3 (-01a) parity: 0o644 — invoke via 'bash <path>' not direct exec.
        # Matches gemini_dispatcher.py script permission (B2 fix — T-OSN-W7-GEMINI-02 R2).
        script_path.chmod(0o644)
        return script_path

    def _write_ingest_log(self, *, ticket_id: str, response: str) -> Path:
        """Write plain-text log to devos/logs/gemini/{date}-{ticket_id}.md.

        The response is stored verbatim as plain text inside a markdown block.
        It is never eval'd, exec'd, or otherwise interpreted.
        """
        now_utc = datetime.now(tz=timezone.utc)
        date_str = now_utc.strftime("%Y-%m-%d")
        log_path = self._log_dir / f"{date_str}-{ticket_id}.md"

        # Plain text storage — no execution of any kind
        content = (
            f"# Gemini Plan B Response — {ticket_id}\n\n"
            f"**Date**: {now_utc.isoformat()}\n"
            f"**Source**: manual paste (Plan B ingest)\n\n"
            f"## Response\n\n"
            f"```\n"
            f"{response}\n"
            f"```\n"
        )
        log_path.write_text(content, encoding="utf-8")
        return log_path


# ---------------------------------------------------------------------------
# CLI entry point (called by Makefile targets)
# ---------------------------------------------------------------------------


def _cli_main(argv: list[str] | None = None) -> int:
    """CLI entry point — python3 -m server.gemini_handoff <subcommand>.

    R6 python CLI interface — Make targets removed (R5/R6 history: osn-wide RCE).
    No Make invocation required for Plan B.

    Subcommands:
        pending       — list pending flag files (no args)
        next          — pick oldest pending, write active.lock, print guidance (no args)
        ingest-stdin  — read stdin + active.lock matching + store log (no args)

    Deprecated subcommands (R1-R4, removed in R5):
        handoff, handoff-env, ingest, ingest-env
        These are no longer registered. Callers get a usage error.
    """
    import argparse
    import os

    parser = argparse.ArgumentParser(prog="gemini_handoff")
    sub = parser.add_subparsers(dest="command")

    # R5 queue-only subcommands — no ad-hoc ticket_id/prompt/images arguments
    sub.add_parser("pending", help="List pending Gemini handoff tickets (no args)")
    sub.add_parser("next", help="Pick oldest pending ticket, print guidance (no args)")
    sub.add_parser("ingest-stdin", help="Read stdin response, match active.lock, store log (no args)")

    args = parser.parse_args(argv)
    project_root = Path(
        os.environ.get("OS3_PROJECT_ROOT") or os.environ.get("OS2_PROJECT_ROOT", ".")
    ).resolve()

    if args.command == "pending":
        gh = GeminiHandoff(project_root=project_root)
        return gh.pending()

    if args.command == "next":
        gh = GeminiHandoff(project_root=project_root)
        return gh.next_pending()

    if args.command == "ingest-stdin":
        gh = GeminiHandoff(project_root=project_root)
        return gh.ingest_stdin()

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(_cli_main())
