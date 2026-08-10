# PR Review Guide: Traceable Refactors and Migration Analysis

Status: current
Scope: proportional review of refactors, migrations, and bounded pull requests
Authority: current implementation, applicable project guidance, and reproducible validation

## Purpose

Use this guide when reviewing a pull request that reorganizes, migrates, extracts, or rewrites an existing feature.

The objective is not only to determine whether the new code works. The review must also determine whether the change remains understandable, traceable, reversible, and safe for future human and AI maintainers.

## Rule status and enforcement

This document defines repository rules and acceptance criteria. It is not a list
of optional discussion points or suggestions for negotiation during review.

Authors must comply with these rules. Reviewers must enforce them and request
changes when a pull request does not comply. Evidence such as runtime
equivalence, AST identity, byte identity, or recoverable Git history may prove
that a rule is satisfied, but it does not waive or renegotiate the rule.

In this document:

- **must**, **required**, and **shall** are mandatory;
- **must not**, **forbidden**, and **not permitted** are prohibitions;
- **prefer** describes the required default when no approved exception exists.

An exception requires explicit maintainer/owner approval and must be documented
with the pull request before implementation. An author’s disagreement with a
rule, or a claim that an alternative is technically equivalent, is not an
exception.

All paths written in review documents, findings, comments, and examples must
be repository-relative. Never include a developer’s username, home directory,
machine-specific drive letter, or absolute local filesystem path. Use paths such
as `Py4GWCoreLib/BuildMgr.py` or `docs/review.md`.

This guide is especially important for migrations from legacy code, architecture changes, framework replacements, and large refactors presented as “no-op” changes.

## Project vision

The preferred change is additive and traceable:

- Preserve the existing source structure whenever practical.
- Keep related changes in the same source file when that allows Git to show the change clearly.
- Make one conceptual change per commit or pull request.
- Preserve method names, call paths, initialization order, and public contracts unless the change explicitly requires otherwise.
- Make the original implementation recognizable while it is being reorganized.
- Keep each intermediate state buildable and testable.
- Prefer a sequence of small, reversible migrations over a parallel replacement implementation.
- Always use an existing project class or approved library when it provides the required capability.
- Extend or modify the provided class/mechanism when the required behavior belongs to it; do not create a replacement copy of equivalent functionality.
- Treat replacement copies and parallel implementations as forbidden by default. They require a documented capability gap, ownership boundary, migration or retirement plan, and explicit maintainer/owner approval.

Runtime equivalence is necessary, but it is not sufficient. A refactor that behaves the same today can still be unacceptable if it destroys source history, hides dependencies, prevents useful review, or makes future regressions difficult to diagnose.

## Scope integrity: one pull request, one purpose

Every pull request must contain one coherent, reviewable purpose: one feature,
one bug fix, one mechanical migration, one infrastructure change, or one
explicitly scoped refactor. A pull request must not bundle unrelated features,
cleanup, relocations, generated data, documentation moves, or opportunistic
fixes merely because they are available on the author branch.

Review the GitHub base-to-head comparison, not only the latest commit or the
lines named in the pull-request description. If that comparison contains
unrelated changes, the pull request is out of scope and must be split or
rebased onto the intended base before approval. Reviewers must not approve one
desirable change while silently accepting unrelated changes attached to it.

A related change may remain when it contributes to the same coherent
user-facing delivery. Do not treat a feature's consumer, shared support code,
configuration, catalog data, or route data as separate features merely because
one could be merged independently. The review question is whether the changed
code works together to deliver one stated outcome, not whether every file is
individually indispensable.

Request a split only when the comparison contains a second independent outcome:
for example, an unrelated bug fix, cleanup, refactor, or feature that neither
contributes to nor changes the behavior promised by the pull request. A broad
parent branch, a convenient working tree, or an author claim that unrelated
code is harmless is not a justification.

### Troubleshooting a mixed-scope pull request

1. Establish the GitHub merge base and head commits, then inspect the complete
   `base..head` file list and commit ancestry.
2. Classify the comparison by delivered outcome. Confirm that related files
   together implement one user-facing feature; follow direct imports and call
   paths only far enough to distinguish that feature from a second independent
   outcome.
3. If an unrelated commit or stacked branch is present, request that the author
   split the work into focused pull requests or rebase the intended feature
   onto the current target branch. Do not accept a promise to address the extra
   code later.
4. Re-review the resulting focused comparison. Verification applies to the
   scoped pull request after the unrelated diff has been removed, not to a
   reviewer-selected subset of the original mixed diff.

Treat an unrelated independent outcome in the submitted GitHub comparison as a
blocker. A large or multi-directory diff is not itself a violation: a coherent
feature may legitimately include a consumer, shared support code, and the data
it exposes. Do not manufacture a scope finding merely because the exact reason
for each related edit is not stated in the description. Review the behavior the
combined diff delivers; request clarification only when that behavior cannot be
determined from the code.

## Proportional scope and review cost

Review the requested change at the smallest scope that can establish correctness.
The commit or pull-request diff is the primary review surface. A large file does
not make the whole file in scope, and a repository-wide feature name does not
authorize a repository-wide investigation.

Use this scope ladder:

1. Changed lines and their containing functions, classes, or declarations.
2. Direct callers, callees, imports, configuration, tests, and owner-controlled
   extension points needed to understand those changes.
3. The affected subsystem only when the diff crosses a runtime, native, UI,
   persistence, bridge, or public-API boundary.
4. Repository-wide analysis only when the change is explicitly cross-cutting,
   a focused check demonstrates a shared failure, or a project rule requires it.

Do not infer a need for full-repository compilation, testing, linting, or system
analysis from the existence of a large file or a broad subsystem name. For a
localized Python change, prefer compilation and Pyright for the changed module
or changed scope, plus the narrowest relevant test. Expand verification only
when the change affects shared APIs, build metadata, native code, injection,
bridge transport, persistence infrastructure, or another boundary whose
consumers cannot be validated locally.

Every review should state what was intentionally not inspected or run when that
omission could otherwise be mistaken for a gap. Unrelated pre-existing issues
must be recorded as baseline evidence, not converted into findings against the
reviewed change.

## JSON classification and placement

Never prescribe a JSON path from its extension alone. Before accepting or
directing a JSON change, identify its owner, whether it is mutable at runtime,
its scope, its schema, and its consumer. The repository-root `json/` tree is a
jail with distinct owners; it is not a generic folder for every JSON-shaped
file.

Classify the file before naming a destination:

1. **Mutable runtime document:** use the concrete `JsonFactory` object. Do not
   hand-write a feature-local path. `JsonFactory(name)` owns account-scoped
   storage under `json/<account>/<name>`; `JsonFactory(name, "global")` owns
   shared storage under `json/Global/<name>`.
