# Py4GW DEMO 2.0

A **live API reference** and access/debug test tool for the Py4GW backend.

Each topic in the sidebar probes a binding surface and shows its data, so you can
see at a glance which getters resolve and which raise.

## How to read a panel

- **Green `OK`** — the binding resolved and returned a value.
- **Red `ERR`** — the binding raised; the message is shown inline.
- **Action buttons** fire mutate/send bindings live (travel, use-skill, invite, …)
  and only on click, never on render.

## Navigation

- The **left column** groups topics by subsystem — pick one to load its panel.
- Some topics expose **tabs** across the top of the content area.
- A **Help** button appears on any topic that ships instructions.

## Notes

- Coverage grows per `docs/demo_replacement/11_build_plan.md`.
- This window is built entirely from `ImGui.SidebarWindow` — see
  `Py4GWCoreLib/ImGui_src/SidebarWindow.py`.

Developed by **Apo**.
