# Contributing

## Core rules
- Keep SSOT under `devos/`
- 1 ticket = 1 PR
- Update contracts when API/UI behavior changes
- Use A-Mode: queue questions in `devos/questions/QUEUE.md`
- New tickets must use `status: todo`
- Approval required before dispatch (`make approve`)

## Workflow
1. Claude 1 decomposes PRD into tickets → saves to `devos/plans/pending/`
2. Review with `make pending` → approve with `make approve`
3. Builders work in parallel, each within their ticket's `files:` scope
4. Gate pipeline runs automatically (tests → secrets → agent-review → verify)
5. Claude 1 reviews PRs before merge

## Fork / adapt
If you fork this OS for your own use:
- Keep the `devos/` structure — it's the communication channel
- Wire `make test` and `make scan-secrets` to your actual stack
- Update `os2.yaml` agent configs for your environment
- Reset `devos/tasks/QUEUE.yaml` to empty (`tickets: []`)
