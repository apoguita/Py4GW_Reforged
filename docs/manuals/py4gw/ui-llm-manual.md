# UI LLM Manual

`ui` is the widest and most fragile manager.

It mixes:

- message-hook infrastructure
- frame tree access
- component construction
- preference access
- async decode support
- callback registries
- shutdown coordination for in-flight hooks

When changing it:

- keep shutdown/drain semantics intact
- preserve clear boundaries between generic UI plumbing and typed helper sugar
- avoid adding one-off feature logic to the core message dispatch path
- treat optional pointer surfaces differently from required ones
