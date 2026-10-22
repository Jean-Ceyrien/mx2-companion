#!/usr/bin/env python3
"""Windows HID/MIDI transport for the MX2 native bridge (hardware validation pending).

Dependencies: hidapi (imports as hid), mido, python-rtmidi.
Create one loopMIDI port first: MX2 for djay. Configure
MX2_MIDI_TO_DJAY / MX2_MIDI_FROM_DJAY to override these exact base names.
Windows mapping outputs must exclusively use zero-based channels 10..14.
Those channels are filtered as feedback; own input messages on 0..9,15 are ignored.
All HID operations run on one worker; there are no firmware or mode writes.
"""
import json
import os
import re
import signal
import sys
import threading
import time

VENDOR, PRODUCT = 0x17CC, 0x2420


def parse_command(line):
    """Match the Swift transport's restricted JSON command vocabulary."""
    try:
        row = json.loads(line)
        target, values = row['to'], row['bytes']
    except (ValueError, KeyError, TypeError):
        raise ValueError('Expected a JSON object with to and bytes') from None
    if not isinstance(values, list) or not 0 < len(values) <= 255:
        raise ValueError('Expected 1 to 255 integer bytes')
    if any(type(v) is not int or not 0 <= v <= 255 for v in values):
        raise ValueError('Invalid byte value')
    if target == 'hid-leds':
        if len(values) != 105 or any(v > 127 for v in values):
            raise ValueError('hid-leds requires exactly 105 bytes in 0..127')
    elif target == 'virtual':
        if len(values) % 3 or any(values[i] & 0xF0 not in (0x80, 0x90, 0xB0)
                                 or values[i + 1] > 127 or values[i + 2] > 127
                                 for i in range(0, len(values), 3)):
            raise ValueError('virtual requires complete Note/CC triples')
    else:
        raise ValueError('Only virtual and hid-leds targets are accepted')
    return target, values


def resolve_port(requested, names):
    """RtMidi Windows may append an enumeration number to a port name."""
    if not requested or requested.casefold().startswith('traktor mx2'):
        raise ValueError('Select a dedicated virtual MIDI port, not the hardware port')
    if names.count(requested) == 1:
        return requested
    matches = [n for n in names if re.fullmatch(re.escape(requested) + r' \d+', n)]
    if len(matches) != 1:
        raise ValueError(f'Expected one MIDI port named {requested!r}; start loopMIDI and create the configured port')
    return matches[0]


def matching_devices(hid):
    return [row for row in hid.enumerate(VENDOR, PRODUCT)
            if row.get('vendor_id') == VENDOR and row.get('product_id') == PRODUCT
            and row.get('usage_page') == 0xFF01 and row.get('usage') == 0
            and row.get('path')]


