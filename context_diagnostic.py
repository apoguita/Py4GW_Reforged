"""
Context Pointer Migration — Diagnostic Dump v2
==============================================
Run in-game to dump all SSM pointer fields, context facade states,
agent array stats, and environment info to a JSON file.

Usage:
    import context_diagnostic
    context_diagnostic.main()

Output: <project_root>/context_dump_<timestamp>.json
"""

import json
import math
import os
import sys
from datetime import datetime
from typing import Any

DUMP_DIR = os.path.dirname(os.path.abspath(__file__))


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────

def _safe(fn, *args, **kwargs):
    try:
        return (True, fn(*args, **kwargs))
    except Exception as exc:
        return (False, f"{type(exc).__name__}: {exc}")


def _fmt_ptr(val):
    if val is None:
        return "0x00000000"
    try:
        ival = int(val)
        return f"0x{ival:08X}"
    except (TypeError, ValueError):
        return str(val)


def _fmt_float(val):
    try:
        f = float(val)
        return f"{f:.3f}" if math.isfinite(f) else str(f)
    except (TypeError, ValueError):
        return str(val)


def _sample(obj, *field_names):
    """Read multiple fields from obj, return {name: {raw, fmt, ok}}."""
    results = {}
    for name in field_names:
        ok, val = _safe(getattr, obj, name)
        if not ok:
            results[name] = {"raw": None, "fmt": f"ERROR: {val}", "ok": False}
            continue
        if val is None:
            results[name] = {"raw": None, "fmt": "None", "ok": True}
        elif isinstance(val, bool):
            results[name] = {"raw": val, "fmt": str(val), "ok": True}
        elif isinstance(val, float):
            results[name] = {"raw": val, "fmt": _fmt_float(val), "ok": True}
        elif isinstance(val, int):
            results[name] = {"raw": val, "fmt": str(val), "ok": True}
        elif isinstance(val, str):
            results[name] = {"raw": val[:120], "fmt": val[:120], "ok": True}
        elif isinstance(val, (list, tuple)):
            results[name] = {"raw": f"len={len(val)}", "fmt": f"len={len(val)}", "ok": True}
        else:
            results[name] = {"raw": None, "fmt": str(type(val).__name__), "ok": True}
    return results


# ─────────────────────────────────────────────────────────────────────
# Section 1 — SSM Raw Data
# ─────────────────────────────────────────────────────────────────────

def dump_ssm():
    result = {"section": "ssm_raw", "ok": False}

    ok, mod = _safe(__import__,
                    "Py4GWCoreLib.native_src.ShMem.SysShaMem",
                    fromlist=["SystemShaMemMgr"])
    if not ok:
        result["error"] = f"import SysShaMem: {mod}"
        return result

    mgr = mod.SystemShaMemMgr
    result["shm_attached"] = getattr(mgr, "shm", None) is not None
    result["shm_name"] = str(getattr(mgr, "shm_name", "?"))
    result["shm_size"] = int(getattr(mgr, "size", 0))
    result["expected_size"] = int(getattr(mgr, "expected_size", 0))
    result["last_error"] = str(getattr(mgr, "last_error", ""))

    header = getattr(mgr, "header_struct", None)
    if header is not None:
        result["header"] = {
            "version": int(header.version),
            "total_size": int(header.total_size),
            "sequence": int(header.sequence),
            "pid": int(header.process_id),
            "hwnd": _fmt_ptr(header.window_handle),
        }

    ptrs = getattr(mgr, "pointers_struct", None)
    if ptrs is not None:
        fields = [f[0] for f in type(ptrs)._fields_]
        raw_ptrs = {}
        for name in fields:
            ok2, val = _safe(getattr, ptrs, name)
            raw_ptrs[name] = _fmt_ptr(val) if ok2 else f"ERROR: {val}"

        nonzero = sum(1 for v in raw_ptrs.values() if v not in ("0x00000000", "None", None) and not v.startswith("ERROR"))
        result["pointers"] = {
            "count": len(fields),
            "nonzero": nonzero,
            "sizeof": int(__import__("ctypes").sizeof(type(ptrs))),
            "fields": raw_ptrs,
        }

    raw = getattr(mgr, "agent_array_struct", None)
    if raw is not None:
        aa = {
            "max_size": int(raw.max_size),
            "count": int(raw.AgentArrayCount),
        }
        ref_names = [
            "AllArray", "AllyArray", "NeutralArray", "EnemyArray",
            "SpiritPetArray", "MinionArray", "NPCMinipetArray",
            "LivingArray", "ItemArray", "OwnedItemArray",
            "GadgetArray", "DeadAllyArray", "DeadEnemyArray",
        ]
        aa["ref_counts"] = {}
        for rn in ref_names:
            arr = getattr(raw, rn, None)
            aa["ref_counts"][rn] = int(arr.count) if arr is not None else 0

        # first 10 agent ptrs
        aa["first_10"] = []
        for i in range(min(int(raw.AgentArrayCount), 10)):
            a = raw.AgentArray[i]
            aa["first_10"].append({"i": i, "ptr": _fmt_ptr(a.ptr), "id": int(a.agent_id)})

        result["agent_array"] = aa

    result["ok"] = True
    return result


# ─────────────────────────────────────────────────────────────────────
# Section 2 — Context Facade Status
# ─────────────────────────────────────────────────────────────────────

