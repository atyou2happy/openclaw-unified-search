---
name: zsc-task-status
description: Skill for project-level task health summary. Installed by `zsc init`; corresponds to `zsc task status`. Use when the user wants a summary of how many tasks are completed, open, or unknown, or wants a "task health" view of the project.
---

# zsc-task-status

Helps summarize project task health under `.agents/tasks`. This skill is installed by `zsc init` and aligns with the CLI command `zsc task status`. Here, `zsc` stands for **zig slice code**.

## ⚠ Scope boundary (mandatory, highest priority)

**Whenever this skill is used, regardless of the user's prompt:** You may only **summarize** task status (e.g. run `zsc task status` or read task files under `.agents/tasks` to report counts). Do not create, edit, or delete any files under `.agents/tasks`, and do not modify any project code or files outside `.agents/tasks`.

## When to use

- User asks for task summary, task health, or how many tasks are done vs open.
- User wants a high-level view of project progress (e.g. "3 completed, 2 open").
- User wants to know overall status of `.agents/tasks` without reading each task.

## What the command does

`zsc task status [path]`:

- Scans all `task_*` directories under `.agents/tasks`.
- For each task, reads the task file (canonical: `task_{no}_{feat}.md`, same as directory; legacy `task.md` supported) and classifies as completed / open / unknown (same rules as `zsc task list`).
- Prints a summary: total, completed, open, unknown.

## Example output

```
[zsc] Task status summary for /path/to/.agents/tasks:
  - total:     5
  - completed:  2
  - open:       2
  - unknown:    1
```

## Suggestions for the AI

- To get the summary, suggest or run: `zsc task status` (or `zsc task status .` from project root).
- Use this when the user cares about counts or health, rather than the full list (use `zsc task list` for the per-task list).