class Transport:
    def __init__(self, hid, mido, emit, to_djay='MX2 for djay', from_djay='MX2 for djay'):
        self.hid, self.mido, self.emit = hid, mido, emit
        self.to_djay, self.from_djay = to_djay, from_djay
        self.stopping = threading.Event()
        self.send_lock = threading.Lock()
        self.led_lock = threading.Lock()
        self.pending_leds = None  # Latest complete image replaces stale queued images.
        self.output = self.input = self.device = self.path = None
        self.thread = None
        self.last_unavailable = None

    def start(self):
        out_name = resolve_port(self.to_djay, self.mido.get_output_names())
        in_name = resolve_port(self.from_djay, self.mido.get_input_names())
        try:
            self.output = self.mido.open_output(out_name)
            self.input = self.mido.open_input(in_name, callback=self.feedback)
        except Exception:
            self.close()
            raise
        self.thread = threading.Thread(target=self.hardware_loop, name='MX2 HID', daemon=True)
        self.thread.start()
        self.emit('ready_native', virtual_name=self.to_djay, midi_to_djay=out_name,
                  midi_from_djay=in_name, vendor_id=VENDOR, product_id=PRODUCT,
                  usage_page=0xFF01, usage=0, manual_app_mode_required=True,
                  automatic_mode_switch=False, platform_hardware_validated=False)

    def feedback(self, message):
        data = message.bytes()
        # loopMIDI echoes the bridge's own input messages on this same bus.
        # Windows mapping feedback exclusively uses reserved channels 10..14.
        # Never relay our controls on channels 0..9 or 15 back into the router.
        if (not self.stopping.is_set() and len(data) == 3
                and data[0] & 0xF0 in (0x80, 0x90, 0xB0)
                and 10 <= (data[0] & 15) <= 14):
            self.emit('feedback', bytes=data, midi_timestamp=time.monotonic_ns())

    def accept(self, line):
        try:
            target, values = parse_command(line)
        except ValueError as error:
            self.emit('error', operation='validate_command', message=str(error))
            return
        if target == 'hid-leds':
            with self.led_lock:
                self.pending_leds = values
            return
        if any(10 <= (values[i] & 15) <= 14 for i in range(0, len(values), 3)):
            self.emit('error', operation='validate_command', message='Channels 10..14 are reserved for djay feedback')
            return
        try:
            with self.send_lock:
                if self.stopping.is_set() or self.output is None:
                    return
                for i in range(0, len(values), 3):
                    self.output.send(self.mido.Message.from_bytes(values[i:i + 3]))
            self.emit('sent', to='virtual', bytes=values)
        except Exception as error:
            self.emit('error', operation='send_virtual', message=str(error))

    def input_report(self, data, seed=False):
        # hidapi includes the report ID for numbered reports. Windows can pad
        # every read to the longest report; trim only known IDs to exact sizes.
        if not data:
            return
        data = list(data)
        size = {1: 15, 2: 53, 3: 20}.get(data[0])
        if size is not None and len(data) >= size:
            data = data[:size]
        self.emit('hid_input', id=self.device_id(), report_id=data[0],
                  bytes_hex=bytes(data).hex(), count=len(data), status=0, seed=seed)

    def device_id(self):
        return self.path.decode('utf-8', 'replace') if isinstance(self.path, bytes) else str(self.path)

    def disconnect(self):
        if self.device is None:
            return
        identifier = self.device_id()
        try:
            self.device.close()
        except Exception:
            pass
        self.device = self.path = None
        self.emit('hid_removed', id=identifier)

    def refresh_device(self):
        rows = matching_devices(self.hid)
        if len(rows) != 1:
            self.disconnect()
            message = ('Connect one Traktor MX2.' if not rows else
                       'Multiple matching MX2 devices; refusing ambiguous routing.')
            if message != self.last_unavailable:
                self.emit('hardware_unavailable', message=message, matching_devices=len(rows))
                self.last_unavailable = message
            return
        path = rows[0]['path']
        if self.device is not None and self.path == path:
            return
        self.disconnect()
        device = self.hid.device()
        try:
            device.open_path(path)
        except Exception:
            device.close()
            raise
        self.device, self.path = device, path
        self.last_unavailable = None
        self.emit('hid_connected', id=self.device_id(), exclusive=False)
        for report_id, size in ((1, 15), (2, 53)):
            try:
                data = device.get_input_report(report_id, size)
                valid = len(data) >= size and data[0] == report_id
                self.emit('seed_status', id=self.device_id(), report_id=report_id,
                          status=0 if valid else -1, count=len(data))
                if valid:
                    self.input_report(data, seed=True)
            except (AttributeError, OSError, ValueError) as error:
                self.emit('seed_status', id=self.device_id(), report_id=report_id,
                          status=-1, count=0, message=str(error))

    def hardware_step(self):
        if self.device is None:
            return
        with self.led_lock:
            image, self.pending_leds = self.pending_leds, None
        if image is not None:
            count = self.device.write(bytes([0x80] + image))
            self.emit('hid_led_status', id=self.device_id(), status=0 if count == 106 else -1,
                      payload_count=105, numbered_count=count, report_id=0x80)
            if count != 106:
                raise OSError(f'Incomplete HID output: {count}/106 bytes')
        self.input_report(self.device.read(64, timeout_ms=20))

    def hardware_loop(self):
        next_scan = 0
        try:
            while not self.stopping.is_set():
                try:
                    now = time.monotonic()
                    if now >= next_scan:
                        self.refresh_device()
                        next_scan = now + 1
                    if self.device is None:
                        self.stopping.wait(0.05)
                    else:
                        self.hardware_step()
                except Exception as error:
                    self.emit('error', operation='hid_io', message=str(error))
                    self.disconnect()
                    self.stopping.wait(0.5)
        finally:
            self.disconnect()

    def close(self):
        self.stopping.set()
        if self.thread is not None and self.thread is not threading.current_thread():
            self.thread.join(timeout=3)
        with self.send_lock:
            for port in (self.input, self.output):
                if port is not None:
                    port.close()
            self.input = self.output = None



