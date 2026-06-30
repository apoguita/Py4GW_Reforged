# StoC LLM Manual

`StoC` is packet-dispatch infrastructure, not business logic.

Important traits:

- callback registration is header-indexed
- supports both pre and post callback phases
- packet emulation is part of the public contract

When editing:

- preserve callback altitude/order expectations
- keep packet ownership and packet lifetime assumptions stable
- avoid subsystem-specific branching in the generic dispatch layer
