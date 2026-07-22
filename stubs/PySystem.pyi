# PySystem stub — Py4GW system services.
# Exact counterpart of src/system/system_bindings.cpp in Py4GW_Reforged_Native
# (PYBIND11_EMBEDDED_MODULE(PySystem)). Submodules below are exposed as
# def_submodule() namespaces, modelled here as classes of static methods.

from enum import IntEnum
from typing import List, Tuple, overload


# ═══════════════ ENUMS ═══════════════════════════════════════════
# Values from `enum class MessageType` in include/base/logger.h (unscoped, 0-based).

class MessageType(IntEnum):
    Info = 0
    Warning = 1
    Error = 2
    Debug = 3
    Success = 4
    Performance = 5
    Notice = 6
    Hook = 7


# ═══════════════ CLASSES ═════════════════════════════════════════

class ConsoleMessage:
    # All members are def_readonly.
    timestamp: str
    display_timestamp: str
    module_name: str
    level: str
    message_type: MessageType
    message: str
    def __repr__(self) -> str: ...


# ═══════════════ TOP-LEVEL FUNCTIONS ════════════════════════════

def get_tick_count64() -> int:
    """Get the frame timestamp tick count as a 64-bit integer."""
    ...

def get_shared_memory_name() -> str:
    """Get the current per-process runtime shared-memory name."""
    ...

def get_credits() -> str:
    """Get the credits for the Py4GW library."""
    ...

def get_license() -> str:
    """Get the license for the Py4GW library."""
    ...

def change_working_directory(path: str) -> bool:
    """Change the current working directory."""
    ...

def request_shutdown_prompt() -> None:
    """Open the Py4GW shutdown confirmation modal."""
    ...

def cancel_shutdown_prompt() -> None:
    """Dismiss a pending shutdown confirmation modal."""
    ...

def is_shutdown_prompt_pending() -> bool:
    """Check whether the shutdown confirmation modal is pending."""
    ...

def in_character_select_screen() -> bool:
    """Check if the character select screen is ready."""
    ...

def has_account_email() -> bool:
    """Check whether the account anchor email has been resolved."""
    ...

def get_account_email() -> str:
    """Get the account email used as the persistence anchor (empty until resolved)."""
    ...

def get_settings_directory() -> str:
    """Get the per-account settings directory (empty until the anchor is resolved)."""
    ...


# ═══════════════ SUBMODULES ══════════════════════════════════════

_MessageTypeAlias = MessageType


class Console:
    """Authoritative script-facing console: logging, retrieval, and window control."""

    # console.attr("MessageType") = PySystem.MessageType (the same enum object).
    MessageType = _MessageTypeAlias

    @staticmethod
    def Log(sender: str, message: str, message_type: MessageType = MessageType.Info) -> None:
        """Write a message to the console."""
        ...

    @staticmethod
    def get_projects_path() -> str:
        """Get the path where Py4GW.dll is located."""
        ...

    @staticmethod
    def get_gw_window_handle() -> int:
        """Get the Guild Wars window handle as an integer."""
        ...

    # Two registered overloads: level string first, then MessageType.
    @overload
    @staticmethod
    def write(module_name: str, message: str, level: str = "INFO") -> None: ...
    @overload
    @staticmethod
    def write(module_name: str, message: str, message_type: MessageType) -> None: ...

    # Two registered overloads: no-arg (all messages), then filtered by type.
    @overload
    @staticmethod
    def get_messages() -> List[ConsoleMessage]: ...
    @overload
    @staticmethod
    def get_messages(message_type: MessageType) -> List[ConsoleMessage]: ...

    @staticmethod
    def filter_messages(module_name: str = "", level: str = "", contains: str = "") -> List[ConsoleMessage]:
        """Filter buffered console messages by module, level, and substring."""
        ...

    @staticmethod
    def clear_messages() -> None:
        """Clear the console message buffer."""
        ...

    @staticmethod
    def set_output_to_file(enabled: bool) -> None:
        """Mirror console messages into the injection log file."""
        ...

    @staticmethod
    def get_output_to_file() -> bool:
        """Check whether console messages are mirrored to the log file."""
        ...

    @staticmethod
    def set_draw_console(enabled: bool) -> None:
        """Show or hide the full console window."""
        ...

    @staticmethod
    def get_draw_console() -> bool:
        """Check whether the full console window is shown."""
        ...

    @staticmethod
    def set_draw_compact_console(enabled: bool) -> None:
        """Show or hide the compact console window."""
        ...

    @staticmethod
    def get_draw_compact_console() -> bool:
        """Check whether the compact console window is shown."""
        ...

    @staticmethod
    def toggle_console() -> None:
        """Toggle the full console window."""
        ...

    @staticmethod
    def toggle_compact_console() -> None:
        """Toggle the compact console window."""
        ...


