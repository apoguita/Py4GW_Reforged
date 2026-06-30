# Context LLM Manual

`Context` is a structural data gateway, not a policy layer.

Its job is:

- resolve access to large game-state roots
- expose typed pointers to context structures
- support higher-level managers that build behavior on top

Rules:

- keep accessor semantics simple
- do not smuggle gameplay actions into context accessors
- when adding new context surfaces, prefer extending the context family cleanly instead of bloating unrelated managers

The context-family headers are part of the subsystem surface even when the aggregate header is the main entry point.
