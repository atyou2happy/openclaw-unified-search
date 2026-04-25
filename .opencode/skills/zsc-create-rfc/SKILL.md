---
name: zsc-create-rfc
description: Skill for creating numbered in-repo RFCs under docs/rfcs. Installed by `zsc init`; corresponds to `zsc rfc new`. Use it to turn a requirement, architecture change, protocol evolution, or engineering governance proposal into a strong technical RFC. This skill creates and designs the RFC only; it does not implement code changes.
---

# zsc-create-rfc

**Scope: create and design RFCs only, without implementing code.** This skill creates numbered RFCs under `docs/rfcs/` and upgrades them into technically rigorous proposals with specification quality.

## Scope boundary (mandatory)

When this skill is active:
- Allowed: read the repository to understand context; create/edit RFC files under `docs/rfcs/`.
- Not allowed: modify project code, task files, or task-group files outside `docs/rfcs/`.
- Not allowed: turn the RFC into a task TODO document.

## Must create a real RFC file (mandatory)

When the user asks to create an RFC, you must create a real file:
1. Preferred: run `zsc rfc new <title>`.
2. Or create manually: `docs/rfcs/rfc_{no}_{slug}.md`.

If no real RFC file exists under `docs/rfcs/`, the work is not complete.

## What an RFC is for (mandatory)

An RFC is not a casual note and not a task-management document. It must:
- Describe the problem and motivation accurately
- Present a proposal that can be reviewed, challenged, and implemented
- State goals, non-goals, compatibility, security, observability, testing, and rollout constraints
- Serve as stable specification input for later task-group / task decomposition

Therefore the RFC must have specification power, not just idea capture.

## Specification quality bar (mandatory)

The default RFC template is strong-spec by design. At minimum it must include:
- `Metadata` with ID, status, authors, reviewers, and dates
- `Goals` and `Non-Goals`
- `Current State`
- `Detailed Proposal`
- `Technical Specification`
- `Compatibility and Migration`
- `Security Considerations`
- `Observability and Operations`
- `Testing and Acceptance`
- `Rollout and Rollback`
- `Alternatives Considered`
- `Risks and Open Questions`

When appropriate, use normative wording:
- `MUST`: required behavior
- `SHOULD`: recommended behavior
- `MAY`: optional behavior

## Accepted input

Input may be:
- A requirement or goal description
- An architecture problem
- An interface or protocol proposal
- An engineering governance proposal
- An existing document path plus extra constraints

If the input is vague, first read repository context and anchor the proposal to concrete modules, interfaces, boundaries, or runtime constraints before writing the RFC.

## Content quality bar (mandatory)

The RFC must not remain high-level and vague. At minimum it should:
- Identify affected modules, directories, boundaries, data flows, or interface contracts
- State core invariants and failure modes
- Explain why alternatives were not selected
- Define compatibility, migration, and rollback strategy
- Define security and observability requirements
- Define testable acceptance criteria

Do not write the RFC as:
- Background-only prose
- Vision-only narrative
- Pure task breakdown
- Slogans without specification constraints

## Status convention

`Status` in metadata should use one of:
- `Draft`
- `Review`
- `Accepted`
- `Implemented`
- `Rejected`
- `Superseded`

New RFCs should default to `Draft`.

## Relation to the task system

- The RFC is a specification and decision document; it does not replace tasks.
- Once the RFC is implementation-ready, it can be decomposed with `zsc-create-task-group`.
- The RFC may include a `Related Task Group` field, but do not place executable TODO lists directly into the RFC.

## Workflow

1. If the RFC file does not exist yet, create `docs/rfcs/rfc_{no}_{slug}.md`.
2. Read the required code and documentation context.
3. Write the problem background, goals, non-goals, and current state.
4. Write the proposal and technical specification.
5. Fill in compatibility, security, observability, testing, rollout, alternatives, and risks.
6. Ensure the RFC can drive later task decomposition.

## Recommended section structure

An RFC should include at least:
1. `## Metadata`
2. `## Summary`
3. `## Motivation`
4. `## Goals`
5. `## Non-Goals`
6. `## Terminology`
7. `## Current State`
8. `## Detailed Proposal`
9. `## Compatibility and Migration`
10. `## Security Considerations`
11. `## Observability and Operations`
12. `## Testing and Acceptance`
13. `## Rollout and Rollback`
14. `## Alternatives Considered`
15. `## Risks and Open Questions`
16. `## Prior Art and References`
17. `## Implementation Notes`

## Notes

- This skill only creates and designs RFCs; it does not execute code changes.
- If the user wants to decompose the RFC into tasks, hand off to `zsc-create-task-group`.
- Keep only the latest valid RFC state and remove clearly stale content.
