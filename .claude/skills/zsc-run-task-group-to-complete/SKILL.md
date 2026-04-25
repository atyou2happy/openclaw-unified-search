---
name: zsc-run-task-group-to-complete
description: Orchestrator skill built on top of zsc-run-task-to-complete. Use it to read one task-group under .agents/task-groups, execute as many child tasks as possible in dependency order, and continuously write back group status until the whole executable set is finished.
---

# zsc-run-task-group-to-complete

**Scope: high-automation execution of all child tasks within one task-group.** This skill reads an existing task-group, repeatedly uses `zsc-run-task-to-complete` on the referenced tasks, and updates group status until all executable work is finished.

## Composition rule (mandatory)

This skill is not a single-task executor. It is a higher-level orchestrator over `zsc-run-task-to-complete`:
- The task-group defines execution order, dependencies, and overall status.
- Each child task must still be executed according to `zsc-run-task-to-complete` rules.
- Do not skip child tasks and mark the group complete directly in the group file.

## Scope boundary (mandatory)

When this skill is active:
- Allowed: read/update the target task-group, execute its referenced tasks, modify related project code/tests/config, and sync task plus group status.
- Not allowed: create unrelated new tasks, redesign the task-group, or change other groups.

## Accepted input

Input must be one of:
- `.agents/task-groups/group_{no}_{name}/{group_file}.md`
- A clear path or identifier that resolves to one specific task-group

Only ask the user for clarification if a unique group cannot be located.

## Primary objective (mandatory)

The first objective is to eliminate all executable tasks in the group, not to restate the group content.

Therefore:
- Read the group first, then execute tasks.
- Default to running the whole group continuously, not only the first task.
- After each completed task, immediately advance to the next executable task.

## Pre-execution validation (mandatory)

Before execution, you must:
1. Open the group markdown.
2. Parse `## Tasks` and `## 依赖关系`.
3. Determine the task topology / execution order.
4. Verify that each referenced task path exists.

If a referenced task is missing:
- Record it in the group;
- Treat it as `blocked`;
- Continue with other unaffected tasks.

## Continuous execution loop

1. Find all tasks whose dependencies are satisfied and whose status is not `done`.
2. Execute them in group order:
   - Update the task status in the group to `doing`
   - Run that task by using `zsc-run-task-to-complete`
   - Write back group status as `done` or `blocked` based on the actual task file result
3. Refresh the status summary after each task.
4. Continue looking for the next executable batch.
5. Stop only when:
   - All tasks are `done`; or
   - Every remaining task is blocked by dependencies or a real blocker.

## Blocked rules (mandatory)

A task may be marked `blocked` only after all of the following are true:
- `zsc-run-task-to-complete` was actually invoked and attempted
- The task file contains a concrete failure record, error summary, or explicit continuation condition

Do not mark a task as `blocked` merely because of subjective concern or unknown implementation effort.

If a task becomes blocked, you must:
- Record a short blocked reason in the group
- Mark which downstream tasks are affected
- Continue executing other unaffected tasks

## Completion closeout (mandatory)

When all tasks in the group are `done`:
1. Update `## 状态汇总` to the fully complete state.
2. Append one dated completion record to the group file.
3. State clearly that all child tasks were completed in this round.

If the group is not fully complete, the group file must still retain:
- The current status summary
- The blocked task list
- The conditions required for the next continuation

## Group status sync rules

After every task status change, sync all of the following:
- `total`
- `todo`
- `doing`
- `done`
- `blocked`

Task completion is determined by the task file:
- If the task `## TODO_LIST` is cleared and only completion records remain, treat it as `done`
- If the task contains an explicit blocked record, treat it as `blocked`
- Otherwise treat it as `todo` or `doing`

## Workflow

1. Open the group markdown and read tasks plus dependencies.
2. Compute the executable task set.
3. Execute child tasks one by one by using `zsc-run-task-to-complete`.
4. After each task, write back group status.
5. Keep advancing until the group is complete or truly blocked.

## Suggested state format

```markdown
## Tasks

- [x] `task_012_xxx`
  Path: `.agents/tasks/task_012_xxx/task_012_xxx.md`
  Workstream: WS1
  Status: done

- [ ] `task_013_xxx`
  Path: `.agents/tasks/task_013_xxx/task_013_xxx.md`
  Workstream: WS2
  Status: blocked
  Reason: missing database credentials

## 状态汇总

- total: 2
- todo: 0
- doing: 0
- done: 1
- blocked: 1
```

## Relation to other skills

- `zsc-create-task-group`: creates the group and child tasks, but does not execute.
- `zsc-create-task`: creates one task.
- `zsc-run-task-to-complete`: executes one task.

This skill is responsible for advancing the whole group, not for redesigning the group structure.
