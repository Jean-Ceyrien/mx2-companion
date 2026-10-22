"""Windows loopMIDI version: identical actions, disjoint feedback channels."""
from copy import deepcopy
import json
import plistlib
import uuid
from build_djay_native_mapping import build as native_build
from build_djay_mapping import ROOT
from mx2_windows_feedback import encode_feedback

OUTPUT = ROOT / 'mappings/Traktor MX2 - Windows RGB.djayMidiMapping'


def remap(row, parent=None):
    inherited = parent or row
    kind = row.get('midiMessageType', inherited['midiMessageType'])
    status = (176 if kind == 3 else 144) | row.get('midiChannel', inherited['midiChannel'])
    new_status, data = encode_feedback(status, [row.get('midiData', inherited['midiData']), 0])
    row.update(midiChannel=new_status & 15, midiData=data[0], midiMessageType=kind)


def build():
    mapping = deepcopy(native_build())
    mapping['uuid'] = str(uuid.uuid5(uuid.NAMESPACE_URL, 'mx2-for-djay/windows-rgb/v1')).upper()
    for row in mapping['controls']:
        if 'output' in row:
            if row['midiChannel'] in (2, 3, 8, 9):
                # Router intentionally ignores shifted-bank feedback on macOS too.
                del row['output']
            else:
                remap(row['output'], row)
    for row in mapping['outputs']:
        remap(row)
    return mapping


if __name__ == '__main__':
    mapping = build()
    OUTPUT.write_bytes(plistlib.dumps(mapping, sort_keys=False))
    print(json.dumps({'controls': len(mapping['controls']), 'output': str(OUTPUT)}))
