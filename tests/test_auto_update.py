from __future__ import annotations

from datetime import UTC, datetime, timedelta

from another_box.auto_update import auto_update_due
from another_box.models import MIN_AUTO_UPDATE_MINUTES, Profile


def test_disabled_auto_update_is_never_due():
    profile = Profile(
        id="profile",
        name="Profile",
        url="https://example.test/config",
        auto_update_enabled=False,
    )

    assert auto_update_due(profile) is False


def test_profile_without_previous_attempt_is_due_immediately():
    profile = Profile(
        id="profile",
        name="Profile",
        url="https://example.test/config",
        auto_update_enabled=True,
    )

    assert auto_update_due(profile) is True


def test_auto_update_waits_for_configured_interval():
    now = datetime(2026, 6, 13, 12, 0, tzinfo=UTC)
    profile = Profile(
        id="profile",
        name="Profile",
        url="https://example.test/config",
        auto_update_enabled=True,
        auto_update_interval_minutes=45,
        last_update_attempt_at=(now - timedelta(minutes=44)).isoformat(),
    )

    assert auto_update_due(profile, now) is False

    profile.last_update_attempt_at = (now - timedelta(minutes=45)).isoformat()
    assert auto_update_due(profile, now) is True


def test_interval_is_clamped_to_thirty_minutes():
    profile = Profile(
        id="profile",
        name="Profile",
        url="https://example.test/config",
        auto_update_enabled=True,
        auto_update_interval_minutes=5,
    )

    assert profile.auto_update_interval_minutes == MIN_AUTO_UPDATE_MINUTES
