"""Desktop controller for the offline WebKit/WebView2 interface.

Only fixed, local actions are exposed to the bundled interface. No arbitrary
paths, commands, URLs or incoming MIDI messages are accepted from JavaScript.
"""
import json
import os
import plistlib
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import threading
import time

from mx2_desktop import command, open_item, resources, user_state, VERSION


class DesktopAPI:
    def __init__(self, monitor=None):
        self._monitor = monitor
        self._lock = threading.RLock()
        self._process = None
        self._log = None
        self._started = 0
        self._error = None
        self._mapping_opened = False
        self._connection_mode = self._load_connection_mode()
        self._closed = False
        self._quitting = False
        self._quit_thread = None
        self._quit_progress = {'stage': 'idle', 'percent': 0, 'message': ''}
        self._window = None
        self._controls_fullscreen = False

    def get_state(self):
        with self._lock:
            process = self._process
            alive = process is not None and process.poll() is None
            if process is not None and not alive:
                if process.returncode:
                    self._error = 'The bridge stopped. Close any other MX2 bridge and try again.'
                self._process = None
                if self._log:
                    self._log.close(); self._log = None
            hardware = self._monitor.snapshot() if self._monitor else {
                'running': False, 'connected': False, 'mode': 'unknown', 'error': 'Device monitor is unavailable.'}
            bridge = {}
            if alive:
                try:
                    state = json.loads((user_state() / 'bridge-status.json').read_text())
                    if (state.get('pid') == process.pid and state.get('running')
                            and state.get('updated_unix_time', 0) >= self._started
                            and 0 <= time.time() - state['updated_unix_time'] < 4):
                        bridge = state
                        bridge['fresh'] = time.time() - state['updated_unix_time'] < 4
                        if bridge['fresh'] and bridge.get('hid_connected'):
                            hardware['connected'] = True
                            if bridge.get('native_mode_confirmed'):
                                hardware.update(mode='native', stale=False, last_observed_mode='native')
                except (OSError, ValueError, KeyError):
                    pass
            return {'version': VERSION, 'platform': sys.platform,
                    'connection_mode': self._connection_mode,
                    'midi_available': sys.platform == 'darwin',
                    'hardware': hardware, 'bridge': {'running': alive, 'ready': bool(bridge.get('ready')),
                    'fresh': bool(bridge.get('fresh')), 'feedback_messages': bridge.get('feedback_messages', 0),
                    'decode_errors': bridge.get('decode_errors', 0)}, 'mapping_opened': self._mapping_opened,
                    'mapping': self.mapping_status(), 'error': self._error}

    @staticmethod
    def _load_connection_mode():
        if sys.platform != 'darwin':
            return 'native'
        try:
            mode = (user_state() / 'connection-mode.txt').read_text().strip()
            return mode if mode in ('native', 'midi') else 'native'
        except OSError:
            return 'native'

    def set_connection_mode(self, mode):
        with self._lock:
            if mode not in ('native', 'midi') or (mode == 'midi' and sys.platform != 'darwin'):
                return {'ok': False, 'message': 'This connection mode is unavailable.'}
            if self._closed or self._quitting:
                return {'ok': False, 'message': 'This window is closing.'}
            if self._process and self._process.poll() is None:
                return {'ok': False, 'message': 'Stop the bridge before changing mode.'}
            try:
                state = user_state()
                state.mkdir(parents=True, exist_ok=True)
                (state / 'connection-mode.txt').write_text(mode + '\n')
            except OSError as error:
                return {'ok': False, 'message': str(error)}
            if mode != self._connection_mode:
                self._mapping_opened = False
            self._connection_mode = mode
            self._error = None
            return {'ok': True}

    def start_bridge(self):
        with self._lock:
            if self._closed or self._quitting:
                return {'ok': False, 'message': 'This window is closing.'}
            if self._process and self._process.poll() is None:
                return {'ok': True}
            state = user_state()
            try:
                state.mkdir(parents=True, exist_ok=True)
                self._log = (state / 'launcher.log').open('a', encoding='utf-8')
                options = {'creationflags': subprocess.CREATE_NO_WINDOW} if sys.platform == 'win32' else {'start_new_session': True}
                worker_mode = '--bridge-worker-midi' if self._connection_mode == 'midi' else '--bridge-worker'
                self._process = subprocess.Popen(command(worker_mode), stdout=self._log,
                                                 stderr=self._log, **options)
                self._started = time.time()
                self._error = None
                return {'ok': True}
            except OSError as error:
                if self._log: self._log.close(); self._log = None
                self._error = str(error)
                return {'ok': False, 'message': 'Could not start the bridge: ' + str(error)}

    def stop_bridge(self):
        with self._lock:
            if self._process and self._process.poll() is None:
                try:
                    (user_state() / 'stop.request').write_text(str(self._process.pid))
                except OSError as error:
                    return {'ok': False, 'message': str(error)}
            return {'ok': True}

    def open_target(self):
        if sys.platform == 'darwin':
            path = Path('/Applications/djay Pro.app')
            if not path.exists():
                return {'ok': False, 'message': 'Open djay Pro from your Applications folder.'}
            open_item(path)
            return {'ok': True}
        return {'ok': False, 'message': 'Open djay Pro from the Windows Start menu.'}

    def mapping_status(self):
        """Detect a matching installed mapping without altering djay's files."""
        name = self._mapping_name()
        source = resources() / 'mappings' / (name + '.djayMidiMapping')
        folders = [Path.home() / 'Music/djay/MIDI Mappings']
        if sys.platform == 'darwin':
            folders.append(Path.home() / 'Library/Containers/com.algoriddim.djay-iphone-free/Data/Music/djay/MIDI Mappings')
        try:
            expected = plistlib.loads(source.read_bytes())
            for folder in folders:
                for candidate in folder.glob(name + '*.djayMidiMapping'):
                    try:
                        actual = plistlib.loads(candidate.read_bytes())
                        if all(actual.get(key) == expected.get(key) for key in ('endpointName', 'controls', 'outputs')):
                            return {'installed': True, 'selection_verified': False}
                    except (OSError, ValueError, plistlib.InvalidFileException):
                        continue
        except (OSError, ValueError, plistlib.InvalidFileException):
            pass
        return {'installed': False, 'selection_verified': False}

    def import_mapping(self):
        if self.mapping_status()['installed']:
            return {'ok': True, 'message': 'The matching mapping is already installed. In djay select MX2 for djay, then close the MIDI editor. No duplicate was imported.'}
        name = self._mapping_name()
        try:
            target = user_state() / 'Import' / (name + '.djayMidiMapping')
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(resources() / 'mappings' / target.name, target)
            open_item(target)
            self._mapping_opened = True
            return {'ok': True, 'message': 'Finish importing in djay, then quit and reopen djay once while keeping Companion open. Select this mapping for MX2 for djay.'}
        except OSError as error:
            return {'ok': False, 'message': str(error)}

    def _mapping_name(self):
        if sys.platform == 'win32':
            return 'Traktor MX2 - Windows RGB'
        return 'Traktor MX2 - Visual Complete' if self._connection_mode == 'midi' else 'Traktor MX2 - Native RGB'

    def open_cheat_sheet(self):
        open_item(resources() / 'distribution/ui/cheatsheet.html')
        return {'ok': True}

    def toggle_controls_fullscreen(self):
        """Toggle the companion window while the controls reference is open."""
        with self._lock:
            if self._closed or self._window is None:
                return {'ok': False, 'message': 'The companion window is unavailable.'}
            try:
                self._window.toggle_fullscreen()
            except Exception as error:
                return {'ok': False, 'message': 'Could not change full screen mode: ' + str(error)}
            self._controls_fullscreen = not self._controls_fullscreen
            return {'ok': True, 'fullscreen': self._controls_fullscreen}

    def quit_app(self):
        """Keep the window responsive while its worker stops every child process."""
        with self._lock:
            if self._quitting:
                return {'ok': True}
            if self._window is None:
                return {'ok': False, 'message': 'The companion window is unavailable.'}
            self._quitting = True
            self._quit_progress = {'stage': 'bridge', 'percent': 5,
                                   'message': 'Arrêt de la connexion avec djay…'}
            self._quit_thread = threading.Thread(target=self._quit_worker,
                                                 name='MX2 shutdown', daemon=False)
            self._quit_thread.start()
        return {'ok': True}

    def get_quit_progress(self):
        with self._lock:
            return dict(self._quit_progress)

    def _set_quit_progress(self, stage, percent, message):
        with self._lock:
            self._quit_progress = {'stage': stage, 'percent': percent, 'message': message}

    def _quit_worker(self):
        try:
            self._shutdown()
        except Exception as error:
            self._set_quit_progress('error', 100, 'Erreur pendant l’arrêt : ' + str(error))
        else:
            self._set_quit_progress('done', 100, 'Tout est arrêté. Fermeture de la fenêtre…')
        # Let the completed state render before the native window closes.
        time.sleep(0.45)
        if self._window is not None:
            self._window.destroy()

    def _wait_for_bridge_exit(self):
        with self._lock:
            process = self._process
        if process is None or process.poll() is not None:
            return True
        try:
            process.wait(timeout=2)
            return True
        except subprocess.TimeoutExpired:
            return False

    def _shutdown(self):
        with self._lock:
            if self._closed:
                return
            self._closed = True
            process = self._process
        self._set_quit_progress('bridge', 10, 'Envoi de la demande d’arrêt à la connexion…')
        self.stop_bridge()
        self._set_quit_progress('bridge', 30, 'Attente de la fin de la connexion…')
        try:
            if not self._wait_for_bridge_exit() and process:
                self._set_quit_progress('bridge', 45, 'La connexion tarde : arrêt forcé du processus…')
                if sys.platform == 'win32':
                    taskkill = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32/taskkill.exe'
                    subprocess.run([str(taskkill), '/PID', str(process.pid), '/T', '/F'],
                                   creationflags=subprocess.CREATE_NO_WINDOW, capture_output=True, timeout=5)
                else:
                    try:
                        os.killpg(process.pid, signal.SIGTERM)
                        process.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait(timeout=1)
                    except ProcessLookupError:
                        pass
        finally:
            self._set_quit_progress('monitor', 70, 'Arrêt du moniteur du contrôleur…')
            try:
                if self._monitor:
                    self._monitor.stop()
            finally:
                self._set_quit_progress('final', 95, 'Fermeture des journaux…')
                if self._log:
                    self._log.close(); self._log = None


def run():
    import webview
    from mx2_device_monitor import DeviceMonitor
    transport = (command('--portable-transport') if sys.platform == 'win32' else
                 [str(resources() / 'tools/mx2-native-transport')])
    monitor = DeviceMonitor(transport + ['--observe'])
    api = DesktopAPI(monitor)
    monitor.start()
    window = webview.create_window('MX2 Companion for djay Pro', str(resources() / 'distribution/ui/index.html'),
                                   js_api=api, width=1240, height=840, min_size=(860, 650),
                                   background_color='#f8f9fa', text_select=False)
    api._window = window
    try:
        webview.start(gui='cocoa' if sys.platform == 'darwin' else 'edgechromium', debug=False)
    finally:
        api._shutdown()
