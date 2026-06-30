# Events LLM Manual

`events` is a callback multiplexing layer over one underlying event message target.

When editing it:

- preserve callback ordering behavior
- keep registration/removal symmetric
- treat `EventID` coverage as a compatibility surface

This subsystem should stay infrastructure-like, not grow domain policy for individual event meanings.
