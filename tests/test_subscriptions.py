from __future__ import annotations

import json

import pytest

from another_box.errors import SubscriptionError, ValidationError
from another_box.models import OUTBOUND_TAG, InboundConfig
from another_box.subscriptions import ProfileService


class StaticClient:
    def __init__(self, value=None, error=None):
        self.value = value
        self.error = error

    def fetch(self, _url):
        if self.error:
            raise self.error
        return self.value


class ReadingValidator:
    def __init__(self, error=None):
        self.error = error
        self.values = []

    def validate(self, path):
        self.values.append(json.loads(path.read_text("utf-8")))
        if self.error:
            raise self.error


def test_create_profile_saves_config_without_sing_box_validation(store):
    source = {
        "outbounds": [{"type": "direct", "tag": OUTBOUND_TAG}],
        "log": {"level": "debug"},
    }
    validator = ReadingValidator(error=AssertionError("validator must not run"))
    service = ProfileService(store, StaticClient(source), validator)

    profile = service.create_profile(
        "Main",
        "https://example.test/config.json",
        InboundConfig(port=2088),
    )

    written = json.loads(store.config_path(profile.id).read_text("utf-8"))
    assert written["inbounds"][0]["listen_port"] == 2088
    assert "log" not in written
    assert validator.values == []
    assert profile.last_update_ok is None


def test_failed_create_keeps_profile_for_later_retry(store):
    service = ProfileService(
        store,
        StaticClient(error=SubscriptionError("network failed")),
        ReadingValidator(),
    )

    profile = service.create_profile(
        "Offline",
        "https://example.test/config.json",
        InboundConfig(),
    )

    assert store.get(profile.id).name == "Offline"
    assert store.get(profile.id).last_update_ok is False
    assert "network failed" in store.get(profile.id).last_error
    assert store.has_config(profile.id) is False


def test_update_validates_before_committing_and_filters_sections(store):
    profile = store.create(
        "Main",
        "https://example.test/config.json",
        InboundConfig(port=2088),
    )
    source = {
        "dns": {"servers": [{"type": "local"}]},
        "inbounds": [{"type": "tun"}],
        "endpoints": [{"type": "wireguard", "tag": "wg"}],
        "outbounds": [{"type": "direct", "tag": OUTBOUND_TAG}],
        "log": {"level": "debug"},
        "experimental": {"cache_file": {"enabled": True}},
    }
    validator = ReadingValidator()
    service = ProfileService(store, StaticClient(source), validator)

    updated = service.update(profile.id)

    written = json.loads(store.config_path(profile.id).read_text("utf-8"))
    assert written["inbounds"][0]["listen_port"] == 2088
    assert written["dns"] == source["dns"]
    assert written["endpoints"] == source["endpoints"]
    assert "log" not in written
    assert "experimental" not in written
    assert updated.last_update_ok is True
    assert validator.values == [written]
    assert json.loads(store.source_path(profile.id).read_text("utf-8")) == source


@pytest.mark.parametrize(
    "error",
    [
        SubscriptionError("network failed"),
        ValidationError("invalid config"),
    ],
)
def test_failed_update_keeps_last_working_files(store, error):
    profile = store.create(
        "Main",
        "https://example.test/config.json",
        InboundConfig(),
    )
    original_source = {"outbounds": [{"type": "direct"}]}
    original_config = {"inbounds": [{"type": "mixed", "listen_port": 2080}]}
    store.commit_configuration(profile, original_source, original_config)

    if isinstance(error, SubscriptionError):
        client = StaticClient(error=error)
        validator = ReadingValidator()
    else:
        client = StaticClient({"outbounds": [{"type": "block"}]})
        validator = ReadingValidator(error=error)
    service = ProfileService(store, client, validator)

    with pytest.raises(type(error)):
        service.update(profile.id)

    assert json.loads(store.source_path(profile.id).read_text("utf-8")) == original_source
    assert json.loads(store.config_path(profile.id).read_text("utf-8")) == original_config
    assert store.get(profile.id).last_update_ok is False


def test_update_of_running_profile_marks_restart_required(store):
    profile = store.create(
        "Main",
        "https://example.test/config.json",
        InboundConfig(),
    )
    service = ProfileService(
        store,
        StaticClient({"outbounds": [{"type": "direct", "tag": OUTBOUND_TAG}]}),
        ReadingValidator(),
        is_running=lambda profile_id: profile_id == profile.id,
    )

    updated = service.update(profile.id)

    assert updated.needs_restart is True


def test_failed_edit_keeps_original_profile_and_configuration(store):
    profile = store.create(
        "Original",
        "https://example.test/original.json",
        InboundConfig(port=2080),
    )
    source = {"outbounds": [{"type": "direct"}]}
    config = {"inbounds": [{"type": "mixed", "listen_port": 2080}]}
    store.commit_configuration(profile, source, config)
    service = ProfileService(
        store,
        StaticClient(error=SubscriptionError("network failed")),
        ReadingValidator(),
    )

    with pytest.raises(SubscriptionError):
        service.edit(
            profile.id,
            "Changed",
            "https://example.test/changed.json",
            InboundConfig(port=9999),
        )

    current = store.get(profile.id)
    assert current.name == "Original"
    assert current.url == "https://example.test/original.json"
    assert current.inbound.port == 2080
    assert json.loads(store.config_path(profile.id).read_text("utf-8")) == config