2. **Modular behavior-tree recipe:** use `json/modular/<topic>/` only when the
   file satisfies the current modular recipe contract and is consumed by the
   modular JSON compiler. A file that merely contains route notes, captures, or
   metadata is not a modular recipe.
3. **Static feature data consumed by Python:** use typed dictionaries, tuples,
   or a catalog in the owning Python data module. Do not maintain a parallel
   JSON copy beside that module. For example, a dungeon bot's route metadata,
   interaction policies, markers, and captures belong in its explicit Python
   catalog when the bot consumes them as Python data.
4. **Static source, capture, generated output, or reference data that is not a
   Python catalog:** identify the existing generator or source owner before
   choosing a path. If no owner, schema, and consumer exist, do not move the
   file to a guessed `json/` subdirectory; remove it from the feature PR or
   establish the owner in a separately scoped change.

Do not place new JSON beside Python modules merely because a feature needs
data. Older loose placement is not precedent. When relocating an established
JSON document, keep the move focused and update every consumer in the same
change.

## Finding severity and enforcement

Severity describes the material effect of the reviewed change, not how strongly
the reviewer feels about a rule. Enforce mandatory rules, but do so at the
lowest severity that accurately represents the consequence.

- **Blocker / critical:** the changed code creates a credible security issue,
  data loss, unsafe runtime behavior, broken ownership boundary, incompatible
  public contract, or an unverified failure on a required integration path.
- **High:** a material correctness, lifecycle, compatibility, or architectural
  defect in the changed behavior that should be fixed before approval. High is
  not a synonym for “the PR description is imperfect” or “the diff is large.”
- **Medium / requested change:** a real maintainability, traceability, or
  validation gap that should be corrected, but does not itself demonstrate a
  dangerous or broken runtime outcome.
- **Low / note:** wording, optional evidence, or an improvement that does not
  affect approval when the implementation is otherwise compliant.

A documentation mismatch, missing explanation, or disputed classification must
not be reported as High unless it hides a material code or contract defect. If
the implementation satisfies an explicitly requested behavior change, report
the implementation as compliant and, at most, request that the PR description
be clarified. Do not require a code change to correct a metadata-only issue.

When evidence is incomplete, label the conclusion unresolved and run the
smallest check that can resolve it. Do not promote uncertainty to a blocker.

## Reuse existing implementations before creating new ones

Pull requests must first use an existing project mechanism that already
provides the required behavior. This includes core classes, shared utilities,
settings and JSON factories, native bindings, callbacks, queues, UI helpers,
window handling, logging/diagnostic facilities, and approved third-party
libraries already used by the repository.

Always prefer modifying or extending the provided mechanism over creating a
replacement copy. Copies are generally harmful because they create competing
sources of truth, divide fixes, obscure ownership, and make future migration
and review harder.

Do not create a parallel implementation merely because a local version appears
easier to write or more convenient to call. A new implementation is justified
only when the existing mechanism cannot provide the required capability and an
approved exception exists. The pull request should then document:

- which existing mechanism was considered;
- the specific capability gap or incompatible contract;
- why extending or adapting the existing mechanism is insufficient;
- who owns the new implementation;
- how duplicate behavior will be avoided or retired.

This rule applies to both feature code and infrastructure. Custom settings,
JSON/INI handlers, file-backed debuggers, window managers, queues, native
dispatch wrappers, and utility classes are not acceptable substitutes for
existing repository mechanisms without an explicit infrastructure decision.

## Canonical enum and catalog ownership

An enum is the canonical owner of a finite set of named domain identities and
their stable values. Catalogs own metadata about those identities, such as
display names, categories, salvage outcomes, provenance, and search aliases.
They must not quietly become a second enum by storing an equivalent set of raw
integer keys or private name-to-value mappings.

For Py4GW game-domain and CoreLib concepts, add or extend the canonical enum
under `Py4GWCoreLib/enums_src/` and export it through
`Py4GWCoreLib/enums.py` when it is part of the supported Python surface. Do
not define or recreate these identities in a widget, `Sources/` feature
package, generated catalog, or private loader. A feature-local enum is allowed
only for implementation state that has no game-domain, persistence, shared
library, or public-API meaning.

When a catalog needs richer data, it must be keyed by or explicitly reference
the canonical enum value. The catalog may store `int(ModelID.SomeItem)` at a
runtime or serialization boundary, but it must not remove the corresponding
enum member, replace the member with an anonymous integer, or independently
assign its value.

Deleting, renaming, or relocating members of a public enum is a compatibility
change. Preserve the original member or an explicit compatibility alias unless
the pull request documents an approved breaking API migration and updates all
supported consumers.

### Troubleshooting enum and catalog conflicts

When a pull request appears to add a catalog, data table, or loader for named
IDs, review it in this order:

1. Identify the domain identity and locate its canonical enum in
   `Py4GWCoreLib/enums_src/`. Check `Py4GWCoreLib/enums.py`, stubs, and direct
   callers to establish whether it is public.
2. Compare the old and new member sets and values. Search the diff for removed
   enum members, new raw integer keys, duplicate `IntEnum` definitions, and
   private `name -> id` tables. Do not accept a catalog as equivalent merely
   because it preserves the integer values.
3. Decide the owner before proposing a fix:
   - Existing enum is complete: the catalog references it and owns metadata
     only.
   - Existing enum is incomplete: add the missing members to the canonical
     enum, export them where required, then build the catalog from those
     members.
   - The catalog needs extra attributes: add typed catalog records keyed by the
     enum; do not add a private replacement enum or a parallel raw-ID source.
   - A public enum must change: preserve aliases and migration compatibility,
     or stop for explicit maintainer approval of a breaking contract.
4. Verify the repair with focused searches for the removed/redefined member
   names and duplicate values, `git diff --check`, and Pyright/Pylance for the
   changed enum, catalog, and direct consumers.

Treat removal or redefinition of a public, re-exported enum as a blocker. A
private catalog or loader that owns reusable enum-derived data is at least a
requested ownership change, and becomes a blocker when it creates a competing
public contract or leaves the old contract unsupported.

The first observed case was a merchant-rule change that removed wiki
salvage-source `ModelID` members and retained their values only as raw keys in
`SALVAGE_MAP`. The correct repair is to retain the named model identities in
the CoreLib enum and let the item catalog describe their salvage metadata.

## Decide between extension and extraction

Before moving code into a new class or file, answer the architectural question:
can the existing class be extended or modified to provide the required
capability? If yes, extend or modify it. Do not create a new ownership boundary
just because a copy in another file appears cleaner.