class environment:
    """Process environment queries."""

    @staticmethod
    def get_gw_window_handle() -> int:
        """Get the Guild Wars window handle as an integer."""
        ...

    @staticmethod
    def get_projects_path() -> str:
        """Get the path where Py4GW.dll is located."""
        ...


class window:
    """Guild Wars window control."""

    @staticmethod
    def resize_window(width: int, height: int) -> None:
        """Resize the Guild Wars window."""
        ...

    @staticmethod
    def move_window_to(x: int, y: int) -> None:
        """Move the Guild Wars window to (x, y)."""
        ...

    @staticmethod
    def set_window_geometry(x: int, y: int, width: int, height: int) -> None:
        """Set the Guild Wars window geometry (x, y, width, height)."""
        ...

    @staticmethod
    def get_window_rect() -> Tuple[int, int, int, int]:
        """Get the Guild Wars window rectangle (left, top, right, bottom)."""
        ...

    @staticmethod
    def get_client_rect() -> Tuple[int, int, int, int]:
        """Get the Guild Wars client rectangle (left, top, right, bottom)."""
        ...

    @staticmethod
    def set_window_active() -> None:
        """Set the Guild Wars window as active (focused)."""
        ...

    @staticmethod
    def set_window_title(title: str) -> None:
        """Set the Guild Wars window title."""
        ...

    @staticmethod
    def is_window_active() -> bool:
        """Check if the Guild Wars window is active (focused)."""
        ...

    @staticmethod
    def is_window_minimized() -> bool:
        """Check if the Guild Wars window is minimized."""
        ...

    @staticmethod
    def is_window_in_background() -> bool:
        """Check if the Guild Wars window is in the background."""
        ...

    @staticmethod
    def set_borderless(enable: bool) -> None:
        """Enable or disable borderless window mode."""
        ...

    @staticmethod
    def set_always_on_top(enable: bool) -> None:
        """Set or unset always-on-top."""
        ...

    @staticmethod
    def flash_window(repeat_count: int = 1) -> None:
        """Flash the Guild Wars taskbar button."""
        ...

    @staticmethod
    def request_attention() -> None:
        """Keep flashing until the window comes to foreground."""
        ...

    @staticmethod
    def get_z_order() -> int:
        """Get the Z-order index of the Guild Wars window."""
        ...

    @staticmethod
    def set_z_order(insert_after: int = 0) -> None:
        """Set the Z-order of the Guild Wars window relative to another window."""
        ...

    @staticmethod
    def send_window_to_back() -> None:
        """Send the Guild Wars window to the bottom of the Z-order stack."""
        ...

    @staticmethod
    def bring_window_to_front() -> None:
        """Bring the Guild Wars window to the front of the Z-order stack."""
        ...

    @staticmethod
    def transparent_click_through(enable: bool) -> None:
        """Make the Guild Wars window click-through."""
        ...

    @staticmethod
    def adjust_window_opacity(alpha: int) -> None:
        """Adjust the Guild Wars window opacity (0-255)."""
        ...

    @staticmethod
    def hide_window() -> None:
        """Hide the Guild Wars window."""
        ...

    @staticmethod
    def show_window() -> None:
        """Show the Guild Wars window if hidden."""
        ...


class script_control:
    """Python script lifecycle control."""

    @staticmethod
    def load(path: str) -> bool:
        """Load a Python script from path."""
        ...

    @staticmethod
    def run() -> bool:
        """Run the currently loaded script."""
        ...

    @staticmethod
    def stop() -> None:
        """Stop the currently running script."""
        ...

    @staticmethod
    def pause() -> bool:
        """Pause the running script."""
        ...

    @staticmethod
    def resume() -> bool:
        """Resume the paused script."""
        ...

    @staticmethod
    def status() -> str:
        """Get current script status."""
        ...

    @staticmethod
    def defer_load_and_run(path: str, delay_ms: int = 1000) -> None:
        """Stop current if needed, then load and run new script after delay (ms)."""
        ...

    @staticmethod
    def defer_stop_load_and_run(path: str, delay_ms: int = 1000) -> None:
        """Force stop, then load and run new script after delay (ms)."""
        ...

    @staticmethod
    def defer_stop_and_run(delay_ms: int = 1000) -> None:
        """Stop current script, then rerun it after delay (ms)."""
        ...


class widget_manager:
    """Always-on widget manager script host."""

    @staticmethod
    def start() -> bool:
        """Load and run the widget manager script."""
        ...

    @staticmethod
    def stop() -> None:
        """Stop the widget manager script."""
        ...

    @staticmethod
    def status() -> str:
        """Get the widget manager run status."""
        ...
