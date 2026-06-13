from __future__ import annotations

import ctypes
import logging
import subprocess
import sys
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from another_box.configuration import ConfigValidator, validate_launch_requirements
from another_box.errors import (
    ProcessConflictError,
    ProcessStartError,
    ValidationError,
)
from another_box.models import Profile
from another_box.logging_config import LOGGER_NAME
from another_box.storage import ProfileStore

logger = logging.getLogger(f"{LOGGER_NAME}.processes")


def is_administrator() -> bool:
    if sys.platform != "win32":
        return True
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except OSError:
        return False


@dataclass(slots=True)
class ManagedProcess:
    profile: Profile
    process: Any
    logs: deque[str] = field(default_factory=lambda: deque(maxlen=500))
    stopping: bool = False
    reader: threading.Thread | None = None


class ProcessManager:
    def __init__(
        self,
        store: ProfileStore,
        validator: ConfigValidator,
        executable: Path,
        launcher: Callable[..., Any] = subprocess.Popen,
        admin_checker: Callable[[], bool] = is_administrator,
        startup_grace: float = 0.35,
    ):
        self.store = store
        self.validator = validator
        self.executable = executable
        self.launcher = launcher
        self.admin_checker = admin_checker
        self.startup_grace = startup_grace
        self._active: dict[str, ManagedProcess] = {}
        self._last_logs: dict[str, deque[str]] = {}
        self._runtime_errors: dict[str, str] = {}
        self._lock = threading.RLock()

    def is_running(self, profile_id: str) -> bool:
        with self._lock:
            managed = self._active.get(profile_id)
            return managed is not None and managed.process.poll() is None

    def active_ids(self) -> list[str]:
        with self._lock:
            return [
                profile_id
                for profile_id, managed in self._active.items()
                if managed.process.poll() is None
            ]

    def active_profiles(self) -> list[Profile]:
        with self._lock:
            return [
                managed.profile
                for managed in self._active.values()
                if managed.process.poll() is None
            ]

    def runtime_error(self, profile_id: str) -> str | None:
        with self._lock:
            return self._runtime_errors.get(profile_id)

    def logs(self, profile_id: str) -> str:
        with self._lock:
            managed = self._active.get(profile_id)
            lines = managed.logs if managed else self._last_logs.get(profile_id)
            if lines is None:
                lines = self.store.load_log(profile_id)
            return "\n".join(lines)

    def start(self, profile_id: str) -> None:
        profile = self.store.get(profile_id)
        config_path = self.store.config_path(profile_id)
        if not config_path.is_file():
            detail = f" Последняя ошибка: {profile.last_error}" if profile.last_error else ""
            raise ProcessStartError(
                "Профиль еще не содержит загруженную конфигурацию. "
                f"Обновите подписку и повторите запуск.{detail}"
            )

        with self._lock:
            if self.is_running(profile_id):
                return
            self._check_conflicts(profile)
            if profile.inbound.kind == "tun" and not self.admin_checker():
                raise ProcessStartError(
                    "Для запуска TUN нужны права администратора. "
                    "Закройте приложение и запустите терминал от имени администратора."
                )

        try:
            validate_launch_requirements(self.store.load_config(profile_id))
            self.validator.validate(config_path)
        except ValidationError as error:
            raise ProcessStartError(f"Проверка конфигурации не пройдена: {error}") from error

        if profile.inbound.kind == "tun":
            self.stop_all()

        if not self.executable.is_file():
            raise ProcessStartError(f"Не найден sing-box: {self.executable}")

        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            process = self.launcher(
                [str(self.executable), "run", "-c", str(config_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=creationflags,
            )
        except OSError as error:
            raise ProcessStartError(f"Не удалось запустить sing-box: {error}") from error

        managed = ManagedProcess(
            profile=profile,
            process=process,
            logs=deque(self.store.load_log(profile_id), maxlen=500),
        )
        with self._lock:
            self._active[profile_id] = managed
            self._runtime_errors.pop(profile_id, None)
        managed.reader = threading.Thread(
            target=self._read_output,
            args=(profile_id, managed),
            name=f"sing-box-{profile_id[:8]}",
            daemon=True,
        )
        managed.reader.start()

        if self.startup_grace:
            time.sleep(self.startup_grace)
        return_code = process.poll()
        if return_code is not None:
            self._finalize_exit(profile_id, managed, return_code)
            message = self.logs(profile_id).strip()
            raise ProcessStartError(message or f"sing-box завершился с кодом {return_code}.")
        if profile.needs_restart:
            profile.needs_restart = False
            self.store.save(profile)

    def stop(self, profile_id: str, timeout: float = 5.0) -> None:
        with self._lock:
            managed = self._active.get(profile_id)
            if managed is None:
                return
            managed.stopping = True
        process = managed.process
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2.0)
        self._finalize_exit(profile_id, managed, process.poll())

    def stop_all(self) -> None:
        for profile_id in self.active_ids():
            self.stop(profile_id)

    def _check_conflicts(self, candidate: Profile) -> None:
        running = self.active_profiles()
        if candidate.inbound.kind == "mixed":
            if any(profile.inbound.kind == "tun" for profile in running):
                raise ProcessConflictError(
                    "Нельзя запустить mixed-профиль, пока активен TUN."
                )
            for profile in running:
                inbound = profile.inbound
                if (
                    inbound.kind == "mixed"
                    and inbound.listen == candidate.inbound.listen
                    and inbound.port == candidate.inbound.port
                ):
                    raise ProcessConflictError(
                        f"Адрес {inbound.endpoint} уже использует профиль «{profile.name}»."
                    )
                if (
                    inbound.kind == "mixed"
                    and inbound.set_system_proxy
                    and candidate.inbound.set_system_proxy
                ):
                    raise ProcessConflictError(
                        "Системный прокси уже управляется другим mixed-профилем."
                    )

    def _read_output(self, profile_id: str, managed: ManagedProcess) -> None:
        stream = managed.process.stdout
        if stream is not None:
            for line in iter(stream.readline, ""):
                text = line.rstrip()
                if text:
                    with self._lock:
                        managed.logs.append(text)
            stream.close()
        return_code = managed.process.wait()
        self._finalize_exit(profile_id, managed, return_code)

    def _finalize_exit(
        self,
        profile_id: str,
        managed: ManagedProcess,
        return_code: int | None,
    ) -> None:
        with self._lock:
            if self._active.get(profile_id) is not managed:
                return
            self._last_logs[profile_id] = deque(managed.logs, maxlen=500)
            self.store.save_log(profile_id, list(managed.logs))
            self._active.pop(profile_id, None)
            if not managed.stopping and return_code is not None:
                tail = list(managed.logs)[-3:]
                detail = " ".join(tail) if tail else f"код {return_code}"
                message = (
                    f"sing-box неожиданно завершился: {detail}"
                )
                self._runtime_errors[profile_id] = message
                logger.error(
                    "Profile %s (%s): %s",
                    managed.profile.name,
                    profile_id,
                    message,
                )
