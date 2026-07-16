"""Unit tests for pywebview_shell/snap.py's pure geometry (RELAY 012).

No committed test file existed for this before now -- RELAY 012's own text
says "re-run the existing geometry unit tests," but `AERO_SNAP_INVESTIGATION.md`
("unit-tested, all zones correct") describes ad-hoc verification during
development, never checked into the repo as a real test file. Writing one
here properly rather than re-doing throwaway checks that vanish afterward.

Run: .venv\\Scripts\\python.exe -m pytest pywebview_shell/test_snap.py -v
(or plain `python -m unittest` -- no pytest dependency assumed; this uses
stdlib unittest so it runs either way).
"""
from __future__ import annotations

import unittest

from pywebview_shell.snap import Zone, classify_zone, zone_rect


class TestClassifyZone(unittest.TestCase):
    MON = (0, 0, 1920, 1080)  # left, top, right, bottom

    def test_left_edge(self):
        self.assertEqual(classify_zone(2, 540, *self.MON), Zone.LEFT)

    def test_right_edge(self):
        self.assertEqual(classify_zone(1918, 540, *self.MON), Zone.RIGHT)

    def test_top_edge_is_max(self):
        self.assertEqual(classify_zone(960, 1, *self.MON), Zone.MAX)

    def test_bottom_edge_middle_does_nothing(self):
        # Matches Windows -- dragging to the bottom-middle doesn't snap.
        self.assertIsNone(classify_zone(960, 1078, *self.MON))

    def test_top_left_corner(self):
        self.assertEqual(classify_zone(2, 2, *self.MON), Zone.TOP_LEFT)

    def test_top_right_corner(self):
        self.assertEqual(classify_zone(1918, 2, *self.MON), Zone.TOP_RIGHT)

    def test_bottom_left_corner(self):
        self.assertEqual(classify_zone(2, 1078, *self.MON), Zone.BOTTOM_LEFT)

    def test_bottom_right_corner(self):
        self.assertEqual(classify_zone(1918, 1078, *self.MON), Zone.BOTTOM_RIGHT)

    def test_center_is_none(self):
        self.assertIsNone(classify_zone(960, 540, *self.MON))


class TestZoneRectNoMinimum(unittest.TestCase):
    """Baseline: min_w/min_h default to 0 (no minimum), matching pre-RELAY-012
    behavior exactly -- these must keep passing unchanged."""

    WORK = (0, 0, 1920, 1080)

    def test_left_half(self):
        self.assertEqual(zone_rect(Zone.LEFT, *self.WORK), (0, 0, 960, 1080))

    def test_right_half(self):
        self.assertEqual(zone_rect(Zone.RIGHT, *self.WORK), (960, 0, 960, 1080))

    def test_max(self):
        self.assertEqual(zone_rect(Zone.MAX, *self.WORK), (0, 0, 1920, 1080))

    def test_all_four_quarters(self):
        self.assertEqual(zone_rect(Zone.TOP_LEFT, *self.WORK), (0, 0, 960, 540))
        self.assertEqual(zone_rect(Zone.TOP_RIGHT, *self.WORK), (960, 0, 960, 540))
        self.assertEqual(zone_rect(Zone.BOTTOM_LEFT, *self.WORK), (0, 540, 960, 540))
        self.assertEqual(zone_rect(Zone.BOTTOM_RIGHT, *self.WORK), (960, 540, 960, 540))

    def test_odd_width_height_split_is_exact(self):
        # 1921x1081 -- integer division must not lose a pixel anywhere.
        work = (0, 0, 1921, 1081)
        left = zone_rect(Zone.LEFT, *work)
        right = zone_rect(Zone.RIGHT, *work)
        self.assertEqual(left[2] + right[2], 1921)
        top_left = zone_rect(Zone.TOP_LEFT, *work)
        bottom_left = zone_rect(Zone.BOTTOM_LEFT, *work)
        self.assertEqual(top_left[3] + bottom_left[3], 1081)


