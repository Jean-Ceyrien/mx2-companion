#!/usr/bin/env python3
"""Build the MX2 virtual-endpoint mapping; no installed user files are changed."""
from collections import defaultdict
from pathlib import Path
import json
import plistlib
import re
import uuid

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / 'mappings/Traktor MX2 - Visual Complete.djayMidiMapping'
CAPABILITIES = ROOT / 'evidence/djay-capabilities.json'
FACTORY = Path('/Applications/djay Pro.app/Contents/Resources/MIDI Mappings')
# Deliberate three-slot macros: one input drives all three slots. Only slot1 feeds
# back to the single physical button, avoiding conflicting slot LED writers.
MACRO_ADDRESSES = {(typ, ch, number) for ch in (0, 1) for typ, number in ((1, 0), (3, 32))}
MACRO_ADDRESSES |= {(3, ch, 32) for ch in (2, 3)}


def canonical(path):
    return re.sub(r'^turntable[1-4]\.', 'turntable.', path)


def target_inventory():
    capabilities = json.loads(CAPABILITIES.read_text())
    valid = set(capabilities['metadata']) | set(capabilities['labels'])
    for file in FACTORY.glob('*.djayMidiMapping'):
        try:
            data = plistlib.loads(file.read_bytes())
        except (ValueError, plistlib.InvalidFileException):
            continue
        for row in data.get('controls', []) + data.get('outputs', []):
            if row.get('keyPath'):
                valid.add(canonical(row['keyPath']))
    return valid


def build():
    controls = []
    def add(channel, number, target, cc=False, rotary=False, feedback=True, hold=False, **extra):
        row = dict(keyPath=target, midiChannel=channel, midiData=number, midiMessageType=3 if cc else 1)
        if rotary:
            row.update(controlType='rotary-64')
        if hold:
            row['buttonMode'] = 'hold'
        if feedback and not cc:
            row['output'] = dict(midiMinValue=0.0, midiMaxValue=127.0)
        row.update(extra)
        controls.append(row)
    for side in range(2):
        deck = f'turntable{side + 1}'
        normal, shifted, strip = side, side + 2, side + 4
        for channel, shift in [(normal, False), (shifted, True)]:
            actions = {29: 'gotoBeginningAndPause' if shift else 'playPause',
                       28: 'gotoZero' if shift else 'cuePositionOrJumpConsideringPlayState1',
                       13: 'toggleQuantize' if shift else 'bpmSync',
                       14: 'resetSpeed' if shift else 'turntableIsSyncMaster',
                       15: 'matchKey' if shift else 'key', 8: 'deckSlipToggle',
                       9: 'reverse' if shift else 'censor', 31: 'loopInOut', 32: 'autoLoopOnOff'}
            for note, action in actions.items():
                add(channel, note, deck+'.'+action, hold=action=='censor')
            add(channel, 4, 'musicLibrary.focusSources' if shift else 'musicLibrary.focusQueue', feedback=False)
            add(channel, 5, 'musicLibrary.unmarkSelectedSongs' if shift else 'musicLibrary.markSelectedSongs', feedback=False)
            add(channel, 6, 'musicLibrary.togglePreview', feedback=False)
            add(channel, 7, 'musicLibrary.toggleLibraryVisible', feedback=False)
            add(channel, 30, f'musicLibrary.load{side + 1}NoInstantDouble' if shift else f'musicLibrary.load{side + 1}', feedback=False)
            add(channel, 16, 'musicLibrary.sourceRotary' if shift else 'musicLibrary.libraryRotary', cc=True, rotary=True)
            add(channel, 17, deck+('.autoLoopMoveRotary' if shift else '.skipRotary'), cc=True, rotary=True)
            add(channel, 18, deck+('.skipDurationRotary' if shift else '.autoLoopDurationRotary'), cc=True, rotary=True)
            add(channel, 19, deck+('.jogSeekMove' if shift else '.scratchingMove'), cc=True, rotary=True,
                rotarySensitivity=25.0, rotaryAcceleration=0)
            add(channel, 40, deck+'.speed', cc=True)
            for slot in range(1, 4):
                add(channel, slot, deck+f'.fx{slot}SelectNext' if shift else deck+f'.fx{slot}Enabled', feedback=not shift)
                add(channel, 32 + slot, deck+f'.fx{slot}ParameterValue', cc=True)
                add(channel, 32, deck+f'.fx{slot}WetDryValue', cc=True)
                if not shift:
                    add(channel, 0, deck+f'.fx{slot}Enabled', feedback=slot==1)
            if shift:
                add(channel, 0, deck+'.fxActive')
        # Touch is always normal-channel; shift seek never acquires scratchingMode.
        add(normal, 33, deck+'.scratchingMode', feedback=False, hold=True)
        add(normal, 34, deck+'.jogPitchBendMode', feedback=False, hold=True)
        add(normal, 35, deck+'.jogSeekMode', feedback=False, hold=True)
        for cc, target in [(32, deck+'.gain'), (33, deck+'.highEQ'), (34, deck+'.midEQ'),
                           (35, deck+'.lowEQ'), (40, f'mixer.lineVolume{side + 1}'), (36, deck+'.filter')]:
            add(strip, cc, target, cc=True)
        add(strip, 0, deck+'.fx1Enabled')
        add(strip, 1, deck+'.fx2Enabled')
        add(strip, 3, f'mixer.monitorActive{side + 1}')
        add(strip, 40, deck+'.filterKill')
        for slot in range(1, 4):
            add(strip, 40 + slot, deck+f'.fx{slot}Enabled')
            add(strip, 36 + slot, deck+f'.fx{slot}WetDryValue', cc=True)
        add(strip, 44, deck+'.instantFx4', hold=True)
        for shifted_pad in (False, True):
            pad_channel = side + (8 if shifted_pad else 6)
            for pad in range(8):
                add(pad_channel, pad, deck+(f'.clearCuePoint{pad + 1}' if shifted_pad else f'.cueOrJumpIfAlreadySet{pad + 1}'))
                stem = 4 - (pad % 4)
                # Normal upper pads mute, lower pads toggle solo; shifted inverses.
                solo = (pad >= 4) != shifted_pad
                add(pad_channel, 16 + pad, deck+f'.unmixerFourTrackChannel{stem}'+('Solo' if solo else 'Muted'))
                sample = f'sampler.turntable{side + 1}.player{pad + 1}'
                add(pad_channel, 32 + pad, sample+('.paused' if shifted_pad else '.playingConsideringHoldSetting'))
                size = ['003125', '00625', '0125', '025', '05', '1', '2', '4'][pad]
                action = f'autoLoop{size}BeatInterval' if shifted_pad else f'bounceLoop{size}BeatInterval'
                add(pad_channel, 48 + pad, deck+'.'+action, hold=not shifted_pad)
    for cc, target in [(32, 'mixer.masterLevel'), (33, 'mixer.monitorMix'), (34, 'mixer.monitorLevel'), (40, 'mixer.crossfade')]:
        add(15, cc, target, cc=True)
    add(15, 5, 'microphone.active')
    return dict(endpointName='MX2 for djay', schemeVersion=1, version=1,
                uuid=str(uuid.uuid5(uuid.NAMESPACE_URL, 'mx2-for-djay/visual-complete/v1')).upper(),
                editor='MX2 calibrated virtual endpoint builder', controls=controls)