Extraction is justified only when another consumer must reuse a defined subset
of the capability without inheriting the original class’s unrelated behavior,
engine, or lifecycle. In that case, the shared class should own the unchanged
implementation and the original class should extend it. The extraction is a
structural ownership change, not a reason to rewrite the method bodies.

When the implementation is byte-identical before and after the move, do not
request retyping, reformatting, or a replacement implementation. Review whether
the new ownership boundary is necessary, whether the host contract is explicit,
and whether initialization, MRO, and call paths remain correct. If no real
second consumer or isolation requirement exists, the correct change is to keep
the code in the existing class and extend that class as needed.

For clarity, a true move removes the implementation from the old owner and
changes which class owns it. A copy leaves two implementations. The latter is
forbidden unless explicitly approved; the former is acceptable when the
ownership change is architecturally required and the implementation remains
unchanged.

## Do not disguise a rewrite as support or compatibility

A module named `Support`, `ReforgedSupport`, `Compat`, `Bridge`, `Adapter`, or
`Fallback` is not a fix merely because it sits beside existing code. It is a
competing rewrite when it reconstructs state, registers its own callbacks or
hooks, independently interprets the same native data, or chooses between a new
path and the old implementation at runtime while leaving the owning code
unchanged.

This pattern is forbidden by default. It bypasses the real defect instead of
repairing it, leaves two lifecycle and state contracts to drift apart, and
makes failure look like an ordinary fallback. Dynamic imports and broad
`except` blocks make the problem worse: they conceal a missing binding,
incorrect initialization order, or broken owner contract rather than exposing
it for repair.

Review a purported support layer as a rewrite, not as a harmless helper, when
any of the following is true:

- it duplicates data or state already owned by an existing CoreLib, native, or
  feature module;
- it installs callbacks, listeners, queues, hooks, or polling independently of
  the existing owner;
- it imports back into a feature consumer in order to emulate the old path;
- it uses runtime availability checks to switch between duplicate
  implementations without an explicit, tested compatibility contract;
- it includes unrelated facilities merely because they are convenient to place
  in the new module.

The required repair is to fix the lowest responsible owner. If the native
binding is absent or wrong, repair and verify that binding first. If the Python
event/state layer interprets the binding incorrectly, extend that existing
owner with the required public API. Consumers then call the corrected owner
directly. Do not add a feature-specific observer, shim, or silent fallback
around it.

Treat a shadow support layer as a blocker when it bypasses a current owner,
creates a second state/lifecycle contract, or hides an unsupported runtime
surface. It may proceed only with a documented, owner-approved compatibility
boundary, one authoritative implementation, a retirement plan for the old
path, and focused verification of both transitions.

## Do not build features around opportunistic attachment points

A feature must not be implemented by searching for incidental override points,
wrapping methods from the outside, monkey-patching classes, shadowing methods,
or intercepting unrelated lifecycle paths merely because those locations are
available. A design does not comply with this policy simply because it uses
existing names or technically attaches to an existing class.

The owning class and its normal extension points must remain the source of
truth. The required order of implementation is:

1. Reuse the existing class and its public API when it already provides the capability.
2. Modify the owning class when the capability is missing or its existing behavior is incorrect.
3. Extend the owning class through an explicit, stable inheritance or composition boundary when the feature intentionally changes or specializes behavior.
4. Add a new shared abstraction only when the ownership/isolation requirement is real and cannot be satisfied by the existing class.

The following patterns are forbidden by default:

- external method replacement or monkey-patching;
- wrappers that bypass the owning class’s normal implementation path;
- overriding incidental methods to inject unrelated policy;
- duplicate helper layers that reproduce the owning class’s logic;
- using private/internal “holes” as the primary integration contract;
- building an entire feature around an accidental callback, lifecycle gap, or side effect instead of adding an explicit extension point.

If the existing class lacks a required extension point, add or modify that
extension point in the owning class. Do not base the feature on a workaround
that exploits the gap. Any required new extension boundary must be explicit,
documented, and owned by the class being extended.

### Hole-based attachment is not an architecture

Some code may technically reuse existing classes while building a feature around
incidental override points, private state, lifecycle gaps, wrappers, or
externally injected policy. Those patterns may appear compliant because they
call existing methods or inherit from existing classes, but they create a
second owner for the behavior.

This is a mandatory repository rule for every pull request and every
contributor. It applies to new features, refactors, extensions, migrations, and
code from any source. Do not introduce or preserve a design that uses an
available “hole” as its primary architecture.
The implementation must use the current owning class and current extension
model:

- If the current class already owns the behavior, call its existing API.
- If the legacy behavior fills a missing capability, add that capability to the
  current owning class or its approved shared library.
- If the behavior intentionally mutates or specializes the class, extend the
  class through an explicit subclass, mixin, composition, or callback contract.
- If multiple classes must share the behavior, create a shared abstraction only
  after establishing that inheritance from the original class would import
  unrelated engine or lifecycle behavior.
- Preserve the current class’s ownership, initialization, dispatch, settings,
  queue, and native-thread contracts while adding or adapting the behavior.

The following approaches are specifically forbidden:

- importing a current class and replacing one of its methods from outside the
  class definition;
- saving the original method, installing a wrapper, and using the wrapper as a
  hidden feature entry point;
- inheriting solely to intercept an unrelated method because it happens to run
  at a convenient time;
- attaching to private fields, private registries, or accidental callbacks
  instead of adding an explicit owner-controlled extension point;
- injecting behavior into a generic lifecycle method that belongs to another
  feature or subsystem;
- maintaining a wrapper that duplicates or shadows current-class behavior while
  claiming to be an adapter;
- copying the current class into a replacement and modifying the copy instead
  of changing or extending the source class.

The implementation is compliant only when a maintainer can identify one
authoritative owner for the behavior and one explicit path by which the feature
reaches that owner. “It uses an existing class,” “it calls the original method,”
or “the override is technically compatible” does not satisfy this rule when the
feature still depends on an incidental attachment point.

## Acceptance rule: traceability must be human-readable

The change must be readable and traceable by a human reviewer in the normal
pull-request diff. A reviewer should be able to understand what moved, what
changed ownership, and what contracts were introduced without reconstructing
the implementation manually.

Human-readable traceability does not mean that every moved method must remain
in the original file, nor does it mean that a legitimate class extension must
be implemented by duplicating or retyping code. When the intended change is a
mechanical extraction into a mixin or base class, byte-identical method bodies,
an explicit host contract, unchanged initialization/call paths, and a clearly
described mapping can provide the required traceability.

