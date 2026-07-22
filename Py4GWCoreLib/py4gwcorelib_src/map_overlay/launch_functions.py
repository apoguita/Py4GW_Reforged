"""Launch-bar function provider for the Map Overlay.

Contributes the Map Overlay's launch-bar commands without the launch_bar core needing to know
about this package: it is referenced by dotted string from ``launch_bar.functions_catalog``'s
``_EXTERNAL_PROVIDERS`` and called once per launch-bar boot (mirrors ``HeroAI.command_api``).

Kept import-safe offline: nothing heavy is imported at module top. Each callback lazy-imports the
overlay surface *inside* the call, so registering a function never instantiates the overlay — that
happens only when the tile is actually clicked.
"""


def _toggle_mode() -> None:
    """Launch-bar callback: flip the shared Map Overlay between Mission Map and Compass."""
    from Py4GWCoreLib.py4gwcorelib_src.map_overlay import toggle_mode

    toggle_mode()


def register_launch_functions() -> None:
    """Register the Map Overlay's launch-bar functions. Idempotent (``register_function`` upserts by id)."""
    from Py4GWCoreLib.py4gwcorelib_src.launch_bar.functions_catalog import LaunchFunction
    from Py4GWCoreLib.py4gwcorelib_src.launch_bar.functions_catalog import register_function

    register_function(
        LaunchFunction(
            id="map_overlay.toggle_mode",
            name="Map Overlay: Toggle Mode",
            icon="ICON_GLOBE",
            group="Overlays",
            category="Map Overlay",
            callback=_toggle_mode,
            tooltip="Switch the Map Overlay between Mission Map and Compass mode.",
        )
    )
