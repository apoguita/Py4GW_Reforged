import PyImGui


class _TextMethods:
    def text(self, text: str):
        PyImGui.text(text)
    def text_unformatted(self, text: str):
        PyImGui.text_unformatted(text)
    def text_link(self, label: str) -> bool:
        return PyImGui.text_link(label)
    def text_link_open_url(self, label: str, url: str | None = None) -> bool:
        return PyImGui.text_link_open_url(label, url)
    def text_colored(self, color, text: str):
        PyImGui.text_colored(color, text)
    def text_disabled(self, text: str):
        PyImGui.text_disabled(text)
    def text_wrapped(self, text: str):
        PyImGui.text_wrapped(text)
    def bullet_text(self, text: str):
        PyImGui.bullet_text(text)
    def label_text(self, label: str, text: str):
        PyImGui.label_text(label, text)