Git can often recover the relationship between an old implementation and a new
file by using rename/copy detection, `git blame -C`, `git log --follow`, or a
custom AST comparison. These are useful review aids, but they are not a
substitute for human-readable traceability.

The normal pull-request diff must remain understandable to a human or AI
reviewer without requiring special Git commands or manually comparing two
complete files. A change that appears as a large deletion from the original
file plus a large addition in a new file can be structurally opaque, but that
appearance alone does not establish that the implementation was rewritten.
When the moved lines are byte-identical and the new class boundary is the
intended change, the mechanical evidence may be enough to make the migration
traceable.

This is an approval concern, not an automatic rejection of every file split. A
large diff is a blocker when it hides semantic edits, lifecycle changes,
unresolved dependencies, or a reimplementation behind the appearance of a
move. It is not a blocker merely because a legitimate class extension causes
GitHub to display relocated code as a deletion plus an addition.

Do not accept an author instruction such as “do not read the relocated lines”
as the only review strategy. Reviewers must still be able to inspect the
changed ownership, contracts, imports, inheritance, and lifecycle in the
ordinary diff, while mechanical comparison may establish that the relocated
method bodies themselves were not rewritten.

When a separate file is architecturally useful, that is not automatic approval
or automatic rejection. Prefer same-file reorganization when it preserves the
intended architecture, but allow a separate-file extraction when the new class
or mixin is the actual purpose of the change. The author must make the reason
for the new ownership boundary, host contract, initialization behavior, and
unchanged method mapping clear. Do not require a rewrite or duplicate
implementation solely to make the diff appear smaller.

## Core distinction: logic rewrite versus structural rewrite

Do not accept the author’s description without inspecting the diff.

A pull request may be:

| Type | Meaning | Review expectation |
| --- | --- | --- |
| Additive change | Adds a new path while preserving the existing path | Verify compatibility and controlled adoption |
| Mechanical relocation | Moves code without changing behavior | Require source-level traceability and proof of equivalence |
| Structural refactor | Changes files, classes, inheritance, or ownership | Review contracts, initialization, MRO, and dependency boundaries |
| Semantic change | Changes runtime behavior or policy | Require explicit behavior specification and tests |
| Rewrite | Recreates the feature using a different structure or implementation | Usually request decomposition before approval |

“The method bodies are AST-identical” proves only one narrow property. It does not prove that class construction, method resolution, imports, initialization order, lifecycle, exception behavior, or integration behavior are unchanged.

## Review workflow

### 1. Capture the requested vision before reviewing the implementation

Write down the constraints that the change must satisfy. At minimum, identify:

- Is this a migration, bug fix, extraction, or behavior change?
- Is the existing implementation expected to remain recognizable?
- Is a new file or class actually required?
- Must the old API remain compatible?
- Are scripts being retired, or must they continue to work during transition?
- Are settings, persistence, callbacks, queues, or native bindings subject to repository-specific rules?
- Must the change be pyright/Pylance clean?
- Does the user require the current behavior to remain unchanged?

If the vision is unclear, ask before evaluating architecture. Do not silently replace “migrate” with “rewrite.”

### 2. Establish the baseline

Record the base and head commits, changed files, and working-tree state. Do not make review conclusions from the head branch alone.

Use the merge-base-to-head diff as the primary evidence. If the request names a
specific commit or bounded hunk, review that boundary first and do not silently
expand the scope to the rest of the branch. Read surrounding code only to
establish a direct contract, call path, or ownership fact.

Useful evidence includes:

```text
git status
git log --oneline --decorate --graph --all
git diff --stat BASE...HEAD
git diff --find-renames --find-copies BASE...HEAD
git diff BASE...HEAD -- path/to/feature.py
```

When GitHub data is available, inspect the pull request metadata, complete changed-file list, patch, comments, reviews, base commit, and head commit. If one endpoint is incomplete, use the commit comparison or file contents at both refs.

Preserve unrelated local changes. Review tooling must not reset, restore, or overwrite the user’s worktree.

### 3. Classify the diff by intent

Separate the change into:

- new behavior;
- moved code;
- renamed code;
- deleted code;
- changed contracts;
- changed imports;
- changed inheritance or composition;
- changed initialization;
- formatting or generated noise;
- tests and documentation.

This classification prevents a large movement diff from being incorrectly treated as a harmless no-op.

### 4. Measure traceability

Ask whether a reviewer can follow the old implementation into the new implementation without manually comparing two complete files.

Prefer:

- the same source file for local reorganization;
- small, contiguous extraction blocks;
- unchanged method bodies during a movement-only commit;
- no formatting changes during movement;
- one follow-up commit for architectural adaptation;
- explicit compatibility wrappers during transition.

The requirement is about understanding the review shape, not merely whether Git
can infer a rename. `--find-copies-harder`, `git blame -C`, `git log --follow`,
and byte/AST identity reports may support a review of a mechanical extraction.
They are insufficient when semantic edits or new lifecycle behavior are mixed
into the move, but they are valid evidence when the class extension is the
intended change and the moved implementation is unchanged.

Be cautious when:

- one file loses most of its implementation and another file is created almost entirely with additions;
- methods are moved and reformatted simultaneously;
- class inheritance changes at the same time as code movement;
- behavior changes are mixed into the extraction;
- reviewers must compare two entire files to understand the delta;
- the commit message claims “pure relocation” but adds new lifecycle or dependency behavior.

### 5. Inspect hidden contracts

For extracted classes, mixins, services, and adapters, inventory every dependency on `self` and every external symbol. Do not accept “independent” or “paradigm-agnostic” claims without checking the actual contract.

Look for dependencies on:

- fields initialized by the old owner;
- methods that remain in the old class;
- `super()` behavior;
- class attributes and descriptors;
- callbacks and generators;
- timers, queues, caches, and shared state;
- settings and persistence objects;
- native/game-thread dispatch guarantees;
- account or multibox scope;
- exception and fallback behavior.

A reusable mixin or service should document its required fields and methods, or expose a clear protocol/interface. If it still relies on many owner-specific methods, describe it as an owner-dependent mixin rather than an independent service.

### 6. Check construction and method resolution

Any change such as:

```python
class ExistingClass(NewMixin):
```

requires review even when `ExistingClass.__init__` is unchanged. Check:

- method resolution order;
- duplicate method names;
- `super()` calls;
- constructors and initialization order;
- class scanning or registration logic;
- type checks and `isinstance` assumptions;
- fallback and subclass behavior;
- public method availability;
- serialization or persistence assumptions.

An unchanged constructor does not prove an unchanged object lifecycle.

### 7. Verify claimed no-op behavior

For a claimed no-op refactor, require evidence proportional to the risk:

