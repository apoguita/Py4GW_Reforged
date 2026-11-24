# Interaction identity catalog

The interaction catalog is an optional, read-only source for recurring NPC,
gadget, and item identities observed by automation consumers. It stores exact
encoded identities together with their known map occurrences, expected
geometry, capture identifiers, provenance, and diagnostic model IDs.

This streamlines shared functions such as `TakeBlessing` and repeated NPC or
gadget interactions: consumers can reference one organized occurrence instead
of copying the same identity and location facts into multiple routes. Encoded
identities are the primary runtime identity because model IDs can vary between
contexts. Geometry still matters when duplicate entities share an encoded
identity; the catalog does not imply that an encoded identity is globally
unique.

## Ownership boundary

- `target_registry.py` remains the owner of generic named modular targets. A
  catalog identity references an existing target-registry entry when the exact
  encoded identity is already present there.
- `interaction_catalog` owns curated occurrence records and exact identities
  that have no existing generic target-registry entry.
- Consumers continue to own movement paths, interaction behavior, duplicate
  selection policy, postconditions, recovery, and lifecycle decisions.
- Adoption is optional. This catalog does not change existing routes or add an
  enforcement gate.

## Lookup

```python
from Py4GWCoreLib.modular.domain.interaction_catalog import (
    get_interaction_occurrence,
)

blessing = get_interaction_occurrence(
    "nightfall.npc.vabbian_scout.enc_8101_5256_8204_5230."
    "wilderness_of_bahdza.-19380_414"
)
encoded_name = blessing.identity.encoded_name_runtime
expected_xy = blessing.target_xy
```

Use occurrence keys in automation code. Alias lookup is intended for tooling
and fails when an alias is ambiguous. Model IDs are retained as diagnostic
evidence, not as the preferred identity.

The package uses typed Python partitions because the catalog is consumed by
Python. Each partition must preserve unique identity and occurrence keys,
non-empty encoded identities, valid occurrence references, and an admitted
validation status. `InteractionCatalog()` validates those invariants while it
loads the static partitions.
