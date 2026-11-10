"""Bundled resources are read-only; customer data belongs to the current user."""
import json
import os
from pathlib import Path
import tempfile
from contextlib import contextmanager


def resource_path(name):
    return Path(__file__).resolve().parent.parent / name


def data_path(name=''):
    override = os.environ.get('HARRY_DATA_DIR')
    root = Path(override) if override else Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'HarryTranslate'
    root.mkdir(parents=True, exist_ok=True)
    return root / name


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name, suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class AlreadyRunning(Exception):
    pass


@contextmanager
def instance_lock():
    """OS-owned file lock is released even after an unexpected process exit."""
    if os.name != 'nt':
        yield
        return
    import msvcrt
    handle = data_path('running.lock').open('a+b')
    acquired = False
    try:
        if handle.seek(0, 2) == 0:
            handle.write(b'0')
            handle.flush()
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            acquired = True
        except OSError:
            raise AlreadyRunning('Harry Translate 已在运行，请切换到已打开的窗口。') from None
        yield
    finally:
        if acquired:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        handle.close()
