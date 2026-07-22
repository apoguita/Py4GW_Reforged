"""FileDialog — an in-overlay file picker built on the native ``PyImGui.filebrowser`` addon.

Replaces ``tkinter.filedialog`` (which needs a Tcl runtime the injected client doesn't have) with
the ImGui file browser that renders inside the game overlay. Because that browser is immediate-mode
(it must be drawn every frame and reports its result by polling — unlike tkinter's blocking call),
this wraps the open → draw-each-frame → result lifecycle behind a simple API:

    _dlg = FileDialog()

    # in your per-frame draw(), after the button that starts it:
    if PyImGui.button("Save"):
        _dlg.open_save("Save Config", valid_types=".json")

    path = _dlg.draw()          # returns the chosen path ONCE on confirm, else None
    if path:
        save_to(path)

``draw()`` MUST be called every frame from the same window/draw scope as the button (the modal opens
at that id-stack level). It returns the selected path a single time when the user confirms, and None
otherwise (including while the picker is open or after a cancel).
"""

import PyImGui


class FileDialog:
    def __init__(self, width: float = 720.0, height: float = 420.0, modal: bool = True) -> None:
        self._fb = PyImGui.filebrowser.FileBrowser()
        try:
            self._fb.set_use_modal(bool(modal))
        except Exception:
            pass
        self._size = (float(width), float(height))
        self._label = ""
        self._mode = PyImGui.filebrowser.DialogMode.OPEN
        self._valid_types = "*.*"
        self._active = False
        self._need_open = False
        self._shown = False
        #: free-form caller label carried from open_*() to the result, so one dialog can serve
        #: several buttons without the caller tracking its own pending-action state.
        self.tag = ""

    # ── start a dialog (arms it; the actual picker appears once draw() runs) ──────────────
    def open_open(self, label: str = "Open File", valid_types: str = "*.*",
                  start_path: str = "", tag: str = "") -> None:
        self._begin(label, PyImGui.filebrowser.DialogMode.OPEN, valid_types, start_path, tag)

    def open_save(self, label: str = "Save File", valid_types: str = "*.*",
                  start_path: str = "", tag: str = "") -> None:
        self._begin(label, PyImGui.filebrowser.DialogMode.SAVE, valid_types, start_path, tag)

    def open_select(self, label: str = "Select Folder", start_path: str = "", tag: str = "") -> None:
        self._begin(label, PyImGui.filebrowser.DialogMode.SELECT, "*.*", start_path, tag)

    def _begin(self, label, mode, valid_types, start_path, tag="") -> None:
        self._label = label
        self._mode = mode
        self._valid_types = valid_types or "*.*"
        self.tag = tag
        if start_path:
            try:
                self._fb.set_current_path(str(start_path))
            except Exception:
                pass
        self._active = True
        self._need_open = True
        self._shown = False

    @property
    def is_open(self) -> bool:
        return self._active

    # ── per-frame render + result poll ───────────────────────────────────────────────────
    def draw(self):
        """Render the picker (when armed) and return the chosen path once, else None."""
        if not self._active:
            return None
        if self._need_open:
            PyImGui.open_popup(self._label)
            self._need_open = False
        try:
            confirmed = self._fb.show_file_dialog(self._label, self._mode, self._size, self._valid_types)
        except Exception:
            self._active = False
            return None
        if confirmed:
            self._active = False
            return self._fb.selected_path
        # The addon closes its own popup on cancel/confirm. Give it one render frame, then treat a
        # closed popup as a cancel so we stop re-arming it.
        if self._shown and not PyImGui.is_popup_open(self._label):
            self._active = False
        self._shown = True
        return None
