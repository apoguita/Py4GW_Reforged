"""Hello World — a guided tour of ``ImGui.SidebarWindow``.

This script is a **teaching demo** for the reusable sidebar/content window helper
that lives in ``Py4GWCoreLib/ImGui_src/SidebarWindow.py`` and is exposed on the
facade as ``ImGui.SidebarWindow``. Run it as a widget and read it top-to-bottom:
every section is commented to explain *why*, not just *what*.

The mental model
----------------
A ``SidebarWindow`` is a window split into two columns:

    ┌── Group ────────────┐┌── content for the ─────────┐
    │  • Topic  (selected)││  currently selected Topic   │
    │  • Topic            ││  (its draw() runs here, or  │
    │ ── Group ──         ││   a bar of its Tabs)        │
    │  • Topic            ││                             │
    └─────────────────────┘└─────────────────────────────┘

You supply the *content* (small zero-argument ``draw`` callables); the helper
owns the *chrome* — the window, the two child regions, the grouped selectable
navigation, per-panel error isolation, optional content tabs, and markdown help.

How you build it — link labels to context functions
----------------------------------------------------
You never manage selection state by hand. You just **link a label to its context
(render) function** and the window shows the right one automatically:

* ``win.add_group(title, default_open=..., collapsible=...)`` — a **collapsible
  header** in the sidebar. Click to expand/collapse, or drive it from code with
  ``expand_all`` / ``collapse_all`` / ``set_group_open``.
* ``win.add_section(group, name, context)``   — a sidebar entry bound to ``context``;
  clicking it auto-shows that function. ``default=True`` picks the first one shown.
* ``win.add_tab(section, name, context)``     — a content tab bound to ``context``;
  selecting the tab auto-shows that function. The content area works just like the
  sidebar, one level in.

Any section or tab may also carry ``help=`` (inline markdown) or ``help_file=`` (a
``.md`` path) — surfaced as a Help button that expands rendered rich text. Window
options include ``show_search`` (a filter box over the sidebar) and ``on_select``
(a callback fired when the active section changes).

Widget-script contract
-----------------------
In-client scripts must be **passive on import** and **frame-driven**: building the
window object below is pure Python (no rendering happens at import), and all the
actual ImGui calls happen inside ``main()``, which the host calls once per frame.
Never render at module top level — it will crash the client.
"""

# ``ImGui`` is the facade wrapper; ``SidebarWindow`` hangs off it as ``ImGui.SidebarWindow``.
from Py4GWCoreLib import ImGui

# We use a few raw PyImGui primitives inside the panels for illustration.
import PyImGui


# ---------------------------------------------------------------------------
# 1) Panel state
# ---------------------------------------------------------------------------
# A "panel" is just a function that draws into the content column. Anything it
# needs to remember between frames lives in module-level state (ImGui is
# immediate-mode: nothing persists unless *you* keep it).
_state = {
    "clicks": 0,          # incremented by the Counter panel's button
    "show_extra": False,  # toggled by the Tabs demo
    "last_selected": "",  # written by the on_select callback below
}


def _on_select(name: str) -> None:
    """on_select fires whenever the active section changes (window-managed state)."""
    _state["last_selected"] = name


# ---------------------------------------------------------------------------
# 2) Panels — each is a zero-argument ``draw`` callable
# ---------------------------------------------------------------------------
# A panel renders INTO the content region the helper already opened for it. It
# must NOT call PyImGui.begin()/end() itself — it only emits widgets. If a panel
# raises, SidebarWindow catches it and prints the error in red instead of tearing
# down the whole window, so a broken panel never kills the tool.

def draw_welcome() -> None:
    """Simplest possible panel: emit a few widgets, no state.

    This is what a ``Topic(draw=...)`` calls every frame while it is selected.
    """
    PyImGui.text("Welcome to the SidebarWindow tour.")
    PyImGui.spacing()
    PyImGui.text_wrapped(
        "Pick topics from the left column. This topic also has a 'Help' button "
        "above (see the inline markdown help attached to it in the builder below)."
    )
    PyImGui.spacing()
    PyImGui.bullet_text("Left column = grouped, selectable navigation.")
    PyImGui.bullet_text("Right column = the selected topic's content.")


def draw_counter() -> None:
    """A panel that *remembers* something across frames.

    Immediate-mode UIs redraw from scratch every frame, so persistent values must
    live outside the draw call (here, ``_state``). The button returns True only on
    the frame it is clicked.
    """
    PyImGui.text(f"Button clicked: {_state['clicks']} time(s)")
    if PyImGui.button("Click me"):
        _state["clicks"] += 1
    PyImGui.same_line(0, 8)
    if PyImGui.button("Reset"):
        _state["clicks"] = 0


def draw_error_demo() -> None:
    """Deliberately raises, to show per-panel error isolation.

    Selecting this topic renders a red error line in the content area — the window
    and every other panel keep working. Remove the ``raise`` to see it go quiet.
    """
    PyImGui.text("The next line raises on purpose:")
    raise RuntimeError("this panel failed — but the window survived")


# --- A topic can host TABS instead of a single draw. Each tab is its own panel. --

