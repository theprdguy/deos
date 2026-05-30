"""Shared ticket_id validation — single source of truth.

Both gemini_dispatcher.py and gemini_handoff.py import from here.
Unifying avoids regex divergence (W1 fix — T-OSN-W7-GEMINI-02 R2).

Pattern supports:
  - Standard segments: T-OSN-W7-GEMINI-02
  - Sub-ticket suffix (single lowercase letter): T-OSN-W7-GEMINI-01a
  - Rejects: trailing dash, path separators, lowercase segments, empty string
"""

from __future__ import annotations

import re


# Canonical ticket_id regex — matches both dispatcher and handoff usage.
# Trailing optional lowercase letter supports sub-ticket ids like T-...-01a.
# (Previously gemini_handoff.py lacked the [a-z]? suffix — W1 fix.)
TICKET_ID_RE = re.compile(r"^T-[A-Z0-9]+(-[A-Z0-9]+)*[a-z]?$")


class TicketIdError(ValueError):
    """ticket_id does not match the expected safe pattern."""


def validate_ticket_id(ticket_id: str) -> None:
    """Reject ticket_id values that don't match the safe pattern.

    Prevents path traversal attacks via flag file names and log file names.

    Args:
        ticket_id: the candidate ticket identifier string.

    Raises:
        TicketIdError: if ticket_id fails the regex check or is empty.
    """
    if not ticket_id or not TICKET_ID_RE.fullmatch(ticket_id):
        raise TicketIdError(
            f"ticket_id {ticket_id!r} is invalid. "
            r"Expected pattern: ^T-[A-Z0-9]+(-[A-Z0-9]+)*[a-z]?$ "
            "(uppercase segments, optional single lowercase suffix, no trailing dash, "
            "no path separators)."
        )
