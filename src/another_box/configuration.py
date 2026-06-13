from __future__ import annotations

import json
import os
import subprocess
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any, Protocol

from another_box.errors import ValidationError
from another_box.models import OUTBOUND_TAG, InboundConfig, SingBoxLogConfig

SUBSCRIPTION_SECTIONS = ("outbounds", "endpoints", "route", "dns")


def build_configuration(
    source: dict[str, Any],
    inbound: InboundConfig,
    log_config: SingBoxLogConfig | None = None,
) -> dict[str, Any]:
    config = {
        section: deepcopy(source[section])
        for section in SUBSCRIPTION_SECTIONS
        if section in source
    }
    config["inbounds"] = [inbound.to_sing_box()]
    config["log"] = (log_config or SingBoxLogConfig()).to_sing_box()
    return config


def validate_launch_requirements(config: dict[str, Any]) -> None:
    outbounds = config.get("outbounds")
    if not isinstance(outbounds, list) or not any(
        isinstance(outbound, dict) and outbound.get("tag") == OUTBOUND_TAG
        for outbound in outbounds
    ):
        raise ValidationError(
            f"Конфигурация должна содержать outbound с tag «{OUTBOUND_TAG}»."
        )


class ConfigValidator(Protocol):
    def validate(self, config_path: Path) -> None: ...


class SingBoxValidator:
    def __init__(self, executable: Path, timeout: float = 20.0):
        self.executable = executable
        self.timeout = timeout

    def validate(self, config_path: Path) -> None:
        if not self.executable.is_file():
            raise ValidationError(
                f"Не найден sing-box: {self.executable}. "
                "Поместите sing-box.exe в папку bin."
            )
        try:
            result = subprocess.run(
                [str(self.executable), "check", "-c", str(config_path)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout,
                creationflags=_creation_flags(),
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise ValidationError(f"Не удалось проверить конфигурацию: {error}") from error
        if result.returncode != 0:
            message = (result.stderr or result.stdout).strip()
            raise ValidationError(message or "sing-box отклонил конфигурацию.")


def validate_data(
    validator: ConfigValidator,
    config: dict[str, Any],
    directory: Path,
) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=".validate-",
        suffix=".json",
        dir=directory,
    )
    path = Path(temporary_name)
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as handle:
            json.dump(config, handle, ensure_ascii=False, indent=2)
        validator.validate(path)
    finally:
        path.unlink(missing_ok=True)


def _creation_flags() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)
