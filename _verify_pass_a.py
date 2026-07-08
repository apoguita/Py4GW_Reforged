"""Pass A verification script — test import chain of the refactored ImGui facade."""
import sys, traceback

def test(label, fn):
    try:
        fn()
        print(f'  ✅ {label}')
    except Exception as e:
        print(f'  ❌ {label}: {e}')
        traceback.print_exc()

print('=== Pass A verification ===')
print()

# 1. Can we import the rewritten _scopes?
test('import _scopes', lambda: __import__('Py4GWCoreLib.ImGui_src._scopes'))

# 2. Can we import _runtime (which imports from _scopes)?
test('import _runtime', lambda: __import__('Py4GWCoreLib.ImGui_src._runtime'))

# 3. Can we import _core shim?
test('import _core shim', lambda: __import__('Py4GWCoreLib.ImGui_src._core'))

# 4. Can we import __init__ (which creates ui singleton)?
test('import ImGui_src __init__', lambda: __import__('Py4GWCoreLib.ImGui_src'))

# 5. Can we import ImGui facade (still imports everything)?
test('import ImGui facade', lambda: __import__('Py4GWCoreLib.ImGui'))

# 6. Can we instantiate ImGuiRuntime?
from Py4GWCoreLib.ImGui_src._runtime import ImGuiRuntime
test('instantiate ImGuiRuntime', lambda: ImGuiRuntime())

# 7. Check scope class hierarchy
from Py4GWCoreLib.ImGui_src._scopes import (
    _BaseScope, _AlwaysEndScope, _ConditionalEndScope,
    _WindowScope, _MenuScope, _GroupScope, _StyleColorScope,
    _TreeNodeScope, _TableScope, ScopeResult, CloseableScopeResult,
)
rt = ImGuiRuntime()
test('_WindowScope is _AlwaysEndScope', lambda: issubclass(_WindowScope, _AlwaysEndScope))
test('_MenuScope is _ConditionalEndScope', lambda: issubclass(_MenuScope, _ConditionalEndScope))
test('_GroupScope is _AlwaysEndScope', lambda: issubclass(_GroupScope, _AlwaysEndScope))
test('_TreeNodeScope is _ConditionalEndScope', lambda: issubclass(_TreeNodeScope, _ConditionalEndScope))

# 8. Check scope factories on runtime instance
test('rt.window(...) returns _WindowScope', lambda: isinstance(rt.window('test'), _WindowScope))
test('rt.menu(...) returns _MenuScope', lambda: isinstance(rt.menu('test'), _MenuScope))
test('rt.table(...) returns _TableScope', lambda: isinstance(rt.table('test', 3), _TableScope))
test('rt.style_color(...) returns _StyleColorScope', lambda: isinstance(rt.style_color(0, (1,0,0,1)), _StyleColorScope))

# 9. Check sub-surfaces exist
test('rt.style is _StyleSurface', lambda: hasattr(rt.style, 'color') and hasattr(rt.style, 'var'))
test('rt.input is _InputSurface', lambda: hasattr(rt.input, 'text') and hasattr(rt.input, 'int'))
test('rt.state is _StateSurface', lambda: hasattr(rt.state, 'bool') and hasattr(rt.state, 'text'))

# 10. Check tracking infrastructure exists
test('_stack_tracker exists', lambda: hasattr(rt, '_stack_tracker'))
test('_state_store exists', lambda: hasattr(rt, '_state_store'))

# 11. Check ImGui facade class still works
from Py4GWCoreLib.ImGui import ImGui
test('ImGui.default is ImGuiRuntime', lambda: isinstance(ImGui.default, ImGuiRuntime))
test('ImGui.create() returns ImGuiRuntime', lambda: isinstance(ImGui.create(), ImGuiRuntime))

print()
print('=== Verification complete ===')
