from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_data_path


def project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


@dataclass(frozen=True, slots=True)
class AppPaths:
    data_dir: Path
    executable: Path

    @classmethod
    def default(cls) -> "AppPaths":
        if sys.platform == "win32" and os.environ.get("APPDATA"):
            data_dir = Path(os.environ["APPDATA"]) / "AnotherBox"
        else:
            data_dir = user_data_path("AnotherBox", appauthor=False, roaming=True)
        return cls(
            data_dir=data_dir,
            executable=project_root() / "bin" / "sing-box.exe",
        )

    @property
    def profiles_dir(self) -> Path:
        return self.data_dir / "profiles"

    @property
    def lock_file(self) -> Path:
        return self.data_dir / "another-box.lock"

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def application_log(self) -> Path:
        return self.logs_dir / "application.log"

    def ensure(self) -> None:
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
