# Render LLM Manual

`render` is a lifecycle-sensitive hook subsystem.

Important traits:

- hooks end-scene and reset
- exposes render callbacks to higher layers such as ImGui
- has explicit hook-drain logic during shutdown

When changing it:

- preserve callback ordering and reset semantics
- respect in-flight render hook drain requirements
- do not casually widen work done inside the render hook itself
