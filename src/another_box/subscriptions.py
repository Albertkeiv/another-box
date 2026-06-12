from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx

from another_box.configuration import ConfigValidator, build_configuration, validate_data
from another_box.errors import SubscriptionError
from another_box.models import Profile, utc_now
from another_box.storage import ProfileStore


class SubscriptionClient:
    def __init__(
        self,
        timeout: float = 20.0,
        transport: httpx.BaseTransport | None = None,
    ):
        self.timeout = timeout
        self.transport = transport

    def fetch(self, url: str) -> dict[str, Any]:
        try:
            with httpx.Client(
                timeout=self.timeout,
                follow_redirects=True,
                verify=True,
                transport=self.transport,
                headers={"User-Agent": "AnotherBox/0.1"},
            ) as client:
                response = client.get(url)
                response.raise_for_status()
                value = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise SubscriptionError(f"Не удалось получить подписку: {error}") from error
        if not isinstance(value, dict):
            raise SubscriptionError("Корень подписки должен быть JSON-объектом.")
        return value


class ProfileService:
    def __init__(
        self,
        store: ProfileStore,
        client: SubscriptionClient,
        validator: ConfigValidator,
        is_running: Callable[[str], bool] | None = None,
    ):
        self.store = store
        self.client = client
        self.validator = validator
        self.is_running = is_running or (lambda _profile_id: False)

    def create_and_update(
        self,
        name: str,
        url: str,
        inbound,
    ) -> Profile:
        profile = self.store.create(name, url, inbound)
        try:
            return self.update(profile.id)
        except Exception:
            self.store.delete(profile.id)
            raise

    def update(self, profile_id: str) -> Profile:
        profile = self.store.get(profile_id)
        try:
            source = self.client.fetch(profile.url)
            config = build_configuration(source, profile.inbound)
            validate_data(self.validator, config, self.store.profile_dir(profile.id))
        except Exception as error:
            profile.last_update_ok = False
            profile.last_error = str(error)
            self.store.save(profile)
            raise

        profile.last_updated_at = utc_now()
        profile.last_update_ok = True
        profile.last_error = None
        profile.needs_restart = self.is_running(profile.id)
        self.store.commit_configuration(profile, source, config)
        return profile

    def edit(
        self,
        profile_id: str,
        name: str,
        url: str,
        inbound,
    ) -> Profile:
        original = self.store.get(profile_id)
        candidate = Profile.from_dict(original.to_dict())
        candidate.name = name.strip()
        candidate.url = url.strip()
        candidate.inbound = inbound
        try:
            source = (
                self.client.fetch(candidate.url)
                if candidate.url != original.url
                else self.store.load_source(candidate.id)
            )
            config = build_configuration(source, candidate.inbound)
            validate_data(self.validator, config, self.store.profile_dir(candidate.id))
        except Exception as error:
            original.last_update_ok = False
            original.last_error = str(error)
            self.store.save(original)
            raise
        candidate.last_updated_at = utc_now()
        candidate.last_update_ok = True
        candidate.last_error = None
        candidate.needs_restart = self.is_running(candidate.id)
        self.store.commit_configuration(candidate, source, config)
        return candidate
