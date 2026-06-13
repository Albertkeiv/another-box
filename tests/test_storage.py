from __future__ import annotations

import json

from another_box.models import InboundConfig, SingBoxLogConfig


def test_profile_round_trip_and_delete(store):
    profile = store.create(
        "Основной",
        "https://example.test/sub.json",
        InboundConfig(port=2081),
    )

    loaded = store.get(profile.id)
    assert loaded.name == "Основной"
    assert loaded.inbound.port == 2081
    assert store.list_profiles() == [loaded]

    store.delete(profile.id)
    assert store.list_profiles() == []


def test_old_profile_defaults_auto_update_to_disabled(store):
    profile = store.create(
        "Legacy",
        "https://example.test/sub.json",
        InboundConfig(),
    )
    metadata = store.metadata_path(profile.id)
    value = json.loads(metadata.read_text("utf-8"))
    value.pop("auto_update_enabled")
    value.pop("auto_update_interval_minutes")
    metadata.write_text(json.dumps(value), encoding="utf-8")

    loaded = store.get(profile.id)

    assert loaded.auto_update_enabled is False
    assert loaded.auto_update_interval_minutes == 60


def test_old_profile_defaults_sing_box_logging(store):
    profile = store.create(
        "Legacy",
        "https://example.test/sub.json",
        InboundConfig(),
    )
    metadata = store.metadata_path(profile.id)
    value = json.loads(metadata.read_text("utf-8"))
    value.pop("sing_box_log")
    metadata.write_text(json.dumps(value), encoding="utf-8")

    loaded = store.get(profile.id)

    assert loaded.sing_box_log == SingBoxLogConfig()


def test_profile_sing_box_logging_round_trip(store):
    profile = store.create(
        "Logging",
        "https://example.test/sub.json",
        InboundConfig(),
    )
    profile.sing_box_log = SingBoxLogConfig(
        enabled=False,
        level="warn",
        timestamp=False,
    )
    store.save(profile)

    loaded = store.get(profile.id)

    assert loaded.sing_box_log == profile.sing_box_log


def test_commit_configuration_writes_all_files(store):
    profile = store.create(
        "Test",
        "https://example.test/sub.json",
        InboundConfig(),
    )
    source = {"outbounds": [{"type": "direct"}], "inbounds": [{"type": "socks"}]}
    config = {"outbounds": source["outbounds"], "inbounds": [{"type": "mixed"}]}

    store.commit_configuration(profile, source, config)

    assert json.loads(store.source_path(profile.id).read_text("utf-8")) == source
    assert json.loads(store.config_path(profile.id).read_text("utf-8")) == config
    assert not list(store.profile_dir(profile.id).glob("*.tmp"))
