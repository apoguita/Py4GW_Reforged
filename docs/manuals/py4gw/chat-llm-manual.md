# Chat LLM Manual

`chat` is heavily hook-driven and closely tied to `ui`.

Important traits:

- hooks send/receive chat functions
- hooks UI callbacks for chat presentation
- owns a `MemoryPatcher` for timestamp behavior
- exposes command interception

When changing it:

- preserve separation between persistent log, transient output, and whisper flows
- keep timestamp patch lifecycle explicit
- remember that command interception is part of the public behavior, not an internal convenience
