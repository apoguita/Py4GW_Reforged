import PyImGui
import PySystem

from Py4GWCoreLib import Agent, Color, ImGui, Player, Routines, ThrottledTimer, Utils
from Py4GWCoreLib.py4gwcorelib_src.Settings import Settings

MODULE_NAME = "Agent Follower"
MODULE_ICON = "Assets/Textures/Module_Icons/Compass+.png"
WIDGET_KEY = "Widgets/Guild Wars/Agent Follower"

INI_PATH = "Widgets/AgentFollower"
INI_FILENAME = "AgentFollower.ini"

DEFAULT_DISTANCE = 400
DEFAULT_INTERVAL_MS = 3000
MIN_INTERVAL_MS = 500

update_timer = ThrottledTimer(DEFAULT_INTERVAL_MS)
initialized = False
INI_KEY = ""
_last_target_valid = None
_last_target_identity = None


def _cfg() -> Settings:
    return Settings(f"{INI_PATH}/{INI_FILENAME}", "account")


def _log(message: str, message_type: PySystem.Console.MessageType = PySystem.Console.MessageType.Info) -> None:
    PySystem.Console.Log(MODULE_NAME, message, message_type)


# ---------------------------------------
# Follow logic
# ---------------------------------------

def _follow_step() -> None:
    """One throttled follow check: walk to the target when out of range."""
    global _last_target_valid, _last_target_identity

    cfg = _cfg()
    if not cfg.get_bool("Follow", "enabled", False):
        _last_target_valid = None
        _last_target_identity = None
        return

    target_id = cfg.get_int("Follow", "agent_id", 0)
    player_id = Player.GetAgentID()
    target_alive = target_id > 0 and Agent.IsValid(target_id) and Agent.IsLiving(target_id)

    if _last_target_valid is True and not target_alive:
        _log(
            f"Follow target {target_id} is no longer valid on this map; standing by.",
            PySystem.Console.MessageType.Warning,
        )
    _last_target_valid = target_alive

    if not target_alive:
        _last_target_identity = None
        return
    if target_id == player_id:
        _last_target_identity = None
        _log("Follow target is yourself; nothing to do.", PySystem.Console.MessageType.Warning)
        return

    target_x, target_y = Agent.GetXY(target_id)
    my_x, my_y = Agent.GetXY(player_id)
    distance = Utils.Distance((target_x, target_y), (my_x, my_y))
    threshold = max(0, cfg.get_int("Follow", "distance", DEFAULT_DISTANCE))

    if distance <= threshold:
        return

    name = Agent.GetNameByID(target_id) or f"#{target_id}"
    identity = (target_id, name)
    if identity != _last_target_identity:
        _last_target_identity = identity
        _log(f"Following {name} (id {target_id}); distance {distance:.0f} > {threshold}, walking to agent.")
    Player.Move(target_x, target_y)


# ---------------------------------------
# Widget lifecycle functions
# ---------------------------------------

def draw_widget():
    """Draws the widget interface."""
    global INI_KEY
    cfg = _cfg()

    if ImGui.Begin(INI_KEY, MODULE_NAME, flags=PyImGui.WindowFlags.AlwaysAutoResize):
        enabled = cfg.get_bool("Follow", "enabled", False)
        new_enabled = PyImGui.checkbox("Follow Enabled", enabled)
        if new_enabled != enabled:
            cfg.set("Follow", "enabled", new_enabled)
            if new_enabled:
                _log("Agent Follower enabled.")
            else:
                _log("Agent Follower disabled.")

        PyImGui.separator()

        target_id = cfg.get_int("Follow", "agent_id", 0)
        new_target = PyImGui.input_int("Agent ID", target_id)
        if new_target != target_id:
            cfg.set("Follow", "agent_id", max(0, new_target))
            _last_target_identity = None

        if PyImGui.button("Set from Current Target"):
            current_target = Player.GetTargetID()
            if Agent.IsValid(current_target) and Agent.IsLiving(current_target):
                cfg.set("Follow", "agent_id", current_target)
                _last_target_identity = None
                _log(f"Follow target set to agent {current_target} ({Agent.GetNameByID(current_target)}).")
            else:
                _log("Current target is not a valid living agent.", PySystem.Console.MessageType.Warning)

        target_id = cfg.get_int("Follow", "agent_id", 0)
        if target_id > 0 and Agent.IsValid(target_id):
            name = Agent.GetNameByID(target_id) or f"#{target_id}"
            target_x, target_y = Agent.GetXY(target_id)
            player_x, player_y = Player.GetXY()
            distance = Utils.Distance((target_x, target_y), (player_x, player_y))
            PyImGui.text(f"Target: {name} (id {target_id})")
            PyImGui.text(f"Distance: {distance:.0f} units")
        else:
            PyImGui.text_colored("Target not found on this map.", Color(255, 120, 120, 255).to_tuple_normalized())

        PyImGui.separator()

        distance = cfg.get_int("Follow", "distance", DEFAULT_DISTANCE)
        new_distance = PyImGui.slider_int("Follow Distance", distance, 50, 2000)
        if new_distance != distance:
            cfg.set("Follow", "distance", new_distance)

        interval_sec = cfg.get_int("Follow", "interval_sec", DEFAULT_INTERVAL_MS // 1000)
        new_interval = PyImGui.slider_int("Check Interval (s)", interval_sec, 1, 30)
        if new_interval != interval_sec:
            cfg.set("Follow", "interval_sec", new_interval)

        PyImGui.separator()

        if PyImGui.button("Stop Movement"):
            Player.Move(0.0, 0.0)
            _log("Move command reset.")

    ImGui.End(INI_KEY)


def tooltip():
    """Optional tooltip for the widget manager."""
    PyImGui.begin_tooltip()

    title_color = Color(255, 200, 100, 255)
    ImGui.push_font("Regular", 20)
    PyImGui.text_colored(MODULE_NAME, title_color.to_tuple_normalized())
    ImGui.pop_font()
    PyImGui.spacing()
    PyImGui.separator()

    PyImGui.text("Follow a given agent by checking the distance")
    PyImGui.text("every few seconds and walking to it when too far.")

    PyImGui.spacing()

    PyImGui.text_colored("Features:", title_color.to_tuple_normalized())
    PyImGui.bullet_text("Set the follow target by agent ID or current target.")
    PyImGui.bullet_text("Configurable follow distance and check interval.")
    PyImGui.bullet_text("Stops automatically when the target leaves the map.")

    PyImGui.spacing()
    PyImGui.separator()
    PyImGui.spacing()

    PyImGui.text_colored("Credits:", title_color.to_tuple_normalized())
    PyImGui.bullet_text("Developed with Py4GW")

    PyImGui.end_tooltip()


def draw():
    """this code runs every frame to draw the widget"""
    global initialized
    if initialized:
        draw_widget()


def main():
    """this code runs every frame; follow logic is throttled internally"""
    global INI_KEY, initialized, update_timer
    if not Routines.Checks.Map.MapValid():
        return
    if not INI_KEY:
        INI_KEY = _cfg().name
        if not INI_KEY:
            return
        initialized = True

    cfg = _cfg()
    interval_ms = cfg.get_int("Follow", "interval_sec", DEFAULT_INTERVAL_MS // 1000) * 1000
    update_timer.SetThrottleTime(max(MIN_INTERVAL_MS, interval_ms))
    if not update_timer.IsExpired():
        return
    update_timer.Reset()
    _follow_step()


if __name__ == "__main__":
    main()