CONTEXTS = [
    # (label, module, class, sample_fields)
    ("CharContext",        "Py4GWCoreLib.native_src.context.CharContext",        "CharContext",              ["player_name_str", "token1", "map_id", "current_map_id", "observe_map_id", "token2", "language"]),
    ("WorldContext",       "Py4GWCoreLib.native_src.context.WorldContext",       "WorldContext",             ["experience", "level", "morale", "foes_killed"]),
    ("AccAgentContext",    "Py4GWCoreLib.native_src.context.AccAgentContext",    "AccAgentContext",          ["instance_timer", "rand1", "rand2"]),
    ("MapContext",         "Py4GWCoreLib.native_src.context.MapContext",         "MapContext",               ["map_type", "map_id", "h0080"]),
    ("GuildContext",       "Py4GWCoreLib.native_src.context.GuildContext",       "GuildContext",             []),
    ("PreGameContext",     "Py4GWCoreLib.native_src.context.PreGameContext",     "PreGameContext",           ["frame_id", "chosen_character_index"]),
    ("CinematicContext",   "Py4GWCoreLib.native_src.context.CinematicContext",   "Cinematic",                ["h0000", "h0004"]),
    ("GameplayContext",    "Py4GWCoreLib.native_src.context.GameplayContext",    "GameplayContext",          ["mission_map_zoom"]),
    ("WorldMapContext",    "Py4GWCoreLib.native_src.context.WorldMapContext",    "WorldMapContext",          ["frame_id", "zoom"]),
    ("MissionMapContext",  "Py4GWCoreLib.native_src.context.MissionMapContext",  "MissionMapContext",        ["frame_id"]),
    ("PartyContext",       "Py4GWCoreLib.native_src.context.PartyContext",       "PartyContext",             []),
    ("TextParser",         "Py4GWCoreLib.native_src.context.TextContext",        "TextParser",               ["language_id", "entries_per_file"]),
    ("ServerRegion",       "Py4GWCoreLib.native_src.context.ServerRegionContext","ServerRegion",             ["region_id"]),
    ("AvailableCharacters","Py4GWCoreLib.native_src.context.AvailableCharacterContext","AvailableCharacterArray", ["available_characters_list"]),
    # ── special: InstanceInfo with deeper AreaInfo sub-sampling ──
    ("InstanceInfo",       "Py4GWCoreLib.native_src.context.InstanceInfoContext","InstanceInfo",             None),
]

CS_NONZERO  = "NONZERO"
CS_NULL     = "NULL"
CS_NOT_RUN  = "NOT_RUN"

def dump_contexts():
    result = {"section": "contexts", "ok": False, "contexts": {}}

    for label, mod_path, cls_name, sample_fields in CONTEXTS:
        entry = {
            "ptr_hex": "NOT_LOADED",
            "ptr_nonzero": False,
            "cached_ctx": "NOT_LOADED",
            "samples": {},
            "errors": [],
        }

        ok, mod = _safe(__import__, mod_path, fromlist=[cls_name])
        if not ok:
            entry["errors"].append(f"import: {mod}")
            result["contexts"][label] = entry
            continue

        facade = getattr(mod, cls_name, None)
        if facade is None:
            entry["errors"].append(f"class {cls_name} missing")
            result["contexts"][label] = entry
            continue

        ok2, ptr_val = _safe(facade.get_ptr)
        if ok2:
            entry["ptr_hex"] = _fmt_ptr(ptr_val)
            entry["ptr_nonzero"] = bool(ptr_val)
        else:
            entry["errors"].append(f"get_ptr: {ptr_val}")

        ok2, ctx = _safe(facade.get_context)
        if ok2:
            entry["cached_ctx"] = "VALID" if ctx is not None else "None"
        else:
            entry["errors"].append(f"get_context: {ctx}")
            ctx = None

        if ctx is not None and sample_fields:
            entry["samples"] = _sample(ctx, *sample_fields)

        result["contexts"][label] = entry

    # ── InstanceInfo deep check ──
    ie = result["contexts"].get("InstanceInfo", {})
    ok, mod = _safe(__import__,
                    "Py4GWCoreLib.native_src.context.InstanceInfoContext",
                    fromlist=["InstanceInfo"])
    if ok:
        facade = getattr(mod, "InstanceInfo", None)
        if facade:
            ctx = _safe(facade.get_context)[1]
            if ctx is not None:
                ie["samples"] = _sample(ctx, "instance_type", "terrain_count")
                # Attempt AreaInfo sub-read
                mi = getattr(ctx, "current_map_info", None)
                if mi is not None:
                    ie["area_info"] = _sample(mi,
                        "campaign", "continent", "region", "type",
                        "flags", "min_party_size", "max_party_size",
                        "min_level", "max_level",
                    )
                    # Plausibility check
                    it = int(getattr(ctx, "instance_type", -1))
                    ie["instance_type_plausible"] = it in (1, 2, 3, 4)
                else:
                    ie["area_info"] = None
                    ie["instance_type_plausible"] = False

    result["ok"] = True
    return result


# ─────────────────────────────────────────────────────────────────────
# Section 3 — AgentArray consumer validation
# ─────────────────────────────────────────────────────────────────────

