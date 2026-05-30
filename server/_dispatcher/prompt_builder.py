"""Prompt-builder cluster extracted from server/dispatcher.py.

Cohesion unit: everything needed to build the subprocess input prompt
(ticket body + orientation header + byte-budget management).

Public API:
    PromptBuilder(config, host, paths) — stateful builder bound to a Dispatcher instance.

All constants (ORIENTATION_START_MARKER etc.) are imported from the parent module to
preserve a single source of truth and avoid divergence.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import yaml as _yaml

if TYPE_CHECKING:
    pass  # kept for future type annotations


# Re-exported from dispatcher module to keep constants SSOT in dispatcher.py.
# Imported lazily inside methods to avoid circular import at module load time.


class PromptBuilder:
    """Builds agent input prompts for subprocess dispatch.

    Extracted from Dispatcher to improve cohesion; all behaviour identical.
    """

    def __init__(self, config: dict, host: Path, paths: dict) -> None:
        self.config = config
        self.host = host
        self.paths = paths

    # ── Public entry point ────────────────────────────────────────────────────

    def build_prompt(self, ticket: dict, *, owner: str | None = None) -> str:
        """Build the prompt string for an agent.

        Note: Agent instructions (CLAUDE.md) are loaded automatically by
        claude -p via CLAUDE_CONFIG_DIR. We only pass the ticket here.
        """
        ticket_prompt = f"""Work on this ticket:

```yaml
{self._ticket_to_yaml(ticket)}
```

