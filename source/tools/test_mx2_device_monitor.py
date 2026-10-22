"""Observer mode proof and no-write guarantees, without touching hardware."""
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from mx2_device_monitor import DeviceMonitor
from mx2_portable_transport import Observer
from test_mx2_portable_transport import Device


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.now = 10.0
        self.monitor = DeviceMonitor(['fake', '--observe'])
        self.monitor._clock = lambda: self.now

    def feed(self, event, **data):
        self.monitor._consume(dict(event=event, **data))

    def hid(self, seed=False, status=0, report=3, raw=None):
        raw = bytes([report] + [0] * ({1: 15, 2: 53, 3: 20}[report] - 1)) if raw is None else raw
        self.feed('hid_input', report_id=report, bytes_hex=raw.hex(), seed=seed, status=status)

    def test_idle_and_seed_never_prove_mode(self):
        self.feed('hid_connected')
        self.feed('ready_observer')
        self.hid(seed=True)
        self.hid(status=-1)
        self.hid(raw=b'\x03\x00')
        self.now += 60
        state = self.monitor.snapshot()
        self.assertTrue(state['connected'])
        self.assertEqual(state['mode'], 'unknown')
        self.assertFalse(state['stale'])

    def test_live_hid_positive_native_and_stale(self):
        self.feed('hid_connected')
        self.hid()
        self.assertEqual(self.monitor.snapshot()['mode'], 'native')
        self.now += 6
        self.assertEqual(self.monitor.snapshot()['mode'], 'stale')
        self.assertEqual(self.monitor.snapshot()['last_observed_mode'], 'native')
        self.hid(report=1)
        self.assertEqual(self.monitor.snapshot()['mode'], 'native')

    def test_midi_positive_evidence_no_clock_or_malformed(self):
        self.feed('hid_connected')
        for data in ([0xF8], [0x90, 1], [0x90, 1, True], [0x90, 200, 1]):
            self.feed('physical_midi_input', bytes=data)
        self.assertEqual(self.monitor.snapshot()['mode'], 'unknown')
        self.feed('physical_midi_input', bytes=[0x90, 29, 127])
        self.assertEqual(self.monitor.snapshot()['mode'], 'midi')
        self.hid()
        self.assertEqual(self.monitor.snapshot()['mode'], 'native')

    def test_reconnect_and_ambiguity_clear_mode(self):
        self.feed('hid_connected')
        self.hid()
        self.feed('hardware_unavailable', matching_devices=2)
        self.assertFalse(self.monitor.snapshot()['connected'])
        self.feed('physical_midi_input', bytes=[0x90, 29, 127])
        self.assertEqual(self.monitor.snapshot()['mode'], 'unknown')
        self.feed('hid_connected')
        self.assertEqual(self.monitor.snapshot()['mode'], 'unknown')
        self.assertIsNone(self.monitor.snapshot()['last_input_age_seconds'])

    def test_observer_reads_and_stops_fake_process_without_commands(self):
        with tempfile.TemporaryDirectory() as temporary:
            helper = Path(temporary) / 'observer.py'
            helper.write_text('import json,sys\n'
                              'print(json.dumps({"event":"ready_observer"}),flush=True)\n'
                              'print(json.dumps({"event":"hid_connected"}),flush=True)\n'
                              'for line in sys.stdin: raise RuntimeError("Unexpected output command")\n')
            monitor = DeviceMonitor([sys.executable, str(helper)])
            monitor.start()
            deadline = time.monotonic() + 2
            while not monitor.snapshot()['ready'] and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue(monitor.snapshot()['ready'])
            self.assertEqual(monitor.snapshot()['mode'], 'unknown')
            monitor.stop()
            self.assertFalse(monitor.snapshot()['running'])

    def test_missing_executable_is_visible_error(self):
        monitor = DeviceMonitor(['/nonexistent/mx2-observer'])
        monitor.start()
        self.assertFalse(monitor.snapshot()['running'])
        self.assertTrue(monitor.snapshot()['error'])
        monitor.stop()


class PortableObserverTests(unittest.TestCase):
    def fixture(self, mido=None):
        row = dict(vendor_id=0x17cc, product_id=0x2420, usage_page=0xff01, usage=0, path=b'fake')
        hid = SimpleNamespace(enumerate=Mock(return_value=[row]), device=Mock(side_effect=Device))
        events = []
        observer = Observer(hid, mido, lambda e, **v: events.append(dict(event=e, **v)))
        return observer, hid, events

    def test_no_output_writes_even_given_commands(self):
        observer, hid, events = self.fixture()
        observer.refresh_device()
        observer.accept(json.dumps(dict(to='hid-leds', bytes=[127] * 105)))
        observer.accept(json.dumps(dict(to='virtual', bytes=[0x90, 29, 127])))
        observer.device.reads = [[3] + [0] * 19]
        observer.hardware_step()
        self.assertEqual(observer.device.writes, [])
        self.assertIsNone(observer.output)
        self.assertEqual(events[-1]['event'], 'hid_input')

    def test_physical_midi_input_only_no_virtual_port_requirement(self):
        mido = SimpleNamespace(get_input_names=Mock(return_value=['Traktor MX2 1']), open_input=Mock())
        observer, hid, events = self.fixture(mido)
        observer.refresh_device()
        mido.open_input.assert_called_once_with('Traktor MX2 1', callback=observer.feedback)
        observer.feedback(SimpleNamespace(bytes=lambda: [0xB0, 1, 64]))
        self.assertEqual(events[-1]['event'], 'physical_midi_input')
        self.assertIsNone(observer.output)

    def test_busy_physical_midi_does_not_disconnect_hid(self):
        mido = SimpleNamespace(get_input_names=Mock(return_value=['Traktor MX2']), open_input=Mock(side_effect=OSError('busy')))
        observer, hid, events = self.fixture(mido)
        observer.refresh_device()
        self.assertIsNotNone(observer.device)
        self.assertEqual(events[-1]['operation'], 'optional_physical_midi')


if __name__ == '__main__':
    unittest.main()
