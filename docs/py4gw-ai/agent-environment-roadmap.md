# Py4GW Agent Environment Roadmap

Status: proposed; research-backed on 2026-08-05
Scope: repository-local Codex and Claude agent guidance, skills, MCP/tool
boundaries, evaluations, and future automation
Authority: current repository configuration, current Codex documentation, and
the cited primary sources; active instructions remain `AGENTS.md` and the
current Py4GW AI guides

## Goal

Give one primary engineering agent the right project context on demand, make
recurring high-risk workflows repeatable, and keep the user in control of
runtime and destructive actions. The goal is not to build an agent bureaucracy
that holds meetings with itself while the dialog getter remains broken.

## Research Conclusions

The recommended starting point is one capable primary agent with clear
instructions and well-scoped tools. Split work into skills first, and introduce
separate agents only when instructions/tool selection become reliably confused
or independent work benefits from isolation or parallelism. This preserves
evaluation and maintenance simplicity.

For Py4GW, use a manager model: ApoBot owns user communication, plan, mutation,
and synthesis. Temporary read-only subagents may investigate independent source
trees, documents, or runtime evidence and return a bounded report. Do not use a
peer handoff mesh for normal repository work.

Treat the system as layers with different jobs:

| Surface | Job | Py4GW direction |
|---|---|---|
| `AGENTS.md` | Always-loaded repository contract | Keep the durable behavior, safety, ownership, and verification rules. |
| Nested `AGENTS.md` | Local invariants that truly differ by subtree | Add only for a stable native, bridge, or generated-artifact boundary. |
| `docs/py4gw-ai/` | Detailed current guidance, research, and plans | Keep evidence-rich knowledge here; never assume it is loaded unless a skill or root contract routes to it. |
| `docs/py4gw-ai/skills/<name>/` | Task-oriented workflow guide for a recognizable recurring user goal | Use for investigation, migration, validation, and authoring procedures. |
| MCP server/tool | Live data or controlled actions | Keep tool schemas narrow, typed, and permission-aware. |
| Temporary subagent | Isolated research, review, or independent verification | Make it read-only unless one owner explicitly grants a bounded write task. |
| Hook | Mechanical lifecycle enforcement | Add only after a manual check has proven worth automating. |
| Plugin | Distribution bundle across repositories/users | Postpone until the local skill/tool package is stable. |
| Automation | Scheduled monitoring or reminders | Use only for a concrete recurring signal, such as a documentation audit. |

## Verified Starting Inventory

The repository already has useful pieces, but they are fragmented:

- `AGENTS.md` is now the active root operating contract and routes detailed
  rules to `docs/py4gw-ai/`.
- `docs/py4gw-ai/skills/` contains the current repository-local workflow catalog.
- `.codex/config.toml` configures a local Ghidra MCP bridge. It has no
  project-local hook or wider tool catalog yet.
- The former ignored `.opencode/` workspace was consolidated and removed on
  2026-08-06. Its verified RE, bridge, and task-guidance material now has
  explicit current owners in `docs/py4gw-ai/skills/`; stale platform configuration,
  duplicate prompts, packages, and task transcripts were retired.
- `CLAUDE.md` delegates to `AGENTS.md`, which is the right direction for shared
  repository behavior.

The first task is therefore consolidation, not creating twenty more skills.

**Decision recorded on 2026-08-05:** build a fresh cross-platform foundation
catalog under `docs/py4gw-ai/skills/` as the replacement. The OpenCode material was
consolidated and removed after review on 2026-08-06.

## Proposed Skill Segmentation

Skills are organized by recurring *user goal*, not by every directory or class
in the repository. A skill may route to several documents and sources, but a
single task should normally load one primary workflow.

### Foundation skills: create first

| Skill | Trigger | Required outcome |
|---|---|---|
| `py4gw-docs-navigation` | Broad unfamiliar work or documentation changes | Locate current owner, source, evidence, and exact relevant records. Existing skill; refresh its references during consolidation. |
| `py4gw-runtime-investigation` | Live client symptom, state mismatch, crash, action/read divergence | Separate source proof from injected-client proof; collect reproduction, logs, affected owner, and safe next test. |
| `py4gw-native-migration` | Legacy-to-Reforged parity or native binding change | Map legacy evidence to current native owner, public bridge contract, build path, and compatibility checks. |
| `py4gw-ui-imgui` | PyImGui, widget, overlay, input, or UI state work | Establish frame/state ownership, native boundary, persistence/input implications, and live-client verification. |
| `py4gw-bridge-mcp` | Bridge daemon, client widget, CLI, or MCP change | Identify the command/data boundary, permissions, schema, client impact, and end-to-end verification. |
| `py4gw-change-verification` | Test, review, build, or completion request | Select focused checks, distinguish offline/live proof, and report residual risk without inventing a global CI command. |
| `py4gw-task-guidance` | Broad, ambiguous, or under-specified request | Turn the request into a proportionate task without creating mandatory intake bureaucracy. |
| `py4gw-re-methodology` | Guild Wars static analysis before a native or Python change | Establish a WASM-first, build-specific evidence chain and map it to the current native owner. |

