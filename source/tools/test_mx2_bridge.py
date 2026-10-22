import json
from pathlib import Path
import unittest

from mx2_bridge import Router, ROOT


class RoutingTests(unittest.TestCase):
    def setUp(self):
        self.router = Router(json.loads((ROOT / 'evidence/midi-profile.json').read_text()))

    def input(self, ch, n, v=127, family=0x90):
        return self.router.input(family | ch, [n, v])

    @staticmethod
    def virtual(messages):
        return [data for to, data in messages if to == 'virtual']

    def test_two_independent_shifts(self):
        self.input(0, 12)
        self.assertEqual(self.virtual(self.input(0, 29)), [[0x92, 29, 127]])
        self.assertEqual(self.virtual(self.input(1, 29)), [[0x91, 29, 127]])

    def test_release_keeps_press_route_when_shift_changes(self):
        self.input(0, 12)
        self.input(0, 28)
        self.input(0, 12, 0)
        self.assertEqual(self.virtual(self.input(0, 28, 0)), [[0x82, 28, 0]])

    def test_pad_release_survives_bank_and_shift_change(self):
        self.input(1, 18)  # sampler
        self.input(1, 20)
        self.input(1, 16)  # hotcue
        self.input(1, 12)
        self.assertEqual(self.virtual(self.input(1, 20, 0)), [[0x87, 32, 0]])

    def test_repeat_touch_ignored_and_jog_mode_releases_scratch(self):
        self.assertEqual(self.virtual(self.input(0, 33)), [[0x90, 33, 127]])
        self.assertEqual(self.virtual(self.input(0, 33)), [])
        self.assertEqual(self.virtual(self.input(0, 11)), [[0x80, 34, 0], [0x80, 35, 0], [0x80, 33, 0]])
        self.assertEqual(self.virtual(self.input(0, 33)), [])

    def test_relative_kept_absolute_sweep_reaches_zero(self):
        self.assertEqual(self.virtual(self.input(0, 19, 63, 0xb0)), [[0xb0, 19, 63]])
        self.assertEqual(self.virtual(self.input(2, 40, 1, 0xb0)), [[0xb4, 40, 0]])
        self.assertEqual(self.virtual(self.input(2, 40, 127, 0xb0)), [[0xb4, 40, 127]])

    def test_fx_selector_routes_both_decks_and_holds_release(self):
        self.input(4, 1)  # FX2
        self.assertEqual(self.virtual(self.input(2, 36, 127, 0xb0)), [[0xb4, 38, 127]])
        self.assertEqual(self.virtual(self.input(3, 2)), [[0x95, 42, 127]])
        self.input(4, 4)
        self.assertEqual(self.virtual(self.input(3, 2, 0)), [[0x85, 42, 0]])

    def test_feedback_hidden_bank_cached_and_restored(self):
        self.router.refresh_modes()
        self.assertEqual(self.router.feedback(0x96, [16, 127]), [])
        result = self.input(0, 17)
        self.assertIn(('hardware', [0x90, 20, 127]), result)
        result = self.input(0, 16)
        self.assertIn(('hardware', [0x90, 20, 0]), result)

    def test_shift_feedback_cannot_overwrite_normal_play_led(self):
        self.assertEqual(self.router.feedback(0x92, [29, 127]), [])
        self.assertEqual(self.router.feedback(0x90, [29, 127]), [('hardware', [0x90, 29, 127])])

    def test_panic_releases_all_notes(self):
        self.input(0, 28)
        self.input(1, 33)
        self.assertEqual(sorted(self.virtual(self.router.panic())), [[0x80, 28, 0], [0x81, 33, 0]])
        self.assertFalse(self.router.held)

    def test_every_measured_control_recognized_no_invalid_output(self):
        for c in self.router.profile.values():
            for val in (c['max'], c['min']):
                result = self.router.input(c['family'] | c['channel'], [c['number'], val])
                for to, data in result:
                    self.assertIn(to, ('virtual', 'hardware'))
                    self.assertEqual(len(data), 3)
                    self.assertIn(data[0] & 240, (0x80, 0x90, 0xb0))
                    self.assertTrue(all(0 <= x < 128 for x in data[1:]))
        self.assertEqual(self.router.unknown_count, 0)


if __name__ == '__main__':
    unittest.main()
