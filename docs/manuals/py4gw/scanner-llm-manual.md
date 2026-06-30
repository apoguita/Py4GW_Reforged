# Scanner LLM Manual

`Scanner` is the runtime-address bridge over `FileScanner`.

What it actually does:

- scans the module image on disk
- tracks matching in-memory section ranges
- translates file-space hits into runtime pointers

Key constraint:

- do not duplicate logic that already exists in `Patterns`; use `Scanner` directly only for low-level scan work or when building generic resolver support

Important code facts from `src/base/scanner.cpp`:

- initialization is cached
- default module is the main process module
- `FunctionFromNearCall()` recursively resolves nested near calls
- `ToFunctionStart()` looks for the classic x86 prologue pattern

When changing it:

- preserve x86 assumptions unless you are intentionally widening platform support
- preserve section translation logic
- avoid widening scans without reason
- keep failure logs short and concrete
