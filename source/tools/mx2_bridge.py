#!/usr/bin/env python3
"""Measured MX2 MIDI -> stateful virtual djay endpoint, with feedback routing.

No HID writes or SysEx. Modes are bridge design choices, not recovered Traktor code.
"""
import argparse
import os
import json
from pathlib import Path
import signal
import subprocess
import sys
import time
import threading

from summarize_midi import Stream
from mx2_runtime_lock import acquire_lock

ROOT = Path(__file__).resolve().parent.parent


class Router:
    def __init__(self, profile):
        self.profile = profile['controls']
        self.names = {(c['channel'], c['family'], c['number']): n for n, c in self.profile.items()}
        self.shift = [False, False]
        self.pad_mode = [0, 0]
        self.vinyl = [True, True]
        self.fx_mode = 4  # Filter
        self.held = {}  # physical address -> virtual address at press (release cannot drift)
        self.feedback_cache = {}
        self.last_led = {}
        self.input_count = self.feedback_count = self.unknown_count = 0

    def led(self, channel, number, value, force=False):
        value = 127 if value else 0
        key = (channel, number)
        if not force and self.last_led.get(key) == value:
            return []
        self.last_led[key] = value
        return [('hardware', [0x90 | channel, number, value])]

    def refresh_modes(self):
        out = []
        for d in range(2):
            out += self.led(d, 12, self.shift[d])
            out += self.led(d, 10, self.vinyl[d])
            out += self.led(d, 11, not self.vinyl[d])
            for mode in range(4):
                out += self.led(d, 16 + mode, self.pad_mode[d] == mode)
            for pad in range(8):
                key = (6 + d, self.pad_mode[d] * 16 + pad)
                # A held pad remains visibly active until its corresponding release.
                pressed = any(k[0] == d and k[2] == 20 + pad for k in self.held)
                out += self.led(d, 20 + pad, pressed or self.feedback_cache.get(key, 0))
        for mode in range(5):
            out += self.led(4, mode, self.fx_mode == mode)
        for d in range(2):
            out += self.led(d + 2, 2, self.feedback_cache.get((d + 4, 40 + (0 if self.fx_mode == 4 else self.fx_mode + 1)), 0))
        return out

    def reset_jogs(self):
        return [('virtual', [0x80 | d, n, 0]) for d in range(2) for n in (33, 34, 35)]

    def release(self, key):
        dest = self.held.pop(key, None)
        return [] if dest is None else [('virtual', [0x80 | dest[0], dest[1], 0])]

    def input(self, status, data):
        family, channel = status & 0xf0, status & 0x0f
        if family not in (0x80, 0x90, 0xb0) or len(data) != 2:
            return []
        number, value = data
        note = family in (0x80, 0x90)
        key = (channel, 0x90 if note else family, number)
        name = self.names.get(key)
        if name is None:
            self.unknown_count += 1
            return []
        self.input_count += 1
        pressed = family == 0x90 and value > 0
        if channel < 2:
            d = channel
            if note and number == 12:
                self.shift[d] = pressed
                return self.refresh_modes()
            if note and number in (10, 11, 16, 17, 18, 19):
                out = []
                if pressed:
                    if number in (10, 11):
                        self.vinyl[d] = number == 10
                        # Clear djay seek/pitch-bend modes left latched by older configurations.
                        out += [('virtual', [0x80 | d, n, 0]) for n in (34, 35)]
                        if not self.vinyl[d]:
                            out += self.release((d, 0x90, 33))
                    else:
                        self.pad_mode[d] = number - 16
                return out + self.refresh_modes()
            dest_channel, dest_number = d + (2 if self.shift[d] else 0), number
            if note and 20 <= number <= 27:
                dest_channel = 6 + d + (2 if self.shift[d] else 0)
                dest_number = self.pad_mode[d] * 16 + number - 20
            if note and number == 33:
                dest_channel = d  # Scratch touch must always release to this same route.
                if pressed and (not self.vinyl[d] or self.shift[d]):
                    return []
        elif channel in (2, 3):
            dest_channel, dest_number = channel + 2, number
            if not note and number == 36:
                dest_number = {4: 36, 0: 37, 1: 38, 2: 39, 3: 36}[self.fx_mode]
            if note and number == 2:
                dest_number = 40 + (0 if self.fx_mode == 4 else self.fx_mode + 1)
        else:
            if note and number < 5:
                if pressed:
                    self.fx_mode = number
                return self.refresh_modes()
            dest_channel, dest_number = 15, number
        if note:
            if not pressed:
                out = self.release(key)
                return out + self.refresh_modes()
            if key in self.held:  # Touch sensors can repeat on-events; don't retrigger actions.
                return []
            self.held[key] = (dest_channel, dest_number)
            return [('virtual', [0x90 | dest_channel, dest_number, value])] + self.refresh_modes()
        # Normalize absolute pots using the full visually confirmed sweep. Relative63/65
        # must be preserved; interpreting them as absolute would reverse encoder behavior.
        c = self.profile[name]
        if c['values'] != [63, 65]:
            low, high = c['min'], c['max']
            value = max(0, min(127, round((value - low) * 127 / (high - low))))
        return [('virtual', [0xb0 | dest_channel, dest_number, value])]

    def feedback(self, status, data):
        family, ch = status & 0xf0, status & 15
        if family not in (0x80, 0x90) or len(data) != 2:
            return []
        number, value = data
        value = 0 if family == 0x80 else value
        self.feedback_count += 1
        self.feedback_cache[(ch, number)] = value
        if ch in (0, 1):
            return self.led(ch, number, value)
        if ch in (6, 7):
            d = ch - 6
            if number // 16 == self.pad_mode[d] and number % 16 < 8:
                return self.led(d, 20 + number % 16, value)
        if ch in (4, 5):
            if number in (0, 1, 3):
                return self.led(ch - 2, number, value)
            if number == 40 + (0 if self.fx_mode == 4 else self.fx_mode + 1):
                return self.led(ch - 2, 2, value)
        if ch == 15 and number == 5:
            return self.led(4, 5, value)
        return []

    def panic(self):
        out = []
        for key in list(self.held):
            out += self.release(key)
        self.shift = [False, False]
        for (ch, number), value in list(self.last_led.items()):
            if value:
                out += self.led(ch, number, 0)
        return out

    def snapshot(self):
        return {'shift': list(self.shift), 'pad_mode': list(self.pad_mode), 'vinyl': list(self.vinyl),
                'channel_fx_mode': self.fx_mode, 'held_notes': len(self.held),
                'input_messages': self.input_count, 'feedback_messages': self.feedback_count,
                'unmapped_messages': self.unknown_count}


