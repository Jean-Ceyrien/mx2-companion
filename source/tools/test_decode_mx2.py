import struct
import unittest
from decode_mx2 import Decoder, jog_delta


def frame(rid, payload, device='a', **extra):
    data = bytes([rid]) + bytes(payload)
    return dict(event='hid_input', id=device, report_id=rid, bytes_hex=data.hex(), byte_count=len(data), status=0, **extra)


class DecoderTests(unittest.TestCase):
    def test_buttons_unknowns_and_encoder_wrap(self):
        d = Decoder()
        baseline = bytearray(14)
        baseline[11] = 15
        self.assertEqual(d.decode(frame(1, baseline)), [])
        baseline[0] = 1
        baseline[10] |= 4  # native button82 deliberately unnamed
        baseline[11] = 0
        events = d.decode(frame(1, baseline))
        self.assertEqual([(e['kind'], e['index']) for e in events], [('button', 0), ('button', 82), ('encoder', 0)])
        self.assertEqual(events[0]['control'], 'left.fx.buttons.1')
        self.assertEqual(events[1]['mapping_evidence'], 'unknown')
        self.assertEqual(events[2]['delta'], 1)
        self.assertEqual(d.decode(frame(1, baseline)), [])

    def test_analog_raw_and_verified_pitch(self):
        d = Decoder()
        d.decode(frame(2, struct.pack('<26H', *([0] * 26))))
        values = [0] * 26
        values[24], values[25] = 4095, 2048
        events = d.decode(frame(2, struct.pack('<26H', *values)))
        self.assertEqual(events[0]['control'], 'left.pitch.fader')
        self.assertEqual(events[0]['delta_raw'], 4095)
        self.assertEqual(events[1]['control'], 'right.pitch.fader')
        self.assertNotIn('normalized', events[0])

    def test_jog_wrap_and_metadata_preserved(self):
        self.assertEqual(jog_delta(2, 958), 4)
        self.assertEqual(jog_delta(958, 2), -4)
        self.assertEqual(jog_delta(0, 0xffffffff), 1)
        self.assertEqual(jog_delta(0xffffffff, 0), -1)
        d = Decoder()
        d.decode(frame(3, b'\x00' * 3 + struct.pack('<IIII', 123, 958, 10, 0xffffffff)))
        events = d.decode(frame(3, b'\x00' * 3 + struct.pack('<IIII', 456, 2, 20, 0), monotonic_ns=99))
        self.assertEqual([e['delta'] for e in events], [4, 1])
        self.assertEqual(events[0]['raw_metadata_u32'], 456)
        self.assertEqual(events[0]['monotonic_ns'], 99)
        self.assertNotIn('speed', events[0])

    def test_frames_validate_and_devices_isolated(self):
        d = Decoder()
        self.assertEqual(d.decode(frame(1, [0] * 13))[0]['event'], 'decode_error')
        bad = frame(1, [0] * 14)
        bad['bytes_hex'] = '02' + bad['bytes_hex'][2:]
        self.assertEqual(d.decode(bad)[0]['event'], 'decode_error')
        self.assertEqual(d.decode(frame(1, [0] * 14)), [])
        self.assertEqual(d.decode(frame(1, [1] + [0] * 13, device='b')), [])
        d.decode({'event': 'session'})
        self.assertEqual(d.decode(frame(1, [1] + [0] * 13)), [])


if __name__ == '__main__':
    unittest.main()
