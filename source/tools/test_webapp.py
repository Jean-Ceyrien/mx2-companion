"""Offline desktop API tests. No app, controller, or virtual MIDI port is opened."""
import json
import plistlib
from pathlib import Path
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from mx2_webapp import DesktopAPI


class FakeMonitor:
    def __init__(self):
        self.running = True
        self.stop = Mock(side_effect=lambda: setattr(self, 'running', False))
        self.start = Mock(side_effect=lambda: setattr(self, 'running', True))
        self.snapshot = Mock(side_effect=lambda: dict(running=self.running, connected=True, mode='unknown', error=None))


class WebAppTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.state = self.root / 'state'
        self.state.mkdir()
        (self.root / 'mappings').mkdir()
        self.monitor = FakeMonitor()
        self.api = DesktopAPI(self.monitor)
        self.api._connection_mode = 'native'
        self.patches = [patch('mx2_webapp.user_state', return_value=self.state),
                        patch('mx2_webapp.resources', return_value=self.root)]
        for item in self.patches:
            item.start()

    def tearDown(self):
        if self.api._log and not self.api._log.closed:
            self.api._log.close()
        for item in reversed(self.patches):
            item.stop()
        self.temporary.cleanup()

    def process(self):
        process = SimpleNamespace(pid=12345, returncode=None, poll=Mock(return_value=None), wait=Mock(), terminate=Mock())
        self.api._process = process
        self.api._started = time.time() - 20
        return process

    def write_status(self, **overrides):
        status = dict(pid=12345, updated_unix_time=time.time(), ready=True, running=True,
                      hid_connected=True, native_mode_confirmed=True,
                      feedback_messages=123, decode_errors=2)
        status.update(overrides)
        (self.state / 'bridge-status.json').write_text(json.dumps(status))

    def test_open_target_only_opens_djay(self):
        with patch('mx2_webapp.sys.platform', 'darwin'), \
                patch('mx2_webapp.Path.exists', return_value=True), \
                patch('mx2_webapp.open_item') as opening:
            self.assertTrue(self.api.open_target()['ok'])
        opening.assert_called_once_with(Path('/Applications/djay Pro.app'))
        self.assertNotIn('target', self.api.get_state())

    def test_quit_reports_progress_without_blocking_window(self):
        process = self.process()
        actions = []
        bridge_waiting = threading.Event()
        bridge_release = threading.Event()
        monitor_waiting = threading.Event()
        monitor_release = threading.Event()
        def wait_for_bridge(timeout):
            actions.append('bridge-wait')
            bridge_waiting.set()
            bridge_release.wait(2)
            actions.append('bridge-exit')
        def stop_monitor():
            monitor_waiting.set()
            monitor_release.wait(2)
            actions.append('monitor-exit')
        process.wait.side_effect = wait_for_bridge
        self.monitor.stop.side_effect = stop_monitor
        self.api._window = SimpleNamespace(destroy=lambda: actions.append('window-close'))
        self.assertTrue(self.api.quit_app()['ok'])
        self.assertTrue(bridge_waiting.wait(1))
        self.assertEqual(self.api.get_quit_progress()['stage'], 'bridge')
        self.assertEqual(actions, ['bridge-wait'])
        bridge_release.set()
        self.assertTrue(monitor_waiting.wait(1))
        self.assertEqual(self.api.get_quit_progress()['stage'], 'monitor')
        self.assertNotIn('window-close', actions)
        monitor_release.set()
        self.api._quit_thread.join(timeout=2)
        self.assertFalse(self.api._quit_thread.is_alive())
        self.assertEqual((self.state / 'stop.request').read_text(), str(process.pid))
        self.assertEqual(actions, ['bridge-wait', 'bridge-exit', 'monitor-exit', 'window-close'])
        self.assertEqual(self.api.get_quit_progress()['percent'], 100)
        process.wait.assert_called_once_with(timeout=2)
        self.monitor.stop.assert_called_once()
        self.assertFalse(self.api.start_bridge()['ok'])
        self.api._shutdown()
        self.monitor.stop.assert_called_once()

    def test_controls_fullscreen_toggles_window_and_reports_state(self):
        window = SimpleNamespace(toggle_fullscreen=Mock())
        self.api._window = window
        self.assertEqual(self.api.toggle_controls_fullscreen(), {'ok': True, 'fullscreen': True})
        self.assertEqual(self.api.toggle_controls_fullscreen(), {'ok': True, 'fullscreen': False})
        self.assertEqual(window.toggle_fullscreen.call_count, 2)
        self.api._shutdown()
        self.assertFalse(self.api.toggle_controls_fullscreen()['ok'])

    def test_wrong_pid_or_previous_run_status_ignored(self):
        self.process()
        for values in (dict(pid=54321), dict(updated_unix_time=self.api._started - 1)):
            self.write_status(**values)
            state = self.api.get_state()
            self.assertTrue(state['bridge']['running'])
            self.assertFalse(state['bridge']['ready'])
            self.assertFalse(state['bridge']['fresh'])
            self.assertEqual(state['bridge']['feedback_messages'], 0)
            self.assertEqual(state['hardware']['mode'], 'unknown')

    def test_stale_status_does_not_publish_ready_or_feedback(self):
        self.process()
        self.write_status(updated_unix_time=time.time() - 10)
        state = self.api.get_state()
        self.assertTrue(state['bridge']['running'])
        self.assertFalse(state['bridge']['ready'])
        self.assertFalse(state['bridge']['fresh'])
        self.assertEqual(state['bridge']['feedback_messages'], 0)
        self.assertEqual(state['hardware']['mode'], 'unknown')

    def test_fresh_matching_status_is_visible(self):
        self.process()
        self.write_status()
        state = self.api.get_state()
        self.assertTrue(state['bridge']['ready'])
        self.assertTrue(state['bridge']['fresh'])
        self.assertEqual(state['bridge']['feedback_messages'], 123)
        self.assertEqual(state['hardware']['mode'], 'native')

    def test_monitor_remains_active_after_bridge_stop(self):
        self.process()
        self.assertTrue(self.api.stop_bridge()['ok'])
        self.api._process = None
        state = self.api.get_state()
        self.assertFalse(state['bridge']['running'])
        self.assertTrue(state['hardware']['running'])
        self.assertTrue(state['hardware']['connected'])
        self.monitor.snapshot.assert_called()
        self.monitor.stop.assert_not_called()

    def test_import_uses_writable_copy_even_if_djay_moves_it(self):
        for platform, title in (('darwin', 'Traktor MX2 - Native RGB'), ('win32', 'Traktor MX2 - Windows RGB')):
            source = self.root / 'mappings' / (title + '.djayMidiMapping')
            source.write_bytes(b'fake mapping')
            seen = []
            def simulate_djay_import(path):
                seen.append(path)
                self.assertNotEqual(path, source)
                self.assertEqual(path.read_bytes(), source.read_bytes())
                path.unlink()
            with patch('mx2_webapp.sys.platform', platform), patch('mx2_webapp.open_item', side_effect=simulate_djay_import):
                self.assertTrue(self.api.import_mapping()['ok'])
            self.assertEqual(seen, [self.state / 'Import' / source.name])
            self.assertEqual(source.read_bytes(), b'fake mapping')
            self.assertTrue(self.api.get_state()['mapping_opened'])

    def test_matching_installed_mapping_does_not_reimport(self):
        title = 'Traktor MX2 - Native RGB.djayMidiMapping'
        source = self.root / 'mappings' / title
        mapping = dict(endpointName='MX2 for djay', controls=[dict(keyPath='mixer.crossfade')], outputs=[])
        source.write_bytes(plistlib.dumps(mapping))
        installed = self.root / 'Music/djay/MIDI Mappings'
        installed.mkdir(parents=True)
        (installed / title).write_bytes(plistlib.dumps(dict(mapping, editor='djay')))
        with patch('mx2_webapp.Path.home', return_value=self.root), patch('mx2_webapp.open_item') as opening:
            self.assertTrue(self.api.mapping_status()['installed'])
            self.assertTrue(self.api.import_mapping()['ok'])
            opening.assert_not_called()

    def test_midi_selection_persists_uses_visual_mapping_and_worker(self):
        title = 'Traktor MX2 - Visual Complete.djayMidiMapping'
        source = self.root / 'mappings' / title
        source.write_bytes(plistlib.dumps(dict(endpointName='MX2 for djay', controls=[], outputs=[])))
        with patch('mx2_webapp.sys.platform', 'darwin'), patch('mx2_webapp.open_item') as opening, \
                patch('mx2_webapp.subprocess.Popen') as spawning:
            spawning.return_value.poll.return_value = None
            self.assertTrue(self.api.set_connection_mode('midi')['ok'])
            self.assertEqual((self.state / 'connection-mode.txt').read_text(), 'midi\n')
            self.assertEqual(self.api.get_state()['connection_mode'], 'midi')
            self.assertTrue(self.api.import_mapping()['ok'])
            self.assertEqual(opening.call_args.args[0].name, title)
            self.assertTrue(self.api.start_bridge()['ok'])
            self.assertEqual(spawning.call_args.args[0][-1], '--bridge-worker-midi')
            self.assertFalse(self.api.set_connection_mode('native')['ok'])

    def test_midi_mode_is_unavailable_on_windows(self):
        with patch('mx2_webapp.sys.platform', 'win32'):
            self.assertFalse(self.api.set_connection_mode('midi')['ok'])

    def test_modified_mapping_is_not_reported_as_matching(self):
        title = 'Traktor MX2 - Native RGB.djayMidiMapping'
        source = self.root / 'mappings' / title
        source.write_bytes(plistlib.dumps(dict(endpointName='MX2 for djay', controls=[], outputs=[])))
        installed = self.root / 'Music/djay/MIDI Mappings'
        installed.mkdir(parents=True)
        (installed / title).write_bytes(plistlib.dumps(dict(endpointName='MX2 for djay', controls=[dict(keyPath='wrong')], outputs=[])))
        with patch('mx2_webapp.Path.home', return_value=self.root):
            self.assertFalse(self.api.mapping_status()['installed'])

    def test_run_starts_monitor_without_starting_bridge(self):
        import mx2_webapp
        self.monitor.running = False
        def render(*args, **kwargs):
            self.assertTrue(self.monitor.running)
        webview = SimpleNamespace(create_window=Mock(), start=Mock(side_effect=render))
        with patch.dict(sys.modules, webview=webview), \
                patch('mx2_device_monitor.DeviceMonitor', return_value=self.monitor) as factory, \
                patch('mx2_webapp.subprocess.Popen') as spawning:
            mx2_webapp.run()
        self.monitor.start.assert_called_once()
        self.monitor.stop.assert_called_once()
        self.assertEqual(factory.call_args.args[0][-1], '--observe')
        spawning.assert_not_called()


if __name__ == '__main__':
    unittest.main()
