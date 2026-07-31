from Py4GWCoreLib import ImGui, Color, Player, IconsFontAwesome5, ColorPalette, GLOBAL_CACHE, SharedCommandType, ConsoleLog, Utils
from Py4GWCoreLib import JsonFactory
from Py4GWCoreLib.py4gwcorelib_src.Settings import Settings
import PyImGui
import PyOverlay
import PySystem

MODULE_NAME = "Layout Manager"
MODULE_ICON = "Textures/Module_Icons/layout manager.png"

screen_overlay = PyOverlay.ScreenOverlay()
screen_overlay.create_overlay(ms=0, destroy=False)

screen_width, screen_height = screen_overlay.get_desktop_size()


_LAYOUTS_DOC = JsonFactory("Widgets/LayoutManager/window_layouts.json", "global")
_TEMPLATES_DOC = JsonFactory("Widgets/LayoutManager/templates.json", "global")
_LOCAL_SETTINGS = Settings("Widgets/LayoutManager.ini", "account")

def _send_message_to(command: SharedCommandType, receiver_email: str, params=(0.0, 0.0, 0.0, 0.0), ExtraData=("", "", "", "")):
    sender_email = Player.GetAccountEmail()
    accounts = GLOBAL_CACHE.ShMem.GetAllAccountData(include_isolated=True) or []
    if not any(acc.AccountEmail == receiver_email for acc in accounts):
        ConsoleLog("Messaging", f"Account with email {receiver_email} not found. Message not sent.", log=True)
        return

    GLOBAL_CACHE.ShMem.SendMessage(sender_email, receiver_email, command, params, ExtraData)


def slider_input_int(label: str, value: int, min_value: int, max_value: int) -> int:
    """Draw a slider + input int combo on one line, clamped to [min_value, max_value]."""
    v = int(value)

    # Use hidden IDs so the visible label can be separate/clean
    slider_id = f"##{label}_slider"
    input_id  = f"##{label}_input"

    # Optional visible label
    start_x = PyImGui.get_cursor_pos_x()
    PyImGui.text(label)
    PyImGui.same_line(start_x + 50, -1)
    #PyImGui.same_line(0, -1)  # 50px gap after the label

    PyImGui.push_item_width(150)
    v_slider = PyImGui.slider_int(slider_id, v, int(min_value), int(max_value))
    if v_slider != v:
        v = v_slider

    PyImGui.same_line(0, -1)
    v_input = PyImGui.input_int(input_id, v)
    if v_input != v:
        # clamp manual input
        if v_input < min_value: v_input = min_value
        if v_input > max_value: v_input = max_value
        v = v_input

    PyImGui.pop_item_width()
    return v


class ClientConfig:
    def __init__(self, email="", alias="", x=0.0, y=0.0, width=0.0, height=0.0, borderless=False, rename_window=False, window_title=""):
        self.email = email
        self.alias = alias
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.borderless = borderless
        self.rename_window = rename_window
        self.window_title = window_title
        self.color:Color =  ColorPalette.GetColor("white")
        self.show_overlay: bool = True 
        self.always_on_top: bool = False
        self.opacity: int = 255  # 0-255
        
    def to_dict(self):
        return {
            "email": self.email,
            "alias": self.alias,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "borderless": self.borderless,
            "rename_window": self.rename_window,
            "window_title": self.window_title,
            "color": self.color.to_tuple(),
            "show_overlay": self.show_overlay,
            "always_on_top": self.always_on_top,
            "opacity": self.opacity
        }
        
    def from_dict(self, data):
        self.email = data.get("email", "")
        self.alias = data.get("alias", "")
        self.x = data.get("x", 0.0)
        self.y = data.get("y", 0.0)
        self.width = data.get("width", 0.0)
        self.height = data.get("height", 0.0)
        self.borderless = data.get("borderless", False)
        self.rename_window = data.get("rename_window", False)
        self.window_title = data.get("window_title", "")
        color_tuple = data.get("color", (255, 255, 255, 255))
        if isinstance(color_tuple, (list, tuple)) and len(color_tuple) == 4:
            self.color = Color(*color_tuple)
        self.show_overlay = data.get("show_overlay", False)
        self.always_on_top = data.get("always_on_top", False)
        self.opacity = data.get("opacity", 255)

