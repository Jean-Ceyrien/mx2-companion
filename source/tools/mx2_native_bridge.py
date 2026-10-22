#!/usr/bin/env python3
"""MX2 native HID -> existing djay virtual MIDI mapping, with native RGB feedback."""
from mx2_runtime_lock import acquire_lock
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

from mx2_bridge import ROOT, Router
from mx2_native import NativeInput, NativeLEDs
from summarize_midi import Stream


def main(resource_root=None, state_root=None, transport_command=None, feedback_decode=None):
    resources = Path(resource_root) if resource_root else ROOT
    state_dir = Path(state_root) if state_root else ROOT / 'evidence'
    state_dir.mkdir(parents=True, exist_ok=True)
    lock = (state_dir / 'bridge.lock').open('a+')
    try:
        acquire_lock(lock)
    except BlockingIOError:
        lock.close()
        print('An MX2 bridge is already running. Stop it before starting another one.', file=sys.stderr)
        return 2
    lock.seek(0); lock.truncate(); lock.write(str(os.getpid())); lock.flush()
    try:
        profile = json.loads((resources / 'evidence/midi-profile.json').read_text())
        router = Router(profile)
        adapter = NativeInput(profile)
        leds = NativeLEDs(profile, json.loads((resources / 'evidence/native-protocol-map.json').read_text()))
        proc = subprocess.Popen(transport_command or [str(resources / 'tools/mx2-native-transport')], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, text=True, bufsize=1,
                                **({'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}))
    except BaseException:
        lock.close()
        raise
    feedback = Stream()
    state_lock = threading.RLock()
    send_lock = threading.RLock()
    log_lock = threading.RLock()
    stopping = threading.Event()
    ready = False
    connected = False
    initialized = False
    last_hid = None
    last_hid_report = None
    frame_count = 0
    started = time.monotonic()
    log = (state_dir / 'native-bridge-live.jsonl').open('a')
    status_path = state_dir / 'bridge-status.json'

    def record(row):
        with log_lock:
            log.write(json.dumps(row, separators=(',', ':')) + '\n'); log.flush()

    def send(messages):
        with send_lock:
            if proc.stdin.closed:
                return
            for target, data in messages:
                if target == 'hardware':
                    continue  # Native LED images replace raw MIDI LED sends.
                proc.stdin.write(json.dumps({'to': target, 'bytes': data}) + '\n')
                if target == 'virtual' and data[0] & 240 != 0xb0:
                    record({'event': 'route', 'to': target, 'bytes': data, 'unix_time': time.time()})
            proc.stdin.flush()

    def publish(running):
        with state_lock:
            age = None if last_hid is None else round(time.monotonic() - last_hid, 3)
            state = dict(router.snapshot(), running=running, ready=ready, mode='native',
                         pid=os.getpid(), transport_pid=proc.pid, virtual_endpoint='MX2 for djay',
                         updated_unix_time=time.time(), hid_connected=connected,
                         last_hid_age_seconds=age, native_mode_confirmed=age is not None and age < 2,
                         hid_frames=frame_count, decode_errors=adapter.decoder.errors,
                         meter_levels=list(leds.meters), end_warning=list(leds.end_warning))
        temporary = status_path.with_suffix('.json.tmp')
        temporary.write_text(json.dumps(state, indent=2) + '\n'); temporary.replace(status_path)

    def lights_and_health():
        previous = None; last_sent = 0; last_status = 0; warned = False
        while not stopping.wait(0.05):
            request = state_dir / 'stop.request'
            try:
                if request.exists() and request.read_text().strip() == str(os.getpid()):
                    request.unlink()
                    stop()
                    return
            except OSError:
                pass
            now = time.monotonic()
            with state_lock:
                image = leds.render(router, now)
                can_send = ready and connected
                silent = now - started > 3 and (last_hid is None or now - last_hid > 2)
            try:
                if can_send and (image != previous or now - last_sent > 1):
                    send([('hid-leds', image)])
                    previous = image; last_sent = now
                if now - last_status > 1:
                    publish(True); last_status = now
                    if silent and not warned:
                        print('No HID input: MX2 must be in native mode (press both SHIFT buttons together once to switch mode).', flush=True)
                    if warned and not silent:
                        print('MX2 HID input received: native mode confirmed.', flush=True)
                    warned = silent
            except (OSError, ValueError) as error:
                if not stopping.is_set():
                    record({'event': 'background_error', 'message': str(error)})
                return

    def restore_cache():
        for (channel, number), value in list(router.feedback_cache.items()):
            router.feedback(0x90 | channel, [number, value])
        router.refresh_modes()

    def stop(signum=None, frame=None):
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
            with state_lock:
                send(router.panic() + router.reset_jogs())
            with send_lock:
                if not proc.stdin.closed:
                    proc.stdin.close()
        except (BrokenPipeError, ValueError):
            pass

    signal.signal(signal.SIGINT, stop); signal.signal(signal.SIGTERM, stop)
    record({'event': 'native_bridge_start', 'unix_time': time.time(), 'pid': os.getpid()})
    worker = threading.Thread(target=lights_and_health, daemon=True); worker.start()
    try:
        for line in proc.stdout:
            row = json.loads(line); event = row.get('event')
            with state_lock:
                if event == 'hid_input' and not stopping.is_set():
                    frame_count += 1; last_hid_report = row.get('report_id')
                    messages = adapter.feed(row)
                    try:
                        report = bytes.fromhex(row.get('bytes_hex', ''))
                        live = (not row.get('seed') and row.get('status', 0) == 0
                                and len(report) == {1: 15, 2: 53, 3: 20}.get(last_hid_report)
                                and row.get('count', len(report)) == len(report)
                                and report[0] == last_hid_report)
                    except (ValueError, TypeError):
                        live = False
                    if live:
                        last_hid = time.monotonic()
                    for status, data in messages:
                        send(router.input(status, data))
                    if messages or row.get('seed') or row.get('status'):
                        record(row)
                elif event == 'feedback' and not stopping.is_set():
                    if not initialized:
                        send(router.reset_jogs()); initialized = True
                    for status, data in feedback.feed(row['bytes']):
                        decoded = feedback_decode(status, data) if feedback_decode else (status, data)
                        if decoded is not None:
                            mapped_status, mapped_data = decoded
                            leds.feedback(mapped_status, mapped_data)
                            router.feedback(mapped_status, mapped_data)
                    if any(data[0] & 240 != 0xb0 for data in [row['bytes']] if data):
                        record(row)
                elif event in ('hid_connected', 'hid_removed', 'hardware_unavailable', 'ready_native', 'seed_status', 'error', 'stopped'):
                    record(row); print(json.dumps(row), flush=True)
                    if event == 'hid_connected':
                        connected = True; adapter.reset(); last_hid = None
                        if ready:
                            send(router.panic() + router.reset_jogs()); restore_cache()
                    elif event in ('hid_removed', 'hardware_unavailable'):
                        connected = False; last_hid = None; adapter.reset()
                        send(router.panic())
                    elif event == 'ready_native':
                        ready = True; restore_cache(); send(router.reset_jogs())
                elif event == 'hid_led_status' and row.get('status') != 0:
                    record(row); print(json.dumps(row), flush=True)
        code = proc.wait()
        record({'event': 'native_bridge_exit', 'code': code, **router.snapshot()})
        return code
    finally:
        stop(); worker.join(timeout=2)
        if proc.poll() is None:
            try: proc.wait(timeout=3)
            except subprocess.TimeoutExpired: proc.terminate()
        publish(False); log.close()
        proc.stdout.close()
        lock.close()


if __name__ == '__main__':
    sys.exit(main())
