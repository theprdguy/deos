"""Parse builder handoff blocks from session logs or subprocess output."""
from __future__ import annotations

import re
from dataclasses import dataclass


BLOCK_LINE_PATTERN = re.compile(r"^\s*Block\s*:\s*(.+?)\s*$", re.IGNORECASE)
DONE_LINE_PATTERN = re.compile(r"^\s*Done\s*:\s*(.+?)\s*$", re.IGNORECASE)
NEXT_LINE_PATTERN = re.compile(r"^\s*Next\s*:\s*(.+?)\s*$", re.IGNORECASE)


@dataclass(frozen=True)
class Handoff:
    """Parsed final handoff state."""

    done: str
    next: str
    block: str

    @property
    def block_is_none(self) -> bool:
        return self.block.lower() == "none"


def parse_block_line(line: str) -> str | None:
    """Return normalized Block value, or None when the line is not valid."""
    match = BLOCK_LINE_PATTERN.fullmatch(line)
    if not match:
        return None
    value = match.group(1).strip()
    if value.startswith(":"):
        value = value.lstrip(":").strip()
    return value or None


def parse_handoff(text: str) -> Handoff | None:
    """Parse the last Done/Next/Block handoff block from text."""
    done: str | None = None
    next_step: str | None = None
    block: str | None = None

    for line in reversed((text or "").splitlines()):
        if block is None:
            parsed_block = parse_block_line(line)
            if parsed_block is not None:
                block = parsed_block
                continue
        if block is not None and next_step is None:
            match = NEXT_LINE_PATTERN.fullmatch(line)
            if match:
                next_step = match.group(1).strip()
                continue
        if block is not None and next_step is not None and done is None:
            match = DONE_LINE_PATTERN.fullmatch(line)
            if match:
                done = match.group(1).strip()
                break

    if done is None or next_step is None or block is None:
        return None
    return Handoff(done=done, next=next_step, block=block)
