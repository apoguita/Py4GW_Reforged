# Panic LLM Manual

The panic subsystem defines failure severity, not just syntax.

Rules:

- `PY4GW_ASSERT` means the process should fail if the condition is false
- `PY4GW_REQUIRE` is semantically the same, but names a required precondition
- recoverable runtime failures should not be rewritten into panics just to simplify control flow

Because `CrashHandler` bridges panic events into reports, new panic sites directly affect crash volume and operator experience.

Use panic paths for:

- impossible states
- hard invariants
- corruption indicators

Do not use them for:

- optional pointers with `continue` policy
- expected version drift
- ordinary feature unavailability