def dump_agentarray_api():
    """Verify the public AgentArray API returns data via SSM."""
    result = {"section": "agentarray_api", "ok": False}

    ok, mod = _safe(__import__, "Py4GWCoreLib.AgentArray", fromlist=["AgentArray"])
    if not ok:
        result["error"] = str(mod)
        return result

    AA = mod.AgentArray
    methods = {
        "GetAgentArray":       lambda: AA.GetAgentArray(),
        "GetAllyArray":        lambda: AA.GetAllyArray(),
        "GetEnemyArray":       lambda: AA.GetEnemyArray(),
        "GetNeutralArray":     lambda: AA.GetNeutralArray(),
        "GetSpiritPetArray":   lambda: AA.GetSpiritPetArray(),
        "GetMinionArray":      lambda: AA.GetMinionArray(),
        "GetNPCMinipetArray":  lambda: AA.GetNPCMinipetArray(),
        "GetItemArray":        lambda: AA.GetItemArray(),
        "GetGadgetArray":      lambda: AA.GetGadgetArray(),
        "GetDeadAllyArray":    lambda: AA.GetDeadAllyArray(),
        "GetDeadEnemyArray":   lambda: AA.GetDeadEnemyArray(),
    }

    result["results"] = {}
    for name, fn in methods.items():
        ok2, val = _safe(fn)
        if ok2:
            result["results"][name] = f"len={len(val)}" if isinstance(val, list) else str(val)
        else:
            result["results"][name] = f"ERROR: {val}"

    result["ok"] = True
    return result


# ─────────────────────────────────────────────────────────────────────
# Section 4 — Struct Layout Verification
# ─────────────────────────────────────────────────────────────────────

def dump_layouts():
    """sizeof + field offsets for key structures."""
    result = {"section": "layouts", "ok": True, "structs": {}}
    import ctypes

    pairs = [
        ("Pointers_SHMemStruct", "Py4GWCoreLib.native_src.ShMem.structs.PointersSSM",
         "Pointers_SHMemStruct"),
        ("AgentArraySHMemStruct", "Py4GWCoreLib.native_src.ShMem.structs.AgentArraySSM",
         "AgentArraySHMemStruct"),
        ("SharedMemoryHeader", "Py4GWCoreLib.native_src.ShMem.SysShaMem",
         "SharedMemoryHeader"),
        ("CharContextStruct", "Py4GWCoreLib.native_src.context.CharContext",
         "CharContextStruct"),
        ("WorldContextStruct", "Py4GWCoreLib.native_src.context.WorldContext",
         "WorldContextStruct"),
        ("InstanceInfoStruct", "Py4GWCoreLib.native_src.context.InstanceInfoContext",
         "InstanceInfoStruct"),
        ("GameContextStruct", "Py4GWCoreLib.native_src.context.GameContext",
         "GameContextStruct"),
        ("PreGameContextStruct", "Py4GWCoreLib.native_src.context.PreGameContext",
         "PreGameContextStruct"),
    ]

    for label, mod_path, cls_name in pairs:
        ok, mod = _safe(__import__, mod_path, fromlist=[cls_name])
        if not ok:
            result["structs"][label] = {"error": str(mod)}
            continue
        cls = getattr(mod, cls_name, None)
        if cls is None:
            result["structs"][label] = {"error": f"{cls_name} missing"}
            continue
        result["structs"][label] = {
            "sizeof": ctypes.sizeof(cls),
            "fields": len(cls._fields_),
        }

    return result


# ─────────────────────────────────────────────────────────────────────
# Section 5 — Environment
# ─────────────────────────────────────────────────────────────────────

def dump_env():
    result = {"section": "env", "ok": True}
    result["python"] = sys.version
    result["platform"] = sys.platform
    result["timestamp"] = datetime.now().isoformat()

    # Verify fix file state
    instanceinfo_path = os.path.join(
        DUMP_DIR, "Py4GWCoreLib", "native_src", "context", "InstanceInfoContext.py"
    )
    if os.path.isfile(instanceinfo_path):
        with open(instanceinfo_path, "r", encoding="utf-8") as fh:
            content = fh.read()
        result["instanceinfo_fix_applied"] = "c_uint32.from_address" in content
    else:
        result["instanceinfo_fix_applied"] = "file_not_found"

    return result


# ─────────────────────────────────────────────────────────────────────
# Section 7 — Demo parity: replicate Py4GW DEMO 2.0 map queries
# ─────────────────────────────────────────────────────────────────────