class TestZoneRectClampAndShift(unittest.TestCase):
    """The RELAY 012 fix itself -- reproduces the exact real bug from
    AERO_SNAP_INVESTIGATION.md's "OPEN BUG" section: Chris's laptop, 250%
    scale, 2880x1800 physical work area, min_size=(560, 400) LOGICAL ==
    (1400, 1000) PHYSICAL at that scale. Unclamped quarters would be
    1440x900 -- shorter than the 1000px minimum height.
    """

    WORK = (0, 0, 2880, 1800)
    MIN_W = 1400
    MIN_H = 1000

    def test_bottom_left_quarter_no_longer_overshoots(self):
        x, y, w, h = zone_rect(Zone.BOTTOM_LEFT, *self.WORK, min_w=self.MIN_W, min_h=self.MIN_H)
        self.assertEqual((x, y, w, h), (0, 800, 1440, 1000))
        self.assertEqual(y + h, 1800)  # bottom edge exactly on the work area boundary, not past it

    def test_bottom_right_quarter_no_longer_overshoots(self):
        x, y, w, h = zone_rect(Zone.BOTTOM_RIGHT, *self.WORK, min_w=self.MIN_W, min_h=self.MIN_H)
        self.assertEqual((x, y, w, h), (1440, 800, 1440, 1000))
        self.assertEqual(y + h, 1800)

    def test_top_left_quarter_grows_downward_no_shift_needed(self):
        # Same clamp applied uniformly (RELAY 012's own instruction -- not
        # bottom-specific), even though this zone's un-clamped symptom was
        # invisible (it just spilled past the midline, never past the work
        # area, so nobody noticed it before).
        x, y, w, h = zone_rect(Zone.TOP_LEFT, *self.WORK, min_w=self.MIN_W, min_h=self.MIN_H)
        self.assertEqual((x, y, w, h), (0, 0, 1440, 1000))
        self.assertLessEqual(y + h, 1800)

    def test_top_right_quarter_grows_downward_no_shift_needed(self):
        x, y, w, h = zone_rect(Zone.TOP_RIGHT, *self.WORK, min_w=self.MIN_W, min_h=self.MIN_H)
        self.assertEqual((x, y, w, h), (1440, 0, 1440, 1000))
        self.assertLessEqual(y + h, 1800)

    def test_halves_and_max_unaffected_by_the_same_minimum(self):
        # Halves/max are already far taller/wider than this minimum -- must
        # be complete no-ops, proving the fix doesn't touch zones that were
        # never broken.
        self.assertEqual(
            zone_rect(Zone.LEFT, *self.WORK, min_w=self.MIN_W, min_h=self.MIN_H),
            (0, 0, 1440, 1800),
        )
        self.assertEqual(
            zone_rect(Zone.MAX, *self.WORK, min_w=self.MIN_W, min_h=self.MIN_H),
            (0, 0, 2880, 1800),
        )

    def test_width_clamp_shifts_right_anchored_quarter_left(self):
        # A narrower work area to force WIDTH clamping too (not just height)
        # -- proves the fix is genuinely symmetric, not a height-only patch.
        # 2000x1800 work area: half_w=1000, right_w=1000 -- below a 1200 min.
        work = (0, 0, 2000, 1800)
        min_w, min_h = 1200, 0
        x, y, w, h = zone_rect(Zone.TOP_RIGHT, *work, min_w=min_w, min_h=min_h)
        self.assertEqual((x, y, w, h), (800, 0, 1200, 900))
        self.assertEqual(x + w, 2000)  # right edge exactly on the boundary, not past it

    def test_width_clamp_left_anchored_quarter_grows_rightward_no_shift(self):
        work = (0, 0, 2000, 1800)
        min_w, min_h = 1200, 0
        x, y, w, h = zone_rect(Zone.TOP_LEFT, *work, min_w=min_w, min_h=min_h)
        self.assertEqual((x, y, w, h), (0, 0, 1200, 900))
        self.assertLessEqual(x + w, 2000)

    def test_no_clamp_when_minimum_already_satisfied(self):
        # A generous work area (e.g. a 4K monitor) where quarters already
        # exceed a normal minimum -- must be a pure no-op, same result as
        # TestZoneRectNoMinimum's equivalent case.
        work = (0, 0, 3840, 2160)
        x, y, w, h = zone_rect(Zone.BOTTOM_RIGHT, *work, min_w=1400, min_h=1000)
        self.assertEqual((x, y, w, h), (1920, 1080, 1920, 1080))


if __name__ == "__main__":
    unittest.main()
