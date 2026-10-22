#!/usr/bin/env python3
"""Export a public-review source kit from an explicit allowlist, never live logs."""
from pathlib import Path
import argparse
import shutil
import zipfile

ROOT = Path(__file__).resolve().parent.parent
VERSION = '0.5.0'
MODULES = ['mx2_desktop.py', 'mx2_webapp.py', 'mx2_device_monitor.py', 'mx2_native_bridge.py',
           'mx2_bridge.py', 'mx2_native.py', 'decode_mx2.py', 'summarize_midi.py',
           'mx2_runtime_lock.py', 'mx2_portable_transport.py', 'mx2_windows_feedback.py',
           'build_djay_mapping.py', 'build_djay_native_mapping.py', 'build_djay_windows_mapping.py',
           'mx2_native_transport.swift', 'mx2_midi_transport.swift', 'test_mx2_bridge.py', 'test_mx2_native.py',
           'test_decode_mx2.py', 'test_mx2_portable_transport.py', 'test_windows_mapping.py',
           'test_desktop_runtime.py', 'test_webapp.py', 'test_cheat_sheet.py', 'test_mx2_device_monitor.py']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, default=ROOT,
                        help='Source snapshot for runtime code and app resources')
    parser.add_argument('--destination', type=Path,
                        default=ROOT / 'release' / ('MX2-Companion-' + VERSION + '-source'))
    args = parser.parse_args()
    source_root = args.source_root.resolve()
    destination = args.destination.resolve()
    if destination.exists():
        raise SystemExit('Refusing to replace an existing source kit; choose a new --destination.')
    destination.mkdir(parents=True, exist_ok=True)
    for folder in ['tools', 'evidence', 'mappings', 'distribution', 'docs', '.github/workflows']:
        (destination / folder).mkdir(parents=True, exist_ok=True)
    for name in MODULES:
        shutil.copy2(source_root / 'tools' / name, destination / 'tools' / name)
    shutil.copy2(source_root / 'tools/mx2-midi-transport', destination / 'tools/mx2-midi-transport')
    shutil.copy2(source_root / 'DEMARRER-MX2.command', destination / 'DEMARRER-MX2.command')
    for name in ['LICENSE', 'LICENSING.md']:
        shutil.copy2(ROOT / name, destination / name)
    for name in ['midi-profile.json', 'native-protocol-map.json', 'djay-capabilities.json']:
        shutil.copy2(source_root / 'evidence' / name, destination / 'evidence' / name)
    for name in ['Traktor MX2 - Native RGB.djayMidiMapping', 'Traktor MX2 - Windows RGB.djayMidiMapping',
                 'Traktor MX2 - Visual Complete.djayMidiMapping']:
        shutil.copy2(source_root / 'mappings' / name, destination / 'mappings' / name)
    for name in ['build_desktop.py', 'build_dmg.py', 'build_classic_midi_package.py',
                 'export_source.py', 'export_github_site.py', 'BUILD-WINDOWS.ps1', 'BUILD-MAC.command',
                 'requirements-build.txt', 'requirements-windows.txt']:
        shutil.copy2(ROOT / 'distribution' / name, destination / 'distribution' / name)
    for folder in ['ui', 'docs', 'licenses']:
        shutil.copytree(source_root / 'distribution' / folder, destination / 'distribution' / folder,
                        dirs_exist_ok=True, ignore=shutil.ignore_patterns('__pycache__', '.DS_Store', '*.pyc'))
    shutil.copytree(ROOT / 'distribution/classic-midi', destination / 'distribution/classic-midi',
                    dirs_exist_ok=True)
    for folder in ['docs', 'distribution/site']:
        shutil.copytree(ROOT / 'distribution/site', destination / folder, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('downloads', '.DS_Store'))
    shutil.copy2(ROOT / 'distribution/github/workflows/pages.yml',
                 destination / '.github/workflows/pages.yml')
    shutil.copy2(ROOT / '.gitignore', destination / '.gitignore')
    (destination / 'README.md').write_text('''# MX2 Companion

Use a Traktor MX2 with djay Pro on Mac. Companion offers Native and MIDI modes, a guided setup, a searchable control reference and 293 mapping actions. The original Classic MIDI package runs the validated pre-app bridge from Terminal.

**[View the website](https://jean-ceyrien.github.io/mx2-companion/)** · **[Download the Mac installer](https://jean-ceyrien.github.io/mx2-companion/downloads/MX2-Companion-0.5.0-macOS-arm64.dmg)** · **[Download Classic MIDI](https://jean-ceyrien.github.io/mx2-companion/downloads/MX2-Classic-MIDI-0.5.0.zip)**

## Install Companion

1. Open the DMG and drag MX2 Companion into Applications.
2. Connect the MX2, choose Native or MIDI in Companion, then start the connection.
3. Import the matching mapping in djay. Select the virtual `MX2 for djay` device and disable the physical Traktor MX2 input to avoid duplicate commands.
4. Set main audio to MX2 channels 1–2 and headphone monitoring to 3–4.

The Mac installer targets Apple silicon. Windows source is included for testing but is not a validated release.

## Classic MIDI without Companion

Use [the Classic MIDI package](distribution/classic-midi/README.md) for the pre-app setup. Run the included Terminal launcher, import Visual Complete, and select the virtual `MX2 for djay` device in djay. Keep the launcher open while mixing. The mapping depends on its MIDI bridge for SHIFT, pad banks and feedback.

## Build and test

Build on macOS with `distribution/BUILD-MAC.command` (Python 3.12 and Xcode command-line tools). To create the DMG, run `python distribution/build_dmg.py` after the app build. Windows build instructions are in `distribution/BUILD-WINDOWS.ps1`.

Run `python3 -m unittest discover -s tools -p 'test_*.py'` for hardware-free checks. See [validation and limitations](distribution/docs/VALIDATION.md) for physical test scope and [third-party notices](distribution/docs/THIRD-PARTY-NOTICES.md) for dependencies and image attribution.

## Website

The static site is in `docs/`. The included GitHub Pages workflow publishes it from `main` after Pages is enabled for the repository.

## License and corresponding source

Copyright (C) 2026 Jean-Ceyrien and contributors. Original project code is licensed under GNU GPL version 3 only (GPL-3.0-only). You may modify and redistribute it under that license; there is no warranty. See [LICENSE](LICENSE), [licensing scope](LICENSING.md) and the third-party notices.

This source kit includes the Python and Swift sources, mappings, interface resources and build scripts for Companion 0.5.0 and Classic MIDI 0.5.0. The public release sources are the archived runtime sources; licensing and packaging were updated on 22 October 2026. Build on the target operating system. No controller, proprietary DJ application, credentials or personal session logs are included.
''')
    archive = Path(str(destination) + '.zip')
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as output:
        for path in sorted(destination.rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts and path.name != '.DS_Store':
                output.write(path, path.relative_to(destination.parent))
    print(archive)


if __name__ == '__main__':
    main()
