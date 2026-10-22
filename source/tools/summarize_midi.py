#!/usr/bin/env python3
"""Summarize saved probe MIDI JSONL as source-aware MIDI 1.0 byte streams."""
import argparse
from collections import Counter
import json
import sys

KINDS = {0x80: 'note_off', 0x90: 'note_on', 0xa0: 'poly_pressure', 0xb0: 'control_change',
         0xc0: 'program_change', 0xd0: 'channel_pressure', 0xe0: 'pitch_bend',
         0xf0: 'sysex', 0xf1: 'time_code_quarter_frame', 0xf2: 'song_position',
         0xf3: 'song_select', 0xf6: 'tune_request', 0xf8: 'timing_clock',
         0xfa: 'start', 0xfb: 'continue', 0xfc: 'stop', 0xfe: 'active_sensing', 0xff: 'reset'}


class Stream:
    def __init__(self):
        self.running = None
        self.pending = None
        self.data = []
        self.sysex_length = None
        self.errors = Counter()

    @staticmethod
    def length(status):
        if status < 0xf0:
            return 1 if status & 0xf0 in (0xc0, 0xd0) else 2
        return {0xf1: 1, 0xf2: 2, 0xf3: 1}.get(status, 0)

    def interrupt(self):
        if self.pending is not None:
            self.errors['truncated_messages'] += 1
            self.pending, self.data = None, []
        if self.sysex_length is not None:
            self.errors['truncated_sysex'] += 1
            self.sysex_length = None

    def feed(self, data):
        output = []
        for value in data:
            if value >= 0xf8:
                if value in KINDS:
                    output.append((value, []))
                else:
                    self.errors['unknown_status_bytes'] += 1
                continue  # Realtime never disturbs message assembly/running status.
            if self.sysex_length is not None:
                if value == 0xf7:
                    output.append((0xf0, {'payload_bytes': self.sysex_length}))
                    self.sysex_length = None
                    continue
                if value < 0x80:
                    self.sysex_length += 1
                    continue
                self.interrupt()  # New non-realtime status abandons unfinished SysEx.
            if value >= 0x80:
                self.interrupt()
                if value < 0xf0:
                    self.running = self.pending = value
                else:
                    self.running = None
                    if value == 0xf0:
                        self.sysex_length = 0
                    elif value in (0xf1, 0xf2, 0xf3):
                        self.pending = value
                    elif value == 0xf6:
                        output.append((value, []))
                    else:  # Undefined F4/F5 or EOX outside SysEx.
                        self.errors['unknown_status_bytes'] += 1
                continue
            if self.pending is None:
                if self.running is None:
                    self.errors['orphan_data_bytes'] += 1
                    continue
                self.pending = self.running
            self.data.append(value)
            if len(self.data) == self.length(self.pending):
                output.append((self.pending, self.data))
                self.pending, self.data = None, []
        return output

    def finish(self):
        self.interrupt()


