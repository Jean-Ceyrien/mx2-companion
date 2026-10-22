"""Offline tests for launch dispatch, Windows feedback, and graceful worker exit."""
import json
import os
from pathlib import Path
import plistlib
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import mx2_desktop as desktop
from mx2_windows_feedback import decode_feedback, encode_feedback

ROOT = Path(__file__).resolve().parent.parent


class DesktopRuntimeTests(unittest.TestCase):
    def test_source_and_frozen_subcommands(self):
        with patch.object(sys, 'frozen', False, create=True):
            command = desktop.command('--bridge-worker')
            self.assertEqual(command[0], sys.executable)
            self.assertEqual(Path(command[1]).name, 'mx2_desktop.py')
            self.assertEqual(command[2], '--bridge-worker')
        with patch.object(sys, 'frozen', True, create=True), patch.object(sys, 'platform', 'darwin'):
            self.assertEqual(desktop.command('--portable-transport'), [sys.executable, '--portable-transport'])

    def test_frozen_windows_routes_to_console_worker(self):
        with patch.object(sys, 'platform', 'win32'), patch.object(sys, 'frozen', True, create=True):
            with patch.object(sys, 'executable', '/Apps/MX2 for djay.exe'):
                result = desktop.command('--bridge-worker')
                self.assertEqual(Path(result[0]), Path('/Apps/MX2BridgeWorker/MX2BridgeWorker.exe'))
                self.assertEqual(result[1], '--bridge-worker')
            with patch.object(sys, 'executable', '/Apps/MX2BridgeWorker/MX2BridgeWorker.exe'):
                self.assertEqual(desktop.command('--portable-transport'),
                                 ['/Apps/MX2BridgeWorker/MX2BridgeWorker.exe', '--portable-transport'])

    def test_windowed_worker_opens_diagnostic_stream(self):
        with tempfile.TemporaryDirectory() as temporary:
            with patch.object(sys, 'stdout', None), patch.object(sys, 'stderr', None), \
                    patch.object(desktop, 'user_state', return_value=Path(temporary)), \
                    patch('mx2_native_bridge.main', return_value=0):
                desktop.worker()
                diagnostic = sys.stdout
                self.assertIs(diagnostic, sys.stderr)
                self.assertEqual(Path(diagnostic.name), Path(temporary) / 'worker.log')
                diagnostic.close()

    def test_resource_and_windows_state_roots(self):
        with patch.object(sys, '_MEIPASS', '/frozen/resources', create=True):
            self.assertEqual(desktop.resources(), Path('/frozen/resources'))
        with patch.object(sys, 'platform', 'win32'), patch.dict(os.environ, LOCALAPPDATA='/user/local'):
            self.assertEqual(desktop.user_state(), Path('/user/local/MX2 for djay'))

    def test_windows_worker_uses_transport_and_feedback_decoder(self):
        with patch.object(sys, 'platform', 'win32'), patch('mx2_native_bridge.main', return_value=7) as main:
            self.assertEqual(desktop.worker(), 7)
            args = main.call_args.args
            self.assertEqual(args[2], desktop.command('--portable-transport'))
            self.assertIs(args[3], decode_feedback)

    def test_mac_midi_worker_uses_original_transport_and_separate_state(self):
        with patch.object(sys, 'platform', 'darwin'), patch('mx2_bridge.main', return_value=0) as main:
            self.assertEqual(desktop.worker('midi'), 0)
            self.assertEqual(main.call_args.args[0:2], (desktop.resources(), desktop.user_state()))
            self.assertEqual(main.call_args.args[2], [str(desktop.resources() / 'tools/mx2-midi-transport')])
            self.assertEqual(main.call_args.kwargs['argv'], [])

    def test_midi_stop_request_shuts_down_idle_transport(self):
        import mx2_bridge
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            helper = state / 'fake_midi_transport.py'
            helper.write_text('import json, sys\n'
                              'print(json.dumps({"event":"ready"}), flush=True)\n'
                              'for line in sys.stdin: pass\n')
            def request_stop():
                deadline = time.monotonic() + 5
                while not (state / 'bridge-status.json').exists() and time.monotonic() < deadline:
                    time.sleep(0.01)
                (state / 'stop.request').write_text(str(os.getpid()))
            requester = threading.Thread(target=request_stop, daemon=True)
            requester.start()
            with patch('mx2_bridge.signal.signal'):
                code = mx2_bridge.main(ROOT, state, [sys.executable, str(helper)], argv=[])
            requester.join(1)
            self.assertEqual(code, 0)
            status = json.loads((state / 'bridge-status.json').read_text())
            self.assertFalse(status['running'])
            self.assertEqual(status['mode'], 'midi')
            self.assertFalse((state / 'stop.request').exists())

    def test_midi_stop_request_terminates_unresponsive_transport(self):
        import mx2_bridge
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            helper = state / 'stuck_midi_transport.py'
            helper.write_text('import json, time\n'
                              'print(json.dumps({"event":"ready"}), flush=True)\n'
                              'time.sleep(30)\n')
            def request_stop():
                deadline = time.monotonic() + 5
                while not (state / 'bridge-status.json').exists() and time.monotonic() < deadline:
                    time.sleep(0.01)
                (state / 'stop.request').write_text(str(os.getpid()))
            requester = threading.Thread(target=request_stop, daemon=True)
            requester.start()
            started = time.monotonic()
            with patch('mx2_bridge.signal.signal'):
                code = mx2_bridge.main(ROOT, state, [sys.executable, str(helper)], argv=[])
            requester.join(1)
            self.assertNotEqual(code, 0)
            self.assertLess(time.monotonic() - started, 8)
            self.assertFalse(json.loads((state / 'bridge-status.json').read_text())['running'])

    def test_windows_mapping_control_inputs_are_feedback_disjoint(self):
        native = plistlib.loads((ROOT / 'mappings/Traktor MX2 - Native RGB.djayMidiMapping').read_bytes())
        windows = plistlib.loads((ROOT / 'mappings/Traktor MX2 - Windows RGB.djayMidiMapping').read_bytes())
        self.assertEqual(len(windows['controls']), 293)
        self.assertNotEqual(windows['uuid'], native['uuid'])
        self.assertEqual(windows['endpointName'], 'MX2 for djay')
        address_mapping = {}
        for before, after in zip(native['controls'], windows['controls']):
            self.assertEqual({k: v for k, v in before.items() if k != 'output'},
                             {k: v for k, v in after.items() if k != 'output'})
            self.assertNotIn(after['midiChannel'], range(10, 15))
            if 'output' not in after:
                continue
            b, a = before['output'], after['output']
            original = ((176 if b.get('midiMessageType', before['midiMessageType']) == 3 else 144)
                        | b.get('midiChannel', before['midiChannel']),
                        b.get('midiData', before['midiData']))
            encoded = ((176 if a.get('midiMessageType', after['midiMessageType']) == 3 else 144)
                       | a.get('midiChannel', after['midiChannel']), a.get('midiData', after['midiData']))
            self.assertIn(encoded[0] & 15, range(10, 15))
            self.assertEqual(decode_feedback(encoded[0], [encoded[1], 127]),
                             (original[0], [original[1], 127]))
            if encoded in address_mapping:
                self.assertEqual(address_mapping[encoded], original)
            address_mapping[encoded] = original
        for b, a in zip(native['outputs'], windows['outputs']):
            family = 176 if b['midiMessageType'] == 3 else 144
            self.assertEqual(decode_feedback(family | a['midiChannel'], [a['midiData'], 100]),
                             (family | b['midiChannel'], [b['midiData'], 100]))

    def test_feedback_codec_round_trip_all_relevant_values(self):
        addresses = [(0x90 | c, n) for c in (0, 1, 4, 5) for n in range(0, 74)]
        addresses += [(0x90 | c, n) for c in (6, 7) for n in range(56)]
        addresses += [(0x9E, 2), (0x9E, 3), (0x9F, 5), (0xBE, 0), (0xBE, 1)]
        # Strip feedback 120/121 are reserved by design; real strip IDs are <74.
        for status, number in addresses:
            for value in (0, 1, 64, 127):
                encoded_status, encoded_data = encode_feedback(status, [number, value])
                self.assertEqual(decode_feedback(encoded_status, encoded_data), (status, [number, value]))
        for channel in list(range(10)) + [15]:
            self.assertIsNone(decode_feedback(0x90 | channel, [29, 127]))

    def test_stop_request_shuts_down_idle_transport_without_signals(self):
        import mx2_native_bridge
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            helper = state / 'fake_transport.py'
            helper.write_text('import json, sys\n'
                              'print(json.dumps({"event":"ready_native"}), flush=True)\n'
                              'print(json.dumps({"event":"hardware_unavailable","message":"fake"}), flush=True)\n'
                              'for line in sys.stdin: pass\n')
            outcome = []
            def request_stop():
                deadline = time.monotonic() + 5
                while not (state / 'bridge-status.json').exists() and time.monotonic() < deadline:
                    time.sleep(0.01)
                (state / 'stop.request').write_text(str(os.getpid()))
            requester = threading.Thread(target=request_stop, daemon=True)
            requester.start()
            # Unit tests must not install process-wide signal handlers.
            with patch('mx2_native_bridge.signal.signal'):
                outcome.append(mx2_native_bridge.main(ROOT, state, [sys.executable, str(helper)]))
            requester.join(1)
            self.assertEqual(outcome, [0])
            status = json.loads((state / 'bridge-status.json').read_text())
            self.assertFalse(status['running'])
            self.assertFalse((state / 'stop.request').exists())


    def test_stop_watchdog_terminates_unresponsive_transport(self):
        import mx2_native_bridge
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            helper = state / 'stuck_transport.py'
            helper.write_text('import json, time\n'
                              'print(json.dumps({"event":"ready_native"}), flush=True)\n'
                              'time.sleep(30)\n')
            def request_stop():
                deadline = time.monotonic() + 5
                while not (state / 'bridge-status.json').exists() and time.monotonic() < deadline:
                    time.sleep(0.01)
                (state / 'stop.request').write_text(str(os.getpid()))
            requester = threading.Thread(target=request_stop, daemon=True)
            requester.start()
            started = time.monotonic()
            with patch('mx2_native_bridge.signal.signal'):
                code = mx2_native_bridge.main(ROOT, state, [sys.executable, str(helper)])
            requester.join(1)
            self.assertNotEqual(code, 0)
            self.assertLess(time.monotonic() - started, 8)
            self.assertFalse(json.loads((state / 'bridge-status.json').read_text())['running'])


if __name__ == '__main__':
    unittest.main()
