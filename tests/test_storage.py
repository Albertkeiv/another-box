from __future__ import annotations

import json

from another_box.models import InboundConfig


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

