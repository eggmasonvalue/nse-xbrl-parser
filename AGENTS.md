# AGENTS

This repository uses agent-maintained docs. Keep them accurate to code and commit only from feature branches.

## Hard guardrails

- Never commit directly to `master`.
- Always work on a branch and open a PR into `master`.
- Keep documentation updates behavior-preserving unless the task explicitly changes runtime behavior.
- Do not edit `markets-constellation/MIGRATION.md` from this repo workflow.

## Read routing (read only what you need)

- Read `context/MAP.md` before changing module layout, parse flow, or file locations.
- Read `context/DECISIONS.md` before changing an existing tradeoff.
- Read `context/CONVENTIONS.md` while writing code, tests, and tooling commands.
- At task start, run `todo list`; claim the task with `todo claim` before editing.

## Write triggers (event-based)

- Module added/moved/removed, or parse/data flow changed -> update `context/MAP.md`.
- Intentional tradeoff, policy call, or accepted risk -> append `context/DECISIONS.md`.
- New repeatable engineering rule -> update `context/CONVENTIONS.md`.
- User-facing behavior, install, or usage changed -> update `README.md`.

## CONVENTIONS vs DECISIONS

- `CONVENTIONS.md` contains imperative rules only, with no rationale.
- If a rule needs a "because", put the rationale in `DECISIONS.md` and keep only the imperative in `CONVENTIONS.md`.

## Do not document

- Changelog/worklog entries (use git history/PRs).
- Feature-status trackers.
- Restatements of obvious code behavior.
- "Decisions" that have no real tradeoff.

## Todos and durable decisions

- Todos are stateful files under `.pi/todos`; keep active implementation notes in the todo body.
- Closed/done todos are garbage-collected after about 7 days.
- Before closing a todo that involved a real tradeoff, copy the durable decision into `context/DECISIONS.md`.

## Definition of Done

A task is done only when code, tests, and matching durable docs are all updated. If a tradeoff changed and `DECISIONS.md` is not updated, the task is not done.
