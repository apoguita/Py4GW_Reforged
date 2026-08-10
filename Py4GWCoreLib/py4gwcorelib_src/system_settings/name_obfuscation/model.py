"""Name Obfuscation model — pure data (default name buckets).

No PyImGui / PyNameObfuscator / Settings imports: just the seed word-lists used to generate fake
names by shuffling one first name + one surname. Users can edit or reset these; the runtime reads
the live (persisted) buckets, falling back to these defaults on a fresh install.
"""

# Lore-flavoured seed pools. Kept deliberately generic/fantasy so a generated alias reads like a
# plausible Guild Wars character name without colliding with anything real.
DEFAULT_FIRST_NAMES: "tuple[str, ...]" = (
    "Aldric", "Bryn", "Caelum", "Dagmar", "Eowin", "Fenris", "Gwenn", "Halden",
    "Isolde", "Joren", "Kaida", "Lorne", "Mirae", "Nyx", "Orrin", "Perrin",
    "Quen", "Rowan", "Sable", "Tarnis", "Ulric", "Vael", "Wren", "Xanthe",
    "Ysolde", "Zoran", "Ashe", "Corvin", "Delphine", "Eiric",
)

DEFAULT_SURNAMES: "tuple[str, ...]" = (
    "Ashford", "Blackmoor", "Cinderfell", "Dawnbreaker", "Emberly", "Frostwind",
    "Grimhollow", "Hollowbrook", "Ironvale", "Jadefire", "Kingsmere", "Lightbringer",
    "Moonshadow", "Nightfall", "Oakenshield", "Palewood", "Quicksilver", "Ravenscar",
    "Stormrider", "Thornwood", "Umbermoor", "Valebrook", "Whitethorn", "Wyrmsbane",
    "Yarrowmere", "Zephyrine", "Duskbane", "Fairwyn", "Greymantle", "Holloway",
)
