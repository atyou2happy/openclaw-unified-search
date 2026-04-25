---
name: zsc-create-task
description: Skill for creating and designing project tasks in .agents/tasks (not executing them). Installed by `zsc init`; corresponds to `zsc task new`. Use when the user wants to create a new task, design the closed-loop description and TODO_LIST, or revise task design. For actually implementing TODOs and running a task, use zsc-run-task instead.
---

# zsc-create-task

**Scope: create and design tasks only.** This skill creates task directories and produces a high-quality 闭环描述 + executable TODO_LIST. It does **not** implement TODOs.

## Scope boundary (mandatory)

When this skill is active, you may only operate under `.agents/tasks/`:
- Allowed: create/edit task directories, task markdown files, and `task_records/log/`.
- Not allowed: modify project code outside `.agents/tasks/`.

## Must actually create task files (mandatory)

When the user asks to create a task, you must create real files under `.agents/tasks/`:
1. Preferred: run `zsc task new <feat_name>`.
2. Or create manually: `.agents/tasks/task_{no}_{feat_name}/`, `task_records/log/`, `task_{no}_{feat_name}.md`.

If files were not created, the task is not done.

## Output quality bar (mandatory)

Before writing TODO_LIST, finish analysis/design internally and encode the result in 闭环描述.

**Do not output TODO items that are mainly about analysis/design/docs/task-management.**
Forbidden TODO intent examples:
- "analyze current code"
- "design方案"
- "write/完善文档"
- "create another task"
- "discuss plan"

## TODO_LIST rules (mandatory)

Every TODO must be a concrete engineering implementation item, directly executable in code/config/module changes.

Each TODO must include:
- Target: specific module/file/path.
- Action: explicit engineering change (`add`, `modify`, `refactor`, `remove`, `wire`, `configure`, `test`).
- Done criteria: verifiable result (test command, behavior check, static check, or build pass).

Additional rules:
- Prefer 4-10 TODOs, each typically finishable within 1-2 hours.
- Split vague/large items into smaller executable ones.
- Do not include long-running observation goals.
- Do not include pure documentation-only TODOs.

## Task structure

Task directory name: `task_{no}_{feat_name}`
Task file name: `{task_dir_name}.md` (same as directory, plus `.md`).

Task file has two sections:
1. `## 闭环描述`
2. `## TODO_LIST`

## Workflow

1. Create task directory and markdown file.
2. Read relevant code context needed for design.
3. Write 闭环描述 with full lifecycle and all project touchpoints.
4. Write TODO_LIST as executable engineering changes only.

## Completion semantics for TODO_LIST section

Always keep this note:

`> 只维护最新版本；完成后清空 TODO，仅保留"完成记录 + 日期"。`

When task is later finished by execution skills, TODOs are cleared and replaced by completion record.

## Template

```markdown
# Task {no}: {feat_name}

## 闭环描述

[Describe the full lifecycle and concrete project touchpoints:
- Create: where resource is created/wired
- Read: where it is consumed
- Update: where it changes
- Delete: where lifecycle closes]

## TODO_LIST

> 只维护最新版本；完成后清空 TODO，仅保留"完成记录 + 日期"。
- （本轮已完成，TODO 清空）

- [ ] [代码] `src/...` 修改/新增 ...；验收：`pytest ...` 通过（或等价验证）
- [ ] [配置] `...` 增加/调整 ...；验收：`zsc ...` 行为符合 ...
- [ ] [测试] `tests/...` 增加 ... 用例覆盖 ...；验收：测试通过
- [ ] [集成] `src/...` 与 `...` 完成注册/接线；验收：端到端路径可用
```

## Notes

- `zsc-create-task` only creates/designs tasks; use `zsc-run-task` or `zsc-run-task-to-complete` to execute TODOs.
- Keep only latest valid task state; remove outdated text.
