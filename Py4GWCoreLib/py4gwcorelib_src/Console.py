import PySystem

def _is_window_active():
    """Return True when the GW game window is the foreground window.
    Falls back to True if the Windows API is unavailable."""
    try:
        import ctypes
        hwnd = PySystem.Console.get_gw_window_handle()
        if hwnd:
            return ctypes.windll.user32.GetForegroundWindow() == hwnd
    except Exception:
        pass
    return True  # safe default: assume active if we can't check

# Attach missing methods that legacy code expects on Console
PySystem.Console.is_window_active = _is_window_active

def ConsoleLog(sender, message, message_type:int=0 , log: bool = True):
    """Logs a message with an optional message type."""
    if log:
        if message_type == 0:
            PySystem.Console.Log(sender, message, PySystem.Console.MessageType.Info)
        elif message_type == 1:
            PySystem.Console.Log(sender, message, PySystem.Console.MessageType.Warning)
        elif message_type == 2:
            PySystem.Console.Log(sender, message, PySystem.Console.MessageType.Error)
        elif message_type == 3:
            PySystem.Console.Log(sender, message, PySystem.Console.MessageType.Debug)
        elif message_type == 4:
            PySystem.Console.Log(sender, message, PySystem.Console.MessageType.Success)
        elif message_type == 5:
            PySystem.Console.Log(sender, message, PySystem.Console.MessageType.Performance)
        elif message_type == 6:
            PySystem.Console.Log(sender, message, PySystem.Console.MessageType.Notice)
        else:
            PySystem.Console.Log(sender, message, PySystem.Console.MessageType.Info)

Console = PySystem.Console