class Observer(Transport):
    """HID-only monitor plus optional read-only physical MIDI subscription."""
    def __init__(self, hid, mido, emit):
        super().__init__(hid, mido, emit)
        self.physical_name = None

    def start(self):
        self.thread = threading.Thread(target=self.hardware_loop, name='MX2 passive HID', daemon=True)
        self.thread.start()
        self.emit('ready_observer', passive=True, virtual_ports_created=False, output_writes=False)

    def accept(self, line):
        self.emit('error', operation='passive_observer', message='Observer accepts no output commands')

    def feedback(self, message):
        if not self.stopping.is_set():
            self.emit('physical_midi_input', bytes=message.bytes(), midi_timestamp=time.monotonic_ns())

    def refresh_device(self):
        super().refresh_device()
        try:
            self.refresh_physical_midi()
        except Exception as error:
            # A busy physical MIDI input must not interrupt passive HID reads.
            self.emit('error', operation='optional_physical_midi', message=str(error))

    def refresh_physical_midi(self):
        if self.mido is None:
            return
        matches = [name for name in self.mido.get_input_names()
                   if re.fullmatch(r'Traktor MX2(?: \d+)?', name)] if self.device is not None else []
        name = matches[0] if len(matches) == 1 else None
        if name != self.physical_name:
            if self.input is not None:
                self.input.close()
                self.input = None
            self.physical_name = None
            if name is not None:
                self.input = self.mido.open_input(name, callback=self.feedback)
                self.physical_name = name
                self.emit('physical_midi_connected', endpoint=name)

    def hardware_step(self):
        if self.device is not None:
            self.input_report(self.device.read(64, timeout_ms=20))


def main():
    output_lock = threading.Lock()

    def emit(event, **values):
        with output_lock:
            print(json.dumps(dict(values, event=event, monotonic_ns=time.monotonic_ns())), flush=True)

    transport = None
    try:
        import hid
        if '--observe' in sys.argv:
            try:
                import mido
                mido.set_backend('mido.backends.rtmidi')
            except Exception as error:
                mido = None
                emit('error', operation='optional_physical_midi', message=str(error))
            transport = Observer(hid, mido, emit)
        else:
            import mido
            mido.set_backend('mido.backends.rtmidi')
            transport = Transport(hid, mido, emit,
                                  os.environ.get('MX2_MIDI_TO_DJAY', 'MX2 for djay'),
                                  os.environ.get('MX2_MIDI_FROM_DJAY', 'MX2 for djay'))
        transport.start()
        for number in (signal.SIGINT, signal.SIGTERM):
            signal.signal(number, lambda *_: sys.exit(0))
        for line in sys.stdin:
            transport.accept(line)
        return 0
    except Exception as error:
        emit('error', operation='transport', message=str(error))
        return 2
    finally:
        if transport is not None:
            transport.close()
        emit('stopped', reason='input_closed_or_exit')


if __name__ == '__main__':
    sys.exit(main())