def dump_demo_map_parity():
    """Mirrors the queries from Sources/ApoSource/py4gw_demo_src/map_demo.py
    draw_map_data_tab().  This tells us exactly which Map.* methods fail."""
    result = {"section": "demo_map_parity", "ok": True, "queries": {}}

    ok, Map = _safe(__import__, "Py4GWCoreLib.Map", fromlist=["Map"])
    if not ok:
        result["error"] = str(Map)
        return result

    Map = Map.Map
    queries = [
        ("GetInstanceTypeName", lambda: Map.GetInstanceTypeName()),
        ("GetMapID",            lambda: Map.GetMapID()),
        ("GetMapName",          lambda: Map.GetMapName()),
        ("GetCampaign",         lambda: Map.GetCampaign()),
        ("GetContinent",        lambda: Map.GetContinent()),
        ("IsGuildHall",         lambda: Map.IsGuildHall()),
        ("GetRegion",           lambda: Map.GetRegion()),
        ("GetRegionType",       lambda: Map.GetRegionType()),
        ("GetDistrict",         lambda: Map.GetDistrict()),
        ("GetLanguage",         lambda: Map.GetLanguage()),
        ("GetAmountOfPlayersInInstance", lambda: Map.GetAmountOfPlayersInInstance()),
        ("GetMaxPartySize",     lambda: Map.GetMaxPartySize()),
        ("GetFoesKilled",       lambda: Map.GetFoesKilled()),
        ("GetFoesToKill",       lambda: Map.GetFoesToKill()),
        ("IsVanquishable",      lambda: Map.IsVanquishable()),
        ("IsVanquishComplete",  lambda: Map.IsVanquishComplete()),
        ("IsInCinematic",       lambda: Map.IsInCinematic()),
        ("HasEnterChallengeButton", lambda: Map.HasEnterChallengeButton()),
        ("IsMapUnlocked",       lambda: Map.IsMapUnlocked()),
        ("GetMinPartySize",     lambda: Map.GetMinPartySize()),
        ("GetMaxLevel",         lambda: Map.GetMaxLevel()),
        ("IsMapReady",          lambda: Map.IsMapReady()),
        ("IsMapDataLoaded",     lambda: Map.IsMapDataLoaded()),
        ("IsMapLoading",        lambda: Map.IsMapLoading()),
        ("IsObservingMatch",    lambda: Map.IsObservingMatch()),
        ("IsExplorable",        lambda: Map.IsExplorable()),
        ("GetInstanceUptime",   lambda: Map.GetInstanceUptime()),
    ]

    for name, fn in queries:
        ok2, val = _safe(fn)
        if ok2:
            if isinstance(val, tuple):
                result["queries"][name] = str(val)
            elif isinstance(val, bool):
                result["queries"][name] = val
            elif isinstance(val, float):
                result["queries"][name] = _fmt_float(val)
            else:
                result["queries"][name] = str(val)[:120]
        else:
            result["queries"][name] = f"ERROR: {val}"

    # ── Deep gate trace ──
    gates = {}
    ok2, ctx = _safe(__import__, "Py4GWCoreLib.Context", fromlist=["GWContext"])
    if ok2:
        GWContext = ctx.GWContext
        for name in ("Map", "Char", "InstanceInfo", "World", "Party"):
            try:
                valid = GWContext.__dict__[name].IsValid()
            except Exception:
                valid = "ERROR"
            gates[f"GWContext.{name}.IsValid"] = valid

    char_ctx = None
    ok2, cc = _safe(__import__, "Py4GWCoreLib.native_src.context.CharContext", fromlist=["CharContext"])
    if ok2:
        char_ctx = cc.CharContext.get_context()
    if char_ctx:
        gates["CharContext.current_map_id"] = int(getattr(char_ctx, "current_map_id", -1))
        gates["CharContext.observe_map_id"] = int(getattr(char_ctx, "observe_map_id", -1))

    inst = None
    ok2, ic = _safe(__import__, "Py4GWCoreLib.native_src.context.InstanceInfoContext", fromlist=["InstanceInfo"])
    if ok2:
        inst = ic.InstanceInfo.get_context()
    if inst:
        gates["InstanceInfo.instance_type"] = int(getattr(inst, "instance_type", -1))

    # Native PyParty — full surface check
    ok2, pp = _safe(__import__, "PyParty")
    if ok2:
        try:
            p = pp.PyParty()
            gates["PyParty.is_party_loaded"] = p.is_party_loaded
            gates["PyParty.party_id"] = getattr(p, "party_id", "N/A")

            # Players
            players = getattr(p, "players", None)
            gates["PyParty.players"] = len(players) if isinstance(players, list) else f"type={type(players).__name__}"
            if isinstance(players, list) and len(players) > 0:
                pl0 = players[0]
                gates["PyParty.players[0].login_number"] = getattr(pl0, "login_number", "N/A") if not isinstance(pl0, dict) else pl0.get("login_number", "N/A")
                gates["PyParty.players[0].called_target_id"] = getattr(pl0, "called_target_id", "N/A") if not isinstance(pl0, dict) else pl0.get("called_target_id", "N/A")
                gates["PyParty.players[0].state"] = getattr(pl0, "state", "N/A") if not isinstance(pl0, dict) else pl0.get("state", "N/A")

            # Heroes
            heroes = getattr(p, "heroes", None)
            gates["PyParty.heroes"] = len(heroes) if isinstance(heroes, list) else f"type={type(heroes).__name__}"
            if isinstance(heroes, list) and len(heroes) > 0:
                h0 = heroes[0]
                gates["PyParty.heroes[0].agent_id"] = getattr(h0, "agent_id", "N/A") if not isinstance(h0, dict) else h0.get("agent_id", "N/A")
                gates["PyParty.heroes[0].owner_player_id"] = getattr(h0, "owner_player_id", "N/A") if not isinstance(h0, dict) else h0.get("owner_player_id", "N/A")
                gates["PyParty.heroes[0].hero_id"] = getattr(h0, "hero_id", "N/A") if not isinstance(h0, dict) else h0.get("hero_id", "N/A")

            # Henchmen
            hench = getattr(p, "henchmen", None)
            gates["PyParty.henchmen"] = len(hench) if isinstance(hench, list) else f"type={type(hench).__name__}"

            # Counts
            gates["PyParty.party_player_count"] = getattr(p, "party_player_count", "N/A")
            gates["PyParty.party_hero_count"] = getattr(p, "party_hero_count", "N/A")
            gates["PyParty.party_size"] = getattr(p, "party_size", "N/A")

        except Exception as e:
            gates["PyParty"] = f"ERROR: {e}"

    # Player number
    ok2, pl = _safe(__import__, "Py4GWCoreLib.Player", fromlist=["Player"])
    if ok2:
        ok3, pn = _safe(pl.Player.GetPlayerNumber)
        gates["Player.GetPlayerNumber"] = pn if ok3 else f"ERROR: {pn}"

    result["gates"] = gates

    return result
