"""Hardware-free transport contract tests; these do not certify Windows hardware."""
import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from mx2_portable_transport import Transport, matching_devices, parse_command, resolve_port


class Device:
    def __init__(self):
        self.closed = False
        self.writes = []
        self.reads = []

    def open_path(self, path):
        self.path = path

    def close(self):
        self.closed = True

    def get_input_report(self, number, size):
        return [number] + [0] * (size - 1)

    def write(self, data):
        self.writes.append(data)
        return len(data)

    def read(self, size, timeout_ms):
        assert size == 64 and timeout_ms == 20
        return self.reads.pop(0) if self.reads else []


def fixture():
    row = dict(vendor_id=0x17CC, product_id=0x2420, usage_page=0xFF01, usage=0, path=b'fake-mx2')
    hid = SimpleNamespace(enumerate=Mock(return_value=[row]), device=Mock(side_effect=Device))
    mido = SimpleNamespace(Message=SimpleNamespace(from_bytes=lambda x: tuple(x)))
    events = []
    transport = Transport(hid, mido, lambda event, **data: events.append(dict(event=event, **data)))
    return transport, hid, events, row


class PortableTransportTests(unittest.TestCase):
    def test_strict_command_validation(self):
        for bad in ({}, [], {'to': 'hid-feature', 'bytes': [0]},
                    {'to': 'virtual', 'bytes': [0x90, True, 1]},
                    {'to': 'virtual', 'bytes': [0xF0, 1, 2]},
                    {'to': 'virtual', 'bytes': [0x90, 128, 1]},
                    {'to': 'virtual', 'bytes': [0x90]},
                    {'to': 'hid-leds', 'bytes': [128] * 105}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                parse_command(json.dumps(bad))
        self.assertEqual(parse_command('{"to":"virtual","bytes":[144,2,127,128,2,0]}')[0], 'virtual')
        self.assertEqual(len(parse_command(json.dumps(dict(to='hid-leds', bytes=[0] * 105)))[1]), 105)

    def test_port_resolution_exact_then_unique_numbered(self):
        self.assertEqual(resolve_port('MX2 for djay', ['MX2 for djay', 'MX2 for djay 1']), 'MX2 for djay')
        self.assertEqual(resolve_port('MX2 for djay', ['MX2 for djay 2']), 'MX2 for djay 2')
        for names in ([], ['MX2 for djay 1', 'MX2 for djay 2'], ['Traktor MX2']):
            with self.assertRaises(ValueError):
                resolve_port('MX2 for djay', names)
        with self.assertRaises(ValueError):
            resolve_port('Traktor MX2', ['Traktor MX2'])

    def test_device_filter_is_exact_and_ambiguous_disconnects(self):
        transport, hid, events, row = fixture()
        hid.enumerate.return_value += [dict(row, usage=1), dict(row, usage_page=0xFF00)]
        self.assertEqual(len(matching_devices(hid)), 1)
        transport.refresh_device()
        device = transport.device
        hid.enumerate.return_value = [row, dict(row, path=b'another')]
        transport.refresh_device()
        self.assertTrue(device.closed)
        self.assertIsNone(transport.device)
        self.assertEqual(events[-1]['matching_devices'], 2)

    def test_seeds_and_reconnect_reset_connection(self):
        transport, hid, events, row = fixture()
        transport.refresh_device()
        seeds = [e for e in events if e['event'] == 'hid_input']
        self.assertEqual([(e['report_id'], e['count'], e['seed']) for e in seeds], [(1, 15, True), (2, 53, True)])
        first = transport.device
        hid.enumerate.return_value = []
        transport.refresh_device()
        self.assertTrue(first.closed)
        hid.enumerate.return_value = [row]
        transport.refresh_device()
        self.assertIsNot(first, transport.device)
        self.assertEqual(len([e for e in events if e['event'] == 'hid_connected']), 2)

    def test_led_image_coalesces_and_numbered_write(self):
        transport, hid, events, row = fixture()
        transport.refresh_device()
        transport.accept(json.dumps(dict(to='hid-leds', bytes=[1] * 105)))
        transport.accept(json.dumps(dict(to='hid-leds', bytes=[6] * 105)))
        transport.hardware_step()
        self.assertEqual(transport.device.writes, [bytes([128] + [6] * 105)])
        self.assertEqual(events[-1]['status'], 0)
        transport.hardware_step()
        self.assertEqual(len(transport.device.writes), 1)

    def test_padded_windows_reports_trim_known_ids_only(self):
        transport, hid, events, row = fixture()
        transport.refresh_device()
        transport.input_report([3] + [0] * 52)
        self.assertEqual(events[-1]['count'], 20)
        transport.input_report([2] + [0] * 4)
        self.assertEqual(events[-1]['count'], 5)  # Preserve truncation for decoder validation.
        transport.input_report([7] + [0] * 30)
        self.assertEqual(events[-1]['count'], 31)

    def test_feedback_channels_prevent_same_bus_echo(self):
        transport, hid, events, row = fixture()
        for channel in range(16):
            transport.feedback(SimpleNamespace(bytes=lambda c=channel: [0x90 | c, 1, 127]))
        self.assertEqual([e['bytes'][0] & 15 for e in events], [10, 11, 12, 13, 14])
        transport.feedback(SimpleNamespace(bytes=lambda: [0xFA]))
        self.assertEqual(len(events), 5)

    def test_virtual_send_rejects_feedback_channels(self):
        transport, hid, events, row = fixture()
        transport.output = Mock()
        transport.accept(json.dumps(dict(to='virtual', bytes=[0x90, 29, 127, 0x91, 29, 0])))
        self.assertEqual(transport.output.send.call_count, 2)
        transport.accept(json.dumps(dict(to='virtual', bytes=[0x9A, 29, 127])))
        self.assertEqual(transport.output.send.call_count, 2)
        self.assertEqual(events[-1]['operation'], 'validate_command')


if __name__ == '__main__':
    unittest.main()
