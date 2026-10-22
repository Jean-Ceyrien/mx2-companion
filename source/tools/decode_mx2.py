#!/usr/bin/env python3
"""Offline, stateful MX2 JSONL input decoder. No device access or writes."""
import argparse
from collections import Counter
import json
import signal
import struct
import sys

# Verified arm64 descriptor call names/addresses from evidence/native-control-map.json.
# Control82 and descriptor bits83-87 remain unnamed; no inferred contiguous map.
BUTTONS = {0: 'left.fx.buttons.1',
 1: 'left.fx.buttons.2',
 2: 'left.fx.buttons.3',
 3: 'left.fx.buttons.4',
 4: 'left.browse.favorite',
 5: 'left.browse.add_to_list',
 6: 'left.browse.preview',
 7: 'left.browse.view',
 8: 'left.flux',
 9: 'left.reverse',
 10: 'left.mode.turntable',
 11: 'left.mode.jogwheel',
 12: 'left.shift',
 13: 'left.sync',
 14: 'left.master',
 15: 'left.key_lock',
 16: 'left.hotcues',
 17: 'left.stems',
 18: 'left.pattern',
 19: 'left.flux_loop',
 20: 'left.pads.1',
 21: 'left.pads.2',
 22: 'left.pads.3',
 23: 'left.pads.4',
 24: 'left.pads.5',
 25: 'left.pads.6',
 26: 'left.pads.7',
 27: 'left.pads.8',
 28: 'left.cue',
 29: 'left.play',
 30: 'right.fx.buttons.1',
 31: 'right.fx.buttons.2',
 32: 'right.fx.buttons.3',
 33: 'right.fx.buttons.4',
 34: 'right.browse.favorite',
 35: 'right.browse.add_to_list',
 36: 'right.browse.preview',
 37: 'right.browse.view',
 38: 'right.flux',
 39: 'right.reverse',
 40: 'right.mode.turntable',
 41: 'right.mode.jogwheel',
 42: 'right.shift',
 43: 'right.sync',
 44: 'right.master',
 45: 'right.key_lock',
 46: 'right.hotcues',
 47: 'right.stems',
 48: 'right.pattern',
 49: 'right.flux_loop',
 50: 'right.pads.1',
 51: 'right.pads.2',
 52: 'right.pads.3',
 53: 'right.pads.4',
 54: 'right.pads.5',
 55: 'right.pads.6',
 56: 'right.pads.7',
 57: 'right.pads.8',
 58: 'right.cue',
 59: 'right.play',
 60: 'mixer.channels.1.deck_fx_assign.1',
 61: 'mixer.channels.1.deck_fx_assign.2',
 62: 'mixer.channels.1.channel_fx.on',
 63: 'mixer.channels.1.cue',
 64: 'mixer.channels.2.deck_fx_assign.1',
 65: 'mixer.channels.2.deck_fx_assign.2',
 66: 'mixer.channels.2.channel_fx.on',
 67: 'mixer.channels.2.cue',
 68: 'mixer.channel_fx.fx1',
 69: 'mixer.channel_fx.fx2',
 70: 'mixer.channel_fx.fx3',
 71: 'mixer.channel_fx.fx4',
 72: 'mixer.channel_fx.filter',
 73: 'mixer.mic',
 74: 'left.browse.encoder.push',
 75: 'left.loop_move.push',
 76: 'left.loop_size.push',
 77: 'right.browse.encoder.push',
 78: 'right.loop_move.push',
 79: 'right.loop_size.push',
 80: 'left.jogwheel.touch',
 81: 'right.jogwheel.touch'}
ANALOGS = {0: 'left.fx.knobs.1',
 1: 'left.fx.knobs.2',
 2: 'left.fx.knobs.3',
 3: 'left.fx.knobs.4',
 4: 'right.fx.knobs.1',
 5: 'right.fx.knobs.2',
 6: 'right.fx.knobs.3',
 7: 'right.fx.knobs.4',
 8: 'mixer.channels.1.gain',
 9: 'mixer.channels.1.eq.high',
 10: 'mixer.channels.1.eq.mid',
 11: 'mixer.channels.1.eq.low',
 12: 'mixer.channels.1.channel_fx.amount',
 13: 'mixer.channels.2.gain',
 14: 'mixer.channels.2.eq.high',
 15: 'mixer.channels.2.eq.mid',
 16: 'mixer.channels.2.eq.low',
 17: 'mixer.channels.2.channel_fx.amount',
 18: 'mixer.main.volume',
 19: 'mixer.cue_mix',
 20: 'mixer.cue_vol',
 21: 'mixer.channels.1.volume',
 22: 'mixer.channels.2.volume',
 23: 'mixer.xfader',
 24: 'left.pitch.fader',
 25: 'right.pitch.fader'}