# ─────────────────────────────────────────────────────────────────────

def dump_email_chain():
    """
    Trace the full GetAccountEmail() resolution path step by step,
    reporting exactly where it breaks.  This is the chain that causes
    the 'Current account email is not available' error in Settings.
    """
    result = {"section": "email_chain", "ok": True, "steps": {}}

    # Step 1: IsMapReady gate
    ok, mod_map = _safe(__import__, "Py4GWCoreLib.Map", fromlist=["Map"])
    if ok:
        Map = mod_map.Map
        ok2, is_ready = _safe(Map.IsMapReady)
        result["steps"]["IsMapReady"] = str(is_ready) if ok2 else f"ERROR: {is_ready}"
    else:
        result["steps"]["IsMapReady"] = f"IMPORT_FAIL: {mod_map}"

    # Step 2: IsMapDataLoaded sub-gates
    ok, mod_ctx = _safe(__import__, "Py4GWCoreLib.Context", fromlist=["GWContext"])
    if ok:
        GWContext = mod_ctx.GWContext
        for name in ("Map", "Char", "InstanceInfo", "World"):
            try:
                valid = getattr(GWContext, name).IsValid()
                result["steps"][f"GWContext.{name}.IsValid"] = valid
            except Exception as exc:
                result["steps"][f"GWContext.{name}.IsValid"] = f"ERROR: {exc}"
    else:
        result["steps"]["GWContext"] = f"IMPORT_FAIL: {mod_ctx}"

    # Step 3: GetAccountEmail raw
    ok, mod_pl = _safe(__import__, "Py4GWCoreLib.Player", fromlist=["Player"])
    if ok:
        Player = mod_pl.Player
        ok2, email = _safe(Player.GetAccountEmail)
        result["steps"]["GetAccountEmail_raw"] = str(email)[:80] if ok2 else f"ERROR: {email}"
    else:
        result["steps"]["GetAccountEmail_raw"] = f"IMPORT_FAIL: {mod_pl}"

    # Step 4: CharContext.player_email_str direct read (bypass cache)
    ok, mod_cc = _safe(__import__,
                       "Py4GWCoreLib.native_src.context.CharContext",
                       fromlist=["CharContext"])
    if ok:
        CharContext = mod_cc.CharContext
        ctx = CharContext.get_context()
        if ctx is not None:
            ok2, raw = _safe(getattr, ctx, "player_email_encoded_str")
            result["steps"]["char_ctx.player_email_encoded"] = (
                str(raw)[:80] if ok2 else f"ERROR: {raw}")
            ok2, decoded = _safe(getattr, ctx, "player_email_str")
            result["steps"]["char_ctx.player_email_decoded"] = (
                str(decoded)[:80] if ok2 else f"ERROR: {decoded}")
        else:
            result["steps"]["char_ctx"] = "None"
    else:
        result["steps"]["char_ctx"] = f"IMPORT_FAIL: {mod_cc}"

    # Step 5: Settings._cached_account_id state
    ok, mod_set = _safe(__import__,
                        "Py4GWCoreLib.database_src.Settings",
                        fromlist=["SETTINGS"])
    if ok:
        sdb = getattr(mod_set, "SETTINGS", None)
        if sdb:
            try:
                sdb._ensure_cache_populated()
                result["steps"]["Settings._cached_account_id"] = (
                    getattr(sdb, "_cached_account_id", "MISSING_ATTR"))
                result["steps"]["Settings._cached_email"] = (
                    str(getattr(sdb, "_cached_email", "MISSING_ATTR"))[:80])
            except Exception as exc:
                result["steps"]["Settings.populate"] = f"ERROR: {exc}"
    else:
        result["steps"]["Settings"] = f"IMPORT_FAIL: {mod_set}"

    return result


# ─────────────────────────────────────────────────────────────────────
# Section 8 — Party demo parity (Py4GW_DEMO.py ShowPartyWindow queries)
# ─────────────────────────────────────────────────────────────────────

