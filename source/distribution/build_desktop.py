#!/usr/bin/env python3
"""Build on the destination OS. No cross-compilation or user-data collection."""
import hashlib
import importlib.metadata
import sysconfig
import tempfile
import html
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parent.parent
NAME = 'MX2 Companion'
VERSION = '0.5.0'


def run(args):
    environment = dict(os.environ, PYINSTALLER_CONFIG_DIR=str(ROOT / 'build/pyinstaller-cache'))
    subprocess.run([str(x) for x in args], cwd=ROOT, check=True, env=environment)


def guide():
    docs = ROOT / 'distribution/docs'
    sections = ''.join('<details><summary>' + html.escape(title) + '</summary><pre>' + html.escape((docs / filename).read_text()) + '</pre></details>'
                       for filename, title in [('README.md', 'Setup and troubleshooting'), ('CONTROL-GUIDE.md', 'All controls'), ('VALIDATION.md', 'Tested features and limitations')])
    (docs / 'START-HERE.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>MX2 for djay — Start here</title><style>body{font:18px/1.6 system-ui;background:#f4f6fa;color:#172439;max-width:850px;margin:32px auto;padding:24px}h1{font-size:38px}li{margin:12px 0}details{background:white;border-radius:8px;padding:18px;margin:18px 0}summary{cursor:pointer;font-weight:bold}pre{white-space:pre-wrap;font:16px/1.6 system-ui;overflow-wrap:anywhere}</style><h1>MX2 for djay</h1><p>Keep the companion app open while mixing. No Terminal is needed in the packaged Mac app.</p><ol><li>Choose Native or MIDI in Companion and use the same mode on the MX2. Press both SHIFT buttons together once to change the hardware mode.</li><li>Open <b>MX2 Companion</b> and click <b>Start connection</b>.</li><li>Click <b>Install djay mapping</b> if it is not installed. Confirm in djay, quit and reopen djay once while Companion stays open, then select <b>MX2 for djay</b> and the mapping for your selected connection mode: Native RGB or Visual Complete on Mac.</li><li>Disable the direct <b>Traktor MX2</b> MIDI connection in djay.</li><li>Set MX2 main audio to channels <b>1–2</b>, headphones to <b>3–4</b>. For previewing only one deck: manual cue selection, CUE MIX toward CUE.</li></ol><p><b>Stop &amp; quit</b> shows shutdown progress, stops the bridge and device monitor, then closes Companion. djay Pro stays open.</p><p><b>Mac:</b> Apple Silicon build. Intel needs a separate build. <b>Windows:</b> preview source/build path, not hardware validated. Create one loopMIDI bus named <b>MX2 for djay</b>. Use the Windows RGB mapping.</p><p>For momentary FX4, turn off the effect's HOLD option in djay. Both SHIFT buttons together switch the hardware mode; do not press them together while mixing.</p>''' + sections + '</html>')


def main():
    if sys.platform not in ('darwin', 'win32'):
        raise SystemExit('Build this application on macOS or Windows.')
    guide()
    licenses = ROOT / 'distribution/licenses'
    licenses.mkdir(exist_ok=True)
    python_license = Path(sysconfig.get_path('stdlib')) / 'LICENSE.txt'
    if python_license.exists():
        shutil.copy2(python_license, licenses / 'Python-LICENSE.txt')
    # Retain license texts from the isolated build environment, including native UI dependencies.
    for dist in importlib.metadata.distributions():
        package_name = dist.metadata.get('Name', 'component')
        for entry in dist.files or []:
            if (entry.name.lower() in ('license', 'licence', 'copying')
                    or (entry.name.lower().startswith(('license', 'licence', 'copying'))
                        and entry.suffix.lower() in ('.txt', '.md', '.rst', '.rtf', '.html', '.bsd', '.mit', '.apache'))):
                source = Path(dist.locate_file(entry))
                if source.is_file() and source.stat().st_size < 2_000_000:
                    filename = package_name + '-' + '_'.join(entry.parts[-3:])
                    shutil.copy2(source, licenses / filename)
    release = ROOT / 'release'; release.mkdir(exist_ok=True)
    stage = ROOT / 'build/desktop-resources'; stage.mkdir(parents=True, exist_ok=True)
    for folder in ['evidence', 'mappings', 'distribution/docs', 'tools']:
        (stage / folder).mkdir(parents=True, exist_ok=True)
    for name in ['LICENSE', 'LICENSING.md']:
        shutil.copy2(ROOT / name, stage / name)
    for name in ['midi-profile.json', 'native-protocol-map.json']:
        shutil.copy2(ROOT / 'evidence' / name, stage / 'evidence' / name)
    for name in ['Traktor MX2 - Native RGB', 'Traktor MX2 - Windows RGB',
                 'Traktor MX2 - Visual Complete']:
        shutil.copy2(ROOT / 'mappings' / (name + '.djayMidiMapping'), stage / 'mappings')
    shutil.copytree(licenses, stage / 'distribution/licenses', dirs_exist_ok=True)
    shutil.copytree(ROOT / 'distribution/ui', stage / 'distribution/ui', dirs_exist_ok=True)
    for path in (ROOT / 'distribution/docs').iterdir():
        if path.is_file(): shutil.copy2(path, stage / 'distribution/docs')
    dist_dir = Path(tempfile.mkdtemp(prefix='mx2-desktop-build-'))
    args = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--windowed', '--onedir', '--name', NAME,
            '--distpath', str(dist_dir), '--workpath', str(ROOT / 'build/pyinstaller'),
            '--specpath', str(ROOT / 'build'), '--icon', str(ROOT / 'distribution/ui/app-icon.png'), '--paths', str(ROOT / 'tools'), '--collect-all', 'webview', '--add-data', str(stage) + ':.' ]
    if sys.platform == 'darwin':
        # Toolchain cache stays inside the build tree, not the user's home cache.
        for source, binary_name in [('mx2_native_transport.swift', 'mx2-native-transport'),
                                    ('mx2_midi_transport.swift', 'mx2-midi-transport')]:
            binary = stage / 'tools' / binary_name
            run(['swiftc', '-target', platform.machine() + '-apple-macosx11.0', '-module-cache-path', ROOT / 'build/swift-cache', ROOT / 'tools' / source, '-o', binary])
            run([binary, '--self-test'])
            args += ['--add-binary', str(binary) + ':tools']
        args += ['--osx-bundle-identifier', 'community.mx2fordjay.bridge']
    else:
        args += ['--hidden-import', 'mido.backends.rtmidi', '--collect-all', 'hid', '--collect-all', 'rtmidi']
    args += [str(ROOT / 'tools/mx2_desktop.py')]
    if sys.platform == 'win32':
        # Console-mode worker keeps JSON stdin/stdout; GUI spawns it with CREATE_NO_WINDOW.
        worker_args = list(args)
        worker_args.remove('--windowed')
        worker_args[worker_args.index(NAME)] = 'MX2BridgeWorker'
        run(worker_args)
    run(args)
    if sys.platform == 'win32':
        shutil.copytree(dist_dir / 'MX2BridgeWorker', dist_dir / NAME / 'MX2BridgeWorker', dirs_exist_ok=True)
    tag = ('macOS-' if sys.platform == 'darwin' else 'Windows-') + platform.machine()
    package = release / ('MX2-Companion-' + VERSION + '-' + tag)
    package.mkdir(exist_ok=True)
    product = dist_dir / (NAME + '.app' if sys.platform == 'darwin' else NAME)
    destination = package / product.name
    if sys.platform == 'darwin':
        run(['/usr/bin/codesign', '--verify', '--deep', '--strict', product])
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(product, destination, symlinks=True)
    shutil.copytree(ROOT / 'distribution/docs', package / 'Guide', dirs_exist_ok=True)
    shutil.copytree(ROOT / 'distribution/ui', package / 'Cheat sheet', dirs_exist_ok=True)
    shutil.copytree(stage / 'mappings', package / 'Mappings', dirs_exist_ok=True)
    shutil.copytree(licenses, package / 'Licenses', dirs_exist_ok=True)
    for name in ['LICENSE', 'LICENSING.md']:
        shutil.copy2(ROOT / name, package / name)
    (package / 'RELEASE-NOTES.txt').write_text('MX2 Companion ' + VERSION + '\nPlatform: ' + tag + '\nCommunity build. No Apple notarization or Windows Authenticode certificate.\nMac controller validation: djay5.6.9, arm64, original MIDI and native bridges. Packaged app verification is recorded separately.\nWindows: experimental until physical HID, MIDI feedback, audio and reconnect tests pass.\n')
    archive = release / (package.name + '.zip')
    if sys.platform == 'darwin':
        run(['/usr/bin/ditto', '-c', '-k', '--norsrc', '--noextattr', '--keepParent', package, archive])
        # Cloud-backed Documents can reattach FinderInfo to the loose .app. Verify
        # the archive after extraction, which is the artifact users install.
        with tempfile.TemporaryDirectory(prefix='mx2-archive-check-') as check_dir:
            run(['/usr/bin/ditto', '-x', '-k', archive, check_dir])
            extracted = Path(check_dir) / package.name / product.name
            run(['/usr/bin/codesign', '--verify', '--deep', '--strict', extracted])
    else:
        shutil.make_archive(str(archive.with_suffix('')), 'zip', root_dir=release, base_dir=package.name)
    shutil.rmtree(dist_dir)
    print(json.dumps({'package': str(package), 'zip': str(archive), 'sha256': hashlib.sha256(archive.read_bytes()).hexdigest()}))


if __name__ == '__main__':
    main()
