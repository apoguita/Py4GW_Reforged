# Map LLM Manual

`map` combines state access, action functions, and test-oriented helpers.

Important traits:

- public structs expose map and mission context shapes
- public methods expose both normal gameplay actions and map-test support
- the subsystem owns at least one patch-backed behavior (`ResolveBypassTolerancePatch`)

When changing it:

- keep test helpers clearly separated from ordinary map APIs
- preserve cinematic/challenge behavior semantics
- treat map travel as a high-side-effect action surface
