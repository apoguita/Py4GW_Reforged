# =============================================================================
# Listeners test - toggle & configure the native GWToolbox-ported listeners.
# -----------------------------------------------------------------------------
# A small ImGui panel over the Py4GWCoreLib.Listeners facade. Enable/disable each
# opt-in listener and tweak its config; state is read back live from the native
# side so what you see is the real listener state, not a local mirror.
#
# Features exercised (all opt-in, off until you tick them here):
#   - Listeners.SkillListFilter        hide known / non-elite skills in skill windows
#   - Listeners.SignetOfCaptureLimit   clamp Signet of Capture count to 10
#   - Listeners.FactionWarning         warn when earned faction reaches a % of the cap
#
# The config setters/getters may be absent until the DLL is rebuilt with the new
# bindings; the panel catches that and reports it in the status line instead of
# erroring.
# =============================================================================

import PyImGui

from Py4GWCoreLib import Listeners

status = {"msg": "ready"}


def _enable_checkbox(label, feature):
    """Checkbox bound to a feature class's IsEnabled/Enable/Disable."""
    try:
        enabled = feature.IsEnabled()
    except Exception as e:
        PyImGui.text("%s: <error %s>" % (label, e))
        return False
    new_val = PyImGui.checkbox(label, enabled)
    if new_val != enabled:
        (feature.Enable if new_val else feature.Disable)()
        status["msg"] = "%s -> %s" % (label, "enabled" if new_val else "disabled")
    return new_val


def _bool_config(label, getter, setter):
    """Indented checkbox bound to a feature's bool get/set pair."""
    try:
        cur = getter()
    except AttributeError:
        PyImGui.text_disabled("  %s (rebuild DLL for this binding)" % label)
        return
    PyImGui.indent(20.0)
    new_val = PyImGui.checkbox(label, cur)
    PyImGui.unindent(20.0)
    if new_val != cur:
        setter(new_val)
        status["msg"] = "%s -> %s" % (label, new_val)


def _int_config(label, getter, setter, lo, hi):
    """Indented int slider bound to a feature's int get/set pair."""
    try:
        cur = getter()
    except AttributeError:
        PyImGui.text_disabled("  %s (rebuild DLL for this binding)" % label)
        return
    PyImGui.indent(20.0)
    new_val = PyImGui.slider_int(label, cur, lo, hi)
    PyImGui.unindent(20.0)
    if new_val != cur:
        setter(new_val)
        status["msg"] = "%s -> %d" % (label, new_val)


def _ui():
    if not PyImGui.begin("Listeners test"):
        PyImGui.end()
        return

    # Registry sanity: show every native-registered listener name.
    try:
        PyImGui.text_disabled("registered: " + ", ".join(Listeners.GetNames()))
    except Exception as e:
        PyImGui.text("Listeners.GetNames() failed: %s" % e)
        PyImGui.end()
        return

    slf = Listeners.SkillListFilter
    PyImGui.separator()
    PyImGui.text("Skill list filter")
    if _enable_checkbox("skill_list_filter", slf):
        _bool_config("hide known skills", slf.GetHideKnownSkills, slf.SetHideKnownSkills)
        _bool_config("hide non-elites on capture", slf.GetHideNonElitesOnCapture, slf.SetHideNonElitesOnCapture)

    PyImGui.separator()
    PyImGui.text("Signet of capture limit")
    _enable_checkbox("signet_of_capture_limit", Listeners.SignetOfCaptureLimit)

    fw = Listeners.FactionWarning
    PyImGui.separator()
    PyImGui.text("Faction warning")
    if _enable_checkbox("faction_warning", fw):
        _int_config("warn at %", fw.GetWarnPercent, fw.SetWarnPercent, 0, 100)

    chest = Listeners.AutoOpenLockedChest
    PyImGui.separator()
    PyImGui.text("Auto-open locked chest")
    if _enable_checkbox("auto_open_locked_chest", chest):
        _bool_config("use key", chest.GetUseKey, chest.SetUseKey)
        _bool_config("use lockpick", chest.GetUseLockpick, chest.SetUseLockpick)

    PyImGui.separator()
    PyImGui.text("Toggle-only features")
    _enable_checkbox("cinematic_skip", Listeners.CinematicSkip)
    _enable_checkbox("auto_return_on_defeat", Listeners.AutoReturnOnDefeat)
    _enable_checkbox("disable_gold_confirmation", Listeners.DisableGoldConfirmation)
    _enable_checkbox("remove_cast_bar_minimum", Listeners.RemoveCastBarMinimum)
    _enable_checkbox("auto_cancel_ua", Listeners.AutoCancelUA)
    _enable_checkbox("faction_donate_skip_name", Listeners.FactionDonateSkipName)
    _enable_checkbox("keep_current_quest", Listeners.KeepCurrentQuest)

    PyImGui.separator()
    PyImGui.text("status: " + status["msg"])
    PyImGui.end()


def main():
    try:
        _ui()
    except AttributeError as e:
        # Facade or module missing -> DLL not built with the listeners bindings yet.
        status["msg"] = "PyListeners missing / stale - rebuild the DLL (%s)" % e
    except Exception as e:
        status["msg"] = "err: %s" % e


if __name__ == "__main__":
    main()