- compile/import validation;
- pyright/Pylance validation for changed modules;
- existing tests;
- focused before/after tests for moved public methods;
- constructor and lifecycle tests;
- method-set and signature comparison;
- call-path comparison;
- representative runtime smoke tests;
- no unexpected changes in logs, queues, settings, or native dispatch.

These are options, not a blanket suite. Select only the checks justified by the
changed layer and contract. A localized Python extraction normally needs focused
syntax/import validation and Pyright for the changed files or symbols; it does
not require compiling or testing the entire repository unless the diff crosses a
shared boundary or focused evidence identifies a broader impact.

AST or byte comparison is useful evidence for a movement-only refactor. Git
copy/rename detection and blame continuity can further establish provenance.
They do not replace review of file ownership, inheritance, initialization, or
lifecycle changes, but a reviewer should not demand a rewrite when those
contracts are explicit and the implementation is unchanged.

### 8. Check whether the pull request is correctly scoped

A safe sequence commonly looks like this:

1. Preserve behavior in the existing implementation.
2. Reorganize code in place when practical, or obtain explicit approval for a separate-file extraction.
3. Keep the movement stage source-preserving and independently reviewable, with no formatting or unrelated edits.
4. Introduce the new abstraction or second consumer in a separate change.
5. Introduce behavior changes behind an explicit adoption path.
6. Retire compatibility code only after consumers have migrated.

Do not combine all six stages into one “cleanup” pull request.

### 9. Verify default-off and opt-in claims literally

“Disabled by default” is not equivalent to “no-op when disabled.” Inspect the actual call path from the existing runtime entry point.

For an opt-in feature, verify that the disabled path does not unnecessarily:

- instantiate the feature controller;
- enumerate accounts or agents;
- read settings repeatedly;
- update caches, timers, breadcrumbs, or state machines;
- perform native or game-thread calls;
- alter shared-memory values;
- generate debug snapshots or overlays.

If the feature supports a diagnostic-only mode, such as an overlay while behavior is disabled, model the two paths explicitly:

```text
feature disabled + overlay disabled -> return before feature processing
feature disabled + overlay enabled  -> compute diagnostic state only
feature enabled                    -> compute and publish behavior
```

The review must compare the claimed disabled path with the actual call graph. A branch inside a deep controller method does not prove that the caller avoided the cost of constructing the controller, collecting inputs, or mutating state.

### 10. Review cross-cutting changes separately from the new feature

New feature code may be additive while its integration changes existing behavior. Identify edits to shared paths such as:

- generic follow or movement resolution;
- common UI drawing;
- shared-memory publishing;
- global settings;
- command dispatch;
- map and lifecycle handling;
- common utility functions.

Do not allow a new feature to hide unrelated behavioral changes behind its integration. If a general improvement is useful to the new feature, review it as a separate change unless the user explicitly accepts the expanded scope.

### 11. Verify every advertised integration path end to end

When documentation claims that a feature reports, receives, publishes, or synchronizes data, trace the entire path:

```text
producer -> transport or shared state -> receiver -> consumer -> observable effect
```

Check for:

- enum or command definitions;
- serialization and parameter shape;
- sender invocation;
- receiver dispatch;
- state update;
- consumer lookup;
- user-visible or runtime effect;
- retry and failure behavior.

A class that defines a reporter but is never instantiated is not an implemented integration. A command that is sent but absent from the enum or receiver is an incomplete path. Remove unsupported claims or complete the entire path before approval.

### 12. Check ownership and lifecycle transitions

Any feature that writes to shared state, flags, settings, caches, or overlays must define ownership and reset behavior.

Review transitions such as:

- feature disabled after being enabled;
- user input replacing an automatic value;
- map change;
- leader change;
- account or party change;
- publisher restart;
- stale or missing native data;
- exception during a partially completed write.

An ownership boolean alone is insufficient if it does not verify that the observed value still matches the value written by the feature. Automatic state must not overwrite a newer manual value merely because the feature previously owned the field.

### 13. Treat silent exception handling as a review risk

New integration code often uses broad `except Exception: pass` blocks around settings, native access, overlays, and shared-memory operations. These may prevent crashes, but they can also make a feature silently inactive and impossible to diagnose.

For every swallowed exception, ask:

- Is failure safe and intentional?
- Is there a diagnostic status or log?
- Can the user distinguish “feature inactive” from “feature failed”?
- Does partial state need to be rolled back?
- Is the exception hiding a missing binding, enum, or integration path?

Require at least one observable diagnostic path for important feature failures.

### 14. Do not add custom file-backed debuggers or persistence

The repository already provides approved interfaces for persistent data and runtime diagnostics. Pull requests must use those interfaces instead of creating ad-hoc file handlers.

#### 14.1 Enforce the persistence folder jail and owner class

The folder jail is part of the persistence contract, not an implementation
detail:

- INI persistence MUST use the concrete `Settings` class and remains under
  `settings/<email>/<name>` for account scope or `settings/Global/<name>` for
  global scope.
- JSON and structured persistence MUST use the concrete `JsonFactory` class
  and remains under `json/<email>/<name>` for account scope or
  `json/Global/<name>` for global scope.
- JSON has no root scope. The only project-root persistence exception is
  `Py4GW.ini`, accessed only through the hardcoded path-less
  `Settings.py4gw_ini()` accessor.
- No feature code may create, select, or write an alternate persistence path
  outside these class-owned roots.

`Settings` and `JsonFactory` are the jail boundaries. They own path
sanitization, scope validation, account/global isolation, native locking,
autosave, and the Python/native persistence contract. A private
`Protocol`, provider, repository, store, document class, wrapper, adapter, or
other interface that reproduces or hides their persistence methods is not a
compliant substitute, even when it currently delegates to the concrete class.
Delegation does not transfer or preserve the required ownership boundary.

Feature-specific code may validate, normalize, and transform in-memory
values. Persistent reads and writes must remain on concrete `Settings` or
`JsonFactory` objects. If either class or its native backend lacks a required
primitive, stop the feature work and report the capability gap to the owner.
Do not add an extension, handler, alternate path, or private persistence
abstraction in the feature PR. Only a separately approved
persistence-infrastructure change may modify the owning implementation, and
that change must preserve the folder jail.

Forbidden in feature or debugging changes unless explicitly authorized as a separate infrastructure project:

- custom `open()` calls for logs, state, or diagnostics;
- `os.makedirs()` or directory creation for feature-owned data;
- custom file-backed logger classes;
- direct writes through `Path.write_text()`, `Path.write_bytes()`, or equivalent;
- custom JSON or INI serialization;
- feature-specific log rotation, file naming, or retention systems.

Use the existing project mechanisms:

