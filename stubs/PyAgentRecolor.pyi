"""Type stub for the embedded PyAgentRecolor module.

One module for ALL overhead name-tag recoloring: living agents, gadgets, and
ground items. The DLL owns three detours (the living-agent color resolver
FUN_007f02e0, CGadgetAgent::GetTextData FUN_007f9950, and CItemAgent::GetTextData
FUN_007fa6a0); Python controls per-category enable/disable and the rule stores.

Colors are ARGB 0xAARRGGBB (opaque red = 0xFFFF0000).
Allegiance ids: 1=Ally, 2=Neutral, 3=Enemy, 4=SpiritPet, 5=Minion, 6=NpcMinipet.
Item rarity ints: 0=White 1=Blue 2=Purple 3=Gold 4=Green. item_type is the
GW::Constants::ItemType int. Item match precedence (first match wins):
    agent_id > item_id > model_id > name(substring) > item_type > rarity

NOTE on item colors: item labels get TRUE arbitrary RGB. For a matched item the
DLL builds an engine-encoded `<c=0xAARRGGBB>name</c>` string (via Ui_CreateEncodedText)
that the game's text renderer colors directly. If the item's name hasn't decoded
yet (async, first frame or two per item kind) it falls back to the nearest of GW's
~7 palette colors until the true-color string is ready, so recolor is immediate and
then exact. Agent and gadget recolors use a raw Color4b and honor ANY ARGB exactly.

LOOT FILTER via the ALPHA channel (item and gadget rules): the ARGB you pass drives
the behavior by its alpha byte (AA in 0xAARRGGBB):
  * alpha 0xFF        -> solid recolor.
  * alpha 0x01..0xFE  -> FADE (semi-transparent label; lower = fainter).
  * alpha 0x00        -> HIDE (the label is blanked entirely).
So a loot filter is just rules: e.g. set_item_type_color(<junk type>, 0x30FFFFFF) to
fade junk, set_item_rarity_color(3, 0xFF00FF00) to highlight golds, or
set_item_model_color(<spam model>, 0x00000000) to hide a specific drop. Precedence
lets a per-item HIDE override a broad rarity highlight. Living-AGENT rules now also
honor alpha the same way (fade via 0x01-0xFE, hide via 0x00) - a second hook on
CCharAgent::GetTextData applies it to the name tag, while the resolver still colors
the target/consider ring.
See docs/RE/name_tag_color_reverse_engineering.md and
docs/RE/item_gadget_recolor_reverse_engineering.md.
"""

# ===================== Living agents =====================

def enable() -> None:
    """Enable living-agent color overriding."""
    ...

def disable() -> None:
    """Disable living-agent color overriding (game defaults return)."""
    ...

def is_enabled() -> bool: ...

def is_hook_installed() -> bool:
    """True if the living-agent resolver detour installed at DLL init."""
    ...

def set_agent_color(agent_id: int, argb: int) -> None:
    """Override one living agent's name-tag color (ARGB). Highest precedence."""
    ...

def remove_agent_color(agent_id: int) -> bool: ...

def set_allegiance_color(allegiance: int, argb: int) -> None:
    """Override a whole allegiance category (1..6). Per-agent rules win."""
    ...

def remove_allegiance_color(allegiance: int) -> bool: ...

def clear_rules() -> None:
    """Drop living-agent color overrides."""
    ...

def get_agent_rules() -> dict[int, int]: ...
def get_allegiance_rules() -> dict[int, int]: ...

def read_consider_color(agent_id: int) -> int:
    """The color the game currently computes for an agent (ARGB), via the
    original resolver. Unaffected by overrides. 0 if unavailable."""
    ...

# ===================== Gadgets =====================

def gadget_enable() -> None:
    """Enable gadget color overriding."""
    ...

def gadget_disable() -> None:
    """Disable gadget color overriding (default yellow returns)."""
    ...

def gadget_is_enabled() -> bool: ...
def gadget_is_hook_installed() -> bool: ...

def set_gadget_color(agent_id: int, argb: int) -> None:
    """Override one gadget's tag color by agent id (ARGB). Highest precedence."""
    ...

def remove_gadget_color(agent_id: int) -> bool: ...

def set_all_gadget_color(argb: int) -> None:
    """Recolor every gadget name tag (ARGB). Per-gadget rules still win."""
    ...

def clear_all_gadget_color() -> None: ...
def gadget_clear_rules() -> None: ...
def get_gadget_rules() -> dict[int, int]: ...
def has_all_gadget_color() -> bool: ...
def get_all_gadget_color() -> int: ...

# ===================== Ground items =====================

def item_enable() -> None:
    """Enable ground-item color overriding."""
    ...

def item_disable() -> None:
    """Disable ground-item color overriding (default label colors return)."""
    ...

def item_is_enabled() -> bool: ...
def item_is_hook_installed() -> bool: ...

def set_item_agent_color(agent_id: int, argb: int) -> None:
    """Recolor one ground-item instance by its agent id (highest precedence)."""
    ...

def remove_item_agent_color(agent_id: int) -> bool: ...

def set_item_id_color(item_id: int, argb: int) -> None:
    """Recolor by item id."""
    ...

def remove_item_id_color(item_id: int) -> bool: ...

def set_item_model_color(model_id: int, argb: int) -> None:
    """Recolor every item of a model id (item 'kind')."""
    ...

def remove_item_model_color(model_id: int) -> bool: ...

def set_item_name_color(substring: str, argb: int) -> None:
    """Recolor items whose decoded name contains `substring` (case-insensitive).
    Names resolve asynchronously, so a rule may take a frame or two per kind."""
    ...

def remove_item_name_color(substring: str) -> bool: ...

def set_item_type_color(item_type: int, argb: int) -> None:
    """Recolor by GW::Constants::ItemType (int)."""
    ...

def remove_item_type_color(item_type: int) -> bool: ...

def set_item_rarity_color(rarity: int, argb: int) -> None:
    """Recolor by rarity (0=White 1=Blue 2=Purple 3=Gold 4=Green)."""
    ...

def remove_item_rarity_color(rarity: int) -> bool: ...

def item_clear_rules() -> None:
    """Drop all item color rules."""
    ...

def get_item_agent_rules() -> dict[int, int]: ...
def get_item_id_rules() -> dict[int, int]: ...
def get_item_model_rules() -> dict[int, int]: ...
def get_item_type_rules() -> dict[int, int]: ...
def get_item_rarity_rules() -> dict[int, int]: ...
def get_item_name_rules() -> list[tuple[str, int]]:
    """List of (lowercased substring, ARGB) name rules."""
    ...

# ===================== Shared =====================

def clear_all_rules() -> None:
    """Drop every color rule across agents, gadgets, and items."""
    ...

def get_diagnostics() -> dict[str, object]:
    """Combined counters across all three categories: *_hook_installed,
    *_enabled, resolver_calls_seen, agent_rule_hits, allegiance_rule_hits,
    gadget_calls_seen, gadget_rule_hits, gadget_all_hits, item_calls_seen,
    item_rule_hits, last_* ids/colors, item_name_cache_size."""
    ...

def get_agent_diagnostics() -> dict[str, object]:
    """Legacy agent-only diagnostics view (initialized, hook_installed, enabled,
    resolver_calls_seen, agent_rule_hits, allegiance_rule_hits, last_agent_id,
    last_color)."""
    ...

def reset_diagnostics() -> None: ...
