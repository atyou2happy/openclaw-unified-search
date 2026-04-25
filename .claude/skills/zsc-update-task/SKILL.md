---
name: zsc-update-task
description: Skill for updating an existing task's content (闭环描述, TODO_LIST, etc.) when it becomes stale. Edit-only; does not execute TODOs—use zsc-run-task for execution. Use when the user wants to refresh a task's context, update 闭环描述 or TODO_LIST, or revise task design without running the task.
---

# zsc-update-task

**Scope: update (edit) an existing task only.** This skill revises task documents under `.agents/tasks/` so they remain accurate and executable. It does **not** implement TODOs.

## Scope boundary (mandatory)

When this skill is active:
- Allowed: read codebase for context, edit only the selected task files under `.agents/tasks/`.
- Not allowed: create new tasks, execute TODOs, or modify code outside `.agents/tasks/`.

## Primary objective (mandatory)

The updated task must be directly runnable by `zsc-run-task` / `zsc-run-task-to-complete`.

This means:
- 闭环描述 is current and complete.
- TODO_LIST is executable engineering work, not planning text.

## TODO_LIST quality rules (mandatory)

When editing TODO_LIST, enforce the same standard as `zsc-create-task`:

- Forbidden TODO intent:
  - analysis/research-only
  - design-discussion-only
  - documentation-only
  - task-management-only (e.g. "create another task")
- Every TODO must include:
  - Target file/module/path
  - Concrete action (`add`, `modify`, `refactor`, `remove`, `wire`, `configure`, `test`)
  - Verifiable done criteria (tests/build/behavior check)
- Split vague/oversized TODOs into smaller executable items.
- Remove stale TODOs that no longer match current codebase state.

## Multi-touchpoint consistency (mandatory)

If delivery requires multiple touchpoints (source, registration/wiring, packaging/manifest, tests), ensure TODO_LIST/闭环描述 explicitly covers each touchpoint so execution phase cannot miss one.

## Workflow

1. Identify the task file to update.
2. Read current 闭环描述 + TODO_LIST and relevant code context.
3. Update 闭环描述 to reflect current lifecycle and touchpoints.
4. Rewrite TODO_LIST to executable engineering items only.
5. Keep maintenance note in TODO_LIST:
   - `> 只维护最新版本；完成后清空 TODO，仅保留"完成记录 + 日期"。`
6. Save task file changes under `.agents/tasks/` only.

## Update checklist (before finish)

- No TODO item is analysis/design/doc-only.
- Each TODO has target + action + acceptance criteria.
- TODO order is runnable from top to bottom.
- No TODO depends on unstated assumptions.
- Task is ready for immediate execution by run skills.

## Notes

- `zsc-update-task` edits task content only.
- Use `zsc-run-task` / `zsc-run-task-to-complete` to execute TODOs.