class LayoutConfig:
    def __init__(self, layout_name: str = "", is_template: bool = False):
        self.layout_name = layout_name
        self.is_template = is_template  # <-- NEW: mark as client-less template when True
        self.clients: list[ClientConfig] = []

    def to_dict(self):
        return {
            "layout_name": self.layout_name,
            "is_template": self.is_template,  # <-- NEW
            "clients": [client.to_dict() for client in self.clients]
        }

    def from_dict(self, data):
        self.layout_name = data.get("layout_name", "")
        self.is_template = data.get("is_template", False)  # <-- NEW (defaults to False)
        self.clients = []
        for client_data in data.get("clients", []):
            client = ClientConfig()
            client.from_dict(client_data)
            self.clients.append(client)

    def get_client_by_email(self, email: str) -> ClientConfig | None:
        for client in self.clients:
            if client.email == email:
                return client
        return None

    def get_client_by_alias(self, alias: str) -> ClientConfig | None:
        for client in self.clients:
            if client.alias == alias:
                return client
        return None

    def add_client(self, client: ClientConfig):
        self.clients.append(client)

    def remove_client(self, client: ClientConfig):
        self.clients.remove(client)

    def update_client(self, email: str, new_client: ClientConfig):
        for i, client in enumerate(self.clients):
            if client.email == email:
                self.clients[i] = new_client
                return

    def get_all_clients(self) -> list[ClientConfig]:
        return self.clients


