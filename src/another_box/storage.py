from __future__ import annotations

import json
import os
import threading
import uuid
from pathlib import Path
from typing import Any

from another_box.errors import ProfileNotFoundError
from another_box.models import InboundConfig, Profile
from another_box.paths import AppPaths


class ProfileStore:
    def __init__(self, paths: AppPaths):
        self.paths = paths
        self.paths.ensure()
        self._lock = threading.RLock()

    def profile_dir(self, profile_id: str) -> Path:
        return self.paths.profiles_dir / profile_id

    def metadata_path(self, profile_id: str) -> Path:
        return self.profile_dir(profile_id) / "profile.json"

    def source_path(self, profile_id: str) -> Path:
        return self.profile_dir(profile_id) / "source.json"

    def config_path(self, profile_id: str) -> Path:
        return self.profile_dir(profile_id) / "config.json"

    def log_path(self, profile_id: str) -> Path:
        return self.profile_dir(profile_id) / "process.log"

    def list_profiles(self) -> list[Profile]:
        with self._lock:
            profiles: list[Profile] = []
            if not self.paths.profiles_dir.exists():
                return profiles
            for directory in self.paths.profiles_dir.iterdir():
                metadata = directory / "profile.json"
                if not directory.is_dir() or not metadata.is_file():
                    continue
                try:
                    profiles.append(Profile.from_dict(self._read_json(metadata)))
                except (OSError, ValueError, TypeError):
                    continue
            return sorted(profiles, key=lambda profile: profile.name.casefold())

    def get(self, profile_id: str) -> Profile:
        with self._lock:
            path = self.metadata_path(profile_id)
            if not path.is_file():
                raise ProfileNotFoundError("Профиль не найден.")
            return Profile.from_dict(self._read_json(path))

    def create(self, name: str, url: str, inbound: InboundConfig) -> Profile:
        with self._lock:
            profile = Profile(
                id=str(uuid.uuid4()),
                name=name.strip(),
                url=url.strip(),
                inbound=inbound,
            )
            directory = self.profile_dir(profile.id)
            directory.mkdir(parents=True, exist_ok=False)
            self.save(profile)
            return profile

    def save(self, profile: Profile) -> None:
        with self._lock:
            self.profile_dir(profile.id).mkdir(parents=True, exist_ok=True)
            self._atomic_json(self.metadata_path(profile.id), profile.to_dict())

    def delete(self, profile_id: str) -> None:
        with self._lock:
            directory = self.profile_dir(profile_id)
            if not directory.exists():
                return
            for path in directory.iterdir():
                if path.is_file():
                    path.unlink()
            directory.rmdir()

    def has_config(self, profile_id: str) -> bool:
        return self.config_path(profile_id).is_file()

    def load_log(self, profile_id: str) -> list[str]:
        path = self.log_path(profile_id)
        if not path.is_file():
            return []
        try:
            return path.read_text(encoding="utf-8").splitlines()[-500:]
        except OSError:
            return []

    def save_log(self, profile_id: str, lines: list[str]) -> None:
        with self._lock:
            self.profile_dir(profile_id).mkdir(parents=True, exist_ok=True)
            self._atomic_text(self.log_path(profile_id), "\n".join(lines[-500:]))

    def load_source(self, profile_id: str) -> dict[str, Any]:
        path = self.source_path(profile_id)
        if not path.is_file():
            raise ProfileNotFoundError("Исходная конфигурация профиля отсутствует.")
        value = self._read_json(path)
        if not isinstance(value, dict):
            raise ValueError("Корень конфигурации должен быть JSON-объектом.")
        return value

    def commit_configuration(
        self,
        profile: Profile,
        source: dict[str, Any],
        config: dict[str, Any],
    ) -> None:
        with self._lock:
            directory = self.profile_dir(profile.id)
            directory.mkdir(parents=True, exist_ok=True)
            self._atomic_bundle(
                {
                    self.source_path(profile.id): source,
                    self.config_path(profile.id): config,
                    self.metadata_path(profile.id): profile.to_dict(),
                }
            )

    @staticmethod
    def _read_json(path: Path) -> Any:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    @staticmethod
    def _atomic_json(path: Path, value: Any) -> None:
        temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            with temporary.open("w", encoding="utf-8", newline="\n") as handle:
                json.dump(value, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _atomic_text(path: Path, value: str) -> None:
        temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            with temporary.open("w", encoding="utf-8", newline="\n") as handle:
                handle.write(value)
                if value:
                    handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _atomic_bundle(values: dict[Path, Any]) -> None:
        transaction = uuid.uuid4().hex
        temporary: dict[Path, Path] = {}
        backups: dict[Path, Path] = {}
        installed: list[Path] = []
        try:
            for destination, value in values.items():
                staged = destination.with_name(f".{destination.name}.{transaction}.tmp")
                with staged.open("w", encoding="utf-8", newline="\n") as handle:
                    json.dump(value, handle, ensure_ascii=False, indent=2)
                    handle.write("\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                temporary[destination] = staged

            for destination in values:
                if destination.exists():
                    backup = destination.with_name(
                        f".{destination.name}.{transaction}.bak"
                    )
                    os.replace(destination, backup)
                    backups[destination] = backup

            for destination, staged in temporary.items():
                os.replace(staged, destination)
                installed.append(destination)
        except Exception:
            for destination in installed:
                destination.unlink(missing_ok=True)
            for destination, backup in backups.items():
                if backup.exists():
                    os.replace(backup, destination)
            raise
        finally:
            for staged in temporary.values():
                staged.unlink(missing_ok=True)
            for backup in backups.values():
                backup.unlink(missing_ok=True)
