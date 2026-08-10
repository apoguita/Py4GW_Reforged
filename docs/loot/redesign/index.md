# Loot redesign — document index

Two documents are current. Everything else is history.

| document | what it is | authority |
|---|---|---|
| **`class.md`** | **The plan — the *what*.** Every behavioural decision, settled with the owner. | Authoritative. Do not re-open a decision recorded here. |
| **`implementation-spec.md`** | **The *how*.** The decision register that must be answered before any code, plus the build order with acceptance gates. | Authoritative. **Implementation may not begin until its register is answered.** |
| `legacy/` | Superseded documents, extracted data, and the record of two reverted implementations. | **Not** a source of decisions. |

## Current state

**No loot code exists.** Two implementations were built from `class.md` and both were reverted; the
repository is at HEAD, running the original `Lootconfig_src.py` and the `LootManager.py` widget.

## Why there are two documents

The plan alone was not enough to build from. Every gap in it became a decision taken silently during
implementation — nine of them, none surfaced before shipping. The result reviewed clean and was
unusable, twice.

So the *what* and the *how* are now deliberately separate, and the how carries one rule:

> **No decisions may be made during implementation.** A question that arises while coding stops the
> work and comes back to the spec to be answered.

## In `legacy/`

- `implementation-audit-vs-plan.md` — the audit of what the second implementation missed, bypassed, or did
  differently. The evidence base for the spec.
- `implementation-log.md` — what the reverted builds contained, kept for the *data* findings
  (catalog defects, placeholder model ids, the dye subsystem), not for design.
- `how-it-works-today.md` — line-cited audit of the **existing** legacy system. Still accurate.
- The former extracted datasets were removed from docs; they were review
  exports, not design authority.
- `index.md`, `loot-redesign.md`, `structure-and-build.md` — superseded design drafts.