class WindowLayouts:
    """Own the shared layout catalog and the live shared-memory account roster."""

    def __init__(self):
        self.layouts: list[LayoutConfig] = []
        self.all_accounts: list[ClientConfig] = []
        self.online_emails: set[str] = set()
        self._template_names: list[str] = []

        # existing UI state...
        self._lcw_selected_layout_idx = -1
        self._lcw_selected_client_idx = -1
        self._lcw_account_picker_idx = 0

        self._edit_layout_name = ""
        self._new_layout_name = ""
        self._template_name = ""
        self._template_picker_idx = 0
        # NEW: per-client editor windows state
        self._client_editor_windows: list[dict] = []  # each: {"layout_idx": int, "client_idx": int, "open": bool}
        self.load_layouts()
        self._load_accounts()
        self._merge_layout_clients_into_accounts()
        self.refresh_accounts_from_shmem()
        self.refresh_template_names()

    def load_layouts(self):
        self.layouts = []
        raw_layouts = _LAYOUTS_DOC.get_json("layouts", [])
        if not isinstance(raw_layouts, list):
            return
        for layout_data in raw_layouts:
            if not isinstance(layout_data, dict):
                continue
            layout = LayoutConfig()
            layout.from_dict(layout_data)
            self.layouts.append(layout)

    def save_layouts(self):
        _LAYOUTS_DOC.set_json("layouts", [layout.to_dict() for layout in self.layouts])

    def _load_accounts(self):
        """Load the global account roster retained from previously observed clients."""
        self.all_accounts = []
        raw_accounts = _LAYOUTS_DOC.get_json("accounts", [])
        if not isinstance(raw_accounts, list):
            return
        for account_data in raw_accounts:
            if not isinstance(account_data, dict):
                continue
            client = ClientConfig()
            client.from_dict(account_data)
            if client.email:
                self.all_accounts.append(client)

    def _save_accounts(self):
        _LAYOUTS_DOC.set_json("accounts", [account.to_dict() for account in self.all_accounts])

    def _merge_layout_clients_into_accounts(self):
        """Keep configured offline clients available in the account picker."""
        known = {account.email for account in self.all_accounts if account.email}
        for layout in self.layouts:
            for client in layout.clients:
                if client.email and client.email not in known:
                    self.all_accounts.append(client)
                    known.add(client.email)

    def refresh_accounts_from_shmem(self):
        """Merge every currently visible client into the persisted global roster."""
        accounts = GLOBAL_CACHE.ShMem.GetAllAccountData(include_isolated=True) or []
        self.online_emails = {
            str(getattr(account, "AccountEmail", "") or "").strip()
            for account in accounts
            if str(getattr(account, "AccountEmail", "") or "").strip()
        }
        known = {account.email: account for account in self.all_accounts if account.email}
        changed = False
        for account in accounts:
            email = str(getattr(account, "AccountEmail", "") or "").strip()
            if not email:
                continue
            character_name = str(
                getattr(getattr(account, "AgentData", None), "CharacterName", "") or ""
            ).strip()
            client = known.get(email)
            if client is None:
                client = ClientConfig(
                    email=email,
                    alias=character_name or email,
                    x=0,
                    y=0,
                    width=800,
                    height=600,
                    borderless=False,
                    rename_window=False,
                    window_title="",
                )
                self.all_accounts.append(client)
                known[email] = client
                changed = True
            elif character_name and (not client.alias or client.alias == client.email):
                client.alias = character_name
                changed = True
        if changed:
            self._save_accounts()

    def refresh_template_names(self):
        """Refresh the shared template-name cache; templates do not change per frame."""
        self._template_names = sorted(
            str(name) for name in _TEMPLATES_DOC.keys("templates") if str(name).strip()
        )

    @staticmethod
    def _template_key(name: str) -> str:
        """Return a stable, jail-safe catalog key from a user-facing template name."""
        cleaned = " ".join(str(name).strip().split())
        cleaned = "".join(character if character.isalnum() or character in " _-." else "_" for character in cleaned)
        return cleaned[:80].strip(" .")

    def template_names(self) -> list[str]:
        return self._template_names

    def overlay_signature(self) -> tuple:
        """Return the static overlay content used to avoid redundant native redraws."""
        entries = []
        for layout in self.layouts:
            for client in layout.clients:
                if not getattr(client, "show_overlay", False):
                    continue
                entries.append(
                    (
                        str(client.email),
                        str(client.alias),
                        int(client.x),
                        int(client.y),
                        int(client.width),
                        int(client.height),
                        int(client.color.to_argb()),
                    )
                )
        return (int(screen_width), int(screen_height), tuple(entries))

    def export_template(self, layout: LayoutConfig, name: str):
        """Save a layout template in the shared, jailed JSON template catalog."""
        key = self._template_key(name)
        if not key:
            return
        layout_dict = layout.to_dict()

        # Force template flag
        layout_dict["is_template"] = True
        for c in layout_dict["clients"]:
            c["email"] = "__TEMPLATE__"

        _TEMPLATES_DOC.set_json("templates/%s" % key, layout_dict)
        self.refresh_template_names()

    def import_template(self, name: str) -> LayoutConfig | None:
        """Load a template from the shared, jailed JSON template catalog."""
        key = self._template_key(name)
        data = _TEMPLATES_DOC.get_json("templates/%s" % key, {})
        if not isinstance(data, dict) or not data:
            return None

        layout = LayoutConfig()
        layout.from_dict(data)
        layout.is_template = True
        return layout

    def get_layout_by_name(self, name: str) -> LayoutConfig | None:
        for layout in self.layouts:
            if layout.layout_name == name:
                return layout
        return None

    def add_layout(self, layout: LayoutConfig):
        self.layouts.append(layout)
        self.save_layouts()

    def remove_layout(self, layout: LayoutConfig):
        self.layouts.remove(layout)
        self.save_layouts()

    def update_layout(self, name: str, new_layout: LayoutConfig):
        for i, layout in enumerate(self.layouts):
            if layout.layout_name == name:
                self.layouts[i] = new_layout
                self.save_layouts()
                return

    def get_all_layouts(self) -> list[LayoutConfig]:
        return self.layouts

    def get_remaining_accounts_from_shmem(self):
        """Compatibility alias for callers from the legacy implementation."""
        self.refresh_accounts_from_shmem()

    def draw_window(self):
        if PyImGui.begin("Layout Management", PyImGui.WindowFlags.AlwaysAutoResize):
            PyImGui.text("Window Layouts:")

            for i, layout in enumerate(self.get_all_layouts()):
                if PyImGui.selectable(
                    layout.layout_name,
                    self._lcw_selected_layout_idx == i,
                    PyImGui.SelectableFlags.NoFlag,
                    (0.0, 0.0),
                ):
                    self._lcw_selected_layout_idx = i
                    self._edit_layout_name = layout.layout_name

            PyImGui.separator()

            if 0 <= self._lcw_selected_layout_idx < len(self.get_all_layouts()):
                layout = self.get_all_layouts()[self._lcw_selected_layout_idx]
                PyImGui.text(f"Editing Layout: {layout.layout_name}")
                self._edit_layout_name = PyImGui.input_text("Layout Name", self._edit_layout_name, 0)

                if PyImGui.button("Save Changes"):
                    layout.layout_name = self._edit_layout_name
                    self.save_layouts()

                PyImGui.same_line(0, -1)
                if PyImGui.button("Delete Layout"):
                    self.remove_layout(layout)
                    self._lcw_selected_layout_idx = -1
                    self._edit_layout_name = ""

                self._template_name = PyImGui.input_text("Template Name", self._template_name, 0)
                if PyImGui.button("Export as Template") and self._template_name.strip():
                    self.export_template(layout, self._template_name)
                    self._template_name = ""

                template_names = self.template_names()
                if template_names:
                    self._template_picker_idx = max(0, min(self._template_picker_idx, len(template_names) - 1))
                    self._template_picker_idx = PyImGui.combo(
                        "Template", self._template_picker_idx, template_names
                    )
                    if PyImGui.button("Import Template"):
                        imported = self.import_template(template_names[self._template_picker_idx])
                        if imported is not None:
                            self.add_layout(imported)
                else:
                    PyImGui.text_disabled("No shared templates saved")

            PyImGui.separator()
            self._new_layout_name = PyImGui.input_text("New Layout Name", self._new_layout_name, 0)
            if PyImGui.button("Add Layout") and self._new_layout_name.strip():
                new_layout = LayoutConfig(layout_name=self._new_layout_name.strip())
                self.add_layout(new_layout)
                self._new_layout_name = ""
        PyImGui.end()

    # --- add this method inside class WindowLayouts ---
    def open_client_editor(self, layout_idx: int, client_idx: int):
        # avoid duplicates
        for win in self._client_editor_windows:
            if win["layout_idx"] == layout_idx and win["client_idx"] == client_idx and win["open"]:
                return
        self._client_editor_windows.append({"layout_idx": layout_idx, "client_idx": client_idx, "open": True})

    def draw_client_editors(self):
        # draw each open editor; collect those to close after drawing
        to_close = []
        for idx, win in enumerate(self._client_editor_windows):
            if not win["open"]:
                to_close.append(idx)
                continue

            lidx = win["layout_idx"]
            cidx = win["client_idx"]

            # validate indices
            if not (0 <= lidx < len(self.layouts)) or not (0 <= cidx < len(self.layouts[lidx].clients)):
                to_close.append(idx)
                continue

            layout = self.layouts[lidx]
            client = layout.clients[cidx]

            # unique window title/id (ImGui uses text before ## as visible, after ## as unique id)
            title = f"Edit Client: {client.email}##{lidx}:{cidx}"
            if PyImGui.begin(title, True, PyImGui.WindowFlags.AlwaysAutoResize):

                PyImGui.text(f"Layout: {layout.layout_name}")
                PyImGui.separator()

                start_x = PyImGui.get_cursor_pos_x()
                PyImGui.text("Alias:")
                PyImGui.same_line(start_x + 50, -1)
                PyImGui.push_item_width(200)
                client.alias = PyImGui.input_text(f"##{client.email}_alias", client.alias, 0)
                start_x = PyImGui.get_cursor_pos_x()
                PyImGui.text("Email:")
                PyImGui.same_line(start_x + 50, -1)
                client.email = PyImGui.input_text(f"##{client.email}_email", client.email, 0)
                PyImGui.pop_item_width()
                PyImGui.push_item_width(100)
                PyImGui.text("Window Title:")
                PyImGui.same_line(0, -1)
                client.window_title = PyImGui.input_text(f"##{client.email}_window_title", client.window_title, 0)
                PyImGui.same_line(0, -1)
                client.rename_window = PyImGui.checkbox("Rename", client.rename_window)
                PyImGui.pop_item_width()

                PyImGui.separator()
                PyImGui.text("Position and Size (px):")

                client.x = slider_input_int("X", int(client.x), -100, int(screen_width))
                client.y = slider_input_int("Y", int(client.y), -100, int(screen_height))

                client.width  = slider_input_int("Width",  int(client.width),  0, int(screen_width))
                client.height = slider_input_int("Height", int(client.height), 0, int(screen_height))

                client.show_overlay = PyImGui.checkbox("Preview Position", getattr(client, "show_overlay", False))
                color = PyImGui.color_edit4("Color", client.color.to_tuple_normalized())
                client.color = Color.from_tuple((float(color[0]), float(color[1]), float(color[2]), float(color[3])))

                PyImGui.separator()

                client.borderless = PyImGui.checkbox("Borderless", client.borderless)
                PyImGui.show_tooltip("this action is non reversable from the client side; the client must be restarted to restore borders")
                PyImGui.same_line(0, -1)
                client.always_on_top = PyImGui.checkbox("Always on Top", getattr(client, "always_on_top", False))
                client.opacity = PyImGui.slider_int("Opacity", getattr(client, "opacity", 255), 0, 255)

                if PyImGui.button("Save"):
                    self.save_layouts()

                PyImGui.same_line(0, -1)
                """if PyImGui.button("Remove From Layout"):
                    layout.remove_client(client)
                    self.save_layouts()
                    to_close.append(idx)  # close this editor; client is gone"""

                if client.email in self.online_emails:
                    if PyImGui.button("Apply to Client Now"):
                        # send messages to that client
                        if client.rename_window:
                            _send_message_to(SharedCommandType.SetWindowTitle, client.email, ExtraData=(client.window_title, "", "", ""))
                        _send_message_to(SharedCommandType.SetWindowGeometry, client.email, params=(int(client.x), int(client.y), int(client.width), int(client.height)))
                        _send_message_to(SharedCommandType.SetBorderless, client.email, params=(float(client.borderless), 0.0, 0.0, 0.0))
                        _send_message_to(SharedCommandType.SetAlwaysOnTop, client.email, params=(float(client.always_on_top), 0.0, 0.0, 0.0))
                        _send_message_to(SharedCommandType.SetOpacity, client.email, params=(float(client.opacity), 0.0, 0.0, 0.0))

                PyImGui.same_line(0, -1)
                if PyImGui.button("Close"):
                    to_close.append(idx)

            PyImGui.end()

        # remove closed windows (from the end to keep indices valid)
        for i in reversed(to_close):
            if 0 <= i < len(self._client_editor_windows):
                self._client_editor_windows.pop(i)


