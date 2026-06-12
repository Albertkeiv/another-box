from __future__ import annotations

import pytest

from another_box.configuration import build_configuration
from another_box.errors import ValidationError
from another_box.models import OUTBOUND_TAG, InboundConfig


def test_build_configuration_keeps_only_allowed_subscription_sections():
    source = {
        "log": {"level": "info"},
        "dns": {"servers": [{"type": "local"}]},
        "inbounds": [{"type": "socks", "listen_port": 1000}],
        "endpoints": [{"type": "wireguard", "tag": "wg"}],
        "outbounds": [
            {"type": "selector", "tag": OUTBOUND_TAG, "outbounds": ["direct"]},
            {"type": "direct", "tag": "direct"},
        ],
        "route": {
            "rules": [
                {"inbound": ["old-in"], "action": "route", "outbound": "direct"},
                {"domain_suffix": [".example.com"], "action": "reject"},
            ]
        },
        "experimental": {"cache_file": {"enabled": True}},
        "ntp": {"enabled": True},
    }
    inbound = InboundConfig(kind="mixed", port=2080)

    result = build_configuration(source, inbound)

    assert result["inbounds"] == [inbound.to_sing_box()]
    assert result["dns"] == source["dns"]
    assert result["endpoints"] == source["endpoints"]
    assert result["outbounds"] == source["outbounds"]
    assert set(result) == {"inbounds", "outbounds", "endpoints", "route", "dns"}
    assert "log" not in result
    assert "experimental" not in result
    assert "ntp" not in result
    assert result["route"]["rules"][0]["inbound"] == ["old-in"]
    assert "inbound" not in result["route"]["rules"][1]
    assert source["inbounds"][0]["type"] == "socks"
    assert source["route"]["rules"][0]["inbound"] == ["old-in"]


def test_optional_allowed_sections_can_be_absent():
    source = {
        "outbounds": [{"type": "direct", "tag": OUTBOUND_TAG}],
        "log": {"level": "debug"},
    }

    result = build_configuration(source, InboundConfig())

    assert set(result) == {"outbounds", "inbounds"}


def test_tun_configuration_uses_current_array_address_shape():
    inbound = InboundConfig(
        kind="tun",
        interface_name="another-box",
        address="172.19.0.1/30",
    )

    result = inbound.to_sing_box()

    assert result["type"] == "tun"
    assert result["tag"] == "tun-in"
    assert result["address"] == ["172.19.0.1/30"]
    assert result["auto_route"] is True
    assert result["strict_route"] is True


def test_inbound_tag_is_user_configurable():
    inbound = InboundConfig(tag="custom")

    assert inbound.tag == "custom"
    assert inbound.to_sing_box()["tag"] == "custom"


def test_old_proxy_inbound_tag_is_migrated_to_kind_default():
    assert InboundConfig(kind="mixed", tag="PROXY").tag == "mixed-in"
    assert InboundConfig(kind="tun", tag="PROXY").tag == "tun-in"


def test_configuration_requires_proxy_outbound():
    with pytest.raises(ValidationError, match="outbound.*PROXY"):
        build_configuration(
            {"outbounds": [{"type": "direct", "tag": "direct"}]},
            InboundConfig(),
        )


def test_nested_logical_route_rules_are_preserved():
    source = {
        "outbounds": [{"type": "direct", "tag": OUTBOUND_TAG}],
        "route": {
            "rules": [
                {
                    "type": "logical",
                    "mode": "or",
                    "rules": [
                        {"inbound": "mixed-in", "network": ["tcp"]},
                        {
                            "type": "logical",
                            "mode": "and",
                            "rules": [{"inbound": ["tun-in"], "port": [443]}],
                        },
                    ],
                    "action": "route",
                    "outbound": "proxy",
                }
            ]
        }
    }

    result = build_configuration(source, InboundConfig())
    nested = result["route"]["rules"][0]["rules"]

    assert nested[0]["inbound"] == "mixed-in"
    assert nested[1]["rules"][0]["inbound"] == ["tun-in"]
