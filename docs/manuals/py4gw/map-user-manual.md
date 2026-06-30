# Map User Manual

`GW::map` is the travel, instance, and map-state subsystem.

Main capabilities:

- travel requests
- map test automation helpers
- challenge/cinematic control
- instance and region inspection
- foes-killed progress queries

Representative API:

- `Travel(...)`
- `MapTestStart(...)`
- `MapTestStop()`
- `GetIsMapLoaded()`
- `GetIsMapUnlocked(...)`
- `GetInstanceTime()`
- `GetFoesKilled()`
- `SkipCinematic()`

Use it for map lifecycle control and instance-state queries.
