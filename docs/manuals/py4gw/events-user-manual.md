# Events User Manual

`GW::events` is the internal event-message hook surface.

Main API:

- `RegisterEventCallback(...)`
- `RemoveEventCallback(...)`

The subsystem exposes event interception around `EventID` traffic so consumers can observe selected internal events without each subsystem hooking the event dispatcher separately.
