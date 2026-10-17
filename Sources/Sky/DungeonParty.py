from __future__ import annotations

from typing import Any

import PyImGui

from Py4GWCoreLib.enums_src.Hero_enums import HeroType
from Py4GWCoreLib.py4gwcorelib_src.BehaviorTree import BehaviorTree


class DungeonPartyConfig:
    """Reusable Party-tab hero selection for dungeon BottingTree scripts.

    The configuration is intentionally empty by default. Selected heroes are
    read lazily when CreateParty actually runs, so UI changes do not require
    rebuilding the main botting tree.
    """

    def __init__(
        self,
        settings: Any,
        *,
        section: str = "Party",
        slot_count: int = 7,
    ) -> None:
        self._settings = settings
        self._section = str(section)
        self._slot_count = max(1, int(slot_count))
        self._loaded = False
        self._slots: list[int] = [0] * self._slot_count

        self._hero_options: list[HeroType] = [HeroType.None_] + sorted(
            [hero for hero in HeroType if hero != HeroType.None_],
            key=lambda hero: self._humanize_hero_name(hero.name).casefold(),
        )
        self._hero_labels: list[str] = [
            self._humanize_hero_name(hero.name) for hero in self._hero_options
        ]
        self._hero_id_to_index: dict[int, int] = {
            int(hero.value): index for index, hero in enumerate(self._hero_options)
        }

    @staticmethod
    def _humanize_hero_name(enum_name: str) -> str:
        if enum_name == "None_":
            return "<Empty>"
        if not enum_name:
            return "<Empty>"

        words: list[str] = []
        current = enum_name[0]
        for char in enum_name[1:]:
            previous = current[-1]
            if (
                (char.isupper() and not previous.isupper())
                or (char.isdigit() and not previous.isdigit())
            ):
                words.append(current)
                current = char
            else:
                current += char
        words.append(current)
        return " ".join(words)

    def _load(self) -> None:
        if self._loaded:
            return

        valid_ids = {int(hero.value) for hero in self._hero_options}
        for index in range(self._slot_count):
            hero_id = int(
                self._settings.get_int(
                    self._section,
                    f"HeroSlot{index + 1}",
                    0,
                )
                or 0
            )
            self._slots[index] = hero_id if hero_id in valid_ids else 0

        self._loaded = True

    def selected_hero_ids(self) -> list[int]:
        """Return selected heroes in slot order, skipping empty/duplicate slots."""
        self._load()

        result: list[int] = []
        seen: set[int] = set()
        for hero_id in self._slots:
            hero_id = int(hero_id)
            if hero_id <= 0 or hero_id in seen:
                continue
            seen.add(hero_id)
            result.append(hero_id)
        return result

    def clear(self) -> None:
        self._load()
        for index in range(self._slot_count):
            if self._slots[index] == 0:
                continue
            self._slots[index] = 0
            self._settings.set(self._section, f"HeroSlot{index + 1}", 0)

    def draw_tab(self) -> None:
        """Draw the Party tab. Empty slots mean CreateParty adds no heroes."""
        self._load()

        PyImGui.text("Heroes added when CreateParty runs")
        PyImGui.separator()
        PyImGui.text("Leave every slot <Empty> to add no heroes.")
        PyImGui.text("Heroes are added in slot order; duplicate selections are ignored.")
        PyImGui.spacing()

        for slot_index in range(self._slot_count):
            hero_id = int(self._slots[slot_index])
            current_index = self._hero_id_to_index.get(hero_id, 0)
            new_index = int(
                PyImGui.combo(
                    f"Hero {slot_index + 1}##DungeonPartyHero{slot_index + 1}",
                    current_index,
                    self._hero_labels,
                )
            )
            if new_index == current_index:
                continue

            new_index = max(0, min(new_index, len(self._hero_options) - 1))
            new_hero_id = int(self._hero_options[new_index].value)
            self._slots[slot_index] = new_hero_id
            self._settings.set(
                self._section,
                f"HeroSlot{slot_index + 1}",
                new_hero_id,
            )

        selected = self.selected_hero_ids()
        PyImGui.spacing()
        PyImGui.separator()
        if selected:
            names = [
                self._hero_labels[self._hero_id_to_index.get(hero_id, 0)]
                for hero_id in selected
            ]
            PyImGui.text(f"Selected: {', '.join(names)}")
        else:
            PyImGui.text("Selected: none")

        if PyImGui.button("Clear Party Heroes##DungeonPartyClear"):
            self.clear()

    def create_party_node(
        self,
        *,
        multibox_invite: bool = True,
        timeout_ms: int = 30_000,
        poll_interval_ms: int = 100,
        aftercast_ms: int = 250,
        log: bool = True,
        name: str = "Create Party From Party Tab",
    ) -> BehaviorTree:
        """Create a lazy BT node using the hero selection at execution time."""

        def _build(_node: BehaviorTree.Node) -> BehaviorTree:
            # Imported lazily to keep this UI helper independent from wrapper
            # initialization order in the dungeon scripts.
            from Sources.ApoSource.ApoBottingLib import wrappers as BT

            return BT.CreateParty(
                hero_ids=self.selected_hero_ids(),
                multibox_invite=multibox_invite,
                timeout_ms=timeout_ms,
                poll_interval_ms=poll_interval_ms,
                aftercast_ms=aftercast_ms,
                log=log,
            )

        return BehaviorTree(
            BehaviorTree.SubtreeNode(
                name=name,
                subtree_fn=_build,
            )
        )
