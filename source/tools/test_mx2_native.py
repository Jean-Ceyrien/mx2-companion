import json
import struct
import unittest
from pathlib import Path
from mx2_native import NativeInput, NativeLEDs
from mx2_bridge import Router, ROOT
from test_decode_mx2 import frame


class NativeTests(unittest.TestCase):
    def setUp(self):
        self.profile = json.loads((ROOT / 'evidence/midi-profile.json').read_text())
        self.adapter = NativeInput(self.profile)
        self.router = Router(self.profile)
        self.leds = NativeLEDs(self.profile, json.loads((ROOT / 'evidence/native-protocol-map.json').read_text()))

    def test_baseline_no_actions_then_both_play_and_release(self):
        self.assertEqual(self.adapter.feed(frame(1, [0] * 14)), [])
        data = bytearray(14)
        data[29 // 8] |= 1 << (29 % 8)
        data[59 // 8] |= 1 << (59 % 8)
        self.assertEqual(self.adapter.feed(frame(1, data)), [(0x90, [29, 127]), (0x91, [29, 127])])
        self.assertEqual(self.adapter.feed(frame(1, [0] * 14)), [(0x80, [29, 0]), (0x81, [29, 0])])

    def test_full_analog_sweep_and_quantization(self):
        self.adapter.feed(frame(2, struct.pack('<26H', *([2048] * 26))))
        values = [2048] * 26
        values[21] = 0
        self.assertEqual(self.adapter.feed(frame(2, struct.pack('<26H', *values))), [(0xb2, [40, 1])])
        values[21] = 4095
        self.assertEqual(self.adapter.feed(frame(2, struct.pack('<26H', *values))), [(0xb2, [40, 127])])

    def test_encoder_wrap_and_jog_motion_conserved(self):
        data = bytearray(14); data[11] = 15
        self.adapter.feed(frame(1, data)); data[11] = 0
        self.assertEqual(self.adapter.feed(frame(1, data)), [(0xb0, [16, 65])])
        def jog(left):
            return frame(3, bytes(3) + struct.pack('<IIII', 1, left, 2, 0))
        self.adapter.feed(jog(958))
        self.assertEqual(self.adapter.feed(jog(2)), [(0xb0, [19, 68])])
        moves = self.adapter.feed(jog(202))
        self.assertEqual(sum(d[1] - 64 for _, d in moves), 200)
        self.assertTrue(all(0 < d[1] < 128 for _, d in moves))

    def test_malformed_or_unknown_input_does_not_drive_controls(self):
        self.assertEqual(self.adapter.feed(frame(1, [0] * 13)), [])
        self.adapter.feed(frame(1, [0] * 14))
        data = bytearray(14); data[10] = 4
        self.assertEqual(self.adapter.feed(frame(1, data)), [])

    def test_meters_independent_and_increasing(self):
        self.assertEqual([self.leds.meter_count(x) for x in (0, 1, 64, 127)], [0, 1, 5, 9])
        self.leds.feedback(0xbe, [0, 127])
        self.leds.feedback(0xbe, [1, 0])
        data = self.leds.render(self.router, 0)
        self.assertEqual(data[87:96], [126] * 9)
        self.assertEqual(data[96:105], [0] * 9)
        self.assertEqual(data[86], 0)  # No invented master clip.

    def test_browse_buttons_stay_lit_on_both_decks(self):
        ids = set(range(4, 8)) | set(range(34, 38))
        for value in (0, 127, 0):
            for led_id, channel, number, _ in self.leds.buttons:
                if led_id in ids:
                    self.router.last_led[(channel, number)] = value
            data = self.leds.render(self.router, 0)
            self.assertEqual([data[i] for i in sorted(ids)], [46] * 8)
            self.assertEqual(data[3], 0)
            self.assertEqual(data[33], 0)

    def test_palette_loop_warning_and_payload_bounds(self):
        self.router.refresh_modes()
        self.assertEqual(self.leds.render(self.router, 0)[20], 44)  # Blue dim.
        self.router.pad_mode[0] = 2
        self.assertEqual(self.leds.render(self.router, 0)[20], 12)  # Orange dim.
        self.leds.feedback(0x9e, [2, 127])
        self.assertEqual(self.leds.render(self.router, 0)[74:80], [6] * 6)
        self.assertEqual(self.leds.render(self.router, 0.3)[74:80], [0] * 6)
        self.router.feedback_cache[(0, 32)] = 127
        data = self.leds.render(self.router, 0.3)
        self.assertEqual(data[74:80], [30] * 6)
        self.assertEqual(len(data), 105)
        self.assertTrue(all(0 <= x < 128 for x in data))


if __name__ == '__main__':
    unittest.main()