def dump_party_demo():
    """Mirror all party queries from Py4GW_DEMO.py ShowPartyWindow()."""
    result = {"section": "party_demo", "ok": True}

    ok, gc = _safe(__import__, "Py4GWCoreLib.GlobalCache", fromlist=["GLOBAL_CACHE"])
    if not ok:
        result["error"] = str(gc)
        return result
    GPC = gc.GLOBAL_CACHE.Party

    # Basic party info
    queries = {}
    for label, fn in [
        ("GetPartyID",       lambda: GPC.GetPartyID()),
        ("GetPartySize",     lambda: GPC.GetPartySize()),
        ("GetPlayerCount",   lambda: GPC.GetPlayerCount()),
        ("GetHeroCount",     lambda: GPC.GetHeroCount()),
        ("GetHenchmanCount", lambda: GPC.GetHenchmanCount()),
        ("IsPartyLoaded",    lambda: GPC.IsPartyLoaded()),
        ("IsPartyLeader",    lambda: GPC.IsPartyLeader()),
        ("IsPartyDefeated",  lambda: GPC.IsPartyDefeated()),
        ("IsHardMode",       lambda: GPC.IsHardMode()),
        ("IsHardModeUnlocked", lambda: GPC.IsHardModeUnlocked()),
        ("IsNormalMode",     lambda: GPC.IsNormalMode()),
        ("IsAllTicked",      lambda: GPC.IsAllTicked()),
    ]:
        ok2, val = _safe(fn)
        queries[label] = str(val) if ok2 else f"ERROR: {val}"

    # Players detail
    ok2, players = _safe(GPC.GetPlayers)
    if ok2:
        queries["players_count"] = len(players) if isinstance(players, list) else "N/A"
        player_details = []
        for i, p in enumerate(players[:8]):  # first 8
            is_dict = isinstance(p, dict)
            pd = {
                "i": i,
                "login_number": p.get("login_number", "N/A") if is_dict else getattr(p, "login_number", "N/A"),
                "state": p.get("state", "N/A") if is_dict else getattr(p, "state", "N/A"),
                "called_target_id": p.get("called_target_id", "N/A") if is_dict else getattr(p, "called_target_id", "N/A"),
            }
            # Agent ID lookup
            try:
                ln = pd["login_number"]
                agent_id = GPC.Players.GetAgentIDByLoginNumber(ln)
                pd["agent_id"] = agent_id
                pd["name"] = str(GPC.Players.GetPlayerNameByLoginNumber(ln))[:40]
            except Exception:
                pd["agent_id"] = "ERROR"
                pd["name"] = "ERROR"
            player_details.append(pd)
        queries["players"] = player_details

        # GetPartyLeaderID
        ok2, leader = _safe(GPC.GetPartyLeaderID)
        queries["GetPartyLeaderID"] = leader if ok2 else f"ERROR: {leader}"

        # Own party number
        ok2, own = _safe(GPC.GetOwnPartyNumber)
        queries["GetOwnPartyNumber"] = own if ok2 else f"ERROR: {own}"

        # IsPlayerTicked
        ok2, own = _safe(GPC.GetOwnPartyNumber)
        if ok2 and own >= 0:
            ok3, ticked = _safe(GPC.IsPlayerTicked, own)
            queries["IsPlayerTicked"] = ticked if ok3 else f"ERROR: {ticked}"
        else:
            queries["IsPlayerTicked"] = "N/A (own party number unknown)"
    else:
        queries["players"] = f"ERROR: {players}"

    # Heroes detail
    ok2, heroes = _safe(GPC.GetHeroes)
    if ok2:
        queries["heroes_count"] = len(heroes) if isinstance(heroes, list) else "N/A"
    else:
        queries["heroes"] = f"ERROR: {heroes}"

    result["queries"] = queries
    return result

# ─────────────────────────────────────────────────────────────────────
# Section 9 — Full demo surface (inventory, player, effects, quests)
# ─────────────────────────────────────────────────────────────────────

def dump_demo_full():
    """Mirror all data queries from Py4GW_DEMO.py across all modules."""
    result = {"section": "demo_full", "ok": True}

    ok, gc = _safe(__import__, "Py4GWCoreLib.GlobalCache", fromlist=["GLOBAL_CACHE"])
    if not ok:
        result["error"] = str(gc)
        return result
    GPC = gc.GLOBAL_CACHE

    queries = {}
    agent_id = 0

    # ── Player ──
    ok2, pl = _safe(__import__, "Py4GWCoreLib.Player", fromlist=["Player"])
    if ok2:
        P = pl.Player
        ok3, _aid = _safe(P.GetAgentID)
        if ok3:
            agent_id = int(_aid) if _aid else 0
        for label, fn in [
            ("GetAgentID",         lambda: P.GetAgentID()),
            ("GetName",            lambda: P.GetName()),
            ("GetAccountName",     lambda: P.GetAccountName()),
            ("GetAccountEmail",    lambda: P.GetAccountEmail()),
            ("GetPlayerNumber",    lambda: P.GetPlayerNumber()),
            ("GetLevel",           lambda: P.GetLevel()),
            ("GetExperience",      lambda: P.GetExperience()),
            ("GetMorale",          lambda: P.GetMorale()),
        ]:
            ok3, val = _safe(fn)
            queries[f"player.{label}"] = str(val)[:80] if ok3 else f"ERROR: {val}"

    # ── Inventory (ShowInventoryWindow) ──
    inv = GPC.Inventory
    for label, fn in [
        ("GetHoveredItemID",      lambda: inv.GetHoveredItemID()),
        ("GetFirstIDKit",         lambda: inv.GetFirstIDKit()),
        ("GetFirstSalvageKit",    lambda: inv.GetFirstSalvageKit()),
        ("GetFirstUnidentifiedItem", lambda: inv.GetFirstUnidentifiedItem()),
        ("GetFirstSalvageableItem",  lambda: inv.GetFirstSalvageableItem()),
        ("GetGoldOnCharacter",    lambda: inv.GetGoldOnCharacter()),
        ("GetGoldInStorage",      lambda: inv.GetGoldInStorage()),
        ("IsStorageOpen",         lambda: inv.IsStorageOpen()),
        ("GetFreeSlotCount",      lambda: inv.GetFreeSlotCount()),
        ("GetBagCount",           lambda: inv.GetBagCount()),
    ]:
        ok2, val = _safe(fn)
        queries[f"inv.{label}"] = str(val) if ok2 else f"ERROR: {val}"

    # ── Agent ──
    if agent_id:
        ok2, ag = _safe(__import__, "Py4GWCoreLib.Agent", fromlist=["Agent"])
        if ok2:
            A = ag.Agent
            for label, fn in [
                ("IsAlive",            lambda: A.IsAlive(agent_id)),
                ("IsDead",             lambda: A.IsDead(agent_id)),
                ("GetHP",              lambda: A.GetHP(agent_id)),
                ("GetMaxHP",           lambda: A.GetMaxHP(agent_id)),
                ("GetEnergy",          lambda: A.GetEnergy(agent_id)),
                ("GetMaxEnergy",       lambda: A.GetMaxEnergy(agent_id)),
                ("GetPrimary",         lambda: A.GetPrimary(agent_id)),
                ("GetSecondary",       lambda: A.GetSecondary(agent_id)),
                ("GetXY",              lambda: A.GetXY(agent_id)),
            ]:
                ok3, val = _safe(fn)
                queries[f"agent.{label}"] = str(val)[:80] if ok3 else f"ERROR: {val}"

    # ── Effects ──
    if agent_id:
        ok2, ef = _safe(__import__, "Py4GWCoreLib.Effects", fromlist=["Effects"])
        if ok2:
            E = ef.Effects
            for label, fn in [
                ("GetEffectCount",     lambda: E.GetEffectCount(agent_id)),
                ("GetBuffCount",       lambda: E.GetBuffCount(agent_id)),
            ]:
                ok3, val = _safe(fn)
                queries[f"effects.{label}"] = str(val) if ok3 else f"ERROR: {val}"

    # ── Skillbar ──
    if agent_id:
        ok2, sb = _safe(__import__, "Py4GWCoreLib.Skillbar", fromlist=["SkillBar"])
        if ok2:
            S = sb.SkillBar
            for label, fn in [
                ("GetSkillbar",        lambda: S.GetSkillbar()),
                ("GetSkillIDBySlot0",  lambda: S.GetSkillIDBySlot(0)),
                ("GetSkillIDBySlot1",  lambda: S.GetSkillIDBySlot(1)),
            ]:
                ok3, val = _safe(fn)
                queries[f"skillbar.{label}"] = str(val)[:80] if ok3 else f"ERROR: {val}"

    # ── Skills ──
    ok2, sk = _safe(__import__, "Py4GWCoreLib.Skill", fromlist=["Skill"])
    if ok2:
        Sk = sk.Skill
        # Use first skill from skillbar as sample
        try:
            sample_skill = S.GetSkillIDBySlot(0)
            if sample_skill:
                for label, fn in [
                    ("GetAdrenaline",  lambda: Sk.GetAdrenaline(int(sample_skill))),
                    ("GetRecharge",    lambda: Sk.GetRecharge(int(sample_skill))),
                ]:
                    ok3, val = _safe(fn)
                    queries[f"skill.{label}"] = str(val) if ok3 else f"ERROR: {val}"
        except Exception:
            pass

    # ── Quests ──
    ok2, q = _safe(__import__, "Py4GWCoreLib.Quest", fromlist=["Quest"])
    if ok2:
        Q = q.Quest
        for label, fn in [
            ("GetActiveQuestId",   lambda: Q.GetActiveQuestId()),
        ]:
            ok3, val = _safe(fn)
            queries[f"quest.{label}"] = str(val) if ok3 else f"ERROR: {val}"

    result["queries"] = queries
    return result

