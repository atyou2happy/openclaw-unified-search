---
name: zsc-help
description: Skill for introducing zsc and its usage to the user. Use when the user asks what zsc is, how to use zsc, how to use zsc skills, or wants an overview of zsc commands and the corresponding AI skills.
---

# zsc-help

**When first mentioning the tool, write zsc(zig slice code); then zsc is fine.**

This skill provides usage guidance only (no file edits).

## Scope boundary (mandatory)

- Introduction/suggestions only.
- Do not create tasks, edit task files, or change code.

## Core skills (unified behavior)

- `zsc-create-rfc`: create/design in-repo RFCs under `docs/rfcs/`.
  - RFCs are specification documents, not TODO lists.
  - They should define goals, non-goals, current state, proposal, compatibility, security, observability, testing, and rollout.
  - They can later drive `zsc-create-task-group`.
- `zsc-create-task`: create/design task docs under `.agents/tasks/` only.
  - Analysis/design must be completed during creation.
  - TODOs must be executable engineering items.
  - Forbidden TODO intent: analysis-only, design-only, documentation-only, task-management-only.
  - Each TODO must include target path/module + concrete action + acceptance criteria.
- `zsc-create-task-group`: create/design one task-group under `.agents/task-groups/` and split it into real child tasks under `.agents/tasks/`.
  - Group level is for scope, workstreams, dependencies, and task references.
  - Child tasks must still satisfy the same quality bar as `zsc-create-task`.
- `zsc-update-task`: edit existing task docs only.
  - Same TODO quality bar as `zsc-create-task`.
  - Updated task should be directly runnable by run skills.
- `zsc-run-task`: interactive execution.
  - No summary-only responses.
  - Default is continuous execution across TODOs, not one-and-stop.
  - Pause only on real blockers (permission, missing required input, reproducible env failure, high-risk action).
- `zsc-run-task-to-complete`: high-automation execution.
  - Primary objective is to eliminate TODO_LIST, not restate task text.
  - Keep executing until cleared or truly blocked.
  - Mark blocked only after concrete attempt + reasonable retry.
- `zsc-run-task-group-to-complete`: high-automation execution for one task-group.
  - Read group dependencies first, then keep advancing executable child tasks.
  - Sync group status after each task until the whole executable set is done or truly blocked.
- `zsc-task-list`: list tasks.
- `zsc-task-status`: task health summary.
- `zsc-help`: this help.

## Recommended flow

1. Write a spec / proposal: `zsc-create-rfc`
2. New work item: `zsc-create-task`
3. Multi-task initiative / RFC decomposition: `zsc-create-task-group`
4. Task refresh/replan: `zsc-update-task`
5. Stepwise execution: `zsc-run-task`
6. Autonomous completion: `zsc-run-task-to-complete`
7. Group-wide autonomous completion: `zsc-run-task-group-to-complete`
8. Overview: `zsc-task-list` / `zsc-task-status`

## CLI mapping (short)

- `zsc init .`
- `zsc rfc new <title>` ↔ `zsc-create-rfc`
- `zsc task new <feat_name>` ↔ `zsc-create-task`
- `zsc task update [TASK]` ↔ `zsc-update-task`
- `zsc task list` ↔ `zsc-task-list`
- `zsc task status` ↔ `zsc-task-status`
- `zsc group new <group_name>` ↔ `zsc-create-task-group`
- `zsc group run [GROUP]` ↔ `zsc-run-task-group-to-complete`

`zsc-run-task` and `zsc-run-task-to-complete` remain single-task AI execution skills.
