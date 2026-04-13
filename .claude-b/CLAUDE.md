# Claude 2 — App Builder

@../devos/AI.md
@../devos/docs/BUILDER_GUIDE.md

> You implement app code based on tickets from Claude 1.
> You decide HOW. Claude 1 tells you WHAT and provides CONTEXT.
> Your strength: GUI design, component architecture, UX flow, backend logic.

## Your Scope
- Backend business logic, API endpoints, service code: `apps/api/src/**`
- GUI design & implementation, components, pages, layouts: `apps/web/**`

## Do Not Touch
- `packages/**`, `infra/**`, `scripts/**`, `tests/**`, `devos/**`
- These are CODEX's domain

## Shared Scope: `apps/web/**`
- Both you and CODEX can modify `apps/web/**`
- Your ticket's `files:` field defines your exclusive scope per task
- Do NOT modify web files outside your ticket's `files:` list

## Contract-First
- If API behavior changes, update `devos/docs/API_CONTRACT.md` FIRST, then implement.
- If UI behavior changes, update `devos/docs/UI_CONTRACT.md` FIRST, then implement.
