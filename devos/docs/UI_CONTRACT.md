# UI Contract — SSOT

> Claude 2 or Codex must update this file BEFORE changing UI behavior.

## Global UI States (mandatory)
Every screen must handle:
- loading
- empty
- error (with retry)
- success

## Screens (placeholder)
| Screen | Route | Primary action | Empty copy | Error copy |
|---|---|---|---|---|
| Home | / | (TBD) | "Nothing here yet." | "Something went wrong." |

## Accessibility baseline
- Buttons have accessible names
- Errors are announced (aria-live)
- Keyboard navigation supports primary flows
