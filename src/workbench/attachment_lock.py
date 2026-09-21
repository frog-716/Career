"""Cross-process lifecycle lock for published attachment paths."""

from contextlib import contextmanager
import os
from pathlib import Path
import threading

try:
    import fcntl
except ImportError:  # pragma: no cover - Career's supported platforms provide fcntl.
    fcntl = None


_local = threading.local()


@contextmanager
def attachment_lifecycle_lock(root):
    """Acquire the shared attachment lock before any DB write lock.

    The small re-entrant layer lets Store startup/recovery and backup call the
    same public helper without opening a second file descriptor in one thread.
    """
    path = Path(root).expanduser().resolve() / ".career-attachment.lock"
    held = getattr(_local, "held", None)
    key = str(path)
    if held and key in held:
        held[key]["depth"] += 1
        try:
            yield
        finally:
            held[key]["depth"] -= 1
        return

    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    os.chmod(path, 0o600)
    if fcntl is not None:
        fcntl.flock(fd, fcntl.LOCK_EX)
    if held is None:
        held = {}
        _local.held = held
    held[key] = {"fd": fd, "depth": 1}
    try:
        yield
    finally:
        entry = held.pop(key, None)
        if entry:
            if fcntl is not None:
                fcntl.flock(entry["fd"], fcntl.LOCK_UN)
            os.close(entry["fd"])

