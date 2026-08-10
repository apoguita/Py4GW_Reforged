"""Dyes -- shipped reference data.

**Dyes have their own subsystem; do not read them as mods or by model id.**

Two facts drive everything here:

* **Every dye shares one model id** -- ``Vial_Of_Dye`` (146). There is no per-colour model id, which
  is why legacy code that fabricated ``ModelID.<Colour>_Dye`` ids could never match a drop.
* **Identification is by item type, and the colour comes from ``Item.Dye``** (``Item.py:634-673``),
  which owns dye reads: an item carries a tint and **four** dye channels, and ``Item.Dye.GetColor``
  resolves a dyed item's ``dye1`` first, falling back to a vial's own colour. ``Item.Dye.IsColor``
  tests the **item type**, not the model id.

So the model id is documentation, not the discriminator: matching on 146 would be fragile *and* would
wrongly admit anything else sharing that model. A dye rule matches **item type + colour**.
"""

from dataclasses import dataclass

# ModelID.Vial_Of_Dye. Informational only -- identification goes through ItemType.Dye.
DYE_MODEL_ID = 146

# ItemType.Dye -- the actual discriminator.
DYE_ITEM_TYPE = 10


@dataclass(frozen=True)
class Dye:
    """A dye colour. ``color_id`` is the ``DyeColor`` value carried by the item's dye info."""

    name: str
    color_id: int


# Colours as the game defines them (``DyeColor``), minus ``NoColor`` -- the absence of a dye.
DYES: tuple[Dye, ...] = (
    Dye('Blue', 2),
    Dye('Green', 3),
    Dye('Purple', 4),
    Dye('Red', 5),
    Dye('Yellow', 6),
    Dye('Brown', 7),
    Dye('Orange', 8),
    Dye('Silver', 9),
    Dye('Black', 10),
    Dye('Gray', 11),
    Dye('White', 12),
    Dye('Pink', 13),
    Dye('Mixed', 1),
)


_BY_COLOR_ID: dict[int, Dye] = {d.color_id: d for d in DYES}


def dye(color_id: int) -> Dye | None:
    return _BY_COLOR_ID.get(int(color_id))


def dye_color_ids() -> set[int]:
    return set(_BY_COLOR_ID)


def is_dye(item_id: int) -> bool:
    """Whether a live item is a dye, by **item type** -- the discriminator the game uses."""
    try:
        from Py4GWCoreLib.Item import Item

        item_type, _ = Item.GetItemType(item_id)
        return int(item_type) == DYE_ITEM_TYPE
    except Exception:
        return False


def color_of(item_id: int) -> int:
    """The dye colour of a live item, through the dye subsystem rather than raw modifiers."""
    try:
        from Py4GWCoreLib.Item import Item

        return int(Item.Dye.GetColor(item_id))
    except Exception:
        return 0


def channels_of(item_id: int):
    """``(tint, [dye1, dye2, dye3, dye4])`` -- an item carries four dye channels, not one."""
    try:
        from Py4GWCoreLib.Item import Item

        return Item.Dye.GetChannels(item_id)
    except Exception:
        return (0, [])
