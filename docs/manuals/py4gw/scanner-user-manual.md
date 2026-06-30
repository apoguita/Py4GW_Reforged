# Scanner User Manual

`PY4GW::Scanner` is the in-memory scan surface used by higher-level systems such as `Patterns`, `CrashHandler`, and handwritten resolvers.

Main API in `include/base/scanner.h`:

- `Initialize(HMODULE module = nullptr)`
- `Find(...)`
- `FindAssertion(...)`
- `FindInRange(...)`
- `ToFunctionStart(...)`
- `FunctionFromNearCall(...)`
- `FindUseOfAddress(...)`
- `FindNthUseOfAddress(...)`
- `FindUseOfString(...)`
- `FindNthUseOfString(...)`
- `IsValidPtr(...)`
- `GetSectionRange(...)`

Behavior:

- it maps the target module through `FileScanner`
- it computes live `.text`, `.rdata`, and `.data` ranges
- it converts file offsets back into runtime addresses

Use it when you need direct memory scanning. Prefer `Patterns::Resolve()` when the pointer can be modeled in JSON.

Practical guidance:

1. Call `Scanner::Initialize()` before scanning.
2. Use the narrowest section possible.
3. Prefer `FunctionFromNearCall()` and `ToFunctionStart()` over ad hoc arithmetic.
4. Validate section assumptions with `IsValidPtr()`.
