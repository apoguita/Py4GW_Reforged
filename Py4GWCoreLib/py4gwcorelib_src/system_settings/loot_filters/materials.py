"""Materials and Wiki-recorded salvage targets -- shipped reference data.

Two distinct things, and they are not the same list:

* :data:`MATERIALS` -- the 36 crafting materials, for wanting a material **when it drops**.
* :data:`WIKI_SALVAGE_TARGETS` -- material targets recorded by Guild Wars Wiki category pages.

**The salvage data informs, it never gates.** It is a relation between an item and a possible material
output, not a claim about whether that output is common or rare. The Wiki record is incomplete, so every
material stays selectable and the data only populates the tooltip and target matching surface.
"""

from dataclasses import dataclass

from .wiki_salvage_targets import WIKI_SALVAGE_TARGETS

COMMON = "common"
RARE = "rare"


@dataclass(frozen=True)
class Material:
    """A crafting material. ``kind`` is how it is obtained by salvaging, or "" if never recorded."""

    name: str
    model_id: int
    kind: str


MATERIALS: tuple[Material, ...] = (
    Material('Amber Chunk', 6532, 'rare'),
    Material('Bolt of Cloth', 925, 'common'),
    Material('Bolt of Damask', 927, ''),
    Material('Bolt of Linen', 926, 'rare'),
    Material('Bolt of Silk', 928, 'rare'),
    Material('Bone', 921, 'common'),
    Material('Chitin Fragment', 954, 'common'),
    Material('Deldrimor Steel Ingot', 950, ''),
    Material('Diamond', 935, 'rare'),
    Material('Elonian Leather Square', 943, ''),
    Material('Feather', 933, 'common'),
    Material('Fur Square', 941, 'rare'),
    Material('Glob of Ectoplasm', 930, ''),
    Material('Granite Slab', 955, 'common'),
    Material('Iron Ingot', 948, 'common'),
    Material('Jadeite Shard', 6533, 'rare'),
    Material('Leather Square', 942, 'rare'),
    Material('Lump of Charcoal', 922, 'rare'),
    Material('Monstrous Claw', 923, 'rare'),
    Material('Monstrous Eye', 931, 'rare'),
    Material('Monstrous Fang', 932, 'rare'),
    Material('Obsidian Shard', 945, ''),
    Material('Onyx Gemstone', 936, 'rare'),
    Material('Pile of Glittering Dust', 929, 'common'),
    Material('Plant Fiber', 934, 'common'),
    Material('Roll of Parchment', 951, 'rare'),
    Material('Roll of Vellum', 952, 'rare'),
    Material('Ruby', 937, 'rare'),
    Material('Sapphire', 938, 'rare'),
    Material('Scale', 953, 'common'),
    Material('Spiritwood Plank', 956, 'rare'),
    Material('Steel Ingot', 949, 'rare'),
    Material('Tanned Hide Square', 940, 'common'),
    Material('Tempered Glass Vial', 939, 'rare'),
    Material('Vial of Ink', 944, 'rare'),
    Material('Wood Plank', 946, 'common'),
)


_BY_MODEL_ID: dict[int, Material] = {m.model_id: m for m in MATERIALS}
_SOURCES: dict[int, set[int]] = {}
for _item, _targets in WIKI_SALVAGE_TARGETS.items():
    for _m in _targets:
        _SOURCES.setdefault(_m, set()).add(_item)


def material(model_id: int) -> Material | None:
    return _BY_MODEL_ID.get(int(model_id))


def material_model_ids() -> set[int]:
    return set(_BY_MODEL_ID)


def salvage_targets(item_model_id: int) -> tuple[int, ...]:
    """Material IDs this item is recorded as being able to salvage into.

    The source is Guild Wars Wiki category evidence. An empty tuple means no relationship was
    recorded; it does not establish that the item cannot salvage into a material.
    """
    return WIKI_SALVAGE_TARGETS.get(int(item_model_id), ())


def salvages_into_material(item_model_id: int, material_model_id: int) -> bool:
    """Whether the Wiki records this item as a source of the material."""
    return int(material_model_id) in salvage_targets(item_model_id)


def known_sources(material_model_id: int) -> int:
    """How many Wiki-recorded items can salvage into a material.

    A result of 0 means unrecorded, not impossible.
    """
    return len(_SOURCES.get(int(material_model_id), ()))
