"""Declarative, class-based API over HeroAI's multibox commands — and its launch-bar bridge.

Everything HeroAI can broadcast to the party lives on one cohesive object, :class:`HeroAICommandAPI`,
so the wiring is not scattered across modules:

* **Declarative actions** — one method per command. Call the one you want:
  ``HeroAICommandAPI().resign()``, ``.pixel_stack()``, ``.form_party()``, … Discoverable via
  autocomplete, individually documented, and type-checked — not a stringly-typed
  ``execute("Resign")`` where the caller must know the magic names.
* **Launch-bar bridge** — :meth:`register_launch_functions` exposes every action as a launch-bar
  function (the launch bar replaces HeroAI's deprecated CommandHotBars), and
  :meth:`import_hotbars_to_launch_bar` migrates any saved hotbars into it.

Each action resolves its own target account set (the party in an explorable, same-map/party accounts
in an outpost — exactly what the old hotbar buttons did) and is fire-and-forget: errors are logged,
never raised. The command *bodies* live in :class:`HeroAI.commands.HeroAICommands`; this class only
gives them a clean, declarative public face.
"""

from typing import Callable
from typing import Sequence

from HeroAI.commands import Command
from HeroAI.commands import HeroAICommands
from HeroAI.utils import SameMapOrPartyAsAccount
from Py4GWCoreLib.GlobalCache import GLOBAL_CACHE
from Py4GWCoreLib.GlobalCache.SharedMemory import AccountStruct
from Py4GWCoreLib.Map import Map
from Py4GWCoreLib.py4gwcorelib_src.Console import ConsoleLog


