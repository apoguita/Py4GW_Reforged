"""In-client smoke test for the direct ImGui_Legacy-Addons file browser binding."""

import PyImGui

MODULE_NAME = 'ImGui_Legacy FileBrowser Test'

_browser = None
_last_selected = ''


def _get_browser():
    global _browser

    if _browser is None:
        fb = PyImGui.filebrowser
        _browser = fb.FileBrowser()
        _browser.set_use_modal(False)
        _browser.set_current_path('C:\\')
    return _browser


def main() -> None:
    global _last_selected

    browser = _get_browser()

    PyImGui.set_next_window_size((520.0, 220.0), PyImGui.ImGuiCond.FirstUseEver)
    if not PyImGui.begin(MODULE_NAME, PyImGui.WindowFlags.NoCollapse):
        PyImGui.end()
        browser.display()
        return

    PyImGui.text('Open the file dialog and select a file to verify the direct addon binding.')
    PyImGui.separator()

    if PyImGui.button('Open File Browser'):
        PyImGui.open_popup('Select Python Script')

    if browser.show_file_dialog(
        'Select Python Script',
        PyImGui.filebrowser.DialogMode.OPEN,
        (700.0, 450.0),
        '.py,.pyw',
    ):
        _last_selected = browser.selected_path

    PyImGui.separator()
    PyImGui.text('Last selected path:')
    if _last_selected:
        PyImGui.text_wrapped(_last_selected)
    else:
        PyImGui.text_disabled('(nothing selected yet)')

    PyImGui.end()
