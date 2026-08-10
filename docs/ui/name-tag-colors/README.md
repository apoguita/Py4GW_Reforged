# Name-Tag Color Documentation Map

This folder contains the historical feature guide and reverse-engineering
record for native name-tag recoloring.

## Authority and status

- `feature-guide.md` documents the earlier `PyAgentTagColor` API and is retained
  for feature history and ARGB examples.
- `reverse-engineering.md` preserves the resolver/detour evidence and in-client
  validation record for that earlier surface.
- The current source/stub/test surface is `AgentRecolor`/`PyAgentRecolor`, with
  Python code under `Py4GWCoreLib/AgentRecolor.py` and
  `Py4GWCoreLib/py4gwcorelib_src/system_settings/agent_recolor/`. It extends coverage beyond
  the old guide, so current API and hook claims require source verification.
- `tests/name_tag_color/` is the current in-client harness location, but its
  README and logs should be checked for the rebuilt DLL/module actually loaded.

## Review order

1. Read the RE record for native pipeline and ABI evidence.
2. Read the feature guide for the historical Python usage surface.
3. Inspect `AgentRecolor`, `PyAgentRecolor.pyi`, and current tests.
4. Use injected-client logs/results to distinguish static evidence from live
   validation.
