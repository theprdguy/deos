# user-outcome-review Gate

## Purpose

`user-outcome-review` is an in-the-loop completion gate for tickets whose result must be inspected by the user before final `done` status. It is designed for Type B failures: work that passes automated checks but is visibly or behaviorally wrong at the final outcome boundary.

## Ticket Schema

The gate is enabled only when a ticket defines `screenshot_tool`.

```yaml
screenshot_tool: playwright | detox | maestro | simctl | eas_preview
device_target: web | ios_sim | android_emu | physical
```

Both fields are optional for backward compatibility. Tickets without `screenshot_tool` skip the gate.

Invalid enum values fail validation before dispatch or review.

## Ownership Split

OS responsibility:
- Detect eligible e2e tickets at the close point after handoff `Block: none` and verify gates pass.
- Run the configured capture branch.
- Ask the user for `OK` or `reject`.
- Mark the ticket `done` only after `OK`.
- On rejection, auto-draft a fast-follow ticket and block the source ticket.

Project responsibility:
- Choose the capture tool and device target.
- Provide project-specific setup, fixtures, screenshots, diffs, simulator state, or preview links.

## Tool Branches

| `screenshot_tool` | Intended target | Default command |
|---|---|---|
| `playwright` | Web UI | `npx playwright test --headed --reporter=line` |
| `detox` | React Native iOS/Android | `npx detox test` |
| `maestro` | React Native / mobile flows | `maestro test .` |
| `simctl` | iOS simulator screenshot | `xcrun simctl io booted screenshot devos/review-artifacts/{ticket}.png` |
| `eas_preview` | Expo/EAS preview metadata | `eas update:list --limit 1 --non-interactive` |

Set `OS2_USER_REVIEW_CAPTURE_CMD` to override the default command for a project.

## Graceful Skip

The gate skips with a stderr warning when:
- `screenshot_tool` is not set.
- The configured tool executable is not installed.
- The capture command fails or times out.

This preserves backward compatibility and allows non-UI projects to keep using stdout, curl, or other project-specific review workflows without adopting the enum.

## Decision Flow

Run:

```bash
make user-review T=T-XXX
```

Accepted decisions:
- OK: `ok`, `pass`, `accept`, `accepted`, `y`, `yes`
- Reject: `reject`, `fail`, `no`, `n`

For automation or tests:

```bash
OS2_USER_REVIEW_DECISION=ok make user-review T=T-XXX
OS2_USER_REVIEW_DECISION=reject make user-review T=T-XXX
```

On `OK`, the gate passes. During dispatch, this allows the dispatcher to mark the ticket `done`.

On `reject`, the dispatcher:
- Creates a parked fast-follow draft ticket with id `{source}-FF-{timestamp}`.
- Blocks the source ticket with `_blocked_reason: user_outcome_rejected: fast-follow draft ...`.
- Leaves CLAUDE1 to review and activate the draft.

## Dispatch Integration

When an agent completes with `Block: none` and verify gates pass:

1. If `screenshot_tool` is unset, skip.
2. If the tool is missing, warn and skip.
3. If the capture succeeds and `OS2_USER_REVIEW_DECISION=ok`, mark `done`.
4. If the capture succeeds and `OS2_USER_REVIEW_DECISION=reject`, draft fast-follow and block.
5. If no user decision is available in the noninteractive dispatcher process, block as `user_outcome_review_pending` and instruct the operator to run `make user-review T=T-XXX`.

