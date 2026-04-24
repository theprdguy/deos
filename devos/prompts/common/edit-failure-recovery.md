# Edit Failure Recovery

Common Edit-tool failures and how to recover. 3 consecutive failures on the same change → stop and report.

## 1. `File has been modified since read`
**Cause**: another process (you on a prior turn, a hook, a user save) changed the file after your Read.

**Recover**:
1. Re-Read the exact same `file_path` (no offset tricks — get the current full/relevant window)
2. Confirm your intended change still makes sense given new content
3. Retry Edit once
4. If it fails again → stop, report the conflict. Do not loop.

## 2. `String to replace not found`
**Cause**: your `old_string` doesn't match byte-exactly. Usually whitespace, a prior edit, or copy-paste line-number prefix contamination.

**Recover**:
1. Grep or Read around the expected location to see the actual current text
2. Check for: leading/trailing whitespace differences, tab vs. spaces, stale prefix (`123\t...` from Read output)
3. Rewrite `old_string` from the verified current content
4. If the content appears to be gone entirely, the edit may have already been applied — verify and skip

## 3. `Multiple matches found` (when `replace_all: false`)
**Cause**: your anchor isn't unique.

**Recover — two options**:
- **Widen the anchor**: include 2–3 surrounding lines to make it unique. Preferred for one-off edits.
- **Set `replace_all: true`**: only when you genuinely want every occurrence changed (renames, etc.). Dangerous for partial refactors.

## Preventive rules
- Edit `old_string` should be **verifiably unique**. Run Grep for the snippet first if in doubt.
- Include 2–3 lines of surrounding context, not just the changed line.
- Never paste line numbers or `cat -n` prefixes into `old_string` — the file itself doesn't contain those.
- After a failed Edit, don't retry blindly. Re-Read, diagnose, then retry once.
