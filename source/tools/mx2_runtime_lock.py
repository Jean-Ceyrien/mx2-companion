"""Nonblocking single-instance lock held by an open file on macOS/Windows."""
import os


def acquire_lock(handle):
    if os.name == 'nt':
        import msvcrt
        handle.seek(0, 2)
        if handle.tell() == 0:
            handle.write(' ')
            handle.flush()
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as error:
            raise BlockingIOError('MX2 bridge already running') from error
    else:
        import fcntl
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
