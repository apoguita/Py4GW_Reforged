# Camera LLM Manual

`camera` mixes direct context manipulation with patch-backed features.

Notable traits from the header:

- explicit movement API
- unlock and fog patch control
- resolver entry points for the camera pointer and camera-related patches

When changing it:

- keep patch-backed toggles explicit
- do not hide patch activation in innocent-looking getters/setters
- preserve the shutdown path for patch cleanup
