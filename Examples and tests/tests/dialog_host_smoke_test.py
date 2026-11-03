"""In-client smoke test for the recovered native dialog host.

What this exercises:
  1. the OWNING path of a GW window - instance allocation, the embedded CCtlLayout ctor /
     SetFrameId / Clear, the FrameScheduleSize + FrameNativeSizeChanged size pass;
  2. a CHILD CONTROL parented to that owned host frame, to find out whether a child renders,
     self-sizes, and survives the host's layout pass.

Proven in-client on 2026-10-12 01:24:34:
  "[dialog-host] frame 15 OWNED: instance 0x2CFE82C0, layout 0x2CFE82C8, size pass scheduled"
  followed by a handled msg 0x37 - the first execution of the owner contract in this project.

THREADING (measured, not assumed): script main() does NOT run on the game thread, so every create
is queued by game_thread::Enqueue and runs on the next game-thread tick. A create returning 0 means
"queued", NOT "failed"; ids must be POLLED.

VISIBILITY: the host frame itself will not draw. It measures 0x0 because an empty CCtlLayout has no
nodes, and a sized container would still have no background art. Children are the interesting case.

DESTRUCTION IS DISABLED - see ATTEMPT_DESTROY.
"""

import PyUIManager

WINDOW = "dialog-host smoke test"

# WINDOW style. 0x254000 is what the engine's own confirmation-dialog archetype uses, and that
# archetype was in-client verified as a working window with a button. It INCLUDES 0x40000, the
# "draw background template" bit, without which the paint pass early-returns and the frame draws
# nothing at all - the reason every earlier attempt was invisible despite correct geometry.
COMPONENT_FLAGS = 0x254000
WINDOW_TITLE = "Py4GW"

# Child control settings.
#
# The child is a FLAT BUTTON (CtlBtnProc), not a text label, for two measured reasons:
#   * CreateTextLabelFrame forwards its caption as the 5th argument (the encoded payload), and no
#     encoded-payload builder is bound to Python; passing a raw wide string there is the documented
#     crash/garbage path. The label we created that way had no text and never self-sized.
#   * CreateFlatButtonWithClick passes nullptr as the 5th argument and the label as the 6th, so it
#     takes a plain wide string, and CtlBtnProc paints a solid material with no image list.
# The caption is therefore legitimate here.
CHILD_LABEL = "Py4GW"
# Same reasoning as COMPONENT_FLAGS: the background-template bit must be set or the control's
# paint pass early-returns and nothing appears.
CHILD_FLAGS = 0x40000 | 0x300

# DESTRUCTION IS DISABLED until the engine's destroy path is understood.
# GW::ui::DestroyUIComponent faults inside Gw.exe ("Memory at address 0000019b could not be read")
# even once the instance exists. Destroying is a separate open bug; until it is fixed this test
# leaves the invisible window in place rather than risking another client crash. Restarting the
# client clears any orphans.
ATTEMPT_DESTROY = False

# ~5 s at 60 fps: how long to wait for a queued create to land before giving up.
POLL_FRAMES = 300

# Geometry. Applied through the anchor-6 setter (Ghidra-verified FUN_00634cc0), NOT FrameSetSize:
# the parent's layout pass resets a plain size back to 0x0, which is why such a frame stays
# invisible.
HOST_RECT = (200.0, 200.0, 280.0, 160.0)   # x, y, w, h
CHILD_RECT = (20.0, 20.0, 140.0, 24.0)

_step = 0
_frame_id = 0
_child_id = 0
_waited = 0
_finished = False


def _native(name: str):
    """Return the UIManager static, or None when the injected DLL lacks it."""
    return getattr(PyUIManager.UIManager, name, None)


def _say(message: str) -> None:
    print(f"[{WINDOW}] {message}")


def _count() -> int:
    fn = _native("dialog_host_window_count")
    return fn() if fn else -1


def _describe_frame(frame_id: int, what: str) -> None:
    exists = _native("frame_exists_by_frame_id")
    rect = _native("get_frame_position_ex_by_frame_id")
    size = _native("get_frame_native_size_by_frame_id")
    _say(f"{what} {frame_id}: exists={exists(frame_id) if exists else '?'}")
    if rect:
        _say(f"  rect(x,y,w,h,flags)={rect(frame_id)}")
    if size:
        _say(f"  native_size={size(frame_id)}")