| Need | Approved mechanism |
| --- | --- |
| INI settings | `Settings` with the correct account or global scope |
| JSON data | The repository JSON factory and its approved storage scope |
| Immediate diagnostics | Console/runtime logging already provided by the project |
| Temporary in-memory history | A bounded runtime data structure with an explicit lifecycle |
| Native/UI diagnostics | Existing native bindings, UI logs, or approved diagnostic widgets |

If a new logging or persistence primitive is genuinely required, it must be its own infrastructure PR with an explicit design, lifecycle, scope, retention, failure, and privacy review. It must not be smuggled into an unrelated feature PR merely because the feature needs temporary debugging.

When reviewing a PR, search both the changed files and their new call paths for `open(`, `os.makedirs`, `Path.write`, `json.dump`, `configparser`, and custom logger names. A diagnostic claim does not authorize a new persistence mechanism.

Also verify that every changed persistence path still reaches a concrete
`Settings` or `JsonFactory` object and remains inside its sanctioned folder.
Search for private JSON/INI access contracts such as `JsonDocument`,
`JsonFactoryProvider`, custom `Settings`/`JsonFactory` lookalikes, or generic
`save`/`reload`/`get_json`/`set_json` handlers. Treat these as persistence
ownership violations even when no raw filesystem call is present.

### 15. Match static validation requirements to project tooling

Do not accept “compiles,” “pyflakes passes,” or “AST-identical” as a substitute for the project’s required checks.

For Python changes, pyright/Pylance is mandatory for every changed Python file
included in the pushed commit or pull request. It is not mandatory for unrelated
repository files. Include directly required imported modules only when the
changed contract cannot be checked without them; do not turn that allowance into
a repository-wide scan.

Report the exact changed-file targets and results. For a large changed file,
target the changed symbols when the tool supports it, and compare against a
baseline when diagnostics are pre-existing. A reviewer may accept pre-existing
diagnostics when they are clearly separated from new diagnostics, but new type
errors in pushed files must be addressed or explicitly justified.

Do not run a full-repository compile, lint, or test suite by default. Broaden
verification only when the change is shared, cross-cutting, build-affecting,
native/runtime-facing, or when a focused check shows a broader regression.

### 15.1 Verification budget and reporting

Before running a broad check, identify the changed layer, the failure it is
intended to detect, and why a focused check cannot detect it. If that reason is
not present, keep the check focused. Report both executed and intentionally
omitted checks, with the scope and reason for each.

This review policy does not require behavioral test suites, runtime smoke tests, client-test matrices, or test evidence as a condition of approval. Do not add testing requirements to review comments when the task is a refactor or code review and the user has not specifically requested tests.

If a module is described as pure or offline-testable, inspect its imports. Imports of native-only modules, timers, settings, game enums, or runtime globals may prevent offline testing even when the algorithm itself is pure.

### 16. ImGui owns window persistence and state

For ImGui windows, ImGui is the owner of window persistence and window state. Feature code must not create competing persistence or positioning systems.

Custom window coordinate and status handlers are not permitted for ordinary ImGui windows, including custom storage of:

- position or screen coordinates;
- size or minimum-size enforcement through per-frame resets;
- collapsed or expanded state;
- visibility or open/closed state;
- focus, docking, or display status;
- manual restoration of saved window geometry.

Use the existing ImGui window API and its `ini_key`/persistence mechanism. Configure initial constraints only through the appropriate ImGui window flags or first-use APIs, and do not force those values again every frame. A feature may decide whether to call `Begin()` or whether a user-facing feature is enabled, but it must not fight ImGui over the window’s persistent state.

When reviewing UI changes, search for:

- custom `SetWindowPos`, `SetWindowSize`, `SetNextWindowPos`, or `SetNextWindowSize` calls;
- per-frame writes to window coordinates or dimensions;
- custom window classes that reposition or restore ordinary ImGui windows;
- separate INI/settings keys duplicating ImGui geometry or visibility;
- code that overwrites `p_open`, collapsed state, or window status after ImGui has evaluated it.

These are review blockers unless the window is explicitly a non-ImGui/native window with a documented ownership boundary. The review must identify the owner of each window’s geometry and persistence and reject multiple competing owners.

## New-feature review example: fight-zone positioning

PR #39 added a new fight-zone package, so its new files were not automatically a traceability violation. The guide identified a different set of issues:

- the advertised default-off path still instantiated and ticked the publisher;
- generic follow placement behavior changed in the same pull request;
- build-line reporting had a producer but no complete command or receive path;
- flag ownership did not reliably detect later manual overrides;
- publisher state was not clearly reset across map and lifecycle transitions;
- behavioral tests and pyright/Pylance validation were missing;
- broad exception handling could make the feature fail silently.

This example demonstrates that the review must evaluate both source traceability and runtime integration. A new package may be structurally appropriate while its integration still violates no-op, lifecycle, scope, or verification requirements.

## Scope review example: Skills Unlocker diagnostics

PR #47 added a custom `SessionLogger` that created `Logs/Sessions` and wrote diagnostic files through `open()` and `os.makedirs()`. This violated both scope and repository policy:

- the PR’s primary scope was Skills Unlocker route behavior;
- the logger was reusable infrastructure;
- generic agent-interaction code was instrumented outside the feature;
- custom file-backed diagnostics bypassed the project’s approved interfaces.

The correct review action is to remove the custom logger from the feature PR. Use existing console or runtime diagnostics for the feature, or create a separate infrastructure proposal if persistent diagnostics are truly needed.

## Common red flags

### Large deletion plus large new-file addition

This often indicates a rewrite or an extraction that Git cannot represent usefully. Ask the author to preserve recognizable code boundaries and separate movement from adaptation.

### New initialization helper that is not used by the current owner

This creates a second lifecycle contract. Either keep initialization in the current owner until the second consumer exists, or explicitly migrate both consumers and test initialization order.

### A service claims independence but calls owner-specific methods

This is hidden coupling. Require a documented protocol, a narrow adapter, or a more accurate architectural description.

### “No behavior change” while changing inheritance

Inheritance changes can affect MRO, `super()`, subclass discovery, type checks, and method collisions. Treat this as a structural risk, not a textual change.

### Formatting mixed with movement

Formatting destroys line-level history and makes semantic review harder. Request a separate formatting change, or defer formatting until after the migration is verified.

### Unrelated bug fixes in an extraction

They make rollback and regression analysis ambiguous. Move them to a separate pull request.

### A new parallel implementation is introduced before the old one is retired

This can create two sources of truth. Require an explicit compatibility strategy and a retirement plan.

### A feature is built around incidental override points

