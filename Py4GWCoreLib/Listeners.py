import PyListeners

__all__ = ["Listeners"]


class Listeners:
    """
    Ergonomic facade over the native PyListeners module: runtime toggles for the
    native game-event listeners, plus per-feature config. Each listener is a
    named unit of native callbacks that can be switched on or off; a disabled
    listener has zero overhead.

    Use the generic methods (Enable/Disable/Toggle by name) for any listener, or
    the nested feature classes (SkillListFilter, SignetOfCaptureLimit,
    FactionWarning) for a named surface with config helpers.
    """

    # Registered listener names (see include/listeners/listeners.h).
    MERCHANT = "merchant"
    AGENT_EVENTS = "agent_events"
    SKILL_LIST_FILTER = "skill_list_filter"
    SIGNET_OF_CAPTURE_LIMIT = "signet_of_capture_limit"
    FACTION_WARNING = "faction_warning"
    CINEMATIC_SKIP = "cinematic_skip"
    AUTO_RETURN_ON_DEFEAT = "auto_return_on_defeat"
    DISABLE_GOLD_CONFIRMATION = "disable_gold_confirmation"
    REMOVE_CAST_BAR_MINIMUM = "remove_cast_bar_minimum"
    AUTO_CANCEL_UA = "auto_cancel_ua"
    AUTO_OPEN_LOCKED_CHEST = "auto_open_locked_chest"
    FACTION_DONATE_SKIP_NAME = "faction_donate_skip_name"
    KEEP_CURRENT_QUEST = "keep_current_quest"

    @staticmethod
    def GetNames():
        """
        Purpose: List the names of all toggleable listeners.
        Args:
            None
        Returns: list[str]
        """
        return PyListeners.list()

    @staticmethod
    def Enable(name):
        """
        Purpose: Enable a listener by name.
        Args:
            name (str): listener name.
        Returns: bool - False if the name is unknown.
        """
        return PyListeners.enable(name)

    @staticmethod
    def Disable(name):
        """
        Purpose: Disable a listener by name.
        Args:
            name (str): listener name.
        Returns: bool - False if the name is unknown.
        """
        return PyListeners.disable(name)

    @staticmethod
    def Toggle(name):
        """
        Purpose: Toggle a listener by name.
        Args:
            name (str): listener name.
        Returns: bool - False if the name is unknown.
        """
        return PyListeners.toggle(name)

    @staticmethod
    def SetEnabled(name, enabled):
        """
        Purpose: Set a listener's enabled state.
        Args:
            name (str): listener name.
            enabled (bool): desired state.
        Returns: bool - False if the name is unknown.
        """
        return PyListeners.set_enabled(name, enabled)

    @staticmethod
    def IsEnabled(name):
        """
        Purpose: Check whether a listener is enabled.
        Args:
            name (str): listener name.
        Returns: bool - False if the name is unknown or disabled.
        """
        return PyListeners.is_enabled(name)

    class SkillListFilter:
        """
        Hide skills in the tome / skill-trainer / skill-capture windows. Opt-in:
        enable it, then set the flags below. Both flags share one native hook.
        """
        NAME = "skill_list_filter"

        @staticmethod
        def Enable():
            """Purpose: Enable the skill-list filter. Returns: bool."""
            return PyListeners.enable(Listeners.SkillListFilter.NAME)

        @staticmethod
        def Disable():
            """Purpose: Disable the skill-list filter. Returns: bool."""
            return PyListeners.disable(Listeners.SkillListFilter.NAME)

        @staticmethod
        def Toggle():
            """Purpose: Toggle the skill-list filter. Returns: bool."""
            return PyListeners.toggle(Listeners.SkillListFilter.NAME)

        @staticmethod
        def IsEnabled():
            """Purpose: Whether the skill-list filter is enabled. Returns: bool."""
            return PyListeners.is_enabled(Listeners.SkillListFilter.NAME)

        @staticmethod
        def SetHideKnownSkills(value):
            """
            Purpose: Hide skills the character already owns from tome / trainer /
                     capture windows.
            Args:
                value (bool)
            Returns: None
            """
            PyListeners.set_hide_known_skills(value)

        @staticmethod
        def GetHideKnownSkills():
            """Purpose: Whether known skills are hidden. Returns: bool."""
            return PyListeners.get_hide_known_skills()

        @staticmethod
        def SetHideNonElitesOnCapture(value):
            """
            Purpose: In the skill-capture window, hide all non-elite skills.
            Args:
                value (bool)
            Returns: None
            """
            PyListeners.set_hide_nonelites_on_capture(value)

        @staticmethod
        def GetHideNonElitesOnCapture():
            """Purpose: Whether non-elites are hidden on capture. Returns: bool."""
            return PyListeners.get_hide_nonelites_on_capture()

    class SignetOfCaptureLimit:
        """
        Clamp the displayed Signet of Capture count to 10 in the skills window.
        Opt-in; no extra config.
        """
        NAME = "signet_of_capture_limit"

        @staticmethod
        def Enable():
            """Purpose: Enable the signet-of-capture limit. Returns: bool."""
            return PyListeners.enable(Listeners.SignetOfCaptureLimit.NAME)

        @staticmethod
        def Disable():
            """Purpose: Disable the signet-of-capture limit. Returns: bool."""
            return PyListeners.disable(Listeners.SignetOfCaptureLimit.NAME)

        @staticmethod
        def Toggle():
            """Purpose: Toggle the signet-of-capture limit. Returns: bool."""
            return PyListeners.toggle(Listeners.SignetOfCaptureLimit.NAME)

        @staticmethod
        def IsEnabled():
            """Purpose: Whether the signet-of-capture limit is enabled. Returns: bool."""
            return PyListeners.is_enabled(Listeners.SignetOfCaptureLimit.NAME)

    class FactionWarning:
        """
        Warn (via the console) when earned faction reaches a percentage of the
        cap in a Luxon/Kurzick challenge or elite-area outpost. Opt-in: enable
        it, then set the threshold percentage.
        """
        NAME = "faction_warning"

        @staticmethod
        def Enable():
            """Purpose: Enable the faction warning. Returns: bool."""
            return PyListeners.enable(Listeners.FactionWarning.NAME)

        @staticmethod
        def Disable():
            """Purpose: Disable the faction warning. Returns: bool."""
            return PyListeners.disable(Listeners.FactionWarning.NAME)

        @staticmethod
        def Toggle():
            """Purpose: Toggle the faction warning. Returns: bool."""
            return PyListeners.toggle(Listeners.FactionWarning.NAME)

        @staticmethod
        def IsEnabled():
            """Purpose: Whether the faction warning is enabled. Returns: bool."""
            return PyListeners.is_enabled(Listeners.FactionWarning.NAME)

        @staticmethod
        def SetWarnPercent(percent):
            """
            Purpose: Set the percentage of the faction cap at which to warn.
            Args:
                percent (int): 0-100 (clamped native-side).
            Returns: None
            """
            PyListeners.set_faction_warn_percent(percent)

        @staticmethod
        def GetWarnPercent():
            """Purpose: The configured faction-warning percentage. Returns: int."""
            return PyListeners.get_faction_warn_percent()

    class CinematicSkip:
        """Automatically skip in-game cinematics. Opt-in; no extra config."""
        NAME = "cinematic_skip"

        @staticmethod
        def Enable():
            """Purpose: Enable cinematic skipping. Returns: bool."""
            return PyListeners.enable(Listeners.CinematicSkip.NAME)

        @staticmethod
        def Disable():
            """Purpose: Disable cinematic skipping. Returns: bool."""
            return PyListeners.disable(Listeners.CinematicSkip.NAME)

        @staticmethod
        def Toggle():
            """Purpose: Toggle cinematic skipping. Returns: bool."""
            return PyListeners.toggle(Listeners.CinematicSkip.NAME)

        @staticmethod
        def IsEnabled():
            """Purpose: Whether cinematic skipping is enabled. Returns: bool."""
            return PyListeners.is_enabled(Listeners.CinematicSkip.NAME)

    class AutoReturnOnDefeat:
        """
        Return the party to the outpost on a wipe (only when the local player is
        the party leader). Opt-in; no extra config.
        """
        NAME = "auto_return_on_defeat"

        @staticmethod
        def Enable():
            """Purpose: Enable auto-return on defeat. Returns: bool."""
            return PyListeners.enable(Listeners.AutoReturnOnDefeat.NAME)

        @staticmethod
        def Disable():
            """Purpose: Disable auto-return on defeat. Returns: bool."""
            return PyListeners.disable(Listeners.AutoReturnOnDefeat.NAME)

        @staticmethod
        def Toggle():
            """Purpose: Toggle auto-return on defeat. Returns: bool."""
            return PyListeners.toggle(Listeners.AutoReturnOnDefeat.NAME)

        @staticmethod
        def IsEnabled():
            """Purpose: Whether auto-return on defeat is enabled. Returns: bool."""
            return PyListeners.is_enabled(Listeners.AutoReturnOnDefeat.NAME)

    class DisableGoldConfirmation:
        """
        Remove the confirmation prompt when selling gold/green items to merchants
        (memory patch). Opt-in; no extra config.
        """
        NAME = "disable_gold_confirmation"

        @staticmethod
        def Enable():
            """Purpose: Enable (remove the confirmation). Returns: bool."""
            return PyListeners.enable(Listeners.DisableGoldConfirmation.NAME)

        @staticmethod
        def Disable():
            """Purpose: Disable (restore the confirmation). Returns: bool."""
            return PyListeners.disable(Listeners.DisableGoldConfirmation.NAME)

        @staticmethod
        def Toggle():
            """Purpose: Toggle the gold/green confirmation removal. Returns: bool."""
            return PyListeners.toggle(Listeners.DisableGoldConfirmation.NAME)

        @staticmethod
        def IsEnabled():
            """Purpose: Whether the confirmation removal is enabled. Returns: bool."""
            return PyListeners.is_enabled(Listeners.DisableGoldConfirmation.NAME)

    class RemoveCastBarMinimum:
        """
        Remove the 1.5s minimum warmup for the cast bar to appear, so very short
        casts still show it (memory patch). Opt-in; no extra config.
        """
        NAME = "remove_cast_bar_minimum"

        @staticmethod
        def Enable():
            """Purpose: Enable cast-bar minimum removal. Returns: bool."""
            return PyListeners.enable(Listeners.RemoveCastBarMinimum.NAME)

        @staticmethod
        def Disable():
            """Purpose: Disable cast-bar minimum removal. Returns: bool."""
            return PyListeners.disable(Listeners.RemoveCastBarMinimum.NAME)

        @staticmethod
        def Toggle():
            """Purpose: Toggle cast-bar minimum removal. Returns: bool."""
            return PyListeners.toggle(Listeners.RemoveCastBarMinimum.NAME)

        @staticmethod
        def IsEnabled():
            """Purpose: Whether cast-bar minimum removal is enabled. Returns: bool."""
            return PyListeners.is_enabled(Listeners.RemoveCastBarMinimum.NAME)

    class AutoCancelUA:
        """Drop Unyielding Aura before recasting it. Opt-in; no extra config."""
        NAME = "auto_cancel_ua"

        @staticmethod
        def Enable():
            """Purpose: Enable auto-cancel Unyielding Aura. Returns: bool."""
            return PyListeners.enable(Listeners.AutoCancelUA.NAME)

        @staticmethod
        def Disable():
            """Purpose: Disable auto-cancel Unyielding Aura. Returns: bool."""
            return PyListeners.disable(Listeners.AutoCancelUA.NAME)

        @staticmethod
        def Toggle():
            """Purpose: Toggle auto-cancel Unyielding Aura. Returns: bool."""
            return PyListeners.toggle(Listeners.AutoCancelUA.NAME)

        @staticmethod
        def IsEnabled():
            """Purpose: Whether auto-cancel Unyielding Aura is enabled. Returns: bool."""
            return PyListeners.is_enabled(Listeners.AutoCancelUA.NAME)

    class AutoOpenLockedChest:
        """
        Auto-send the use-key and/or use-lockpick response at a locked chest.
        Opt-in: enable it, then set which response(s) to send.
        """
        NAME = "auto_open_locked_chest"

        @staticmethod
        def Enable():
            """Purpose: Enable auto-open at locked chests. Returns: bool."""
            return PyListeners.enable(Listeners.AutoOpenLockedChest.NAME)

        @staticmethod
        def Disable():
            """Purpose: Disable auto-open at locked chests. Returns: bool."""
            return PyListeners.disable(Listeners.AutoOpenLockedChest.NAME)

        @staticmethod
        def Toggle():
            """Purpose: Toggle auto-open at locked chests. Returns: bool."""
            return PyListeners.toggle(Listeners.AutoOpenLockedChest.NAME)

        @staticmethod
        def IsEnabled():
            """Purpose: Whether auto-open at locked chests is enabled. Returns: bool."""
            return PyListeners.is_enabled(Listeners.AutoOpenLockedChest.NAME)

        @staticmethod
        def SetUseKey(value):
            """
            Purpose: Auto-send the 'use key' response at a locked chest.
            Args:
                value (bool)
            Returns: None
            """
            PyListeners.set_auto_open_use_key(value)

        @staticmethod
        def GetUseKey():
            """Purpose: Whether the 'use key' response is auto-sent. Returns: bool."""
            return PyListeners.get_auto_open_use_key()

        @staticmethod
        def SetUseLockpick(value):
            """
            Purpose: Auto-send the 'use lockpick' response at a locked chest.
            Args:
                value (bool)
            Returns: None
            """
            PyListeners.set_auto_open_use_lockpick(value)

        @staticmethod
        def GetUseLockpick():
            """Purpose: Whether the 'use lockpick' response is auto-sent. Returns: bool."""
            return PyListeners.get_auto_open_use_lockpick()

    class FactionDonateSkipName:
        """
        Prefill the character-name field when donating faction (one-click
        donation). Opt-in; no extra config.
        """
        NAME = "faction_donate_skip_name"

        @staticmethod
        def Enable():
            """Purpose: Enable faction-donate name skip. Returns: bool."""
            return PyListeners.enable(Listeners.FactionDonateSkipName.NAME)

        @staticmethod
        def Disable():
            """Purpose: Disable faction-donate name skip. Returns: bool."""
            return PyListeners.disable(Listeners.FactionDonateSkipName.NAME)

        @staticmethod
        def Toggle():
            """Purpose: Toggle faction-donate name skip. Returns: bool."""
            return PyListeners.toggle(Listeners.FactionDonateSkipName.NAME)

        @staticmethod
        def IsEnabled():
            """Purpose: Whether faction-donate name skip is enabled. Returns: bool."""
            return PyListeners.is_enabled(Listeners.FactionDonateSkipName.NAME)

    class KeepCurrentQuest:
        """
        Keep the manually-chosen quest active when the game auto-adds a new one.
        Opt-in; no extra config.
        """
        NAME = "keep_current_quest"

        @staticmethod
        def Enable():
            """Purpose: Enable keep-current-quest. Returns: bool."""
            return PyListeners.enable(Listeners.KeepCurrentQuest.NAME)

        @staticmethod
        def Disable():
            """Purpose: Disable keep-current-quest. Returns: bool."""
            return PyListeners.disable(Listeners.KeepCurrentQuest.NAME)

        @staticmethod
        def Toggle():
            """Purpose: Toggle keep-current-quest. Returns: bool."""
            return PyListeners.toggle(Listeners.KeepCurrentQuest.NAME)

        @staticmethod
        def IsEnabled():
            """Purpose: Whether keep-current-quest is enabled. Returns: bool."""
            return PyListeners.is_enabled(Listeners.KeepCurrentQuest.NAME)