Each skill needs a short trigger description, a workflow, explicit evidence
sources, a mutation/approval boundary, and a defined report. It should link to
current documents rather than copy large, volatile project facts into its body.

### Later skills: create only after repeated demand

- `py4gw-automation-behavior-trees` for BottingTree, multibox, HeroAI, and
  action-versus-observed-state investigation.
- `py4gw-persistence-change` for Settings, JsonFactory, migration, and data
  compatibility work.
- `py4gw-documentation-maintenance` only if documentation moves and index
  validation become frequent enough to justify a workflow beyond navigation.

Do not create a generic `researcher`, `coder`, or `reviewer` skill. Those names
describe a stance, not a stable Py4GW workflow.

## Agent Roles and Delegation

Use roles as temporary task contracts, not permanent personalities or a folder
of unattended agents.

| Role | May do | Must not do |
|---|---|---|
| Primary ApoBot | Own the user conversation, plan, mutations, synthesis, and final verification report | Delegate the final decision or hide uncertainty behind a subagent. |
| Source researcher | Search current/native/legacy/doc sources and return cited findings | Edit implementation or assert live runtime behavior. |
| Runtime investigator | Analyze supplied logs, reproduce safely, identify the next observation | Change production/runtime state without explicit scope. |
| Change reviewer | Inspect a diff for ownership, migration, compatibility, and test gaps | Silently fix or expand the requested scope. |
| Verification analyst | Run or design focused checks and classify evidence | Claim live-client proof from offline checks. |

Delegate only when the work is independent, bounded, and can return a concise
artifact. Keep one writer per file set. Parallel agents sharing a dirty tree are
not teamwork; they are a race condition wearing a lanyard.

## Tool and Safety Model

Classify every future MCP/tool operation before exposing it:

| Risk | Examples | Default handling |
|---|---|---|
| Read-only | Search source, query local symbol map, list clients | Allowed within task scope; return structured evidence. |
| Reversible workspace write | Edit a tracked source/doc file | Follow root contract, patch review, and focused verification. |
| External or sibling-project write | Modify native sibling project, send bridge command | Confirm target and scope; record owner and verification boundary. |
| Runtime action | Injected client command, dialog action, live memory interaction | Require explicit task scope and distinguish requested action from observed result. |
| Destructive/irreversible | Reset, clean, force push, branch deletion, data deletion | Require explicit authorization for exact target and operation. |

MCP tools should expose clear input and output schemas, return structured data
when practical, and keep access/authentication in the server rather than in
skill prose. Tool annotations are informative, not a substitute for trust or
authorization.

## Phased Rollout

### Phase 0: consolidate and measure

1. Create a current skill catalog with owner, trigger, sources, tool access,
   risk level, and verification method.
2. Keep the skill catalog aligned with current owners; consolidate or retire
   obsolete workflow material rather than preserving a parallel agent system.
3. Define a small fixture set of representative prompts: native migration,
   runtime bug investigation, UI change, bridge change, documentation move,
   task guidance, RE analysis, and narrow review.
4. Evaluate the existing navigation skill against those fixtures before adding
   another skill. A skill that cannot route one task correctly should not gain
   friends.

### Phase 1: establish the foundation skills

Create the skills in the order listed above, one at a time. For each: write the
workflow, add its small reference set, run positive and negative trigger
fixtures, and review its overlap with `AGENTS.md` and existing skills.

### Phase 2: add bounded delegation and evaluation

Use the role contracts above for source research and change review. Store task
fixtures and deterministic assertions in a repository-owned evaluation area;
use human review for nuanced quality and runtime findings. Evaluate outcomes
(correct owner, correct source, successful test), not merely fluent prose.

### Phase 3: enforce only proven mechanical checks

Add a project-local hook only if a manual repeatable check has repeatedly caught
real errors. Likely candidates are a documentation-index freshness check or a
final `git diff --check`; do not use hooks to recreate judgment, prompt review,
or hidden side effects.

### Phase 4: package and automate selectively

Package a plugin only when the skills, MCP tools, references, and versioning are
stable enough to distribute beyond this repository. Add an automation only for
a scheduled signal with an owner and response policy, such as a weekly
documentation-path audit. Do not schedule broad autonomous code changes.

## Consolidation Status

The foundation catalog, task-guidance workflow, and RE methodology are now in
place. Future work should add a skill only after a recurring goal, a clear
owner, and a compact trigger/verification contract are evidenced. Live-client
actions remain subject to the root contract's explicit scope requirements.

## Sources

- [OpenAI: A practical guide to building agents](https://openai.com/business/guides-and-resources/a-practical-guide-to-building-ai-agents/)
- [Anthropic: Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
- [Model Context Protocol: tools specification](https://modelcontextprotocol.io/specification/2025-06-18/server/tools)
- [LangChain: multi-agent patterns](https://docs.langchain.com/oss/javascript/langchain/multi-agent/index)
- [Codex: custom instructions with AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md.md)
- [OpenAI plugin skills concept](https://developers.openai.com/plugins/concepts/skills.md)
