---
name: zsc-run-task
description: Skill for executing a task: implement TODOs, update task file, and mark completion. Use when the user wants to run a task, do the work, implement TODO items, or finish a task. Task creation and design is handled by zsc-create-task.
---

# zsc-run-task

**Scope: execute one existing task.** This skill implements TODOs, updates task progress, and clears TODO_LIST on completion.

## Scope boundary (mandatory)

When this skill is active:
- Allowed: execute one selected task, modify related project code, update the selected task markdown.
- Not allowed: create new tasks; redesign other tasks.

## Execution-first rule (mandatory)

Do not respond with task summary only.

When user asks to run a task, you must:
1. Read TODO_LIST.
2. Perform real implementation for unchecked TODOs (code/config/test changes).
3. Update task file progress.

A pure restatement of task content is considered failure.

## Minimal-interruption rule (mandatory)

Default behavior is continuous execution across TODOs in one session.
Do not stop after one TODO unless:
- User explicitly asks for single-step mode.
- You hit a real blocker: missing permission, missing required external input, reproducible environment/toolchain failure, or high-risk destructive action.

## Task workflow

1. Identify target task and open `{task_dir_name}.md` (or legacy `task.md`).
2. Parse unchecked `- [ ]` TODOs in order.
3. For each TODO, run loop:
   - Implement concrete changes.
   - Run relevant checks/tests when feasible.
   - Update task file (`- [ ]` -> `- [x]` or equivalent done note).
   - Move to next TODO immediately.
4. Continue until TODO queue is empty or truly blocked.

## Blocked policy

A TODO can be marked blocked only after at least one concrete implementation attempt.
When blocked, record:
- What was changed/tried.
- Exact failure signal.
- What is needed to continue.

Do not mark blocked by assumption only.

## Completion rewrite (mandatory)

When no unchecked TODO remains for this round:
1. Rewrite entire `## TODO_LIST` section.
2. Keep note:
   - `> 只维护最新版本；完成后清空 TODO，仅保留"完成记录 + 日期"。`
3. Keep completion marker:
   - `- （本轮已完成，TODO 清空）`
4. Add one dated completion record line.
5. Remove old checkbox items (`- [ ]` / `- [x]`).

## Notes

- `zsc-run-task` executes TODOs; `zsc-create-task` designs tasks.
- Goal is to finish as many TODOs as safely possible in one run, not to pause after each item.