class HeroAICommandAPI:
    """Single façade for HeroAI's multibox commands and their launch-bar integration.

    A process-wide singleton (like :class:`HeroAICommands`): ``HeroAICommandAPI()`` always returns
    the same object, so bound-method callbacks handed to the launch bar stay stable across reloads.
    """

    _instance = None

    # Launch-bar function ids are namespaced so the hotbar importer can reconstruct them from a
    # command name (``heroai.Resign``).
    FUNCTION_ID_PREFIX = "heroai."
    _GROUP = "HeroAI"
    _FALLBACK_ICON = "ICON_BOLT"

    def __new__(cls) -> "HeroAICommandAPI":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    # ---------------------------------------------------------------------------------------
    # Dispatch core
    # ---------------------------------------------------------------------------------------

    def _resolve_accounts(self) -> list[AccountStruct]:
        """The accounts a command acts on, mirroring the legacy hotbar dispatch.

        In an explorable, the active party slots on our map/party; in an outpost, every account
        sharing our map or party. Broadcast-style commands (e.g. travel) re-derive their own targets
        internally, so passing this list is always safe.
        """
        if Map.IsExplorable():
            return [
                account
                for account in GLOBAL_CACHE.ShMem.GetAllActiveSlotsData()
                if account.IsSlotActive and SameMapOrPartyAsAccount(account)
            ]
        return [
            account
            for account in GLOBAL_CACHE.ShMem.GetAllAccountData()
            if SameMapOrPartyAsAccount(account)
        ]

    def _run(self, command: Command) -> None:
        """Resolve the target accounts and run ``command`` against them. Never raises."""
        if command.command_function is None:
            return
        try:
            command(self._resolve_accounts())
        except Exception as e:
            ConsoleLog("HeroAI", f"Error executing command '{command.name}': {e}")

    # ---------------------------------------------------------------------------------------
    # Declarative command methods — one per HeroAI command. Call the one you want.
    # ---------------------------------------------------------------------------------------

    def pixel_stack(self) -> None:
        """Stack every alt account on the leader's exact position."""
        self._run(HeroAICommands().PixelStack)

    def interact_with_target(self) -> None:
        """Make the whole party interact with the leader's current target."""
        self._run(HeroAICommands().InteractWithTarget)

    def unlock_chest(self) -> None:
        """Send the lowest party-slot account to unlock the leader's targeted chest."""
        self._run(HeroAICommands().UnlockChest)

    def take_dialog_with_target(self) -> None:
        """Take the dialog offered by the leader's current target on every account."""
        self._run(HeroAICommands().TakeDialogWithTarget)

    def open_consumables(self) -> None:
        """Open (or close) the consumables configuration window."""
        self._run(HeroAICommands().OpenConsumables)

    def flag_heroes(self) -> None:
        """Start flagging all heroes to a chosen spot. Explorable only."""
        self._run(HeroAICommands().FlagHeroes)

    def unflag_heroes(self) -> None:
        """Clear all hero flags. Explorable only."""
        self._run(HeroAICommands().UnflagHeroes)

    def resign(self) -> None:
        """Resign the mission on every account. Explorable only."""
        self._run(HeroAICommands().Resign)

    def donate_faction(self) -> None:
        """Donate faction to the guild on every account."""
        self._run(HeroAICommands().DonateFaction)

    def pick_up_loot(self) -> None:
        """Pick up ground loot on every account."""
        self._run(HeroAICommands().PickUpLoot)

    def combat_prep(self) -> None:
        """Use the combat-preparation skills on every account. Explorable only."""
        self._run(HeroAICommands().CombatPrep)

    def disband_party(self) -> None:
        """Make all heroes leave the party. Outpost only."""
        self._run(HeroAICommands().DisbandParty)

    def form_party(self) -> None:
        """Invite all heroes to the party (traveling those on another map first). Outpost only."""
        self._run(HeroAICommands().FormParty)

    def travel_alts_to_leader_map(self) -> None:
        """Send every alt account to the leader's current map. Outpost only."""
        self._run(HeroAICommands().TravelAltsToLeaderMap)

    def leave_party_and_travel_gh(self) -> None:
        """Leave the party and travel to the Guild Hall on every account."""
        self._run(HeroAICommands().LeavePartyAndTravelGH)

    # ---------------------------------------------------------------------------------------
    # Launch-bar bridge
    # ---------------------------------------------------------------------------------------

    def function_id_for(self, command_name: str) -> str:
        """The launch-bar ``function_id`` a HeroAI command is registered under."""
        return f"{self.FUNCTION_ID_PREFIX}{command_name}"

    def _catalog(self) -> list[tuple[Callable[[], None], Command]]:
        """Explicit (action method, command) pairs exposed to the launch bar.

        The list is deliberate — adding a command to the launch bar is a conscious edit here — while
        display metadata (icon/tooltip/map kinds) is read from the :class:`Command`, never duplicated.
        """
        c = HeroAICommands()
        return [
            (self.pixel_stack, c.PixelStack),
            (self.unlock_chest, c.UnlockChest),
            (self.interact_with_target, c.InteractWithTarget),
            (self.take_dialog_with_target, c.TakeDialogWithTarget),
            (self.open_consumables, c.OpenConsumables),
            (self.flag_heroes, c.FlagHeroes),
            (self.unflag_heroes, c.UnflagHeroes),
            (self.resign, c.Resign),
            (self.donate_faction, c.DonateFaction),
            (self.pick_up_loot, c.PickUpLoot),
            (self.combat_prep, c.CombatPrep),
            (self.disband_party, c.DisbandParty),
            (self.form_party, c.FormParty),
            (self.travel_alts_to_leader_map, c.TravelAltsToLeaderMap),
            (self.leave_party_and_travel_gh, c.LeavePartyAndTravelGH),
        ]

    @staticmethod
    def _category_for(map_types: Sequence[str]) -> str:
        """Launch-bar picker subgroup: split commands by where they apply."""
        has_exp = "Explorable" in map_types
        has_out = "Outpost" in map_types
        if has_exp and not has_out:
            return "Explorable"
        if has_out and not has_exp:
            return "Outpost"
        return "General"

    def register_launch_functions(self) -> None:
        """Register every HeroAI command as a launch-bar function (idempotent per boot).

        Launch-bar imports are resolved here, not at module import: the launch-bar package is purged
        and reimported on reload while this module is not, so binding ``register_function`` at call
        time guarantees we populate the *current* catalog. The launch bar stores icons by Font
        Awesome constant *name*, while commands carry the glyph, so we reverse-map glyph → name once.
        """
        from Py4GWCoreLib.py4gwcorelib_src.launch_bar.function_runtime import list_icons
        from Py4GWCoreLib.py4gwcorelib_src.launch_bar.functions_catalog import LaunchFunction
        from Py4GWCoreLib.py4gwcorelib_src.launch_bar.functions_catalog import register_function

        glyph_to_name = {glyph: name for name, glyph in list_icons()}

        for callback, command in self._catalog():
            register_function(
                LaunchFunction(
                    id=self.function_id_for(command.name),
                    name=command.name,
                    icon=glyph_to_name.get(command.icon, self._FALLBACK_ICON),
                    group=self._GROUP,
                    category=self._category_for(command.map_types),
                    callback=callback,
                    tooltip=command.tooltip,
                )
            )

    def import_hotbars_to_launch_bar(self) -> int:
        """Recreate every saved HeroAI CommandHotBar as a launch bar. Returns the number imported.

        Each hotbar becomes its own launch bar, one tile per assigned command bound to the matching
        ``heroai.*`` function, with grid positions preserved. Empty hotbars are skipped. Triggered by
        the "Import to Launch Bar" button in HeroAI's deprecated Hotbars settings tab.
        """
        import LaunchBar

        from HeroAI.settings import Settings

        settings = Settings()
        imported = 0

        for hotbar_id, hotbar in settings.CommandHotBars.items():
            layout: list[tuple[int, int, str, str]] = []
            for row, cmd_row in hotbar.commands.items():
                for col, cmd_name in cmd_row.items():
                    if not cmd_name or cmd_name == "Empty":
                        continue
                    layout.append((int(col), int(row), self.function_id_for(cmd_name), str(cmd_name)))

            if not layout:
                continue

            bar = LaunchBar.add_function_bar(hotbar.name or hotbar_id, layout)
            if bar is not None:
                imported += 1

        ConsoleLog("HeroAI", f"Imported {imported} hotbar(s) into the launch bar.")
        return imported


def register_launch_functions() -> None:
    """Module-level provider entry referenced by the launch-bar catalog.

    Listed in ``functions_catalog._EXTERNAL_PROVIDERS`` as ``"HeroAI.command_api:register_launch_functions"``
    and called on every launch-bar boot; delegates to the singleton :class:`HeroAICommandAPI`.
    """
    HeroAICommandAPI().register_launch_functions()
