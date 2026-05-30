# Contributing

## Core rules
- Keep SSOT under `devos/`
- 1 ticket = 1 PR
- Update contracts when API/UI behavior changes
- Use A-Mode: queue questions in `devos/questions/QUEUE.md`
- New tickets must use `status: todo`
- Approval required before dispatch (`os3 approve`)

## Workflow
1. Claude 1 decomposes PRD into tickets → saves to `devos/plans/pending/`
2. Review with `os3 pending` → approve with `os3 approve`
3. Builders work in parallel, each within their ticket's `files:` scope
4. Gate pipeline runs automatically (tests → secrets → agent-review → verify)
5. Claude 1 reviews PRs before merge

## Fork / adapt
If you fork this OS for your own use:
- Keep the `devos/` structure — it's the communication channel
- Wire `os3 test` and `os3 scan-secrets` to your actual stack
- Configure `osn.yaml` defaults and per-project `.os3.yaml` gate overrides
- Reset `devos/tasks/QUEUE.yaml` to empty (`tickets: []`)
