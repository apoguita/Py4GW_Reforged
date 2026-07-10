# AvChar Diagnostic
# Drop into a Py4GW python project's Widgets folder and let it run.
# It dumps every link of the available-character chain and writes
#   ~/avchar_diag_<project>.txt
# Run it in BOTH the legacy and reforged python projects and share both files.

import os
import struct
import ctypes
from ctypes import wintypes

MODULE_NAME = "AvChar Diagnostic"

# ---------------------------------------------------------------------------
# crash-safe memory read (ReadProcessMemory never faults on a bad pointer)
# ---------------------------------------------------------------------------
_k32 = ctypes.windll.kernel32
_k32.ReadProcessMemory.argtypes = [
    wintypes.HANDLE, wintypes.LPCVOID, wintypes.LPVOID,
    ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t),
]
_k32.ReadProcessMemory.restype = wintypes.BOOL
_HPROC = _k32.GetCurrentProcess()


def rpm(addr, size):
    """Read `size` bytes at `addr`; returns bytes or None (never crashes)."""
    if not addr:
        return None
    buf = (ctypes.c_ubyte * size)()
    n = ctypes.c_size_t(0)
    ok = _k32.ReadProcessMemory(_HPROC, ctypes.c_void_p(addr), buf, size, ctypes.byref(n))
    if not ok or n.value != size:
        return None
    return bytes(buf)


def u32(b, off):
    return struct.unpack_from("<I", b, off)[0]


def i32(b, off):
    return struct.unpack_from("<i", b, off)[0]


# ---------------------------------------------------------------------------
# output (console + buffered to a file)
# ---------------------------------------------------------------------------
_lines = []


def emit(s=""):
    _lines.append(str(s))
    try:
        import Py4GW
        Py4GW.Console.Log(MODULE_NAME, str(s), Py4GW.Console.MessageType.Info)
    except Exception:
        pass
    try:
        print(s)
    except Exception:
        pass


def project_tag():
    try:
        import Py4GWCoreLib
        return os.path.basename(os.path.dirname(os.path.dirname(Py4GWCoreLib.__file__)))
    except Exception:
        return "unknown"


