#!/usr/bin/env python3
"""English desktop launcher. Frozen workers reuse the same signed app executable."""
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
import time

VERSION = '0.5.0'


def resources():
    return Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent))


def user_state():
    if sys.platform == 'win32':
        base = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData/Local'))
    else:
        base = Path.home() / 'Library/Application Support'
    return base / 'MX2 for djay'


def command(mode):
    if getattr(sys, 'frozen', False):
        executable = Path(sys.executable)
        if sys.platform == 'win32' and executable.stem != 'MX2BridgeWorker':
            executable = executable.parent / 'MX2BridgeWorker/MX2BridgeWorker.exe'
        return [str(executable), mode]
    return [sys.executable, str(Path(__file__).resolve()), mode]


def open_item(path):
    if sys.platform == 'win32':
        os.startfile(str(path))
    else:
        subprocess.Popen(['/usr/bin/open', str(path)])


def worker(mode='native'):
    if sys.stdout is None or sys.stderr is None:
        user_state().mkdir(parents=True, exist_ok=True)
        diagnostic = (user_state() / 'worker.log').open('a', encoding='utf-8', buffering=1)
        sys.stdout = diagnostic
        sys.stderr = diagnostic
    if mode == 'midi':
        if sys.platform != 'darwin':
            raise RuntimeError('MIDI bridge is available only on macOS.')
        from mx2_bridge import main
        return main(resources(), user_state(), [str(resources() / 'tools/mx2-midi-transport')], argv=[])
    from mx2_native_bridge import main
    transport = None
    decode = None
    if sys.platform == 'win32':
        from mx2_windows_feedback import decode_feedback
        transport, decode = command('--portable-transport'), decode_feedback
    return main(resources(), user_state(), transport, decode)


def self_check():
    import plistlib
    import mx2_native
    from mx2_bridge import Router
    from mx2_windows_feedback import decode_feedback
    root = resources()
    profile = json.loads((root / 'evidence/midi-profile.json').read_text())
    native_map = json.loads((root / 'evidence/native-protocol-map.json').read_text())
    lights = mx2_native.NativeLEDs(profile, native_map).render(Router(profile), 0)
    if any(lights[i] != 46 for i in (*range(4, 8), *range(34, 38))):
        raise RuntimeError('Both decks must keep FAV, star, Preview and View lit.')
    for name in ['Traktor MX2 - Native RGB', 'Traktor MX2 - Windows RGB',
                 'Traktor MX2 - Visual Complete']:
        mapping = plistlib.loads((root / 'mappings' / (name + '.djayMidiMapping')).read_bytes())
        assert len(mapping['controls']) == 293
    for filename in ['index.html', 'app.js', 'app-icon.png', 'style.css', 'style-modern.css',
                     'cheatsheet.html', 'cheatsheet.js', 'cheat.css', 'cheat-modern.css',
                     'mx2.png', 'mx2-wordmark.svg']:
        if not (root / 'distribution/ui' / filename).is_file():
            raise RuntimeError('Missing UI resource: ' + filename)
    controls = json.loads((root / 'distribution/ui/controls.json').read_text())['controls']
    assert len(controls) == 116
    for filename in ['Manrope-Variable.ttf', 'SpaceGrotesk-Variable.ttf',
                     'OFL-Manrope.txt', 'OFL-SpaceGrotesk.txt']:
        if not (root / 'distribution/ui/fonts' / filename).is_file():
            raise RuntimeError('Missing font resource: ' + filename)
    if sys.platform == 'darwin':
        for name in ('mx2-native-transport', 'mx2-midi-transport'):
            result = subprocess.run([str(root / 'tools' / name), '--self-test'], capture_output=True)
            if result.returncode:
                raise RuntimeError(result.stderr.decode())
    return {'version': VERSION, 'platform': sys.platform, 'architecture': platform.machine(), 'resources': 'OK'}


def main():
    from mx2_webapp import run
    run()


if __name__ == '__main__':
    if '--portable-transport' in sys.argv:
        from mx2_portable_transport import main as transport_main
        sys.exit(transport_main())
    elif '--bridge-worker' in sys.argv:
        sys.exit(worker())
    elif '--bridge-worker-midi' in sys.argv:
        sys.exit(worker('midi'))
    elif '--self-check' in sys.argv:
        result = self_check()
        if '--check-output' in sys.argv:
            Path(sys.argv[sys.argv.index('--check-output') + 1]).write_text(json.dumps(result))
        elif sys.stdout is not None:
            print(json.dumps(result))
    else:
        main()
