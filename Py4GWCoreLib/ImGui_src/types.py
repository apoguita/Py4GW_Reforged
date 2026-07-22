import PyImGui
from enum import IntEnum, Enum

TEXTURE_FOLDER = "Textures\\Game UI\\"
MINIMALUS_FOLDER = "Textures\\Themes\\Minimalus\\"


class ControlAppearance(Enum):
    Default = 0
    Primary = 1
    Danger = 2

class StyleTheme(IntEnum):
    Py4GW = 0
    # Backward-compat alias: settings saved before the rename stored the name
    # "ImGui". StyleTheme["ImGui"] still resolves; .name reads back as "Py4GW",
    # so load_theme() looks for Styles/Py4GW.default.json.
    ImGui = 0
    Guild_Wars = 1
    Minimalus = 2
    Smoke = 3
    Contrast = 4
    Negative = 5
    
class VerticalAlignment(IntEnum):
    '''
    Vertical Alignment Options
    '''
    Above = 0
    Top = 1
    Middle = 2
    Bottom = 3
    Below = 4


class HorizontalAlignment(IntEnum):
    '''
    Horizontal Alignment Options
    '''
    LeftOf = 0
    Left = 1
    Center = 2
    Right = 3
    RightOf = 4


_H_SHIFT = 0
_V_SHIFT = 3

_H_MASK = 0b111 << _H_SHIFT
_V_MASK = 0b111 << _V_SHIFT

class Alignment(IntEnum):
    '''
    All Combinations of VerticalAlignment and HorizontalAlignment
    as bit-packed enum values.
    Allows easy extraction of vertical and horizontal components.
    
    Properties:
        vertical: VerticalAlignment
        horizontal: HorizontalAlignment
    
    Example:
        alignment = Alignment.TopRight
        alignment.vertical      --> VerticalAlignment.Top
        alignment.horizontal    --> HorizontalAlignment.Right
    '''
    
    # bit layout:
    # bits 0â€“2 : horizontal (0â€“4)
    # bits 3â€“5 : vertical   (0â€“4)

    AboveLeftOf    = (VerticalAlignment.Above  << _V_SHIFT) | HorizontalAlignment.LeftOf
    AboveLeft      = (VerticalAlignment.Above  << _V_SHIFT) | HorizontalAlignment.Left
    AboveCenter    = (VerticalAlignment.Above  << _V_SHIFT) | HorizontalAlignment.Center
    AboveRight     = (VerticalAlignment.Above  << _V_SHIFT) | HorizontalAlignment.Right
    AboveRightOf   = (VerticalAlignment.Above  << _V_SHIFT) | HorizontalAlignment.RightOf

    TopLeftOf      = (VerticalAlignment.Top    << _V_SHIFT) | HorizontalAlignment.LeftOf
    TopLeft        = (VerticalAlignment.Top    << _V_SHIFT) | HorizontalAlignment.Left
    TopCenter      = (VerticalAlignment.Top    << _V_SHIFT) | HorizontalAlignment.Center
    TopRight       = (VerticalAlignment.Top    << _V_SHIFT) | HorizontalAlignment.Right
    TopRightOf     = (VerticalAlignment.Top    << _V_SHIFT) | HorizontalAlignment.RightOf

    MidLeftOf      = (VerticalAlignment.Middle << _V_SHIFT) | HorizontalAlignment.LeftOf
    MidLeft        = (VerticalAlignment.Middle << _V_SHIFT) | HorizontalAlignment.Left
    MidCenter      = (VerticalAlignment.Middle << _V_SHIFT) | HorizontalAlignment.Center
    MidRight       = (VerticalAlignment.Middle << _V_SHIFT) | HorizontalAlignment.Right
    MidRightOf     = (VerticalAlignment.Middle << _V_SHIFT) | HorizontalAlignment.RightOf

    BottomLeftOf   = (VerticalAlignment.Bottom << _V_SHIFT) | HorizontalAlignment.LeftOf
    BottomLeft     = (VerticalAlignment.Bottom << _V_SHIFT) | HorizontalAlignment.Left
    BottomCenter   = (VerticalAlignment.Bottom << _V_SHIFT) | HorizontalAlignment.Center
    BottomRight    = (VerticalAlignment.Bottom << _V_SHIFT) | HorizontalAlignment.Right
    BottomRightOf  = (VerticalAlignment.Bottom << _V_SHIFT) | HorizontalAlignment.RightOf

    BelowLeftOf    = (VerticalAlignment.Below  << _V_SHIFT) | HorizontalAlignment.LeftOf
    BelowLeft      = (VerticalAlignment.Below  << _V_SHIFT) | HorizontalAlignment.Left
    BelowCenter    = (VerticalAlignment.Below  << _V_SHIFT) | HorizontalAlignment.Center
    BelowRight     = (VerticalAlignment.Below  << _V_SHIFT) | HorizontalAlignment.Right
    BelowRightOf   = (VerticalAlignment.Below  << _V_SHIFT) | HorizontalAlignment.RightOf

    @property
    def vertical(self) -> VerticalAlignment:
        return VerticalAlignment((self.value & _V_MASK) >> _V_SHIFT)

    @property
    def horizontal(self) -> HorizontalAlignment:
        return HorizontalAlignment((self.value & _H_MASK) >> _H_SHIFT)

    @classmethod
    def from_parts(
        cls,
        vertical: VerticalAlignment,
        horizontal: HorizontalAlignment,
    ) -> "Alignment":
        return cls((vertical << _V_SHIFT) | horizontal)
    
