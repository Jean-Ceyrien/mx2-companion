"""Passive MX2 status observer. Neither this class nor --observe writes device state.

Mode is positive evidence, never inferred from silence. Input-report seeds are
connection snapshots, not evidence of the active mode. Stale evidence is exposed
separately so applications can ask the user to move a control rather than guess.
"""
import json
import subprocess
import sys
import threading
import time


class DeviceMonitor:
    def __init__(self, command):
        if not isinstance(command, list) or not command or any(not isinstance(v, str) for v in command):
            raise ValueError('Observer command must be a nonempty list of strings')
        self.command = list(command)
        self._lock = threading.RLock()
        self._clock = time.monotonic
        self._proc = None
        self._reader = None
        self._stopping = False
        self._reset()

    def _reset(self):
        self._ready = False
        self._connected = False
        self._mode = 'unknown'
        self._last_input = None
        self._last_event = None
        self._error = None
        self._frames = 0

    def start(self):
        with self._lock:
            if self._proc is not None and self._proc.poll() is None:
                return
            self._reset()
            self._stopping = False
            options = {'creationflags': getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000)} if sys.platform == 'win32' else {}
            try:
                proc = subprocess.Popen(self.command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT, text=True, bufsize=1, **options)
            except OSError as error:
                self._error = str(error)
                return
            self._proc = proc
            self._reader = threading.Thread(target=self._drain, args=(proc,), name='MX2 passive observer', daemon=True)
            self._reader.start()

    def _drain(self, proc):
        try:
            for line in proc.stdout:
                try:
                    row = json.loads(line)
                except ValueError:
                    with self._lock:
                        if proc is self._proc:
                            self._error = line.strip()[-500:]
                    continue
                with self._lock:
                    if proc is self._proc and not self._stopping:
                        self._consume(row)
        except (OSError, ValueError) as error:
            with self._lock:
                if proc is self._proc and not self._stopping:
                    self._error = str(error)
        finally:
            with self._lock:
                if proc is self._proc:
                    self._ready = False
                    self._connected = False
                    self._mode = 'unknown'
                    self._last_input = None
                    if not self._stopping and self._error is None:
                        self._error = 'Passive observer stopped unexpectedly'
            proc.stdout.close()

    def _consume(self, row):
        """Called under _lock; separate for deterministic offline evidence tests."""
        if not isinstance(row, dict):
            return
        now = self._clock()
        self._last_event = now
        event = row.get('event')
        if event == 'ready_observer':
            self._ready = True
        elif event == 'hid_connected':
            self._connected = True
            self._mode = 'unknown'
            self._last_input = None
            self._error = None
        elif event in ('hid_removed', 'hardware_unavailable'):
            self._connected = False
            self._mode = 'unknown'
            self._last_input = None
        elif event == 'error':
            self._error = str(row.get('message', row.get('operation', 'Observer error')))[:500]
        elif event == 'hid_input' and self._connected:
            report_id = row.get('report_id')
            expected = {1: 15, 2: 53, 3: 20}.get(report_id)
            try:
                raw = bytes.fromhex(row.get('bytes_hex', ''))
            except (TypeError, ValueError):
                return
            if (row.get('status') == 0 and not row.get('seed', False) and expected is not None
                    and len(raw) == expected and raw[0] == report_id):
                self._mode, self._last_input = 'native', now
                self._frames += 1
        elif event == 'physical_midi_input' and self._connected:
            data = row.get('bytes')
            if (isinstance(data, list) and len(data) >= 3
                    and all(type(v) is int and 0 <= v <= 255 for v in data)
                    and any(data[i] & 0xF0 in (0x80, 0x90, 0xB0)
                            and data[i + 1] < 128 and data[i + 2] < 128
                            for i in range(len(data) - 2))):
                self._mode, self._last_input = 'midi', now

    def snapshot(self):
        with self._lock:
            now = self._clock()
            age = None if self._last_input is None else max(0.0, now - self._last_input)
            stale = self._connected and age is not None and age > 5
            return dict(running=self._proc is not None and self._proc.poll() is None,
                        ready=self._ready, connected=self._connected,
                        mode='stale' if stale else self._mode,
                        last_observed_mode=self._mode, stale=stale,
                        last_input_age_seconds=None if age is None else round(age, 3),
                        last_event_age_seconds=None if self._last_event is None else round(max(0, now - self._last_event), 3),
                        hid_frames=self._frames, error=self._error, passive=True)

    def stop(self):
        with self._lock:
            self._stopping = True
            proc, reader = self._proc, self._reader
        if proc is not None:
            # Observer stdin is never used for writes; EOF asks it to exit.
            if proc.stdin is not None:
                try:
                    proc.stdin.close()
                except OSError:
                    pass
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.terminate()
                try:
                    proc.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=1)
        if reader is not None and reader is not threading.current_thread():
            reader.join(timeout=1)
        with self._lock:
            if self._proc is proc:
                self._proc = self._reader = None
                self._reset()
