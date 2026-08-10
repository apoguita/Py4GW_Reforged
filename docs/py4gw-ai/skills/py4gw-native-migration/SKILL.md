---
name: py4gw-native-migration
description: Use when a Py4GW feature must be compared or migrated from legacy GWCA/Python behavior to the current Py4GW_Reforged_Native owner, binding, and public contract.
---

# Py4GW Native Migration

## Scope

- Own legacy parity analysis, native ownership mapping, Python/native contract review, and migration verification planning.
- Do not assume legacy behavior is current truth or modify the sibling native repository without explicit scope.

## Evidence Order

1. Current Reforged Python caller, stubs, and public contract.
2. Current `Py4GW_Reforged_Native` module, headers, offsets, and build files.
3. Reproducible injected-client behavior where applicable.
4. Legacy Py4GW/GWCA source as parity evidence only.

## Workflow

1. Define the legacy contract: inputs, result, failure behavior, and evidence that users/scripts depend on it.
2. Locate the current Python entry point and the native module that owns the capability. Read `docs/architecture/records/reforged-migration/` and the relevant current source before comparing legacy code.
3. Map legacy manager/API semantics to the current owner. Review conversions, lifetime, calling conventions, exceptions, queueing, and public naming at the Python/native boundary.
4. Prefer a native owner-controlled fix over a Python compatibility shim when the defect is below the Python layer.
5. Define focused Python, native-build, and live-client verification. State which proof cannot be obtained offline.

## Completion Report

Report legacy evidence, current owner, affected bridge contract, proposed migration/fix boundary, compatibility risk, required build/runtime checks, and unresolved offset or client-version dependency.
