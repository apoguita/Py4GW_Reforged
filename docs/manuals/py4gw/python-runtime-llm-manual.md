# Python Runtime LLM Manual

`python_runtime` is one of the highest-risk lifecycle subsystems.

Key constraints:

- interpreter startup must be explicit
- interpreter shutdown must not rely on CRT global destruction
- script state and deferred actions must stay coherent across start/stop transitions

Recent practical lesson:

- process-detach finalization is unsafe for Python; keep shutdown explicit and idempotent

When changing this subsystem:

- preserve the distinction between interpreter lifetime and script lifetime
- do not reintroduce implicit static-destructor finalization
- be careful with GIL restoration and thread-state handling
