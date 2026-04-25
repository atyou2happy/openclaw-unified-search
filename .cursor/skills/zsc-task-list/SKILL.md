---
name: zsc-task-list
description: Skill for listing and browsing tasks under .agents/tasks. Installed by `zsc init`; corresponds to `zsc task list`. Use when the user wants to see all tasks, find a task by name or number, or understand which tasks are open vs completed.
---

# zsc-task-list

Helps list and browse project tasks under `.agents/tasks`. This skill is installed by `zsc init` and aligns with the CLI command `zsc task list`. Here, `zsc` stands for **zig slice code**.  
When there are **many tasks**, this skill should **call `zsc task list` once and let the LLM group tasks** instead of opening each task file individually.

## ⚠ Scope boundary (mandatory, highest priority)

**Whenever this skill is used, regardless of the user's prompt:**

- You may only **list or browse** tasks under `.agents/tasks` (for example: run `zsc task list` or, in rare cases, read specific task files to report details).
- **Do not** create, edit, or delete any files under `.agents/tasks`.
- **Do not** modify any project code or files outside `.agents/tasks`.
- For performance, **do not open N task files one by one** just to build a list. Prefer **a single `zsc task list` call** and analyze its textual output.

## When to use

- User asks to list tasks, show task list, or see what tasks exist.
- User wants to find a task by number (e.g. task_02) or feature name.
- User wants to know which tasks are open vs completed.

## How to get the task list (CLI behavior)

`zsc task list [path]`:

- Scans `.agents/tasks` for directories named `task_*`.
- For each directory, resolves the task markdown file via:
  - canonical `task_{no}_{feat}.md` (same as directory name, e.g. `task_03_init_lang_prompt/md`), or
  - legacy `task.md` as a fallback when present.
- Derives a coarse-grained **status** per task:
  - **completed**: task file contains the marker `（本轮已完成，TODO 清空）` and **no** unchecked `- [ ]` items.
  - **open**: task file contains at least one unchecked `- [ ]` TODO.
  - **unknown**: no task file, or status cannot be inferred.
- Prints a concise list, for example:
  - `[zsc] Tasks under /path/to/.agents/tasks:`
  - `  - task_01_zsc_cli           [open]      Task 01: zsc_cli`
  - `  - task_02_zsc_task_cli      [completed] Task 02: zsc_task_cli`

## Grouping and analysis (LLM behavior)

When there are many tasks, the goal is to **build a grouped “task map”** from a single `zsc task list` run:

1. **Run the command once**
   - Prefer `zsc task list .` from the project root (or `zsc task list <path>` if the project root is different).
   - Capture the full textual output.

2. **Parse the list output**
   - Ignore header lines like `[zsc] Tasks under ...`.
   - For each bullet line, extract:
     - `task_id`: directory name (e.g. `task_04_zsc_task_list_grouping`).
     - `status`: `open` / `completed` / `unknown` from the `[...]` part.
     - `title`: everything after the status, often starting with `Task NN:` in the markdown.

3. **Form groups by relatedness**
   - Prefer groups that help the user understand the project, for example:
     - By **feature / module**: tasks whose IDs or titles share a common slug (e.g. `zsc_cli`, `zsc_task_cli`, `init_lang_prompt`).
     - By **lifecycle / workflow**: tasks that clearly belong to the same workflow step (e.g. “CLI basics”, “task management”, “update flows”).
     - By **status** when lists are long: within each feature/module group, separate `open` vs `completed`.
   - Keep the number of top-level groups reasonable (e.g. 3–7 groups), merging very small or highly similar groups.

4. **Present grouped output**
   - For each group, output:
     - A short **group title** and a one-sentence **summary** (what this cluster of tasks is about).
     - A bullet list of tasks, for example:
       - `- task_02_zsc_task_cli [open]    Task 02: zsc_task_cli`
   - Highlight **open** tasks first inside each group; `completed` tasks can be shown after them.
   - If the list is extremely long, you may:
     - Focus on open tasks plus a brief count of completed ones per group, or
     - Summarize low-priority groups instead of listing every task.

5. **Optional fallbacks**
   - If `zsc` is not available in the environment, explain this clearly to the user.
   - In that case, only read a **small number** of task files directly (for example, specific ones the user mentions) instead of scanning everything.

## Suggestions for the AI

- To get the actual list, **always start** by suggesting or running: `zsc task list` (or `zsc task list .` from the project root).
- Use the command output as the **single source of truth** for task IDs, titles, and statuses, and then build grouped views as described above.
- When discussing tasks, prefer referring to task directory names (e.g. `task_01_zsc_cli`, `task_02_zsc_task_cli`) and their status (`open` / `completed` / `unknown`) as derived from the list output.
