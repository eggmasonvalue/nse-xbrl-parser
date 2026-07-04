# AGENTS.md

Agent-maintained docs are for durable context only. Code is the source of truth;
docs route agents and preserve non-obvious project rationale.

## Guardrails

- Never commit directly to `main`; work on a branch and open a PR.
- Keep changes scoped; avoid incidental refactors.
- Verify behavior with commands before documenting claims.

## Read routing

- Read `context/MAP.md` before changing module layout, ownership, or data flow.
- Read `context/DECISIONS.md` before changing a recorded tradeoff.
- Read `context/CONVENTIONS.md` while writing or editing code.
- Run `todo list` at task start; `todo claim <id>` before editing orchestrated
  todos.

## Write triggers

- `context/MAP.md`: files/modules added, removed, moved, or data flow changed.
- `context/DECISIONS.md`: only choices that pass the decision-log bar below.
- `context/CONVENTIONS.md`: new repeatable coding/testing rule.
- `README.md`: user-facing setup or usage changed.

## Decision-log bar

`context/DECISIONS.md` is a curated ADR file, not a worklog. Append only when a
choice changes architecture, public behavior, data shape, dependency ownership,
or an expensive migration path **and** future agents need non-obvious rationale
to avoid re-litigating it.

Do not append decisions for bug fixes, cleanup, dead-code removal, renames,
mechanical refactors, one-feature implementation tactics, or routine test/lint
chores. Before appending, prefer amending or superseding an existing decision.
When in doubt, do not append; keep task-local rationale in the todo, PR, commit
message, or final response.

## What not to document

- Changelogs/worklogs; git already has history.
- Feature/status checklists duplicated from code/tests.
- Restatements of obvious code behavior.
- Decisions that fail the decision-log bar.

## CONVENTIONS vs DECISIONS

- `CONVENTIONS.md` contains terse imperative rules only.
- Rationale belongs in `DECISIONS.md` only if it passes the decision-log bar.

## Todos ↔ Decisions

Use todos as stateful task records, not scratch notes. Keep live working context
in the todo body. Before closing a todo, graduate durable rationale to
`context/DECISIONS.md` only if it passes the decision-log bar.

## Definition of Done

Code, tests/lint, and durable docs must agree. If a change passes the
decision-log bar, its rationale must be recorded before the task is done.
