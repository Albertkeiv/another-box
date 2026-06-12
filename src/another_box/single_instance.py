from __future__ import annotations

from PySide6.QtCore import QLockFile


class SingleInstance:
    def __init__(self, lock_path: str):
        self._lock = QLockFile(lock_path)
        self._lock.setStaleLockTime(0)

    def acquire(self) -> bool:
        return self._lock.tryLock(100)

    def release(self) -> None:
        self._lock.unlock()

