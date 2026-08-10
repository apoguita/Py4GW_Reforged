# Py4GW Documentation Style and Maintenance Guide

**Status:** Current maintenance policy. The existing documentation tree is a
transitioning corpus and is not itself proof that every path or filename meets
this policy.

## Purpose

Documentation must be findable by the question a reader has, not by the
author, the migration batch, or the method used to obtain the evidence. This
guide defines how new records are named, located, linked, reviewed, and moved.
It applies to Markdown and text records, plus helper scripts that explain or
reproduce a documented finding. Documentation is not a data store.

Documentation is navigation and evidence. It never replaces the owning Python
or native source, build configuration, or live injected-client observation.

## The Classification Rule

Every record has three independent properties:

| Property | Question it answers | Where it is represented |
|---|---|---|
| Topic | What is this about? | Directory path |
| Kind | What role does this document play? | Optional child directory and README map |
| Status | How should its claims be treated? | Document header and README map |

Do not use one property in place of another. In particular, reverse
engineering is a research method, not a topic. A UI reverse-engineering record
belongs with UI; an item-modifier reverse-engineering record belongs with
items. Only cross-topic RE methodology may live in a dedicated methods area.

The standard path shape is:

```text
docs/<topic>/<optional-kind>/<lower-kebab-case-name>.<extension>
```

Choose the smallest existing topic that answers a reader's question. Do not
create a top-level topic merely for a project, author, implementation phase,
or evidence method.

## Topics and Document Kinds

Topic folders describe the subject, such as UI, items, loot, automation,
persistence, bridge, game client, architecture, Py4GW AI, or validation. They
must use names a new contributor can understand without repository history.

Use a kind folder only when it makes a topic easier to browse. The controlled
kind names are:

- `guides` — how to use or change a subsystem.
- `reference` — stable factual reference material and API/format catalogues.
- `research` — investigations, reverse engineering, experiments, and findings.
- `plans` — proposed, incomplete, or scheduled work.
- `records` — decisions, handovers, audits, postmortems, and session records.
- `generated` — reproducible derived output.
- `tools` — generators, formatters, probes, and their usage notes.
- `archive` — superseded material retained for provenance.

A topic with only one or two records should not gain decorative kind folders.
Its `README.md` is sufficient until the contents require subdivision.

## Names and Extensions

### Documentation records

- Use lowercase kebab case: `dialog-state-regression.md`,
  `item-modifier-catalog.md`.
- Use Markdown for documentation. Do not store JSON, CSV, or another
  machine-readable dataset under `docs/`.
- A data-producing tool owns its inputs and outputs outside `docs/`; document
  the owner, provenance, and reproduction procedure here instead.
- Use a name that describes the subject and document role. Do not repeat the
  enclosing topic without need.
- Do not use ordinal prefixes such as `01_`, `R3_`, or `v2_`. Record a reading
  sequence in the local `README.md` instead.
- Do not encode status in a filename. Use `Status:` in the document and the
  local README map.
- Use an ISO date only when chronology is essential to discovery, in the form
  `2026-08-05-dialog-state-investigation.md`.
- Spell acronyms in lowercase in paths: `imgui`, `mcp`, `py4gw`, `wasm`.
  Preserve official capitalization in prose and headings.

### Code and generated artifacts

- Python tools use `snake_case.py`, following the repository Python rules.
- Generated files are renamed only by changing their generator and every
  consumer in the same change. Never hand-rename generated output.
- Do not store transient caches, bytecode, live logs, private configuration,
  or machine-readable captures under documentation. The producing tool owns
  its path; the topic README records that contract.

## Required Document Metadata

New and materially revised factual documents begin with a title followed by
these concise fields when applicable:

```text
# Dialog State Investigation

Status: runtime-verified
Scope: native UI callback dispatch
Authority: current native source and injected-client reproduction
```

Permitted status values are `current`, `proposed`, `historical`, `generated`,
and `runtime-verified`. Use more than one only when necessary, for example
`historical; runtime-verified on 2026-08-05`. A plan, handover, or archive must
never silently imply that it describes current behavior.

## README Maps

Every non-trivial topic directory has a `README.md`. It must state:

1. The topic and its boundary.
2. The authority order for claims in that topic.
3. A short map of notable files, their kind, and their status.
4. The current source, native module, generator, or runtime evidence that owns
   the topic when applicable.
5. How to reproduce a runtime finding or refresh tool-owned material.

Keep the root `docs/README.md` focused on entry points and this policy. Do not
turn it into a second documentation index.

## Adding or Moving a Record

Before adding a substantial record or moving any existing path:

1. Identify the topic, kind, status, owner, and intended reader question.
2. Search for existing records before creating a new folder or duplicate.
3. For a move or rename, prepare a complete `old path -> new path` map,
   including generated outputs, tools, source-code references, and inbound
   Markdown links.
4. Move a coherent topic batch; do not relocate a few files and leave an
   orphaned partial category behind.
5. Update every affected README, generator, consumer, and path reference in
   the same change.
6. Update the nearest README and `documentation-index.md` when a top-level
   route changes, verify that old paths no longer resolve, and run
   `git diff --check`.

Preserve historical evidence. Move it into an appropriate `archive` area and
label it; do not rewrite an old plan to resemble a current implementation.

## Review Checklist

- Does the directory answer what the record is about?
- Does the filename follow the appropriate naming convention?
- Are topic, kind, and status kept separate?
- Does the header state status and authority when claims could be mistaken for
  current behavior?
- Are code, generator, runtime-log, and Markdown path references updated?
- Does the nearest README remain a useful map?
- Was `documentation-index.md` updated when a top-level route changed?

If any answer is no, stop the move or addition and fix the documentation
structure before adding more material to it.
