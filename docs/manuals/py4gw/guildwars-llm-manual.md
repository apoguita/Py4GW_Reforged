# GuildWars LLM Manual

`GW` is the lifecycle coordinator for the manager layer.

Its value is ordering:

- startup order encodes subsystem dependencies
- shutdown order unwinds them safely

When changing it:

- preserve reverse-order shutdown
- treat hook/patch enable and disable boundaries as part of the contract
- do not move manager-local policy into this file unless the concern is truly cross-cutting