def validate(mapping, valid=None):
    valid = target_inventory() if valid is None else valid
    addresses = defaultdict(list)
    for row in mapping['controls']:
        target = row['keyPath']
        if '.' not in target or canonical(target) not in valid:
            raise ValueError('Unproven target: '+target)
        if not (0 <= row['midiChannel'] <= 15 and 0 <= row['midiData'] <= 127):
            raise ValueError('Invalid MIDI address')
        if row.get('condition') or row.get('modifier'):
            raise ValueError('Bridge handles modes; no native class conditions/modifiers allowed')
        addresses[(row['midiMessageType'], row['midiChannel'], row['midiData'])].append(row)
    for address, rows in addresses.items():
        if len(rows) > 1:
            if address not in MACRO_ADDRESSES or len(rows) != 3:
                raise ValueError(f'Unintended duplicate address {address}')
            suffix = 'Enabled' if address[0] == 1 else 'WetDryValue'
            expected = {f'turntable{address[1] % 2 + 1}.fx{i}{suffix}' for i in range(1, 4)}
            if {row['keyPath'] for row in rows} != expected:
                raise ValueError(f'Unexpected macro targets {address}')
            if sum('output' in row for row in rows) > 1:
                raise ValueError('Macro has competing feedback writers')
    return mapping


def main():
    mapping = validate(build())
    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_bytes(plistlib.dumps(mapping, sort_keys=False))
    print(json.dumps(dict(output=str(OUTPUT), rows=len(mapping['controls']), endpoint=mapping['endpointName'])))


if __name__ == '__main__':
    main()