ENCODERS = {0: 'left.browse.encoder',
 1: 'left.loop_move',
 2: 'left.loop_size',
 3: 'right.browse.encoder',
 4: 'right.loop_move',
 5: 'right.loop_size'}
JOGS = {0: 'left.jogwheel', 1: 'right.jogwheel'}
ADDRESSES = {'analog': {0: '0x1002772b8',
            1: '0x1002772fc',
            2: '0x100277340',
            3: '0x100277384',
            4: '0x100277e48',
            5: '0x100277e84',
            6: '0x100277ec0',
            7: '0x100277efc',
            8: '0x100276ae4',
            9: '0x100276b3c',
            10: '0x100276b94',
            11: '0x100276be4',
            12: '0x100276d44',
            13: '0x100276e74',
            14: '0x100276ec4',
            15: '0x100276f14',
            16: '0x100276f64',
            17: '0x1002770ac',
            18: '0x1002768dc',
            19: '0x100276920',
            20: '0x100276964',
            21: '0x100276c34',
            22: '0x100276fb4',
            23: '0x1002769ac',
            24: '0x100277d8c',
            25: '0x100278924'},
 'button': {0: '0x1002773c8',
            1: '0x10027740c',
            2: '0x100277450',
            3: '0x100277494',
            4: '0x1002774e0',
            5: '0x100277534',
            6: '0x100277580',
            7: '0x1002775c0',
            8: '0x100277650',
            9: '0x10027769c',
            10: '0x1002776e8',
            11: '0x100277730',
            12: '0x1002777d8',
            13: '0x10027781c',
            14: '0x100277868',
            15: '0x1002778b0',
            16: '0x1002778fc',
            17: '0x100277944',
            18: '0x100277990',
            19: '0x1002779d8',
            20: '0x100277ab4',
            21: '0x100277b00',
            22: '0x100277b4c',
            23: '0x100277b98',
            24: '0x100277be4',
            25: '0x100277c30',
            26: '0x100277c7c',
            27: '0x100277cc8',
            28: '0x100277d0c',
            29: '0x100277d50',
            30: '0x100277f44',
            31: '0x100277f8c',
            32: '0x100277fd4',
            33: '0x10027801c',
            34: '0x100278064',
            35: '0x1002780b8',
            36: '0x100278104',
            37: '0x100278148',
            38: '0x1002781dc',
            39: '0x100278224',
            40: '0x100278270',
            41: '0x1002782bc',
            42: '0x100278368',
            43: '0x1002783b0',
            44: '0x1002783fc',
            45: '0x100278444',
            46: '0x10027848c',
            47: '0x1002784d8',
            48: '0x100278520',
            49: '0x100278568',
            50: '0x100278644',
            51: '0x100278690',
            52: '0x1002786dc',
            53: '0x100278728',
            54: '0x100278774',
            55: '0x1002787c0',
            56: '0x10027880c',
            57: '0x100278858',
            58: '0x10027889c',
            59: '0x1002788e4',
            60: '0x100276a04',
            61: '0x100276a54',
            62: '0x100276cec',
            63: '0x100276aa0',
            64: '0x100276d94',
            65: '0x100276de4',
            66: '0x10027705c',
            67: '0x100276e30',
            68: '0x1002770f8',
            69: '0x100277144',
            70: '0x100277190',
            71: '0x1002771dc',
            72: '0x100277230',
            73: '0x100277274',
            74: '0x10027760c',
            75: '0x100277a20',
            76: '0x100277a68',
            77: '0x100278194',
            78: '0x1002785b0',
            79: '0x1002785f8',
            80: '0x100277790',
            81: '0x10027831c'},
 'encoder': {0: '0x10027760c',
             1: '0x100277a20',
             2: '0x100277a68',
             3: '0x100278194',
             4: '0x1002785b0',
             5: '0x1002785f8'},
 'jog': {0: '0x100277790', 1: '0x10027831c'}}

def signed32(value):
    return (value + 2**31) % 2**32 - 2**31


def jog_delta(current, previous):
    value = signed32(current - previous)
    if value > 480:
        value -= 960
    if value < -480:
        value += 960
    return value


