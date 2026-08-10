"""Pure data for the title-on-map-load feature."""

from dataclasses import dataclass

from Py4GWCoreLib.enums_src.Title_enums import TitleID
from Py4GWCoreLib.enums_src.Title_enums import TITLE_NAME


@dataclass(frozen=True)
class TitleMapRule:
    """A title and the map names/IDs that select it."""

    title_id: TitleID
    map_names: tuple[str, ...]
    map_ids: tuple[int, ...] = ()

    @property
    def title_name(self) -> str:
        return TITLE_NAME.get(self.title_id, self.title_id.name)


@dataclass
class TitleOnMapLoadConfig:
    enabled: bool = True


TITLE_MAP_RULES: tuple[TitleMapRule, ...] = (
    TitleMapRule(
        TitleID.Asuran,
        (
            "Alcazia Tangle", "Arbor Bay", "Gadd's Encampment", "Magus Stones", "Rata Sum", "Riven Earth",
            "Sparkfly Swamp", "Tarnished Haven", "Umbral Grotto", "Verdant Cascades", "Vlox's Falls",
            "Finding the Bloodstone (Level 1)", "Finding the Bloodstone (Level 2)",
            "Finding the Bloodstone (Level 3)", "The Elusive Golemancer (Level 1)",
            "The Elusive Golemancer (Level 2)", "The Elusive Golemancer (Level 3)",
        ),
    ),
    TitleMapRule(
        TitleID.Deldrimor,
        (
            "A Gate Too Far (Level 1)", "A Gate Too Far (Level 2)", "A Gate Too Far (Level 3)",
            "A Time for Heroes", "Central Transfer Chamber", "Destruction's Depths (Level 1)",
            "Destruction's Depths (Level 2)", "Destruction's Depths (Level 3)",
            "Genius Operated Living Enchanted Manifestation", "Glint's Challenge",
            "Raven's Point (Level 1)", "Raven's Point (Level 2)", "Raven's Point (Level 3)",
        ),
        (617, 618, 619),
    ),
    TitleMapRule(
        TitleID.Norn,
        (
            "Attack of the Nornbear", "Bjora Marches", "Boreal Station", "Cold as Ice", "Curse of the Nornbear",
            "Drakkar Lake", "Eye of the North", "Gunnar's Hold", "Ice Cliff Chasms", "Jaga Moraine",
            "Mano a Norn-o", "Norrhart Domains", "Olafstead", "Service in Defense of the Eye", "Sifhalla",
            "The Norn Fighting Tournament", "Varajar Fells",
        ),
    ),
    TitleMapRule(
        TitleID.Ebon_Vanguard,
        (
            "Against the Charr", "Ascalon City", "Assault on the Stronghold", "Blood Washes Blood",
            "Cathedral of Flames (Level 1)", "Cathedral of Flames (Level 2)", "Cathedral of Flames (Level 3)",
            "Dalada Uplands", "Diessa Lowlands", "Doomlore Shrine", "Dragon's Gullet", "Eastern Frontier",
            "Flame Temple Corridor", "Fort Ranik", "Frontier Gate", "Grendich Courthouse", "Grothmar Wardowns",
            "Longeye's Ledge", "Nolani Academy", "Old Ascalon", "Piken Square", "Regent Valley",
            "Rragar's Menagerie (Level 1)", "Rragar's Menagerie (Level 2)", "Rragar's Menagerie (Level 3)",
            "Ruins of Surmia", "Sacnoth Valley", "Sardelac Sanitarium", "The Breach", "The Great Northern Wall",
            "Warband Training", "Warband of Brothers (Level 1)", "Warband of Brothers (Level 2)",
            "Warband of Brothers (Level 3)",
        ),
    ),
    TitleMapRule(
        TitleID.Lightbringer,
        (
            "Abaddon's Gate", "Basalt Grotto", "Bone Palace", "Crystal Overlook", "Depths of Madness",
            "Domain of Anguish", "Domain of Fear", "Domain of Pain", "Domain of Secrets",
            "The Ebony Citadel of Mallyx", "Dzagonur Bastion", "Forum Highlands", "Gate of Desolation",
            "Gate of Fear", "Gate of Madness", "Gate of Anguish", "Gate of Pain", "Gate of Secrets",
            "Gate of Torment", "Gate of the Nightfallen Lands", "Grand Court of Sebelkeh", "Heart of Abaddon",
            "Jennur's Horde", "Joko's Domain", "Lair of the Forgotten", "Nightfallen Coast", "Nightfallen Garden",
            "Nightfallen Jahai", "Nundu Bay", "Poisoned Outcrops", "Remains of Sahlahja", "Ruins of Morah",
            "The Alkali Pan", "The Mirror of Lyss", "The Mouth of Torment", "The Ruptured Heart",
            "The Shadow Nexus", "The Shattered Ravines", "The Sulfurous Wastes", "Throne of Secrets",
            "Vehtendi Valley", "Yatendi Canyons",
        ),
    ),
)


# Quest-based overrides retain the old widget's precedence over map-name matching.
QUEST_TITLE_OVERRIDES: dict[int, TitleID] = {
    897: TitleID.Deldrimor,
    873: TitleID.Norn,
}
