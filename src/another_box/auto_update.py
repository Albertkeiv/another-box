from __future__ import annotations

from datetime import UTC, datetime, timedelta

from another_box.models import MIN_AUTO_UPDATE_MINUTES, Profile


def auto_update_due(profile: Profile, now: datetime | None = None) -> bool:
    if not profile.auto_update_enabled:
        return False
    reference_text = profile.last_update_attempt_at or profile.last_updated_at
    if not reference_text:
        return True
    try:
        reference = datetime.fromisoformat(reference_text)
    except ValueError:
        return True
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=UTC)
    current = now or datetime.now(UTC)
    interval = timedelta(
        minutes=max(MIN_AUTO_UPDATE_MINUTES, profile.auto_update_interval_minutes)
    )
    return current >= reference.astimezone(UTC) + interval
