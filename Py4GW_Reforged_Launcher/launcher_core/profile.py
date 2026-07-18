"""GW1-only profile model.

Trimmed from GWxLauncher/Domain/GameProfile.cs: every GW2 field and the Toolbox
fields are dropped (GWToolbox++ is incompatible with current Py4GW; GW2 stays on the
existing C# launcher). Py4GW and gMod injection, GW1 auto-login, and window placement
are kept since they're still in scope.

`password_protected` is the only place a password lives on this model -- it's always
a DPAPI blob (see crypto.py), never plaintext. There is deliberately no plaintext
password field, so plaintext-at-rest isn't just avoided by convention, it's
structurally impossible to accidentally serialize one.
"""

from __future__ import annotations

import dataclasses
import uuid
from typing import Any


@dataclasses.dataclass
class GameProfile:
    # -----------------------------
    # Identity / launch
    # -----------------------------
    id: str = dataclasses.field(default_factory=lambda: uuid.uuid4().hex)
    name: str = ""
    executable_path: str = ""
    launch_arguments: str = ""
    bulk_launch_enabled: bool = False

    # -----------------------------
    # Mods / injection (Py4GW, gMod only -- no Toolbox)
    # -----------------------------
    # RELAY 060: True by default for a brand-new profile -- a fresh product
    # decision (Apo's own feedback batch), NOT restoring old behavior:
    # confirmed via `git log -S` across this repo's entire history that the
    # retired imgui launcher never defaulted this True either. Imported
    # profiles are unaffected -- legacy_import.py already sets this
    # explicitly from the source data, never from this dataclass default.
    py4gw_enabled: bool = True
    py4gw_dll_path: str = ""

    gmod_enabled: bool = False
    gmod_dll_path: str = ""
    gmod_plugin_paths: list[str] = dataclasses.field(default_factory=list)

    # RELAY 057: auto-run script at launch. Old-launcher-compatible field
    # (legacy_import.py already flagged this exact name as dropped/
    # unsupported on import before this field existed) -- written into
    # Py4GW.ini's [settings] autoexec_script key immediately before
    # injection, same mechanism Py4GW_Reforged_Native's RunAutoexecOnce()
    # already consumes. Empty string = no auto-run script for this profile.
    script_path: str = ""

    # -----------------------------
    # Auto-login
    # -----------------------------
    # RELAY 060: same fresh-default reasoning as py4gw_enabled above -- True
    # for a brand-new profile, confirmed never true historically either,
    # imported profiles unaffected (legacy_import.py sets this explicitly).
    auto_login_enabled: bool = True
    email: str = ""
    password_protected: str = ""  # base64; DPAPI-encrypted. Never plaintext.

    auto_select_character_enabled: bool = False
    character_name: str = ""

    # -----------------------------
    # Window placement
    # -----------------------------
    windowed_mode_enabled: bool = True
    window_x: int = 0
    window_y: int = 0
    window_width: int = 800
    window_height: int = 600
    window_maximized: bool = False

    window_remember_changes: bool = False
    window_lock_changes: bool = False
    window_block_inputs: bool = False

    # -----------------------------
    # Team membership (multibox team support)
    # -----------------------------
    # A profile can belong to more than one team. "ALL" is not a real team and never
    # appears here -- it's a built-in view mode in the UI layer, not stored data.
    team_ids: list[str] = dataclasses.field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "GameProfile":
        known_fields = {f.name for f in dataclasses.fields(GameProfile)}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return GameProfile(**filtered)
