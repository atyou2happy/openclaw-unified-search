---
name: zsc-run-task-to-complete
description: High-automation skill for running a task end-to-end. Use when the user wants to let the AI execute as many TODOs as safely possible in one go, with minimal interaction. Task creation and design is handled by zsc-create-task; interactive execution is handled by zsc-run-task.
---

# zsc-run-task-to-complete

**Scope: high-automation execution to clear TODO_LIST.** Execute one task end-to-end with minimal interaction.

## Scope boundary (mandatory)

- Allowed: execute one selected task; change related project code/tests/config; update that task markdown.
- Not allowed: create new tasks; redesign other tasks.

## Primary objective (mandatory)

Primary objective is to implement TODOs and eliminate TODO_LIST, not to summarize task text.

Therefore:
- Do real edits before reporting progress.
- Continue automatically across TODOs.
- Stop only for true blockers or dangerous actions.

## Continuous execution loop

1. Parse unchecked TODO queue.
2. For each TODO:
   - Execute concrete code/config/test actions.
   - Run checks/tests when feasible.
   - Mark done in task file.
   - Move to next TODO immediately.
3. Repeat until queue is empty.

## Anti-premature-stop rule (mandatory)

Do not stop because of generic uncertainty.
Only pause if one of these applies:
- Missing required user input that cannot be inferred.
- Missing permission/access.
- Reproducible environment/toolchain failure after retry.
- High-risk destructive or production-impact operation.

## Blocked policy (mandatory)

Before marking blocked, do at least one concrete implementation attempt and one reasonable fix/retry.
Record in task file:
- Attempted changes/commands.
- Error output summary.
- Next required condition.

## Completion rewrite (mandatory)

When no unchecked TODO remains for this round:
1. Rewrite `## TODO_LIST`.
2. Keep note:
   - `> 只维护最新版本；完成后清空 TODO，仅保留"完成记录 + 日期"。`
3. Keep marker:
   - `- （本轮已完成，TODO 清空）`
4. Add one dated completion line summarizing execution outcome.
5. Remove old checkbox items.

## Relation to zsc-run-task

- `zsc-run-task`: interactive step-by-step mode.
- `zsc-run-task-to-complete`: autonomous continuous mode, maximize completion in one session.
