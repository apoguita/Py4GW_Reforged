# Logger LLM Manual

`Logger` is safe for normal runtime use, not for every OS callback context.

Important properties from `src/base/logger.cpp`:

- mutex-protected
- file I/O capable
- stores a bounded entry buffer

Implication:

- do not introduce `Logger` calls into places where lock-taking or file I/O is unsafe, especially `DllMain` detach paths

Preserve:

- no-frills formatting
- low-overhead in-memory retention
- address/hook assertion helpers

If a path needs guaranteed reporting during teardown or crash handling, prefer raw file I/O or existing crash-side artifact code instead of the normal logger.