After completing:
1. Run the verify command in the ticket
2. Write a session log to devos/logs/
3. Output the 4-line handoff format
"""
        orientation = self.build_orientation_header()
        if not orientation:
            return ticket_prompt
        # Note: the caller (_run_subprocess) is responsible for printing the
        # orientation preload diagnostic — we do not duplicate it here.
        return self._fit_prompt_to_input_limit(
            ticket_prompt=ticket_prompt,
            orientation=orientation,
            ticket_id=str(ticket.get("id", "")),
            owner=owner,
        )

    def build_orientation_header(self, *, max_bytes: int | None = None) -> str:
        """Compose the optional read-only dispatcher orientation header."""
        from server.dispatcher import (
            ORIENTATION_END_MARKER,
            ORIENTATION_START_MARKER,
        )

        dispatch_cfg = self.config.get("dispatch", {}) or {}
        orientation_files = dispatch_cfg.get("orientation_files") or []
        if not orientation_files:
            return ""

        body_parts: list[str] = []
        for entry in orientation_files:
            path_text, range_spec = self._orientation_file_spec(entry)
            if not path_text:
                continue
            path = self.host / path_text
            if not path.exists():
                import logging
                logging.getLogger(__name__).info(
                    "Orientation file missing, preserving legacy prompt: %s", path_text
                )
                return ""
            try:
                content = path.read_text(encoding="utf-8")
            except OSError as exc:
                import logging
                logging.getLogger(__name__).warning(
                    "Could not read orientation file %s: %s", path_text, exc
                )
                return ""
            sliced = self._slice_orientation_content(content, range_spec)
            if sliced.strip():
                body_parts.append(f"# --- {path_text} ---\n{sliced.rstrip()}")

        if not body_parts:
            return ""

        body = "\n\n".join(body_parts).rstrip()
        header = f"{ORIENTATION_START_MARKER}\n{body}\n{ORIENTATION_END_MARKER}\n\n"
        limit = max_bytes if max_bytes is not None else dispatch_cfg.get("orientation_max_bytes")
        if not limit:
            return header
        return self._truncate_orientation_header(header, int(limit))

    # ── Private helpers ───────────────────────────────────────────────────────

    def _orientation_file_spec(self, entry: object) -> tuple[str | None, object]:
        """Return (path, range) from a string or mapping orientation file spec."""
        if isinstance(entry, str):
            return entry, None
        if isinstance(entry, dict):
            path = entry.get("path") or entry.get("file")
            return str(path) if path else None, entry.get("range") or entry.get("lines")
        return None, None

    def _slice_orientation_content(self, content: str, range_spec: object) -> str:
        """Apply a one-based inclusive line range to orientation content."""
        if not range_spec:
            return content
        start: int | None = None
        end: int | None = None
        if isinstance(range_spec, str):
            match = re.match(r"^\s*(\d+)\s*-\s*(\d+)\s*$", range_spec)
            if match:
                start, end = int(match.group(1)), int(match.group(2))
        elif isinstance(range_spec, (list, tuple)) and len(range_spec) == 2:
            start, end = int(range_spec[0]), int(range_spec[1])
        elif isinstance(range_spec, dict):
            raw_start = range_spec.get("start")
            raw_end = range_spec.get("end")
            if raw_start is not None and raw_end is not None:
                start, end = int(raw_start), int(raw_end)
        if start is None or end is None:
            return content
        lines = content.splitlines()
        return "\n".join(lines[max(start - 1, 0) : max(end, 0)])

    def _truncate_orientation_header(self, header: str, max_bytes: int) -> str:
        """Byte-safe truncate while preserving markers when possible."""
        from server.dispatcher import (
            ORIENTATION_END_MARKER,
            ORIENTATION_START_MARKER,
            ORIENTATION_TRUNCATED_MARKER,
        )

        if len(header.encode("utf-8")) <= max_bytes:
            return header

        prefix = f"{ORIENTATION_START_MARKER}\n"
        suffix = f"\n{ORIENTATION_TRUNCATED_MARKER}\n{ORIENTATION_END_MARKER}\n\n"
        budget = max_bytes - len(prefix.encode("utf-8")) - len(suffix.encode("utf-8"))
        if budget <= 0:
            return self._truncate_bytes(
                f"{prefix}{ORIENTATION_TRUNCATED_MARKER}\n{ORIENTATION_END_MARKER}\n\n",
                max_bytes,
            )

        body = header[len(prefix):]
        end_marker_index = body.rfind(f"\n{ORIENTATION_END_MARKER}")
        if end_marker_index != -1:
            body = body[:end_marker_index]
        truncated_body = self._truncate_bytes(body, budget).rstrip()
        return (
            f"{prefix}{truncated_body}\n"
            f"{ORIENTATION_TRUNCATED_MARKER}\n{ORIENTATION_END_MARKER}\n\n"
        )

    def _truncate_bytes(self, text: str, max_bytes: int) -> str:
        """Truncate UTF-8 text without splitting a code point."""
        if max_bytes <= 0:
            return ""
        encoded = text.encode("utf-8")
        if len(encoded) <= max_bytes:
            return text
        return encoded[:max_bytes].decode("utf-8", errors="ignore")

    def _fit_prompt_to_input_limit(
        self,
        *,
        ticket_prompt: str,
        orientation: str,
        ticket_id: str,
        owner: str | None,
    ) -> str:
        """Shrink optional orientation when the combined subprocess input is too large."""
        from server.dispatcher import DEFAULT_SUBPROCESS_INPUT_MAX_BYTES

        dispatch_cfg = self.config.get("dispatch", {}) or {}
        max_input = int(
            dispatch_cfg.get("subprocess_input_max_bytes")
            or dispatch_cfg.get("input_max_bytes")
            or DEFAULT_SUBPROCESS_INPUT_MAX_BYTES
        )
        prompt = f"{orientation}{ticket_prompt}"
        if len(prompt.encode("utf-8")) <= max_input:
            return prompt

        ticket_bytes = len(ticket_prompt.encode("utf-8"))
        orientation_budget = max_input - ticket_bytes
        print(
            f"WARNING: dispatcher input for {ticket_id} exceeds {max_input} bytes; "
            "shrinking orientation header",
            file=sys.stderr,
        )
        if orientation_budget <= 0:
            return ticket_prompt
        return f"{self.build_orientation_header(max_bytes=orientation_budget)}{ticket_prompt}"

    @staticmethod
    def _ticket_to_yaml(ticket: dict) -> str:
        return _yaml.dump(ticket, allow_unicode=True)