def draw_tab_overview() -> None:
    """Content of the first tab."""
    PyImGui.text_wrapped(
        "A Topic with ``tabs=[...]`` renders a tab bar across the top of the "
        "content area. Each Tab has its own draw callable, help, and error box."
    )


def draw_tab_playground() -> None:
    """Content of the second tab — a tiny stateful toggle."""
    label = "Extra shown" if _state["show_extra"] else "Extra hidden"
    if PyImGui.button(f"Toggle extra ({label})"):
        _state["show_extra"] = not _state["show_extra"]
    if _state["show_extra"]:
        PyImGui.separator()
        PyImGui.text_colored("Surprise! This only draws while toggled on.",
                             ImGui.SidebarWindow.ACCENT_COLOR)


def draw_controls() -> None:
    """Drive the collapsible sidebar from code.

    Groups are collapsible headers — click to toggle, or control them
    programmatically. The window owns the expand/collapse state, so these calls
    are all it takes.
    """
    PyImGui.text_wrapped("Sidebar groups are collapsible headers. Toggle by clicking, "
                         "or drive them from code:")
    if PyImGui.button("Expand all"):
        WINDOW.expand_all()
    PyImGui.same_line(0, 8)
    if PyImGui.button("Collapse all"):
        WINDOW.collapse_all()
    PyImGui.spacing()
    # on_select (wired in the builder) keeps this in sync as you click the sidebar.
    PyImGui.text(f"Last selected section: {_state['last_selected'] or '(none yet)'}")


def draw_markdown_panel() -> None:
    """Render **rich text** with the native markdown addon.

    ``ImGui.SidebarWindow.render_markdown(text)`` routes through the imgui_markdown
    addon (``PyImGui.markdown.render``) and falls back to wrapped text if it is
    unavailable — so it is always safe to call.
    """
    ImGui.SidebarWindow.render_markdown(
        "# Rich text\n"
        "This block is **markdown**, rendered by the native addon.\n\n"
        "- headings, **bold**, *italic*\n"
        "- bullet lists\n"
        "- links open in your browser\n\n"
        "Use the same call to render `.md` *help files* for instructions."
    )


# ---------------------------------------------------------------------------
# 3) Build the window (pure construction — safe at import time)
# ---------------------------------------------------------------------------
# Constructing the window and adding sections does NOT render anything; it just
# records structure (which label is wired to which function). All rendering waits
# for main() -> WINDOW.draw().
WINDOW = ImGui.SidebarWindow(
    "Hello World — SidebarWindow demo",
    sidebar_width=220.0,        # left column width, pixels
    content_width=560.0,        # right column width, pixels
    height=460.0,               # shared height of both columns
    collapsible_groups=True,    # sidebar groups render as collapsible headers (default)
    show_search=True,           # add a filter box above the groups
    on_select=_on_select,       # called whenever the active section changes
)

# ``add_group`` returns a Group handle; the order you add sections is their order
# in the sidebar. Each group is a collapsible header — pass default_open=False to
# start it collapsed, or collapsible=False for a plain (always-open) header.
_intro = WINDOW.add_group("Getting Started")

# add_section LINKS a sidebar label to its "context" (render) function. Clicking
# the section automatically shows that function — the window tracks which section
# is selected, so you never wire up selection state yourself. ``default=True``
# makes this the section shown on first open; ``help=`` adds a Help button that
# expands rendered markdown above the panel.
WINDOW.add_section(_intro, "Welcome", draw_welcome, default=True,
                   help="### Welcome section\nThis text is linked to the section "
                        "via `help=` and rendered as **markdown** on demand.")
WINDOW.add_section(_intro, "Counter", draw_counter)
WINDOW.add_section(_intro, "Sidebar controls", draw_controls)

# A TABBED section works the same way, one level deeper. Create the section with
# no context (it will host tabs), then link each tab to its own context function
# with add_tab. Selecting a tab automatically shows that function's content — the
# content area behaves exactly like the sidebar, just scoped to this section.
_gallery = WINDOW.add_group("Content Patterns")
WINDOW.add_section(_gallery, "Tabs")  # no context -> this section hosts tabs
WINDOW.add_tab("Tabs", "Overview", draw_tab_overview,
               help="Tabs live inside one section's content area.")
WINDOW.add_tab("Tabs", "Playground", draw_tab_playground)

WINDOW.add_section(_gallery, "Error handling", draw_error_demo)

# This group starts COLLAPSED to show the collapsible-header behaviour.
_rich = WINDOW.add_group("Rich Text", default_open=False)
WINDOW.add_section(_rich, "Markdown", draw_markdown_panel)


# ---------------------------------------------------------------------------
# 4) The per-frame entry point
# ---------------------------------------------------------------------------
def main() -> None:
    """Called once per frame by the host. One call renders the entire window."""
    # ``draw()`` opens the window + both child columns, renders the sidebar and the
    # selected topic (or its tabs), and closes everything. It returns the window's
    # visibility, which you can ignore for a simple always-on tool.
    WINDOW.draw()


if __name__ == "__main__":
    main()
