#!/usr/bin/env python3
"""Package the validated pre-app MIDI bridge, mapping and launcher."""
from pathlib import Path
import plistlib
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'release/MX2-Classic-MIDI-0.5.0.zip'
FOLDER = 'MX2 Classic MIDI'
FILES = [
    'LICENSE',
    'LICENSING.md',
    'DEMARRER-MX2.command',
    'mappings/Traktor MX2 - Visual Complete.djayMidiMapping',
    'tools/mx2_bridge.py',
    'tools/mx2_midi_transport.swift',
    'tools/mx2-midi-transport',
    'tools/mx2_runtime_lock.py',
    'tools/summarize_midi.py',
    'evidence/midi-profile.json',
]


def main():
    mapping = ROOT / FILES[1]
    assert len(plistlib.loads(mapping.read_bytes())['controls']) == 293
    subprocess.run([str(ROOT / 'tools/mx2-midi-transport'), '--help'], check=True,
                   stdout=subprocess.DEVNULL)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUT, 'w', zipfile.ZIP_DEFLATED) as package:
        for name in FILES:
            path = ROOT / name
            if not path.is_file():
                raise FileNotFoundError(path)
            info = zipfile.ZipInfo.from_file(path, f'{FOLDER}/{name}')
            info.compress_type = zipfile.ZIP_DEFLATED
            package.writestr(info, path.read_bytes())
        guide = ROOT / 'distribution/classic-midi/README.md'
        package.write(guide, f'{FOLDER}/README.md')
        package.write(ROOT / 'distribution/docs/THIRD-PARTY-NOTICES.md',
                      f'{FOLDER}/THIRD-PARTY-NOTICES.md')
    print(OUT)


if __name__ == '__main__':
    main()
