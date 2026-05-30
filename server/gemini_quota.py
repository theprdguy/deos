"""Daily quota counter for the Gemini dispatcher — T-OSN-W7-GEMINI-04.

Responsibilities:
1. Atomically increment a per-day call counter stored in
   server/state/gemini_quota_{YYYY-MM-DD}.json using fcntl advisory locking.
2. Return the current count so the caller can decide whether Plan A is
   allowed or whether Plan B handoff should be used.
3. Append one JSONL line to devos/logs/gemini/quota_{YYYYMM}.jsonl with
   outcome information (success / fallback / quota_exceeded / error).
4. When the cap is exceeded, auto-register a Q-* item in
   devos/questions/QUEUE.md (one per calendar day, idempotent).

File-lock strategy
------------------
We use fcntl.flock() (shared across the interpreter, not re-entrant) with an
exclusive lock on an adjacent lock-file (gemini_quota_{date}.lock) so that
concurrent dispatchers in the same process or across processes do not race
on the counter JSON.

Atomic rename fallback (Windows / non-POSIX): if fcntl is unavailable the
module falls back to a best-effort write without the lock.  This scenario is
unlikely on macOS/Linux but documented for portability.

Cross-process idempotency — sentinel file (R2 BLOCKER 1 fix)
-------------------------------------------------------------
_register_quota_question uses a sentinel file written with O_CREAT|O_EXCL so
that even when two OS-level processes simultaneously detect cap exhaustion,
exactly one succeeds in creating the sentinel and one registers the Q-* entry.
The sentinel lives at devos/state/quota_q_{YYYY-MM-DD}.flag and is never
committed (covered by .gitignore).

State files (never committed — covered by .gitignore):
  server/state/gemini_quota_{YYYY-MM-DD}.json   counter
  server/state/gemini_quota_{YYYY-MM-DD}.lock   lock sentinel
  devos/state/quota_q_{YYYY-MM-DD}.flag         cross-process Q-* sentinel
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_DAILY_CAP: int = 50

# Sentinel written to questions/QUEUE.md (idempotent — checked before write)
_QUOTA_Q_TAG = "quota-exceeded"

# Valid values for quota_overflow_action config key
_OVERFLOW_ACTIONS = frozenset({"questions_queue", "silent", "raise"})


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class QuotaExceededError(RuntimeError):
    """Raised when the daily call cap has been reached."""


def load_gemini_config(project_root: Optional[Path] = None) -> dict:
    """Read full server/config/gemini.yaml; return parsed dict (empty on error).

    Keys returned (with defaults if absent):
      daily_call_cap          int   50
      quota_overflow_action   str   "questions_queue"
      fallback_on_quota_exceeded bool True
    """
    if project_root is None:
        project_root = Path(__file__).resolve().parent.parent
    config_path = project_root / "server" / "config" / "gemini.yaml"
    if not config_path.exists():
        return {}
    try:
        import yaml  # type: ignore[import-untyped]
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        logger.warning("Could not read gemini.yaml: %s", exc)
        return {}


def load_daily_cap(project_root: Optional[Path] = None) -> int:
    """Read daily_call_cap from server/config/gemini.yaml; fall back to DEFAULT."""
    data = load_gemini_config(project_root)
    cap = data.get("daily_call_cap", DEFAULT_DAILY_CAP)
    if isinstance(cap, int) and cap > 0:
        return cap
    return DEFAULT_DAILY_CAP


class GeminiQuota:
    """Per-day call counter with file-lock safety for concurrent dispatchers.

    Usage::

        quota = GeminiQuota(project_root, daily_cap=50)
        # Before calling gemini subprocess:
        quota.check_and_increment(ticket_id)   # raises QuotaExceededError if at cap
        # After call completes:
        quota.log_outcome(ticket_id, model, input_tokens, output_tokens, outcome)

    ``check_and_increment`` atomically reads, validates, and increments the
    counter under an exclusive file lock so parallel dispatchers cannot both
    reach count==cap-1 and both succeed.
    """

    def __init__(
        self,
        project_root: Path,
        daily_cap: int = DEFAULT_DAILY_CAP,
        overflow_action: str = "questions_queue",
        fallback_on_quota_exceeded: bool = True,
    ) -> None:
        self.project_root = project_root.resolve()
        self.daily_cap = daily_cap
        # quota_overflow_action: "questions_queue" | "silent" | "raise"
        self.overflow_action = overflow_action if overflow_action in _OVERFLOW_ACTIONS else "questions_queue"
        # fallback_on_quota_exceeded: True = route to Plan B handoff; False = let caller decide
        self.fallback_on_quota_exceeded = fallback_on_quota_exceeded
        self._state_dir = self.project_root / "server" / "state"
        self._log_dir = self.project_root / "devos" / "logs" / "gemini"
        self._questions_path = self.project_root / "devos" / "questions" / "QUEUE.md"
        # Cross-process Q-* sentinel dir (devos/state/)
        self._devos_state_dir = self.project_root / "devos" / "state"
        self._state_dir.mkdir(parents=True, exist_ok=True)
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._devos_state_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Counter file paths (date-partitioned)
    # ------------------------------------------------------------------

    def _today_utc(self) -> str:
        return datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")

    def _counter_path(self, date_str: Optional[str] = None) -> Path:
        d = date_str or self._today_utc()
        return self._state_dir / f"gemini_quota_{d}.json"

    def _lock_path(self, date_str: Optional[str] = None) -> Path:
        d = date_str or self._today_utc()
        return self._state_dir / f"gemini_quota_{d}.lock"

    # ------------------------------------------------------------------
    # File-lock helpers
    # ------------------------------------------------------------------

    def _acquire_lock(self, lock_file_path: Path):
        """Open (or create) the lock file and acquire an exclusive flock.

        Returns the open file object — caller must close it to release.
        Falls back to a no-op context on non-POSIX systems.
        """
        lock_fd = open(lock_file_path, "w", encoding="utf-8")  # noqa: SIM115
        try:
            import fcntl
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
        except ImportError:
            # Non-POSIX — best-effort (no lock)
            logger.debug("fcntl unavailable — quota counter not locked (non-POSIX)")
        return lock_fd

    def _release_lock(self, lock_fd) -> None:
        try:
            import fcntl
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
        except ImportError:
            pass
        finally:
            try:
                lock_fd.close()
            except OSError:
                pass

    # ------------------------------------------------------------------
    # Read / write counter (called under lock)
    # ------------------------------------------------------------------

    def _read_counter(self, counter_path: Path) -> dict:
        """Read counter JSON; return default dict if missing or corrupt."""
        if not counter_path.exists():
            return {"count": 0, "date": self._today_utc()}
        try:
            data = json.loads(counter_path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("count"), int):
                return data
        except (json.JSONDecodeError, OSError):
            pass
        return {"count": 0, "date": self._today_utc()}

    def _write_counter(self, counter_path: Path, data: dict) -> None:
        """Write counter JSON atomically via tmp-rename (best effort)."""
        tmp = counter_path.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps(data), encoding="utf-8")
            os.replace(tmp, counter_path)
        except OSError as exc:
            logger.error("Failed to write quota counter: %s", exc)
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass

    # ------------------------------------------------------------------
    # Public: check + increment
    # ------------------------------------------------------------------

    def get_today_count(self) -> int:
        """Return today's call count (read-only, no lock needed for display)."""
        counter_path = self._counter_path()
        data = self._read_counter(counter_path)
        return data.get("count", 0)

    def check_and_increment(self, ticket_id: str) -> int:
        """Atomically check cap and increment counter.

        Returns the new count after incrementing (i.e., 1-based call number).

        Raises:
            QuotaExceededError: if current count >= daily_cap before increment.
        """
        date_str = self._today_utc()
        counter_path = self._counter_path(date_str)
        lock_path = self._lock_path(date_str)

        lock_fd = self._acquire_lock(lock_path)
        try:
            data = self._read_counter(counter_path)
            count = data.get("count", 0)

            if count >= self.daily_cap:
                logger.warning(
                    "Gemini daily cap reached (%d/%d) for ticket %s — triggering handoff",
                    count, self.daily_cap, ticket_id,
                )
                self._register_quota_question()
                raise QuotaExceededError(
                    f"Gemini daily cap reached ({count}/{self.daily_cap}). "
                    "Plan A blocked — use Plan B handoff."
                )

            new_count = count + 1
            data["count"] = new_count
            data["date"] = date_str
            data["last_ticket"] = ticket_id
            self._write_counter(counter_path, data)
            logger.debug("Quota counter: %d/%d for ticket %s", new_count, self.daily_cap, ticket_id)
            return new_count
        finally:
            self._release_lock(lock_fd)

    def set_cap_reached(self) -> None:
        """Force the counter to daily_cap (called when CLI reports quota exhaustion).

        This pins the counter so subsequent check_and_increment calls
        immediately raise QuotaExceededError without re-attempting Plan A.

        R2 fix: _register_quota_question() is now called inside the lock block
        (before release) so the counter write and Q-* registration are a single
        atomic unit from this thread's perspective.  Cross-process safety is
        provided by the O_CREAT|O_EXCL sentinel file inside _register_quota_question
        — this double-guard ensures correctness at both intra-thread and
        cross-process level.
        """
        date_str = self._today_utc()
        counter_path = self._counter_path(date_str)
        lock_path = self._lock_path(date_str)

        lock_fd = self._acquire_lock(lock_path)
        try:
            data = self._read_counter(counter_path)
            data["count"] = self.daily_cap
            data["date"] = date_str
            data["cap_forced"] = True
            self._write_counter(counter_path, data)
            logger.info("Quota counter forced to cap (%d) by CLI exhaustion signal", self.daily_cap)
            # R2 BLOCKER 1 fix: call inside lock — cross-process safety via sentinel file
            self._register_quota_question()
        finally:
            self._release_lock(lock_fd)

    # ------------------------------------------------------------------
    # JSONL quota log (outcome)
    # ------------------------------------------------------------------

    def log_outcome(
        self,
        ticket_id: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        outcome: str,  # "success" | "fallback" | "quota_exceeded" | "error"
    ) -> None:
        """Append one JSONL line to devos/logs/gemini/quota_{YYYYMM}.jsonl.

        Fields: timestamp UTC / ticket_id / model / input_tokens / output_tokens / outcome
        """
        now_utc = datetime.now(tz=timezone.utc)
        ym = now_utc.strftime("%Y%m")
        quota_log = self._log_dir / f"quota_{ym}.jsonl"
        entry = {
            "ts": now_utc.isoformat(),
            "ticket_id": ticket_id,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "outcome": outcome,
        }
        try:
            with open(quota_log, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except OSError as exc:
            logger.warning("Could not write quota log: %s", exc)

    # ------------------------------------------------------------------
    # questions/QUEUE.md auto-registration (idempotent — cross-process safe)
    # ------------------------------------------------------------------

    def _sentinel_path(self, date_str: Optional[str] = None) -> Path:
        """Return the cross-process sentinel file path for today's quota Q-* entry.

        devos/state/quota_q_{YYYY-MM-DD}.flag
        Written with O_CREAT|O_EXCL so exactly one process succeeds (R2 fix).
        """
        d = date_str or self._today_utc()
        return self._devos_state_dir / f"quota_q_{d}.flag"

    def _register_quota_question(self) -> None:
        """Auto-register a Q-* quota-exceeded item in devos/questions/QUEUE.md.

        Cross-process idempotency (R2 BLOCKER 1 fix): uses a sentinel file
        written with O_CREAT|O_EXCL.  Only the process that exclusively creates
        the sentinel file proceeds to append to QUEUE.md — all others skip.
        This is atomic across OS processes, unlike fcntl which is per-process.

        overflow_action values:
          "questions_queue" (default) — append Q-* entry to QUEUE.md
          "silent"                    — skip Q-* registration entirely
          "raise"                     — raise RuntimeError (caller handles)

        Q-id format: Q-{YYYYMMDDHHMI}-quota to avoid collisions with other Q-NNN items.
        """
        # Honor quota_overflow_action config
        if self.overflow_action == "silent":
            logger.debug("quota_overflow_action=silent — skipping Q-* registration")
            return
        if self.overflow_action == "raise":
            raise RuntimeError(
                f"Gemini daily cap ({self.daily_cap}) reached — "
                "quota_overflow_action=raise configured."
            )

        today = self._today_utc()
        sentinel = self._sentinel_path(today)

        # R2 BLOCKER 1 fix: O_CREAT|O_EXCL — atomic cross-process sentinel creation.
        # Only the first process to reach here wins; all others get EEXIST → return.
        try:
            fd = os.open(str(sentinel), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            os.close(fd)
        except FileExistsError:
            # Another process already created the sentinel — Q-* already registered.
            logger.debug("Quota sentinel already exists for %s — skipping Q-* registration", today)
            return
        except OSError as exc:
            logger.warning("Could not create quota sentinel file %s: %s", sentinel, exc)
            # Fall through — best effort: append QUEUE.md regardless (sentinel creation failed,
            # cross-process atomicity not guaranteed for this branch — rare ENOSPC/EACCES).

        # We won the sentinel race — proceed to append QUEUE.md
        try:
            now_utc = datetime.now(tz=timezone.utc)
            q_id = f"Q-{now_utc.strftime('%Y%m%d%H%M')}-quota"
            entry = (
                f"\n---\n\n"
                f"## {q_id}: Gemini daily cap reached ({today})\n"
                f"Status: [open]\n"
                f"Ticket: T-OSN-W7-GEMINI-04\n"
                f"Blocking: no\n"
                f"Tag: quota-exceeded-{today}\n"
                f"\n"
                f"**Question**: Gemini Plan A daily cap ({self.daily_cap} calls) reached on {today} UTC.\n"
                f"All subsequent Plan A calls have been automatically rerouted to Plan B handoff.\n"
                f"\n"
                f"**Action required**: Wait until the next UTC day (midnight UTC) for the quota to reset,\n"
                f"or manually increase `daily_call_cap` in `server/config/gemini.yaml` if the current\n"
                f"limit is too restrictive for your workflow.\n"
                f"\n"
                f"**Options**:\n"
                f"  A) Wait for UTC midnight reset — no action required, quota auto-resets.\n"
                f"  B) Increase `daily_call_cap` in server/config/gemini.yaml.\n"
                f"**Recommendation**: A — the cap exists to protect the free OAuth tier.\n"
                f"**Default (if no response)**: A — Plan B handoff will handle all remaining calls today.\n"
            )

            with open(self._questions_path, "a", encoding="utf-8") as f:
                f.write(entry)
            logger.info("Quota question registered: %s in %s", q_id, self._questions_path)

        except OSError as exc:
            logger.warning("Could not register quota question: %s", exc)