class Summary:
    def __init__(self):
        self.sources = {}
        self.invalid_records = 0
        self.non_midi_records = 0
        self.session = 0

    def source(self, row):
        # ID and endpoint jointly avoid merging unrelated endpoints with duplicate IDs.
        key = (self.session, str(row.get('id', 'unknown')), str(row.get('endpoint_ref', 'unknown')))
        if key not in self.sources:
            self.sources[key] = dict(stream=Stream(), packets=0, bytes=0, packet_lengths=Counter(),
                                     statuses=Counter(), channels=Counter(), groups={}, sysex_lengths=Counter(),
                                     first_ns=None, last_ns=None, midi_timestamp_first=None, midi_timestamp_last=None)
        return self.sources[key]

    def feed(self, row):
        if row.get('event') == 'session':
            self.session += 1
        if row.get('event') != 'midi_input':
            self.non_midi_records += 1
            return
        try:
            data = bytes.fromhex(row['bytes_hex'])
            if row.get('byte_count', len(data)) != len(data):
                raise ValueError('byte count mismatch')
        except (KeyError, TypeError, ValueError):
            self.invalid_records += 1
            return
        source = self.source(row)
        source['packets'] += 1
        source['bytes'] += len(data)
        source['packet_lengths'][len(data)] += 1
        for field, first, last in [('monotonic_ns', 'first_ns', 'last_ns'), ('midi_timestamp', 'midi_timestamp_first', 'midi_timestamp_last')]:
            if field in row:
                if source[first] is None:
                    source[first] = row[field]
                source[last] = row[field]
        for status, values in source['stream'].feed(data):
            source['statuses'][status] += 1
            if status == 0xf0:
                source['sysex_lengths'][values['payload_bytes']] += 1
                continue
            channel = (status & 15) + 1 if status < 0xf0 else None
            if channel is not None:
                source['channels'][channel] += 1
            kind = status & 0xf0 if status < 0xf0 else status
            number = values[0] if kind in (0x80, 0x90, 0xa0, 0xb0) else None
            value = None
            if kind in (0xe0, 0xf2):
                value = values[0] | (values[1] << 7)
            elif values:
                value = values[-1]
            key = (status, channel, number)
            group = source['groups'].setdefault(key, dict(count=0, values=Counter()))
            group['count'] += 1
            if value is not None:
                group['values'][value] += 1

    def finish(self):
        output = []
        totals = Counter()
        errors = Counter()
        for (session, identity, endpoint), source in sorted(self.sources.items()):
            source['stream'].finish()
            errors.update(source['stream'].errors)
            groups = []
            for (status, channel, number), data in sorted(source['groups'].items()):
                kind = status & 0xf0 if status < 0xf0 else status
                values = sorted(data['values'])
                item = dict(status=f'{status:02x}', kind=KINDS[kind], channel=channel,
                            count=data['count'], min=min(values) if values else None,
                            max=max(values) if values else None, unique_values=values,
                            value_counts={str(k): data['values'][k] for k in values})
                if number is not None:
                    item['controller' if kind == 0xb0 else 'note'] = number
                groups.append(item)
            output.append(dict(session=session, id=identity, endpoint_ref=endpoint, packets=source['packets'],
                               bytes=source['bytes'], packet_length_counts=dict(sorted(source['packet_lengths'].items())),
                               first_monotonic_ns=source['first_ns'], last_monotonic_ns=source['last_ns'],
                               first_midi_timestamp=source['midi_timestamp_first'], last_midi_timestamp=source['midi_timestamp_last'],
                               messages=sum(source['statuses'].values()),
                               status_counts={f'{k:02x}': v for k, v in sorted(source['statuses'].items())},
                               channel_counts=dict(sorted(source['channels'].items())), groups=groups,
                               sysex_payload_length_counts=dict(source['sysex_lengths']), errors=dict(source['stream'].errors)))
            totals.update(packets=source['packets'], bytes=source['bytes'], messages=sum(source['statuses'].values()))
        return dict(format='MX2 MIDI stream summary v1', totals=dict(totals), sources=output,
                    errors=dict(errors), invalid_records=self.invalid_records, ignored_non_midi_records=self.non_midi_records,
                    limitations=['MIDI channels are numbered 1–16; notes/controllers are raw decimal IDs.',
                                 'Physical control names and relative encoder interpretation require separate evidence.',
                                 'Timestamps are preserved without inferring clock units or converting device speed.',
                                 'SysEx payloads are counted without retaining potentially unbounded message bytes.',
                                 'A capture beginning/ending mid-message may contain orphan/truncated data.'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path', nargs='?', default='-')
    args = parser.parse_args()
    summary = Summary()
    source = sys.stdin if args.path == '-' else open(args.path, encoding='utf-8')
    try:
        for line in source:
            try:
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise ValueError('Expected object')
                summary.feed(row)
            except (TypeError, ValueError):
                summary.invalid_records += 1
    finally:
        if source is not sys.stdin:
            source.close()
    result = summary.finish()
    result['input'] = args.path
    print(json.dumps(result, indent=2, sort_keys=True))
    return 1 if result['invalid_records'] or result['errors'] else 0


if __name__ == '__main__':
    sys.exit(main())
