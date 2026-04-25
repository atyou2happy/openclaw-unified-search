---
name: zsc-create-task-group
description: Orchestrator skill built on top of zsc-create-task. Use it to create a task-group under .agents/task-groups from an RFC or prompt, and split it into a set of executable tasks under .agents/tasks. This skill only creates and designs the group and child tasks; it does not execute TODOs.
---

# zsc-create-task-group

**Scope: create and design a task-group plus its child tasks, without executing TODOs.** This skill creates a task-group under `.agents/task-groups/` and uses `zsc-create-task` standards to produce a set of tasks under `.agents/tasks/`.

## Composition rule (mandatory)

This skill is not a replacement for `zsc-create-task`; it is a higher-level orchestrator:
- The task-group captures source, scope, decomposition, dependencies, and task references.
- Each child task must still be created with the same structure and quality bar required by `zsc-create-task`.
- Do not stuff task-level implementation TODOs into the task-group markdown.

## Scope boundary (mandatory)

When this skill is active, you may only operate under:
- `.agents/task-groups/`
- `.agents/tasks/`

Allowed:
- Create/edit task-group directories, group `.md`, and `group_records/log/`
- Create/edit the task directories and task `.md` files referenced by the group

Not allowed:
- Modify project code or files outside `.agents/task-groups/` and `.agents/tasks/`
- Execute any task TODOs

## Accepted input

Input should be one of:
- An RFC document path
- A prompt or goal description
- An RFC plus extra constraints

If the input is an RFC, first extract:
- In-scope goals
- Out-of-scope items
- Workstreams / milestones
- Dependencies
- The set of tasks that should exist

## Required creation result (mandatory)

When the user asks to create a task-group, you must create all of the following for real:

1. Task-group directory:
   - `.agents/task-groups/group_{no}_{group_name}/`
2. Main group file:
   - `.agents/task-groups/group_{no}_{group_name}/group_{no}_{group_name}.md`
3. Group records directory:
   - `.agents/task-groups/group_{no}_{group_name}/group_records/log/`
4. A real set of tasks:
   - `.agents/tasks/task_{no}_{feat_name}/`
   - `.agents/tasks/task_{no}_{feat_name}/task_{no}_{feat_name}.md`

If only the group markdown exists and no real child tasks were created, the work is not complete.

## Task-group design quality bar (mandatory)

Before creating child tasks, finish the group-level design and write it into the group markdown.

The group should contain only:
- Source RFC / prompt
- Goals and non-goals
- Workstreams / milestones
- Child task list
- Dependency graph
- Status summary rules

Do not place the following in group task items:
- Code-level TODO details
- Management-only actions like analysis, research, writing docs, or splitting again later
- Closed-loop implementation details that belong to an individual task

## Child task splitting rules (mandatory)

Each child task must:
- Be a single engineering closed loop that `zsc-run-task` or `zsc-run-task-to-complete` can execute independently
- Have a clear boundary with minimal overlap with other tasks
- Have explicit dependencies so it can fit into group order
- Still obey the `zsc-create-task` TODO_LIST rules

Recommended sizing:
- A task-group usually contains 3-10 child tasks
- Each child task should still be an engineering unit roughly sized for 1-2 hours
- If a child task is still too large, split it into multiple tasks instead of pushing detail back into the group

## Task-group structure

- Directory name: `group_{no}_{group_name}`
- Group file name: `{group_dir_name}.md` and it must match the directory name

The group file must contain:
1. `## 来源`
2. `## 目标`
3. `## 非目标`
4. `## Workstreams`
5. `## Tasks`
6. `## 依赖关系`
7. `## 状态汇总`

## Tasks section rules (mandatory)

Each item under `## Tasks` must include at least:
- Task name
- Task file path
- Workstream ownership (optional but recommended)
- Initial status

Recommended format:

```markdown
- [ ] `task_012_go_platform_bootstrap`
  Path: `.agents/tasks/task_012_go_platform_bootstrap/task_012_go_platform_bootstrap.md`
  Workstream: WS1
  Status: todo
```

## Status summary rules

The group does not track code-level TODOs. It tracks task-level status only:
- `todo`: task has not started
- `doing`: task is in progress
- `done`: task is finished and its TODO_LIST has been cleared
- `blocked`: task is paused due to a real blocker

## Workflow

1. Read the RFC or prompt and extract scope plus non-goals.
2. Design the task-group structure, workstreams, and dependencies.
3. Create the task-group directory, main file, and records directory.
4. Split the work into child tasks.
5. For each child task, use the `zsc-create-task` quality bar and create the real task files.
6. Register all task references and initial statuses in the group markdown.

## Template

```markdown
# Task Group {no}: {group_name}

## 来源

- RFC: `docs/...`
- Prompt: `...`

## 目标

- ...

## 非目标

- ...

## Workstreams

- WS1: ...
- WS2: ...

## Tasks

- [ ] `task_012_xxx`
  Path: `.agents/tasks/task_012_xxx/task_012_xxx.md`
  Workstream: WS1
  Status: todo

- [ ] `task_013_xxx`
  Path: `.agents/tasks/task_013_xxx/task_013_xxx.md`
  Workstream: WS2
  Status: todo

## 依赖关系

- `task_013_xxx` depends on `task_012_xxx`

## 状态汇总

- total: 2
- todo: 2
- doing: 0
- done: 0
- blocked: 0
```

## Notes

- This skill only creates the task-group and child tasks. Use `zsc-run-task-group-to-complete` for execution.
- The design standard for each child task fully reuses `zsc-create-task`; do not lower the quality bar.
- The RFC remains an architecture/scope document and should not be turned into a task-management document.
