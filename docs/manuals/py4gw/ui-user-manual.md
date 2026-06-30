# UI User Manual

`GW::ui` is the largest manager surface in the repository. It owns UI messaging, frame lookup, typed frame helpers, preferences, async decode helpers, and UI callback registration.

Main capability groups:

- send and receive UI messages
- inspect and manipulate frames
- create typed frame components
- query and set preferences
- decode encoded strings asynchronously
- register UI and frame-message callbacks

Representative API:

- `SendUIMessage(...)`
- `SendFrameUIMessage(...)`
- `GetFrame...`
- `Create...Frame(...)`
- `GetPreference(...)`
- `SetPreference(...)`
- `AsyncDecodeStr(...)`
- `RegisterUIMessageCallback(...)`
- `RegisterFrameUIMessageCallback(...)`

Use it whenever a feature is primarily a UI concern.