This creates hidden coupling and makes the accidental integration location part
of the architecture. Require the owning class to be modified or given an
explicit extension point, or require a genuine subclass/composition boundary.
Do not approve wrappers, monkey patches, method shadowing, or unrelated
lifecycle interception as the primary implementation strategy.

## AI-oriented review instructions

When asking another AI agent to review a pull request, provide these instructions:

```text
Review this pull request against the repository’s traceable-migration policy.

The primary objective is to preserve behavior and source traceability. Do not assume that a large movement diff is safe because the author calls it a relocation or because AST comparison passes.

First establish the base and head revisions. Then inventory changed files, additions, deletions, renames, inheritance changes, initialization changes, public API changes, and behavior changes.

Classify the pull request as additive, mechanical relocation, structural refactor, semantic change, or rewrite. State which classification is supported by the actual diff.

Compare the implementation against the user’s vision:

- Is the original implementation still recognizable?
- Can Git and a human reviewer follow the change without comparing two complete files manually?
- Were movement, architecture, formatting, and behavior changes separated?
- Did inheritance or composition change?
- Did initialization order or lifecycle change?
- Does a new service actually have an explicit dependency contract?
- Are old APIs and call paths preserved?
- Are settings, persistence, callbacks, queues, and native dispatch contracts unchanged?
- Does the implementation reuse existing project classes and approved libraries instead of reimplementing equivalent functionality?
- If a provided class already owns the capability, was it modified or extended instead of copied?
- Is the feature using an explicit extension point, or is it exploiting an incidental override, wrapper, monkey patch, or lifecycle hole?
- Does the implementation avoid hole-based attachment regardless of where the code originated or who authored the pull request?
- Are tests and pyright/Pylance checks sufficient for the changed scope?

Do not modify the repository. Produce evidence-backed findings with file paths and line references. Separate blockers, requested changes, risks, and positive evidence.

If the change violates traceability, recommend a smaller sequence of commits
and request changes. Prefer same-file reorganization when practical, but do not
require it when the new file is the intended class extension and the extraction
is mechanical. For a separate-file extraction, require a clear ownership and
host-contract explanation, unchanged method mapping, and separate treatment of
any semantic or lifecycle changes. Do not treat AST identity, byte identity,
rename detection, `git blame`, or `git log --follow` as proof that semantic
changes are safe; do not reject a mechanically proven class extension merely
because GitHub renders it as a large deletion and addition.
```

## Review output must answer the original request

The final review is for the user who requested the change or review. It must
answer whether the submitted diff delivers that original requested outcome
within the stated scope and repository contracts. It is not a transcript of a
reviewerâ€™s tools, guesses, or private decision process.

Lead with the verdict, then present only facts needed for the requester to
understand the decision:

- **Verified:** directly supported by the submitted diff, current owner,
  declared public contract, or a check that actually ran.
- **Inferred:** a reasoned interpretation of verified evidence; label it as
  such and state the consequence rather than presenting it as proof.
- **Unresolved:** requires native, runtime, or external evidence that was not
  available. State the smallest check needed to resolve it.

Do not claim that a native binding, callback, or runtime surface is absent,
broken, or available merely because a `try` import succeeds or fails, a stub
exists, a sibling source file exists, or the pull request does not modify it.
Those facts establish only that the pull request has not proven the relevant
runtime contract. Phrase the finding accordingly and require the owner-level
evidence needed by the original request.

Do not write the review as instructions to the reviewer, a list of exploratory
commands, or a broad architecture lecture. Use file and symbol references to
explain what the diff does, how that conflicts with the requested outcome, and
what the author must change before the original user can safely accept it.

Every requested change or blocker must state a complete, concrete causal path:

1. **Changed code:** the exact new or altered symbol and its behavior.
2. **Existing path affected:** the current symbol, owner, or public contract it
   replaces, bypasses, duplicates, or leaves incomplete.
3. **Concrete consequence:** the observable incorrect behavior, incompatible
   contract, competing state/lifecycle, or review-scope failure caused by that
   relationship. Do not substitute labels such as "ownership issue," "shim," or
   "architecture problem" for this explanation.
4. **Required correction:** the specific owner and smallest change that repairs
   the path. Do not write generic directions such as "fix the root cause" or
   "use the proper owner" without naming it.
5. **Evidence boundary:** the smallest unresolved fact, if any, and the exact
   check needed to settle it.

If a finding cannot name this path, investigate further or omit it. A review
must be difficult to misinterpret: the author should be able to point to the
named code, see the broken connection, and know the first required edit.

## Required direction must explain why

For a request-changes or blocking verdict, finish with a **Required direction**
section. It is the author's repair plan, not a reviewer checklist. Each item
must name one concrete action and immediately explain why that action is
necessary for the original request to be safely accepted.

Order the items by dependency when applicable: first restore a reviewable
scope, then remove a competing or bypassing path, correct the responsible
owner, move consumers onto that owner, and finally provide the evidence that
proves the repaired path. Do not force steps that do not apply; the important
part is that every required step has a specific purpose.

Do not write unexplained directions such as "split the PR," "fix the native
layer," or "add tests." State the concrete failure each action removes. For
example, a scope split is required because unrelated files make it impossible
to identify which changes implement the requested behavior or to revert only
that behavior; an owner-layer repair is required because a feature-local
fallback cannot make an unproven event stream reliable.

## Mandatory verdict-post format

Every pull-request review must be written as the following author-facing
verdict post. This is the required output, not a suggestion to be replaced by
a conversational summary, a raw finding dump, or an architecture lecture.

```text
Verdict for the original request: [approve / request changes / block] — [one
sentence saying whether this PR delivers the requested result and why it does
or does not].

[Only the findings that decide the verdict.]

[SEVERITY] [a concrete statement of the problem]
`changed code` now [does this specific thing]. It [bypasses / duplicates /
replaces / leaves incomplete] `existing code or path`. As a result, [the
specific wrong result, hidden failure, competing state, or scope problem].

Required direction:
1. [Exact action: name the file, symbol, and change required.]
   Why: [Explain the exact failure this removes and why it is necessary for
   the original request.]
2. [Next exact action.]
   Why: [Explain its concrete purpose and dependency on the prior action.]
3. [Focused proof needed before approval.]
   Why: [State what static inspection cannot establish.]

The current implementation is [the concrete description of what it actually
does], not [the requested root-cause fix].
```

The findings establish the verdict; **Required direction** is the binding
repair plan. Keep both short and dense. Include only a finding that changes
what the author must do before the PR can be accepted. Do not pad the post
with generic acceptance criteria, tool transcripts, background theory, or
possible future improvements.

