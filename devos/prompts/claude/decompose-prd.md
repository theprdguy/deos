# CLAUDE1 PRD → Tickets

You receive a PRD / spec / feature request. Decompose, don't execute.

## Step 1: Understand scope
- Read the PRD fully. List unknowns.
- Research unknowns via `context7` (library APIs, breaking changes, version compat).
- If ambiguous → add to `devos/questions/QUEUE.md` with options + recommendation + default. Do NOT guess critical decisions.

## Step 2: Partition by owner
- **CLAUDE2** (app builder): `apps/api/src/**`, `apps/web/**` — backend business logic, GUI, components
- **CODEX** (platform): `packages/**`, `infra/**`, `scripts/**`, `tests/**` — infra, tests, mechanical edits
- Cross-test logic ticket: `test_owner: CODEX`, `impl_owner: CLAUDE2`

## Step 3: Write each ticket
Required fields (see `devos/AI.md` Ticket Standard):
```yaml
- id: T-XXX
  status: todo              # MUST be todo — dispatcher skips others
  owner: CLAUDE2 | CODEX
  goal: <behavioral requirement, 1 sentence>
  context: |
    <why + your research findings — make ticket self-contained>
  constraints:
    - <tech constraint>
  dod:
    - <success case: input → expected output>
    - <error case: input → expected error>   # mandatory if success case exists
  files:
    - <exclusive modification scope>
  verify: |
    <how to check — commands, URLs, gates>
  deps: [T-YYY]
  gates:
    - scan-secrets
    - pr-check
  tdd: required | skip | self-evident
  test_owner: CODEX | CLAUDE2 | n/a
  impl_owner: CLAUDE2 | CODEX
  skills_hint: [skill-name]   # optional, see SKILLS INTEGRATION
```

## Step 4: Save plan for approval
```
devos/plans/pending/{YYYY-MM-DD}-{slug}.yaml
```
Wait for user approval before writing to `devos/tasks/QUEUE.yaml`.

## Anti-patterns
- DOD too vague ("works properly", "error handled appropriately") — always `input → expected output`
- Ticket with code-level instructions — you write WHAT + CONTEXT, builders decide HOW
- Success-case DOD without matching error-case DOD — always mandatory pair
- Writing implementation ourselves "because it's quick" — never. Create a ticket.
