# Py4GW Skill Authoring Guide

Status: proposed; adopt with the agent-environment roadmap
Scope: repository workflows under `docs/py4gw-ai/skills/`
Authority: `AGENTS.md`, the current Py4GW AI guides, and the skill surface
described by current Codex documentation

## Decide the Right Surface First

Use the smallest durable surface that solves the problem:

| Need | Use | Do not use |
|---|---|---|
| Repository-wide behavior or safety rule | `AGENTS.md` | A skill that might not load. |
| Stable rule for one code subtree | Nested `AGENTS.md` | A global rule that pollutes unrelated work. |
| Repeatable workflow with selective context | Skill | A giant root contract. |
| Detailed evidence, research, or reference | `docs/py4gw-ai/` or owning topic docs | A skill that duplicates volatile facts. |
| Live data or controlled external/runtime action | MCP tool/server | Prompt text pretending to be an API. |
| Scheduled observation or reminder | Automation | A permanent agent loop. |
| Portable bundle for other repositories/users | Plugin | A one-off repository skill. |

## The Skill Contract

Create a skill only when all of these are true:

1. Users can recognize the task by a stable goal.
2. The task recurs or has enough risk to deserve a repeatable workflow.
3. The workflow needs more context than the root contract should always carry.
4. It has a clear owner, evidence path, mutation boundary, and completion
   report.
5. It can be tested against at least one positive and one negative prompt.

Avoid skills named after an implementation directory, a model, or a vague role.
`py4gw-runtime-investigation` is a useful goal; `gw`, `helper`, and `researcher`
are not.

## Recommended Layout

```text
docs/py4gw-ai/skills/<lower-kebab-name>/
  SKILL.md
  references/                 # small, stable supporting material only
  scripts/                    # optional deterministic helpers
  templates/                  # optional report/fixture templates
```

Use `SKILL.md` front matter to state a unique name and a description that names
the user's goal and the conditions that should trigger it. The description is
the routing contract; make it concrete enough to avoid loading the skill for
unrelated work.

## Required Sections in `SKILL.md`

1. **Purpose and trigger** - what a user asks for that activates this workflow.
2. **Scope and exclusions** - which layer and outcomes it owns; when another
   skill or the root contract takes precedence.
3. **Evidence order** - current source, native sibling, stubs/build config,
   runtime proof, then legacy parity material.
4. **Workflow** - smallest ordered investigation/change/verification sequence.
5. **Tool and approval boundary** - read-only versus write/runtime/destructive
   operations, and when to stop for confirmation.
6. **Output contract** - owner, files/interfaces, evidence, checks, limitations,
   and next safe action.
7. **References** - links to current topic maps and only the small supporting
   records required repeatedly.

## Authoring Template

```markdown
---
name: py4gw-example-workflow
description: Use when a user asks to <recognizable recurring goal>; routes the
  task to <owning layer> and requires <key evidence/verification>.
---

# Py4GW Example Workflow

## Scope

- Owns: ...
- Does not own: ...

## Evidence Order

1. Current owning source and stubs/build configuration.
2. Reproducible runtime evidence when behavior is runtime-dependent.
3. Legacy source only as parity evidence.

## Workflow

1. Identify ...
2. Read ...
3. Confirm ...
4. Stop for confirmation before ...
5. Verify ...

## Completion Report

Report the owner, evidence, changed interface/files, checks actually run,
runtime limitation, and unresolved assumption.
```

## How to Direct ApoBot

Use normal task language. The most useful requests state outcome, evidence,
scope, and authority:

```text
Investigate why <observable symptom> occurs in <subsystem>.
Use the runtime-investigation workflow. Do not modify code.
Return the owning layer, reproduction/evidence, likely cause, and the smallest
safe native or Python next step.
```

```text
Create a skill for <recurring goal>.
It should trigger when users ask <examples>, use <sources/tools>, never perform
<actions> without confirmation, and report <acceptance criteria>.
First give me the skill contract and overlap analysis; do not create files yet.
```

```text
Implement <change> using <skill>.
One agent owns edits. Delegate only read-only source research and a final diff
review. Run <checks>; do not use the live client.
```

```text
Review this candidate MCP tool.
Classify its risk, specify input/output schema and authorization boundary, and
say whether a skill alone would be enough instead.
```

## Skill Review Checklist

- Is the trigger specific enough to load only for the intended goal?
- Does it route to current docs and owning sources rather than repeat stale
  project facts?
- Does it name the runtime and approval boundary?
- Does it overlap materially with an existing skill or root instruction?
- Does it specify observable verification and a bounded final report?
- Do positive and negative prompt fixtures show that it activates appropriately?

Do not publish, install a plugin, add a hook, or expose a new MCP action merely
because the skill reads nicely. A well-formatted unsafe tool is still a very
polite trap.