window_manager = WindowLayouts()
layout_manager_window_open = _LOCAL_SETTINGS.get_bool("Windows", "layout_editor_open", False)
_last_account_refresh_ms = 0
_overlay_signature: tuple | None = None

draw_screen_rect = False

def DrawMainWindow():
    global layout_manager_window_open, draw_screen_rect
    icon = IconsFontAwesome5.ICON_GRIP_HORIZONTAL

    if PyImGui.begin(f"{icon} {MODULE_NAME}", True,
                     PyImGui.WindowFlags.AlwaysAutoResize | PyImGui.WindowFlags.MenuBar):

        if PyImGui.begin_menu_bar():
            if PyImGui.begin_menu("Edit Layouts"):
                previous_open = layout_manager_window_open
                layout_manager_window_open = PyImGui.checkbox("Layout Manager", layout_manager_window_open)
                if layout_manager_window_open != previous_open:
                    _LOCAL_SETTINGS.set_bool("Windows", "layout_editor_open", layout_manager_window_open)
                PyImGui.end_menu()
            PyImGui.end_menu_bar()
        
        PyImGui.text("Manage and apply window layouts to clients.")
        layouts = window_manager.get_all_layouts()
        layout_names = [l.layout_name for l in layouts]
        if not layout_names:
            layout_names = ["<no layouts>"]

        # clamp index
        if not (0 <= window_manager._lcw_selected_layout_idx < len(layout_names)):
            window_manager._lcw_selected_layout_idx = 0 if layouts else -1

        prev_idx = window_manager._lcw_selected_layout_idx
        window_manager._lcw_selected_layout_idx = PyImGui.combo("Layout", window_manager._lcw_selected_layout_idx, layout_names)

        if window_manager._lcw_selected_layout_idx != prev_idx:
            window_manager._lcw_selected_client_idx = -1

        PyImGui.separator()
        PyImGui.text("Clients")
        
        if 0 <= window_manager._lcw_selected_layout_idx < len(layouts):
            layout = layouts[window_manager._lcw_selected_layout_idx]

            online_emails = window_manager.online_emails

            if PyImGui.begin_table("clients_table", 6, PyImGui.TableFlags.Borders | PyImGui.TableFlags.RowBg | PyImGui.TableFlags.Resizable):
                # Header row
                PyImGui.table_next_row()
                PyImGui.table_set_column_index(0); PyImGui.text("Alias")
                PyImGui.table_set_column_index(1); PyImGui.text("Email")
                PyImGui.table_set_column_index(2)
                label = f"{IconsFontAwesome5.ICON_EYE}" if not all(c.show_overlay for c in layout.clients) else f"{IconsFontAwesome5.ICON_EYE_SLASH}"
                tooltip = "Show Overlays (All)" if not all(c.show_overlay for c in layout.clients) else "Hide Overlays (All)"
                if PyImGui.button(f"{label}##all"):
                    for c in layout.clients:
                        c.show_overlay = not c.show_overlay
                    window_manager.save_layouts()
                PyImGui.show_tooltip(tooltip)
                PyImGui.table_set_column_index(3)
                if PyImGui.button(f"Apply All##apply_All"):
                    for c in layout.clients:
                        if c.email in online_emails:
                            if c.rename_window:
                                _send_message_to(SharedCommandType.SetWindowTitle, c.email, ExtraData=(c.window_title, "", "", ""))
                            _send_message_to(SharedCommandType.SetWindowGeometry, c.email, params=(int(c.x), int(c.y), int(c.width), int(c.height)))
                            _send_message_to(SharedCommandType.SetBorderless, c.email, params=(float(c.borderless), 0.0, 0.0, 0.0))
                            _send_message_to(SharedCommandType.SetAlwaysOnTop, c.email, params=(float(c.always_on_top), 0.0, 0.0, 0.0))
                            _send_message_to(SharedCommandType.SetOpacity, c.email, params=(float(c.opacity), 0.0, 0.0, 0.0))
                PyImGui.show_tooltip("Apply Settings (All)")
                PyImGui.table_set_column_index(4); PyImGui.text(f"Edit")
                PyImGui.table_set_column_index(5); PyImGui.text("Client State")

                # Client rows
                for i, c in enumerate(layout.clients):
                    PyImGui.table_next_row()

                    # Col 0: Alias
                    PyImGui.table_set_column_index(0)
                    PyImGui.text(f"{c.alias}")
                    
                    # Col 1: Email
                    PyImGui.table_set_column_index(1)
                    PyImGui.text(f"{c.email}")

                    # Col 2: Preview toggle (button caption = state)
                    PyImGui.table_set_column_index(2)
                    
                    label = f"{IconsFontAwesome5.ICON_EYE}" if not c.show_overlay else f"{IconsFontAwesome5.ICON_EYE_SLASH}"
                    tooltip = "Show Overlay" if not c.show_overlay else "Hide Overlay"
                    if PyImGui.button(f"{label}##{i}show_overlay"):
                        c.show_overlay = not c.show_overlay
                        window_manager.save_layouts()
                    PyImGui.show_tooltip(tooltip)

                    # Col 3: Apply button
                    PyImGui.table_set_column_index(3)
                    if c.email in online_emails:
                        if PyImGui.button(f"{IconsFontAwesome5.ICON_DESKTOP}##{i}apply"):
                            if c.email in online_emails:
                                if c.rename_window:
                                    _send_message_to(SharedCommandType.SetWindowTitle, c.email, ExtraData=(c.window_title, "", "", ""))
                                _send_message_to(SharedCommandType.SetWindowGeometry, c.email, params=(int(c.x), int(c.y), int(c.width), int(c.height)))
                                _send_message_to(SharedCommandType.SetBorderless, c.email, params=(float(c.borderless), 0.0, 0.0, 0.0))
                                _send_message_to(SharedCommandType.SetAlwaysOnTop, c.email, params=(float(c.always_on_top), 0.0, 0.0, 0.0))
                                _send_message_to(SharedCommandType.SetOpacity, c.email, params=(float(c.opacity), 0.0, 0.0, 0.0))
                        PyImGui.show_tooltip("Apply Settings")
                    else:
                        PyImGui.text_disabled(f"{IconsFontAwesome5.ICON_DESKTOP}")
                    # Col 4: Edit
                    PyImGui.table_set_column_index(4)
                    if PyImGui.button(f"{IconsFontAwesome5.ICON_COG}##{i}"):
                        window_manager.open_client_editor(window_manager._lcw_selected_layout_idx, i)

                    # Col 5: Client state
                    PyImGui.table_set_column_index(5)
                    PyImGui.text_colored("Online" if c.email in online_emails else "Offline", Utils.TrueFalseColor(c.email in online_emails))

                PyImGui.end_table()



            # Add client section
            PyImGui.separator()
            PyImGui.text("Add Client to Layout:")

            existing_emails = {c.email for c in layout.clients}
            available_accounts = [acc for acc in window_manager.all_accounts if acc.email not in existing_emails]

            if available_accounts:
                account_labels = [f"{acc.alias} ({acc.email})" for acc in available_accounts]
                window_manager._lcw_account_picker_idx = PyImGui.combo("Available Accounts", window_manager._lcw_account_picker_idx, account_labels)
                if PyImGui.button("Add Selected Client"):
                    sel = available_accounts[window_manager._lcw_account_picker_idx]
                    layout.add_client(sel)
                    window_manager.save_layouts()
            else:
                PyImGui.text("<no more accounts available>")

    PyImGui.end()