# ─────────────────────────────────────────────────────────────────────
# Section 10 — Full inventory diagnostic (mirrors ShowItemDataWindow)
# ─────────────────────────────────────────────────────────────────────

def dump_inventory_demo():
    """Mirror ALL queries from Py4GW_DEMO.py inventory + item data windows."""
    result = {"section": "inventory_demo", "ok": True}

    ok, gc = _safe(__import__, "Py4GWCoreLib.GlobalCache", fromlist=["GLOBAL_CACHE"])
    if not ok:
        result["error"] = str(gc)
        return result
    GPC = gc.GLOBAL_CACHE

    queries = {}
    inv = GPC.Inventory

    for label, fn in [
        ("GetHoveredItemID",       lambda: inv.GetHoveredItemID()),
        ("GetFirstIDKit",          lambda: inv.GetFirstIDKit()),
        ("GetFirstSalvageKit",     lambda: inv.GetFirstSalvageKit()),
        ("GetFirstUnidentifiedItem", lambda: inv.GetFirstUnidentifiedItem()),
        ("GetFirstSalvageableItem",  lambda: inv.GetFirstSalvageableItem()),
        ("GetGoldOnCharacter",     lambda: inv.GetGoldOnCharacter()),
        ("GetGoldInStorage",       lambda: inv.GetGoldInStorage()),
        ("IsStorageOpen",          lambda: inv.IsStorageOpen()),
        ("GetFreeSlotCount",       lambda: inv.GetFreeSlotCount()),
        ("GetBagCount",            lambda: inv.GetBagCount()),
    ]:
        ok2, val = _safe(fn)
        queries[f"inv.{label}"] = str(val) if ok2 else f"ERROR: {val}"

    # Find a sample item
    sid = 0
    for try_fn in [lambda: inv.GetFirstUnidentifiedItem(),
                   lambda: inv.GetHoveredItemID(),
                   lambda: inv.GetFirstSalvageableItem()]:
        ok2, val = _safe(try_fn)
        if ok2 and val:
            sid = int(val)
            break
    queries["sample_item_id"] = sid

    if sid:
        it = GPC.Item
        for label, fn in [
            ("GetItemType",        lambda: it.GetItemType(sid)),
            ("GetModelID",         lambda: it.GetModelID(sid)),
            ("GetModelFileID",     lambda: it.GetModelFileID(sid)),
            ("GetSlot",            lambda: it.GetSlot(sid)),
            ("GetAgentID",         lambda: it.GetAgentID(sid)),
            ("GetAgentItemID",     lambda: it.GetAgentItemID(sid)),
            ("Rarity.GetRarity",   lambda: it.Rarity.GetRarity(sid)),
            ("Rarity.IsWhite",     lambda: it.Rarity.IsWhite(sid)),
            ("Rarity.IsBlue",      lambda: it.Rarity.IsBlue(sid)),
            ("Rarity.IsPurple",    lambda: it.Rarity.IsPurple(sid)),
            ("Rarity.IsGold",      lambda: it.Rarity.IsGold(sid)),
            ("Rarity.IsGreen",     lambda: it.Rarity.IsGreen(sid)),
            ("Properties.IsCustomized", lambda: it.Properties.IsCustomized(sid)),
            ("Properties.GetValue",     lambda: it.Properties.GetValue(sid)),
            ("Properties.GetQuantity",  lambda: it.Properties.GetQuantity(sid)),
            ("Properties.IsEquipped",   lambda: it.Properties.IsEquipped(sid)),
            ("Properties.GetProfession",lambda: it.Properties.GetProfession(sid)),
            ("Properties.GetInteraction",lambda: it.Properties.GetInteraction(sid)),
            ("Type.IsWeapon",       lambda: it.Type.IsWeapon(sid)),
            ("Type.IsArmor",        lambda: it.Type.IsArmor(sid)),
            ("Type.IsInventoryItem",lambda: it.Type.IsInventoryItem(sid)),
            ("Type.IsStorageItem",  lambda: it.Type.IsStorageItem(sid)),
            ("Type.IsMaterial",     lambda: it.Type.IsMaterial(sid)),
            ("Type.IsRareMaterial", lambda: it.Type.IsRareMaterial(sid)),
            ("Type.IsZCoin",        lambda: it.Type.IsZCoin(sid)),
            ("Type.IsTome",         lambda: it.Type.IsTome(sid)),
            ("Usage.IsUsable",      lambda: it.Usage.IsUsable(sid)),
            ("Usage.GetUses",       lambda: it.Usage.GetUses(sid)),
            ("Dye.GetColor",        lambda: it.Dye.GetColor(sid)),
            ("Mods.GetModCount",    lambda: it.Mods.GetModCount(sid)),
        ]:
            ok2, val = _safe(fn)
            queries[f"item.{label}"] = str(val)[:80] if ok2 else f"ERROR: {val}"

    result["queries"] = queries
    return result

