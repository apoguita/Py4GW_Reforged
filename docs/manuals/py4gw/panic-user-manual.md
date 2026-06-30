# Panic User Manual

`panic.h` defines the repository-wide panic and assertion macros.

Main macros:

- `PY4GW_PANIC`
- `PY4GW_ASSERT`
- `PY4GW_ASSERT_MSG`
- `PY4GW_REQUIRE`
- `PY4GW_UNREACHABLE`

Main functions:

- `RegisterLogHandler(...)`
- `RegisterPanicHandler(...)`
- `FatalAssert(...)`
- `FatalAssertMsg(...)`
- `Panic(...)`
- `LogMessage(...)`

Use assertions for invariants that should stop execution. Use ordinary logging for recoverable errors.
