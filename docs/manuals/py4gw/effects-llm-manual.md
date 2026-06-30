# Effects LLM Manual

`effects` is a narrow manager with hook and resolver plumbing behind a small public surface.

Keep it small:

- effect-state helpers
- explicit effect actions
- minimal hook footprint

Do not turn it into a second context layer. If broader effect data is needed, model the data in context and keep this manager behavior-oriented.