class Decoder:
    def __init__(self, initial=False):
        self.state = {}
        self.initial = initial
        self.frames = Counter()
        self.events = Counter()
        self.errors = 0
        self.first_ns = None
        self.last_ns = None

    def decode(self, row):
        if row.get('event') == 'session':
            self.state.clear()
            return []
        if row.get('event') != 'hid_input':
            return []
        metadata = {k: row[k] for k in ('id', 'label', 'monotonic_ns', 'elapsed_ns', 'report_id', 'report_type', 'status') if k in row}
        def error(reason):
            self.errors += 1
            return [dict(metadata, event='decode_error', reason=reason, bytes_hex=row.get('bytes_hex'))]
        if row.get('status', 0) != 0:
            return error('Nonzero HID callback status; frame ignored')
        try:
            data = bytes.fromhex(row['bytes_hex'])
            rid = row['report_id']
        except (KeyError, ValueError, TypeError):
            return error('Invalid frame encoding')
        self.frames[f'{rid}:{len(data)}'] += 1
        timestamp = row.get('monotonic_ns')
        if timestamp is not None:
            if self.first_ns is None:
                self.first_ns = timestamp
            self.last_ns = timestamp
        if not data or data[0] != rid:
            return error('Expected report ID included at byte zero')
        expected = {1: 15, 2: 53, 3: 20}.get(rid)
        if expected is None or len(data) != expected or row.get('byte_count', len(data)) != len(data):
            return error('Unknown report ID or unexpected frame length')
        payload = data[1:]
        output = []
        device = row.get('id', '<unspecified>')
        def change(kind, index, value, names=None, **extra):
            key = (device, kind, index)
            previous = self.state.get(key)
            self.state[key] = value
            if previous == value or (previous is None and not self.initial):
                return
            item = dict(metadata, event='control', kind=kind, index=index, raw=value,
                        initial=previous is None, **extra)
            if names and index in names:
                item.update(control=names[index], mapping_evidence='static_descriptor', descriptor_address=ADDRESSES[kind][index])
            else:
                item.update(control=f'raw.{kind}.{index}', mapping_evidence='unknown')
            if previous is not None:
                item['previous_raw'] = previous
                if kind == 'encoder':
                    delta = value - previous
                    if delta > 7:
                        delta -= 16
                    if delta < -7:
                        delta += 16
                    item['delta'] = delta
                elif kind == 'jog':
                    item['delta'] = jog_delta(value, previous)
                elif kind == 'analog':
                    item['delta_raw'] = value - previous
            self.events[kind] += 1
            output.append(item)
        if rid == 1:
            for i in range(83):
                change('button', i, (payload[i // 8] >> (i % 8)) & 1, BUTTONS)
            for i in range(83, 88):
                change('unassigned_bit', i, (payload[i // 8] >> (i % 8)) & 1)
            for i in range(6):
                change('encoder', i, (payload[11 + i // 2] >> (4 * (i % 2))) & 15, ENCODERS)
        elif rid == 2:
            for i, value in enumerate(struct.unpack('<26H', payload)):
                change('analog', i, value, ANALOGS)
        else:
            change('jog_header', 0, payload[:3].hex())
            for i in range(2):
                raw_metadata, position = struct.unpack_from('<II', payload, 3 + i * 8)
                change('jog', i, position, JOGS,
                       raw_metadata_u32=raw_metadata, raw_metadata_hex=payload[3 + i * 8:7 + i * 8].hex(),
                       position_signed32=signed32(position))
        return output

    def summary(self):
        return dict(event='decode_summary', frames=dict(self.frames), changes=dict(self.events),
                    errors=self.errors, first_monotonic_ns=self.first_ns, last_monotonic_ns=self.last_ns,
                    convention='report ID included at byte zero; exact known lengths required')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path', nargs='?', default='-', help='probe JSONL file, or - for stdin')
    parser.add_argument('--initial', action='store_true', help='also emit first observed state; never synthesize a delta')
    parser.add_argument('--summary-only', action='store_true')
    args = parser.parse_args()
    decoder = Decoder(initial=args.initial)
    source = sys.stdin if args.path == '-' else open(args.path, encoding='utf-8')
    try:
        for number, line in enumerate(source, 1):
            try:
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise ValueError('JSON record must be an object')
                events = decoder.decode(row)
            except (ValueError, TypeError) as exc:
                decoder.errors += 1
                events = [dict(event='decode_error', line=number, reason=str(exc))]
            if not args.summary_only:
                for event in events:
                    print(json.dumps(event, sort_keys=True))
    finally:
        if source is not sys.stdin:
            source.close()
    print(json.dumps(decoder.summary(), sort_keys=True))
    return 1 if decoder.errors else 0


if __name__ == '__main__':
    # Behave like a normal Unix filter when a consumer such as head closes early.
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    sys.exit(main())