Use ordinary code-language first. Name the file and symbol, say what it now
does, name the existing code it affects, and state the resulting failure. Do
not substitute labels such as "architecture issue," "abstraction leak,"
"compatibility layer," "binding," or "ownership" for that explanation. A
technical term is allowed only when the sentence also says plainly what it
means in this PR.

Do not vary the verdict post because a user prompt happens to be brief or
because a prior review used a different style. The guide controls the form:
the review must always deliver the original-request verdict, decisive evidence,
and an action-plus-why repair sequence.

### Canonical author-facing review text

Use this exact structure for a request-changes or blocking review. Replace the
bracketed facts with evidence from the PR; do not add a reviewer diary, a
second summary, generic acceptance criteria, or extra sections that dilute the
decision.

```text
Verdict for the original request: request changes — [this PR does not deliver
the requested result because it does X instead of repairing Y].

[BLOCKER] `[new file or symbol]` [does the specific new thing].

`[existing file or symbol]` already [does or owns the relevant existing work].
`[new file or symbol]` [duplicates, bypasses, replaces, or silently falls back
from] that path.

As a result, [state the one concrete bad outcome: two answers for the same
state, hidden failure, a bypassed implementation, incompatible behavior, or
an unreviewable mixed scope].

[Repeat only for another blocker that changes the repair direction.]

Required direction:

1. [Exact action: remove, move, repair, or route specific code through a
   named existing owner.]
   Why: [the exact bad outcome this removes].

2. [Next exact action, in dependency order.]
   Why: [why the first action alone cannot deliver the original request].

3. [Focused proof required before approval.]
   Why: [what the diff and static checks cannot prove].

The current implementation is [what the PR actually does], not [the requested
root-cause fix].
```

The author must be able to read this post without knowing the reviewer's
private terminology. Prefer statements such as "this creates a second cast
tracker" or "this hides a failed import and uses old data" over labels such as
"competing state," "fallback topology," or "binding issue." Keep the named
file and symbol, but explain the connection in normal code language.

### Superseded detailed checklist (do not use as review output)

The following checklist may help an investigator collect evidence, but it is
not author-facing review output and must not replace the verdict post above:

```text
Verdict for the original request: [approve / request changes / block] — [short reason].

[SEVERITY] [short, concrete finding title]
Changed code: `path:line` — [what the changed symbol now does].
Existing path affected: `path:symbol` — [what it currently owns or guarantees].
Consequence: [the precise behavior, contract, state, or scope failure created by the change].
Required correction: [the exact symbol/owner to change and what to remove, preserve, or route through].
Evidence boundary: [only when unresolved; name the exact missing fact and smallest resolving check].

Required direction:
1. [Specific required action.]
   Why: [The exact failure, ambiguity, or competing path that this action removes, and why that matters to the original request.]
2. [Next specific required action.]
   Why: [Its concrete purpose and dependency on the previous repair.]
3. [Focused evidence required to accept the repaired path.]
   Why: [What the diff or static inspection cannot establish on its own.]

Acceptance criteria:
- Existing behavior and public contracts are preserved.
- The original implementation remains recognizable.
- The ordinary pull-request diff clearly identifies the ownership/class-extension change and its contracts.
- Moved implementation is byte/AST-identical when the change is claimed to be mechanical.
- Git provenance tools and mechanical comparison are supporting evidence, not substitutes for reviewing inheritance, initialization, and dependencies.
- No unrelated formatting or bug fixes are included.
- Initialization, MRO, lifecycle, and dependency contracts are explicit.
- Existing project mechanisms and approved libraries are reused where applicable; any new parallel implementation documents a concrete capability gap and retirement/ownership plan.
- Provided classes are extended or modified when appropriate; replacement copies are not introduced without an approved exception.
- Hole-based attachment patterns are not introduced or preserved; the current class owns the behavior through an explicit integration path.
- Pyright/Pylance checks pass for the changed Python scope. Behavioral test suites are not a default approval requirement unless specifically requested.
```

## Case study: combat-service extraction

The review of PR #34 is a useful example of the distinction between runtime equivalence and traceable change.

The pull request presents itself as a pure relocation of combat utilities from `BuildMgr.py` into `combat_services.py`. The method-body preservation claims and compile checks are useful positive evidence. However, the diff removes most of the implementation from the original file, recreates it in a new file, changes `BuildMgr` inheritance, and introduces a second initialization contract.

The correct review conclusion is not necessarily “the code is behaviorally wrong.”
First determine whether the large diff is a genuine mechanical extraction needed
for the class extension or an opaque reimplementation. If the moved methods are
byte-identical, the host contract is explicit, initialization and call paths are
unchanged, and no semantic changes are bundled, the class extension can be
accepted as a traceable mechanical migration. Do not require a rewrite merely
because the file split makes GitHub display deletions and additions.

The author may provide evidence that the moved methods are byte-identical and
that Git can recover their prior commits. That is meaningful positive evidence,
not something to disregard. The review must then focus on the actual structural
risks: inheritance/MRO, host dependencies, initialization order, public call
paths, and whether any semantic edits were bundled into the move. A large
deletion plus a large new-file addition is not, by itself, grounds to require a
rewrite.

## Review record to append after each analysis

For future pull requests, add a short record containing:

- PR number and title;
- base and head commits;
- requested user vision;
- actual diff classification;
- changed-file and line-count summary;
- traceability assessment;
- hidden-contract findings;
- validation performed;
- blockers and required decomposition;
- accepted exceptions to this guide and why.
- review scope, checks run, checks omitted, and the reason for each;
- severity rationale for every requested change or blocker.

This record allows later reviews to enrich the guide with project-specific patterns instead of repeating the same analysis from scratch.

## Continuous review feedback loop

This guide is a living review contract. A review that exposes a new,
repeatable failure pattern is not complete when the verdict is posted: the
pattern must feed back into this guide so that the next review can identify it
earlier, explain it more clearly, and require the right repair without
relearning the same lesson.

When a review finds a pattern that the guide does not already cover:

1. Record the verified code path: what was changed, what existing path it
   bypassed, duplicated, or left incomplete, and the concrete result.
2. Add a focused rule at the relevant topic in this guide. State the ownership
   rule, the symptom a reviewer should look for, and the troubleshooting steps
   that establish the real owner before a workaround is accepted.
3. Update the canonical verdict-post language when the new pattern needs a
   clearer author-facing explanation or a new required-direction step.
4. On later reviews, check the new rule first. If the pattern returns, tighten
   the rule or its troubleshooting rather than writing the same vague comment
   again.

Do not turn a one-off suspicion into permanent policy. Add a rule only when
the submitted code and current owners establish the causal path, or when the
rule is explicitly adopted as repository direction. Keep runtime facts marked
as unresolved until injected-client evidence proves them.