def main(resource_root=None, state_root=None, transport_command=None, argv=None):
    resources = Path(resource_root) if resource_root else ROOT
    state_dir = Path(state_root) if state_root else ROOT / 'evidence'
    state_dir.mkdir(parents=True, exist_ok=True)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', type=Path, default=resources / 'evidence/midi-profile.json')
    parser.add_argument('--log', type=Path, default=state_dir / 'bridge-live.jsonl')
    args = parser.parse_args(argv)
    lock = (state_dir / 'bridge.lock').open('a+')
    try:
        acquire_lock(lock)
    except BlockingIOError:
        lock.close()
        print('La passerelle MX2 est déjà lancée. Gardez la session existante ouverte.', file=sys.stderr)
        return 2
    lock.seek(0)
    lock.truncate()
    lock.write(str(os.getpid()))
    lock.flush()
    try:
        router = Router(json.loads(args.profile.read_text()))
        proc = subprocess.Popen(transport_command or [str(resources / 'tools/mx2-midi-transport')],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
    except BaseException:
        lock.close()
        raise
    streams = {'input': Stream(), 'feedback': Stream()}
    stopping = threading.Event()
    send_lock = threading.RLock()
    router_lock = threading.RLock()
    log_lock = threading.RLock()
    ready = False
    initialized = False
    log = args.log.open('a')

    def record(row):
        with log_lock:
            log.write(json.dumps(row, separators=(',', ':')) + '\n')
            log.flush()

    def send(messages):
        with send_lock:
            if proc.stdin.closed:
                return
            for to, data in messages:
                proc.stdin.write(json.dumps({'to': to, 'bytes': data}) + '\n')
                if data[0] & 240 != 0xb0:
                    record({'event': 'route', 'to': to, 'bytes': data, 'unix_time': time.time()})
            if messages:
                proc.stdin.flush()

    def stop(signum, frame):
        if stopping.is_set():
            return
        stopping.set()
        def bound_shutdown():
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()
        threading.Thread(target=bound_shutdown, daemon=True).start()
        try:
            with router_lock:
                send(router.panic())
            with send_lock:
                proc.stdin.close()  # Transport drains its serial command queue before EOF cleanup.
        except (BrokenPipeError, ValueError):
            pass

    heartbeat_stop = threading.Event()
    status_path = state_dir / 'bridge-status.json'
    def publish_status(running):
        with router_lock:
            snapshot = router.snapshot()
        state = dict(snapshot, running=running, mode='midi', pid=os.getpid(),
                     transport_pid=proc.pid, updated_unix_time=time.time(),
                     virtual_endpoint='MX2 for djay', ready=ready)
        temporary = status_path.with_suffix('.json.tmp')
        temporary.write_text(json.dumps(state, indent=2) + '\n')
        temporary.replace(status_path)

    def heartbeat():
        while not heartbeat_stop.is_set():
            request = state_dir / 'stop.request'
            try:
                if request.exists() and request.read_text().strip() == str(os.getpid()):
                    request.unlink()
                    stop(None, None)
            except OSError:
                pass
            try:
                publish_status(True)
            except OSError as error:
                print('Status file unavailable: ' + str(error), file=sys.stderr, flush=True)
            heartbeat_stop.wait(1.0)

    heartbeat_thread = threading.Thread(target=heartbeat, daemon=True)
    heartbeat_thread.start()
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    record({'event': 'bridge_start', 'unix_time': time.time(), 'profile': str(args.profile)})
    try:
        for line in proc.stdout:
            row = json.loads(line)
            event = row.get('event')
            if event in streams and not stopping.is_set():
                with router_lock:
                    if event == 'feedback' and not initialized:
                        send(router.reset_jogs())
                        initialized = True
                    for status, data in streams[event].feed(row['bytes']):
                        messages = getattr(router, event)(status, data)
                        send(messages)
                record(row)
            elif event in ('ready', 'hardware_connected', 'hardware_unavailable', 'error', 'stopped'):
                record(row)
                print(json.dumps(row), flush=True)
                if event == 'ready':
                    ready = True
                with router_lock:
                    if ready and not stopping.is_set() and event in ('ready', 'hardware_connected'):
                        send(router.reset_jogs() + router.refresh_modes())
                    if event == 'hardware_unavailable':
                        send([(to, data) for to, data in router.panic() if to == 'virtual'])
        code = proc.wait()
        record({'event': 'bridge_exit', 'code': code, **router.snapshot()})
        return code
    finally:
        if proc.poll() is None:
            stop(None, None)
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill(); proc.wait(timeout=1)
        heartbeat_stop.set()
        heartbeat_thread.join(timeout=2)
        publish_status(False)
        log.close()
        proc.stdout.close()
        lock.close()


if __name__ == '__main__':
    sys.exit(main())
