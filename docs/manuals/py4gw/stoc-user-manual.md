# StoC User Manual

`GW::StoC` is the server-to-client packet interception layer.

Main capabilities:

- register pre-packet callbacks
- register post-packet callbacks
- remove callbacks
- emulate packet handling

Representative API:

- `RegisterPacketCallback(...)`
- `RegisterPostPacketCallback(...)`
- `RemoveCallback(...)`
- `RemovePostCallback(...)`
- `EmulatePacket(...)`

Use it when you need packet observation or controlled packet emulation.
