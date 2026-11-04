"""Exercise the compatibility module with native input and keyboard boundaries doubled."""
import importlib.util,sys,unittest
from typing import Any
from pathlib import Path
from types import ModuleType,SimpleNamespace as NS
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
class TextInputTests(unittest.TestCase):
 def setUp(self):
  self.keys=set();self.now=0.;self.active=True;self.value=None
  gui: Any=ModuleType('PyImGui')
  def input_text(label,text,*args,**kwargs):return text if self.value is None else self.value
  gui.input_text=input_text;gui.input_text_multiline=input_text
  gui.input_text_with_hint=lambda label,hint,text,*a,**k:input_text(label,text)
  gui.get_item_id=lambda:1;gui.is_item_active=lambda:self.active;gui.is_item_focused=lambda:False
  gui.is_item_hovered=lambda:False;gui.is_mouse_clicked=lambda _:False;gui.get_io=lambda:NS(want_text_input=self.active)
  spec=importlib.util.spec_from_file_location('input_compat_test',ROOT/'Py4GWCoreLib/pyimgui_input_compat.py')
  assert spec is not None and spec.loader is not None
  self.m: Any=importlib.util.module_from_spec(spec)
  with patch.dict(sys.modules,{'PyImGui':gui}):spec.loader.exec_module(self.m)
  self.m._down=lambda vk:vk in self.keys;self.m.time=NS(monotonic=lambda:self.now)
  self.gui=gui;self.m.install()
 def test_backspace_fallback_and_native_no_double_delete(self):
  self.keys={8};self.assertEqual(self.gui.input_text('field','abc'),'ab')
  self.keys.clear();self.gui.input_text('field','abc');self.keys={8};self.value='ab'
  self.assertEqual(self.gui.input_text('field','abc'),'ab')
 def test_ctrl_a_replaces_whole_value_or_backspace_clears_it(self):
  self.keys={17,65};self.assertEqual(self.gui.input_text('field','abc'),'abc')
  self.keys.clear();self.value='abcZ';self.assertEqual(self.gui.input_text('field','abc'),'Z')
  self.keys={17,65};self.value=None;self.gui.input_text('field','abc')
  self.keys={8};self.assertEqual(self.gui.input_text('field','abc'),'')
 def test_inactive_field_is_unchanged(self):
  self.active=False;self.keys={8};self.assertEqual(self.gui.input_text('field','abc'),'abc')
 def test_repeat_waits_for_delay_and_releases(self):
  self.keys={8};self.assertEqual(self.gui.input_text('field','abc'),'ab')
  self.now=.1;self.assertEqual(self.gui.input_text('field','ab'),'ab')
  self.now=.4;self.assertEqual(self.gui.input_text('field','ab'),'a')
  self.keys.clear();self.gui.input_text('field','a');self.keys={8};self.assertEqual(self.gui.input_text('field','a'),'')
 def test_install_is_idempotent_and_force_keeps_one_wrapper(self):
  first=self.gui.input_text;native=first._py4gw_original
  self.m.install();self.assertIs(self.gui.input_text,first)
  self.m.install(force=True);self.assertIs(self.gui.input_text._py4gw_original,native)
 def test_hint_and_multiline_use_correct_text_argument(self):
  self.keys={8};self.assertEqual(self.gui.input_text_with_hint('field','hint','abc'),'ab')
  self.keys.clear();self.gui.input_text_multiline('field','abc');self.keys={8}
  self.assertEqual(self.gui.input_text_multiline('field','abc'),'ab')
if __name__=='__main__':unittest.main()
