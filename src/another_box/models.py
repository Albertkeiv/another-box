from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

InboundKind = Literal["mixed", "tun"]
TunStack = Literal["mixed", "system", "gvisor"]
LogLevel = Literal["trace", "debug", "info", "warn", "error", "fatal", "panic"]
LOG_LEVELS = ("trace", "debug", "info", "warn", "error", "fatal", "panic")
OUTBOUND_TAG = "PROXY"
INBOUND_TAG = "IN"
MIN_AUTO_UPDATE_MINUTES = 30
DEFAULT_AUTO_UPDATE_MINUTES = 60


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(slots=True)
class InboundConfig:
    kind: InboundKind = "mixed"
    tag: str = INBOUND_TAG
    listen: str = "127.0.0.1"
    port: int = 2080
    set_system_proxy: bool = False
    interface_name: str = "sing-box"
    address: str = "172.19.0.1/30"
    mtu: int = 9000
    stack: TunStack = "mixed"
    auto_route: bool = True
    strict_route: bool = True

    def __post_init__(self) -> None:
        self.tag = INBOUND_TAG

    def to_sing_box(self) -> dict[str, Any]:
        if self.kind == "mixed":
            return {
                "type": "mixed",
                "tag": INBOUND_TAG,
                "listen": self.listen,
                "listen_port": self.port,
                "set_system_proxy": self.set_system_proxy,
            }
        return {
            "type": "tun",
            "tag": INBOUND_TAG,
            "interface_name": self.interface_name,
            "address": [self.address],
            "mtu": self.mtu,
            "stack": self.stack,
            "auto_route": self.auto_route,
            "strict_route": self.strict_route,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "InboundConfig":
        allowed = cls.__dataclass_fields__.keys()
        return cls(**{key: value for key, value in data.items() if key in allowed})

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def endpoint(self) -> str:
        if self.kind == "mixed":
            return f"{self.listen}:{self.port}"
        return f"{self.interface_name} · {self.address}"


@dataclass(slots=True)
class SingBoxLogConfig:
    enabled: bool = True
    level: LogLevel = "info"
    timestamp: bool = True

    def __post_init__(self) -> None:
        if self.level not in LOG_LEVELS:
            self.level = "info"

    def to_sing_box(self) -> dict[str, Any]:
        return {
            "disabled": not self.enabled,
            "level": self.level,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SingBoxLogConfig":
        allowed = cls.__dataclass_fields__.keys()
        return cls(**{key: value for key, value in data.items() if key in allowed})


@dataclass(slots=True)
class Profile:
    id: str
    name: str
    url: str
    inbound: InboundConfig = field(default_factory=InboundConfig)
    sing_box_log: SingBoxLogConfig = field(default_factory=SingBoxLogConfig)
    created_at: str = field(default_factory=utc_now)
    last_updated_at: str | None = None
    last_update_attempt_at: str | None = None
    last_update_ok: bool | None = None
    last_error: str | None = None
    needs_restart: bool = False
    auto_update_enabled: bool = False
    auto_update_interval_minutes: int = DEFAULT_AUTO_UPDATE_MINUTES

    def __post_init__(self) -> None:
        self.auto_update_interval_minutes = max(
            MIN_AUTO_UPDATE_MINUTES,
            int(self.auto_update_interval_minutes),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Profile":
        values = dict(data)
        values["inbound"] = InboundConfig.from_dict(values.get("inbound", {}))
        values["sing_box_log"] = SingBoxLogConfig.from_dict(
            values.get("sing_box_log", {})
        )
        allowed = cls.__dataclass_fields__.keys()
        return cls(**{key: value for key, value in values.items() if key in allowed})

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["inbound"] = self.inbound.to_dict()
        result["sing_box_log"] = asdict(self.sing_box_log)
        return result