def collect_all():
    sections = []
    for label, fn in [
        ("env",       dump_env),
        ("layouts",   dump_layouts),
        ("ssm_raw",   dump_ssm),
        ("contexts",  dump_contexts),
        ("agentarray_api", dump_agentarray_api),
        ("email_chain", dump_email_chain),
        ("demo_map_parity", dump_demo_map_parity),
        ("party_demo", dump_party_demo),
        ("demo_full", dump_demo_full),
        ("inventory_demo", dump_inventory_demo),
    ]:
        ok, sec = _safe(fn)
        sections.append(sec if ok else {"section": label, "ok": False, "error": str(sec)})
    return {"sections": sections}


def write_dump(data):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(DUMP_DIR, "context_dump.json")
    with open(filename, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, default=str)
    return filename


_has_run = False


def main():
    global _has_run
    if _has_run:
        print("[ContextDump] Already ran.")
        return
    _has_run = True

    print("[ContextDump] Collecting ...")
    data = collect_all()
    path = write_dump(data)

    ctx_sec = None
    ssm_sec = None
    for sec in data.get("sections", []):
        sn = sec.get("section", "")
        if sn == "contexts":
            ctx_sec = sec
        elif sn == "ssm_raw":
            ssm_sec = sec

    total = valid = 0
    if ctx_sec:
        for e in ctx_sec.get("contexts", {}).values():
            total += 1
            if e.get("cached_ctx") == "VALID":
                valid += 1

    nonzero = "?"
    if ssm_sec:
        nonzero = ssm_sec.get("pointers", {}).get("nonzero", "?")

    fix_applied = False
    for sec in data.get("sections", []):
        if sec.get("section") == "env":
            fix_applied = sec.get("instanceinfo_fix_applied", False)
            break

    print(f"[ContextDump] Done: {path}")
    print(f"[ContextDump] SSM nonzero ptrs: {nonzero}")
    print(f"[ContextDump] Contexts valid:  {valid}/{total}")
    print(f"[ContextDump] InstanceInfo fix: {'APPLIED' if fix_applied else 'NOT FOUND'}")

    # InstanceInfo deep check
    ie = ctx_sec.get("contexts", {}).get("InstanceInfo", {}) if ctx_sec else {}
    ai = ie.get("area_info")
    if ai:
        campaign = ai.get("campaign", {}).get("raw", "?")
        region = ai.get("region", {}).get("raw", "?")
        it = ie.get("samples", {}).get("instance_type", {}).get("raw", "?")
        print(f"[ContextDump] InstanceInfo: type={it} campaign={campaign} region={region}")

    # Email chain
    ec = None
    for sec in data.get("sections", []):
        if sec.get("section") == "email_chain":
            ec = sec
            break
    if ec:
        steps = ec.get("steps", {})
        raw = steps.get("GetAccountEmail_raw", "?")
        isready = steps.get("IsMapReady", "?")
        inst_valid = steps.get("GWContext.InstanceInfo.IsValid", "?")
        print(f"[ContextDump] Email: map_ready={isready} instanceinfo_valid={inst_valid} email={raw}")
    else:
        print(f"[ContextDump] InstanceInfo: no AreaInfo (pointer may still be wrong)")

    return path


if __name__ == "__main__":
    main()
