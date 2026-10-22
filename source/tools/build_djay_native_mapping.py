#!/usr/bin/env python3
"""Add factory-proven djay outputs to the unchanged calibrated control mapping.

Virtual output contract (zero-based MIDI channels):
  CC14:0/1 = deck1/2 mono meter, range0..127.
  NOTE14:2/3 = deck1/2 approaching track end, off0/on127.
Loop state already arrives through the base mapping's normal deck note32.

Static output evidence, installed djay factory mappings:
- Pioneer DDJ-FLX6: turntableN.monoMeter, controlType=control, MIDI CC.
- Pioneer DDJ-WeGO3: turntableN.display.isApproachingEndOfSong, MIDI Note.
- Numark NS6II additionally exposes turntableN.display.songProgress via CC.
- Reloop Mixon4 exposes mixer.masterLeftMeter/masterRightMeter via CC.
No exact master clip, loaded flag, or remaining-time output path was found in
factory output entries; none is invented. Song progress/master meters are not
emitted by this revision because the bridge contract needs only meters/end flag.
These paths are static factory evidence; runtime output delivery still needs test.
"""
from copy import deepcopy
from pathlib import Path
import json
import plistlib
import uuid

from build_djay_mapping import build as build_base, validate as validate_base, FACTORY, ROOT

OUTPUT = ROOT / 'mappings/Traktor MX2 - Native RGB.djayMidiMapping'
OUTPUT_CONTRACT = {(3, 14, 0): 'turntable1.monoMeter',
                   (3, 14, 1): 'turntable2.monoMeter',
                   (1, 14, 2): 'turntable1.display.isApproachingEndOfSong',
                   (1, 14, 3): 'turntable2.display.isApproachingEndOfSong'}


def factory_output_targets():
    """Return actual shipped output paths, excluding arbitrary model-name guesses."""
    targets = set()
    for file in FACTORY.glob('*.djayMidiMapping'):
        try:
            mapping = plistlib.loads(file.read_bytes())
        except (ValueError, plistlib.InvalidFileException):
            continue
        for row in mapping.get('outputs', []):
            if row.get('keyPath'):
                targets.add(row['keyPath'])
    return targets


def build():
    mapping = deepcopy(build_base())
    mapping['uuid'] = str(uuid.uuid5(uuid.NAMESPACE_URL, 'mx2-for-djay/native-rgb/v1')).upper()
    mapping['editor'] = 'MX2 native RGB virtual endpoint builder'
    outputs = []
    for (kind, channel, number), path in OUTPUT_CONTRACT.items():
        output = dict(keyPath=path, midiChannel=channel, midiData=number, midiMessageType=kind,
                      midiMinValue=0.0, midiMaxValue=127.0)
        if kind == 3:
            output['controlType'] = 'control'
        outputs.append(output)
    mapping['outputs'] = outputs
    return mapping


def validate(mapping):
    validate_base(mapping)
    if mapping['controls'] != build_base()['controls']:
        raise ValueError('Native mapping must preserve base control bindings exactly')
    if mapping['endpointName'] != 'MX2 for djay':
        raise ValueError('Incorrect virtual endpoint name')
    if 'customClassName' in mapping:
        raise ValueError('Native custom class is not part of this bridge contract')
    targets = factory_output_targets()
    addresses = set()
    for row in mapping.get('outputs', []):
        address = (row['midiMessageType'], row['midiChannel'], row['midiData'])
        if address in addresses:
            raise ValueError('Duplicate output address')
        addresses.add(address)
        if row['keyPath'] not in targets:
            raise ValueError('Output path has no factory evidence: '+row['keyPath'])
        if OUTPUT_CONTRACT.get(address) != row['keyPath']:
            raise ValueError('Output does not match bridge contract')
        if row.get('midiMinValue') != 0 or row.get('midiMaxValue') != 127:
            raise ValueError('Output range must remain0..127')
        if address[0] == 3 and row.get('controlType') != 'control':
            raise ValueError('Meter must use the factory control output type')
    if addresses != set(OUTPUT_CONTRACT):
        raise ValueError('Missing bridge output')
    return mapping


def main():
    mapping = validate(build())
    OUTPUT.write_bytes(plistlib.dumps(mapping, sort_keys=False))
    print(json.dumps(dict(output=str(OUTPUT), endpoint=mapping['endpointName'],
                          controls=len(mapping['controls']), outputs=mapping['outputs'])))


if __name__ == '__main__':
    main()