class TextDecorator(IntEnum):
    None_ = 0
    Underline = 1
    Strikethrough = 2
    Highlight = 3
    
class StyleColorType(IntEnum):
    Default = 0
    Custom = 1
    Texture = 2

class SortDirection(Enum):
    No_Sort = 0
    Ascending = 1
    Descending = 2    

def _style_var(name: str) -> int:
    """Resolve a style var index from the live PyImGui binding.

    These indices are positional in ImGui's ImGuiStyleVar_ enum and shift
    whenever ImGui inserts a new var. Hardcoding them here silently pushed the
    wrong field (and, where the types disagreed, pushed nothing while still
    popping), so the values are always taken from the DLL.
    """
    return int(getattr(PyImGui.ImGuiStyleVar, name))

class ImGuiStyleVar(IntEnum):
    Alpha = _style_var('Alpha')
    DisabledAlpha = _style_var('DisabledAlpha')
    WindowPadding = _style_var('WindowPadding')
    WindowRounding = _style_var('WindowRounding')
    WindowBorderSize = _style_var('WindowBorderSize')
    WindowMinSize = _style_var('WindowMinSize')
    WindowTitleAlign = _style_var('WindowTitleAlign')
    ChildRounding = _style_var('ChildRounding')
    ChildBorderSize = _style_var('ChildBorderSize')
    PopupRounding = _style_var('PopupRounding')
    PopupBorderSize = _style_var('PopupBorderSize')
    FramePadding = _style_var('FramePadding')
    FrameRounding = _style_var('FrameRounding')
    FrameBorderSize = _style_var('FrameBorderSize')
    ItemSpacing = _style_var('ItemSpacing')
    ItemInnerSpacing = _style_var('ItemInnerSpacing')
    IndentSpacing = _style_var('IndentSpacing')
    CellPadding = _style_var('CellPadding')
    ScrollbarSize = _style_var('ScrollbarSize')
    ScrollbarRounding = _style_var('ScrollbarRounding')
    GrabMinSize = _style_var('GrabMinSize')
    GrabRounding = _style_var('GrabRounding')
    TabRounding = _style_var('TabRounding')
    ButtonTextAlign = _style_var('ButtonTextAlign')
    SelectableTextAlign = _style_var('SelectableTextAlign')
    SeparatorTextBorderSize = _style_var('SeparatorTextBorderSize')
    SeparatorTextAlign = _style_var('SeparatorTextAlign')
    SeparatorTextPadding = _style_var('SeparatorTextPadding')