# ---------------------------------------------------------------------------
# the dump
# ---------------------------------------------------------------------------
def dump():
    tag = project_tag()
    emit("=" * 72)
    emit("AVAILABLE CHARACTER DIAGNOSTIC   project=%s" % tag)
    emit("=" * 72)

    # 1) Pointers directory (shared memory) --------------------------------
    ssm = None
    try:
        from Py4GWCoreLib.native_src.ShMem.SysShaMem import SystemShaMemMgr
        ssm = SystemShaMemMgr.get_pointers_struct()
    except Exception as e:
        emit("[pointers] import/get failed: %r" % (e,))

    av_ptr = 0
    pre_ptr = 0
    if ssm is not None:
        emit("[Pointers_SHMemStruct] slot values (order == native struct order):")
        for fname, _ftype in ssm._fields_:
            try:
                val = getattr(ssm, fname) or 0
            except Exception:
                val = 0
            emit("    %-22s = 0x%08X" % (fname, val))
        av_ptr = getattr(ssm, "AvailableCharacters", 0) or 0
        pre_ptr = getattr(ssm, "PreGameContext", 0) or 0
    else:
        emit("[pointers] get_pointers_struct() returned None (SSM not ready)")

    # 2) resolve the account-roster global directly from the pattern -------
    emit("")
    emit("[direct pattern] 8b 35 ?? ?? ?? ?? 57 69 F8 84 00 00 00  off=0x2 sect=TEXT")
    NativeSymbol = None
    try:
        from Py4GWCoreLib.native_src.internals.native_symbol import NativeSymbol
    except Exception:
        try:
            from Py4GWCoreLib.native_src.ShMem.SysShaMem import NativeSymbol
        except Exception as e:
            emit("    NativeSymbol import failed: %r" % (e,))

    sym_g = 0
    if NativeSymbol is not None:
        try:
            sym = NativeSymbol(
                "avchar_diag",
                b"\x8b\x35\x00\x00\x00\x00\x57\x69\xF8\x84\x00\x00\x00",
                "xx????xxxxxxx",
                0x2,
                0,  # ScannerSection.TEXT
            )
            emit("    operand addr      = 0x%08X" % (sym.addr or 0))
            sym_g = sym.read_ptr()
            emit("    global (read_ptr) = 0x%08X" % sym_g)
        except Exception as e:
            emit("    pattern resolve FAILED: %r" % (e,))

    # 3) the crux comparison ----------------------------------------------
    emit("")
    emit("[compare] SSM.AvailableCharacters=0x%08X   direct-global=0x%08X   match=%s"
         % (av_ptr, sym_g, (av_ptr == sym_g and av_ptr != 0)))

    # 4) interpret each candidate as a GW::Array container -----------------
    def dump_container(label, ptr):
        emit("")
        emit("[container] %s @ 0x%08X" % (label, ptr))
        b = rpm(ptr, 0x10)
        if b is None:
            emit("    <unreadable>")
            return None
        buffer_, cap, size, param = u32(b, 0), u32(b, 4), u32(b, 8), u32(b, 12)
        emit("    m_buffer=0x%08X  capacity=%d  size=%d  param=0x%08X"
             % (buffer_, cap, size, param))
        return (buffer_, cap, size)

    c_ssm = dump_container("SSM.AvailableCharacters", av_ptr) if av_ptr else None
    c_sym = dump_container("direct-pattern global", sym_g) if sym_g else None

    # 5) decode elements (0x84 stride: name@0x18, props@0x40) --------------
    def dump_elements(cont, source):
        if not cont:
            return
        buffer_, cap, size = cont
        emit("")
        emit("[elements] from %s: buffer=0x%08X capacity=%d size=%d"
             % (source, buffer_, cap, size))
        if not buffer_ or size == 0 or size > 100:
            emit("    (nothing to dump / implausible size)")
            return
        for i in range(min(size, 12)):
            elem = buffer_ + i * 0x84
            b = rpm(elem, 0x84)
            if b is None:
                emit("    [%d] <unreadable @0x%08X>" % (i, elem))
                continue
            name_raw = b[0x18:0x18 + 40]
            try:
                name = name_raw.decode("utf-16-le", "replace").split("\x00")[0]
            except Exception:
                name = "<decode err>"
            props = [u32(b, 0x40 + k * 4) for k in range(17)]
            map_id = (props[0] >> 16) & 0xFFFF
            primary = (props[2] >> 20) & 0xF
            secondary = (props[7] >> 10) & 0xF
            campaign = props[7] & 0xF
            level = (props[7] >> 4) & 0x3F
            is_pvp = ((props[7] >> 9) & 0x1) == 1
            emit("    [%d] name=%r lvl=%d prim=%d sec=%d camp=%d map=%d pvp=%s"
                 % (i, name, level, primary, secondary, campaign, map_id, is_pvp))
            emit("         first0x18=%s" % (b[:0x18].hex(" "),))
            emit("         name_raw =%s" % (name_raw.hex(" "),))

    dump_elements(c_ssm, "SSM.AvailableCharacters")
    if c_sym and c_sym != c_ssm:
        dump_elements(c_sym, "direct-pattern")

    # 6) PreGameContext preview buffer (the OTHER, separate list) ----------
    emit("")
    emit("[pregame] PreGameContext ptr = 0x%08X" % pre_ptr)
    if pre_ptr:
        tail = rpm(pre_ptr + 0xD0, 0x2C)  # tail block 0xD0..
        if tail:
            emit("    max_characters=%d chosen_index=%d preview=%d pending=%d"
                 % (u32(tail, 0x00), i32(tail, 0x04), i32(tail, 0x08), i32(tail, 0x0C)))
            emit("    chars_buffer=0x%08X chars_capacity=%d chars_count=%d"
                 % (u32(tail, 0x10), u32(tail, 0x14), u32(tail, 0x18)))
        else:
            emit("    <tail unreadable>")

    # 7) the high-level API the widget actually calls ----------------------
    emit("")
    emit("[API] Map.Pregame.GetAvailableCharacterList()")
    try:
        from Py4GWCoreLib import Map
        lst = Map.Pregame.GetAvailableCharacterList()
        emit("    returned %d entries" % len(lst))
        for i, c in enumerate(lst[:12]):
            try:
                emit("    [%d] player_name=%r level=%s pvp=%s prim=%s"
                     % (i, c.player_name, c.level, c.is_pvp, c.primary))
            except Exception as e:
                emit("    [%d] <accessor error: %r>" % (i, e))
    except Exception as e:
        emit("    API FAILED: %r" % (e,))

    # write file -----------------------------------------------------------
    emit("")
    emit("=" * 72)
    out = os.path.join(os.path.expanduser("~"), "avchar_diag_%s.txt" % tag)
    try:
        with open(out, "w", encoding="utf-8") as f:
            f.write("\n".join(_lines))
        emit("WROTE: %s" % out)
    except Exception as e:
        emit("file write failed: %r" % (e,))
    emit("=" * 72)


# ---------------------------------------------------------------------------
# driver: run once, a few frames in so shared memory is populated
# ---------------------------------------------------------------------------
_done = False
_frames = 0


def main():
    global _done, _frames
    if _done:
        return
    _frames += 1
    ready = False
    try:
        from Py4GWCoreLib.native_src.ShMem.SysShaMem import SystemShaMemMgr
        ready = SystemShaMemMgr.get_pointers_struct() is not None
    except Exception:
        ready = False
    if ready or _frames > 120:
        try:
            dump()
        except Exception as e:
            emit("DUMP CRASHED: %r" % (e,))
        _done = True


if __name__ == "__main__":
    main()
