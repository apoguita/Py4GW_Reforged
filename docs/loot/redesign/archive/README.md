# LEGACY — superseded, not the basis for the new class

Everything in this folder is **historical**. The loot class is being constructed fresh, guided by the
owner; these documents are **not** the design and must not be treated as decisions.

Why they were retired: they accumulated inferred design, reframed decisions the owner had already
settled, and were written before the system was properly understood. An implementation built from them
was reverted.

**What is still worth reading here — facts, not design:**

- `how-it-works-today.md` — a line-cited audit of the *existing* system, corroborated against the
  code. Useful as reference for how things work today; every claim carries a `file:line`. Note it also
  records where earlier versions of these docs were **wrong** (marked `[was wrong]`).
- The former grouping, salvage, and drop-information exports were deliberately
  removed from documentation. They had no live consumer and were data, not
  design. The source audit and current owner remain the evidence to consult.

**What to ignore here:** `index.md`, `loot-redesign.md`, `structure-and-build.md` as design
authorities. They contain proposals, structures and build orders that are superseded.

The new work lives in the parent folder.