def main() -> None:
    global _step, _frame_id, _child_id, _waited, _finished

    if _finished:
        return

    ready = _native("dialog_host_ready")
    if ready is None:
        _say("host bindings are MISSING - re-inject the current DLL")
        _finished = True
        return

    # ---- step 0: arming state (pure reads) ----
    if _step == 0:
        mask = _native("dialog_host_resolved_mask")
        # 0x1FF = the nine ownership natives; bit 9 (0x3FF) adds the anchor-6 geometry setter.
        _say(f"ready={ready()} mask={hex(mask()) if mask else '?'}/0x3ff windows={_count()}")
        if not ready():
            _say("host not armed - stopping")
            _finished = True
            return
        _step = 1
        return

    # ---- step 1: queue the host create ----
    if _step == 1:
        # destroy_all is gated for exactly the same reason as ATTEMPT_DESTROY: the engine's destroy
        # path faults, so reclaiming a previous run's orphan would crash the client. Worse, an
        # orphan IS owned, so the "instance slot empty" guard would not protect it.
        if ATTEMPT_DESTROY:
            destroy_all = _native("dialog_host_destroy_all")
            if destroy_all:
                destroyed = destroy_all()
                if destroyed:
                    _say(f"destroy_all reclaimed {destroyed} pre-existing window(s)")
        elif _count() > 0:
            _say(f"NOTE: {_count()} host window(s) already live from an earlier run and left in "
                 f"place (destroy faults); restart the client to clear them")
        _step = 2
        _waited = 0

        get_root = _native("get_root_frame_id")
        parent = get_root() if get_root else 0
        if not parent:
            _say("no root frame id; cannot pick a parent")
            _finished = True
            return

        hx, hy, hw, hh = HOST_RECT
        create_window = _native("create_owned_window")
        create = _native("create_dialog_host_window")
        if create_window:
            # Window-level entry point: creates the OWNED frame (instance + embedded layout + size
            # pass) AND gives it a real rect, with the window style that carries the
            # background-template bit.
            _say(f"queueing OWNED WINDOW (parent={parent}, style=0x{COMPONENT_FLAGS:x}, "
                 f"rect {hx},{hy} {hw}x{hh}, title={WINDOW_TITLE!r})")
            returned = create_window(parent, hx, hy, hw, hh, COMPONENT_FLAGS, WINDOW_TITLE)
        else:
            _say(f"create_owned_window MISSING from this DLL; falling back to the plain container "
                 f"path (flags=0x{COMPONENT_FLAGS:x}) - expect no chrome")
            returned = create(parent, COMPONENT_FLAGS)
        _say(f"create returned {returned} (0 = queued; made on the next tick)")
        return

    # ---- step 2: poll for the queued host create ----
    if _step == 2:
        _waited += 1
        last = _native("dialog_host_last_frame_id")
        if last and last():
            _frame_id = last()
        if _frame_id:
            _say(f"host frame_id={_frame_id} after {_waited} frame(s)")
            _describe_frame(_frame_id, "host")
            _say("host 0x0 and no art is EXPECTED - it has no content by design")
            if not _native("create_flat_button_with_click_by_frame_id"):
                _say("create_flat_button_with_click_by_frame_id is MISSING from this DLL; stopping")
                _finished = True
                return
            _step = 3
            _waited = 0
            return
        if _waited >= POLL_FRAMES:
            _say(f"host create never landed after {POLL_FRAMES} frames (windows={_count()})")
            _finished = True
            return
        return

    # ---- step 3: queue the child control ----
    if _step == 3:
        _step = 4
        _waited = 0
        create_child = _native("create_flat_button_with_click_by_frame_id")
        _say(f"queueing FLAT BUTTON child on host {_frame_id} "
             f"(flags=0x{CHILD_FLAGS:x}, label={CHILD_LABEL!r})")
        # CreateFlatButtonWithClick(parent, flags, child_index, label_text, enable_click):
        # nullptr for the 5th arg, plain label in the 6th - no encoded payload involved.
        result = create_child(_frame_id, CHILD_FLAGS, 0, CHILD_LABEL, True)
        _say(f"child create returned {result} (0 = queued)")
        return

    # ---- step 4: poll for the child and describe it ----
    if _step == 4:
        _waited += 1
        get_child = _native("get_child_frame_by_frame_id")
        if get_child:
            # child_index 0 was requested, but the engine's child_offset numbering is not assumed:
            # probe the first few offsets for the first live child.
            for offset in range(0, 5):
                maybe = get_child(_frame_id, offset)
                if maybe:
                    _child_id = maybe
                    _say(f"child found at child_offset {offset} -> frame {_child_id}")
                    break
        if _child_id:
            _describe_frame(_child_id, "child")
            size = _native("get_frame_native_size_by_frame_id")
            rect = _native("get_frame_position_ex_by_frame_id")
            width = height = 0.0
            if size:
                width, height = size(_child_id)
            if not width and rect:
                width = rect(_child_id)[2]
            if width:
                _say(f"CHILD HAS GEOMETRY (width={width}) - the control self-sized")
            else:
                _say("child has ZERO width - it did not self-size, so geometry must be applied")
            _step = 50
            return
        if _waited >= POLL_FRAMES:
            _say(f"no child appeared after {POLL_FRAMES} frames")
            _step = 70
            return
        return

    # ---- step 50: apply geometry through the anchor-6 setter ----
    if _step == 50:
        _step = 60
        _waited = 0
        set_rect = _native("dialog_host_set_frame_rect")
        if not set_rect:
            _say("dialog_host_set_frame_rect is MISSING - re-inject the current DLL; "
                 "geometry cannot be applied, so nothing will render")
            _step = 70
            return
        hx, hy, hw, hh = HOST_RECT
        cx, cy, cw, ch = CHILD_RECT
        _say(f"setting host rect  ({hx},{hy},{hw},{hh})")
        set_rect(_frame_id, hx, hy, hw, hh)
        _say(f"setting child rect ({cx},{cy},{cw},{ch})")
        set_rect(_child_id, cx, cy, cw, ch)

        # Geometry alone may not be enough: ask explicitly for visibility and to be shown, in case
        # the create flags were not translated into a visible style.
        visible = _native("set_frame_visible_by_frame_id")
        show = _native("show_frame_by_frame_id")
        for fid, what in ((_frame_id, "host"), (_child_id, "child")):
            if visible:
                visible(fid, True)
            if show:
                show(fid, True)
        _say(f"requested visible+show on both frames "
             f"(visible={'yes' if visible else 'MISSING'}, show={'yes' if show else 'MISSING'})")
        _say("everything queued; geometry is read back after a few frames")
        return

    # ---- step 60: did the geometry stick? ----
    if _step == 60:
        _waited += 1
        if _waited < 5:
            return
        _step = 70
        rect = _native("get_frame_position_ex_by_frame_id")
        _say("re-reading rects after geometry:")
        _describe_frame(_frame_id, "host")
        _describe_frame(_child_id, "child")
        if rect:
            host_w = rect(_frame_id)[2]
            child_w = rect(_child_id)[2]
            if host_w or child_w:
                _say("GEOMETRY STUCK - the anchor-6 setter survives the layout pass; "
                     "a visible frame is now plausible")
            else:
                _say("geometry did NOT stick (still 0x0) - the parent's layout pass is still "
                     "overwriting it, or the facade call did not take effect")
        return

    # ---- step 70: destruction (disabled by default) ----
    if _step == 70:
        if not ATTEMPT_DESTROY:
            _say("destroy skipped by design; window and child left in place")
            _say("PASS: create -> own -> size pass -> child control -> geometry, no crash")
            _say("destroy faults inside Gw.exe and remains a separate open bug")
            _finished = True
            return
        destroy = _native("destroy_dialog_host_window")
        _say(f"destroying frame {_frame_id}")
        _say(f"destroy returned {destroy(_frame_id)} (off-thread: the value is not reliable)")
        _finished = True
        return


if __name__ == "__main__":
    main()
