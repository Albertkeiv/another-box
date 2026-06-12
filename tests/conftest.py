from __future__ import annotations

from pathlib import Path

import pytest

from another_box.paths import AppPaths
from another_box.storage import ProfileStore


@pytest.fixture
def app_paths(tmp_path: Path) -> AppPaths:
    executable = tmp_path / "bin" / "sing-box.exe"
    executable.parent.mkdir()
    executable.touch()
    return AppPaths(data_dir=tmp_path / "data", executable=executable)


@pytest.fixture
def store(app_paths: AppPaths) -> ProfileStore:
    return ProfileStore(app_paths)