def tooltip():
    PyImGui.begin_tooltip()

    # Title
    title_color = Color(255, 200, 100, 255)
    ImGui.push_font("Regular", 20)
    PyImGui.text_colored("Layout Manager", title_color.to_tuple_normalized())
    ImGui.pop_font()
    PyImGui.spacing()
    PyImGui.separator()

    # Description
    #ellaborate a better description 
    PyImGui.text("This widget allows you to manage and apply window layouts to multiple Guild Wars clients.")
    PyImGui.spacing()

    # Features
    PyImGui.text_colored("Features:", title_color.to_tuple_normalized())
    PyImGui.bullet_text("Create, edit, and delete window layouts.")
    PyImGui.bullet_text("Assign clients to layouts with specific window positions and sizes.")
    PyImGui.bullet_text("Apply layouts to clients instantly via Shared Memory messaging.")

    PyImGui.spacing()
    PyImGui.separator()
    PyImGui.spacing()

    # Credits
    PyImGui.text_colored("Credits:", title_color.to_tuple_normalized())
    PyImGui.bullet_text("Developed by Apo")
    PyImGui.bullet_text("Contributors: fruitchewy")

    PyImGui.end_tooltip()


def main():
    global layout_manager_window_open, draw_screen_rect, _last_account_refresh_ms, _overlay_signature

    now_ms = int(PySystem.get_tick_count64())
    if now_ms - _last_account_refresh_ms >= 1000:
        window_manager.refresh_accounts_from_shmem()
        window_manager.refresh_template_names()
        _last_account_refresh_ms = now_ms

    DrawMainWindow()
    if layout_manager_window_open:
        window_manager.draw_window()
    
    window_manager.draw_client_editors()

    overlay_signature = window_manager.overlay_signature()
    if overlay_signature != _overlay_signature:
        _overlay_signature = overlay_signature
        has_overlay = bool(overlay_signature[2])
        if has_overlay:
            screen_overlay.show(True)
            screen_overlay.begin()
            white = ColorPalette.GetColor("white").to_argb()
            for layout in window_manager.layouts:
                for client in layout.clients:
                    if not getattr(client, "show_overlay", False):
                        continue
                    argb = client.color.to_argb()
                    faded_argb = client.color.copy()
                    faded_argb.set_a(100)
                    screen_overlay.draw_rect_filled(
                        int(client.x), int(client.y), int(client.width), int(client.height), faded_argb.to_argb()
                    )
                    screen_overlay.draw_rect(
                        int(client.x), int(client.y), int(client.width), int(client.height), argb, 2.0
                    )
                    screen_overlay.draw_text_box(
                        int(client.x),
                        int(client.y),
                        int(client.width),
                        int(client.height),
                        client.alias,
                        white,
                        px_size=48.0,
                        hcenter=True,
                        vcenter=True,
                    )
            screen_overlay.end()
        else:
            screen_overlay.show(False)

if __name__ == "__main__":
    main()
