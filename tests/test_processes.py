from __future__ import annotations

import io
import threading

import pytest

from another_box.errors import ProcessConflictError, ProcessStartError
from another_box.models import InboundConfig
from another_box.processes import ProcessManager


class PassingValidator:
    def validate(self, _path):
        return None


class FakeProcess:
    def __init__(self, returncode=None, output=""):
        self.returncode = returncode
        self._finished = threading.Event()
        self.stdout = FakeStream(self, output)
        self.terminated = False
        self.killed = False

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        if self.returncode is None:
            if not self._finished.wait(timeout):
                if timeout is not None:
                    raise TimeoutError
            if self.returncode is None:
                self.returncode = 0
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = 0
        self._finished.set()

    def kill(self):
        self.killed = True
        self.returncode = -9
        self._finished.set()


class FakeStream:
    def __init__(self, process, output):
        self.process = process
        self.lines = iter(output.splitlines(keepends=True))

    def readline(self):
        try:
            return next(self.lines)
        except StopIteration:
            self.process._finished.wait()
            return ""

    def close(self):
        return None


class Launcher:
    def __init__(self):
        self.processes = []

    def __call__(self, *_args, **_kwargs):
        process = FakeProcess()
        self.processes.append(process)
        return process


def create_ready_profile(store, name, inbound):
    profile = store.create(name, f"https://example.test/{name}", inbound)
    store.commit_configuration(profile, {"outbounds": []}, {"inbounds": []})
    return profile


def manager(store, app_paths, launcher=None, admin=True):
    return ProcessManager(
        store,
        PassingValidator(),
        app_paths.executable,
        launcher=launcher or Launcher(),
        admin_checker=lambda: admin,
        startup_grace=0,
    )


def test_multiple_mixed_profiles_can_run_on_different_ports(store, app_paths):
    first = create_ready_profile(store, "one", InboundConfig(port=2080))
    second = create_ready_profile(store, "two", InboundConfig(port=2081))
    process_manager = manager(store, app_paths)

    process_manager.start(first.id)
    process_manager.start(second.id)

    assert set(process_manager.active_ids()) == {first.id, second.id}
    process_manager.stop_all()


def test_mixed_port_conflict_is_rejected(store, app_paths):
    first = create_ready_profile(store, "one", InboundConfig(port=2080))
    second = create_ready_profile(store, "two", InboundConfig(port=2080))
    process_manager = manager(store, app_paths)
    process_manager.start(first.id)

    with pytest.raises(ProcessConflictError, match="уже использует"):
        process_manager.start(second.id)


def test_only_one_system_proxy_profile_is_allowed(store, app_paths):
    first = create_ready_profile(
        store,
        "one",
        InboundConfig(port=2080, set_system_proxy=True),
    )
    second = create_ready_profile(
        store,
        "two",
        InboundConfig(port=2081, set_system_proxy=True),
    )
    process_manager = manager(store, app_paths)
    process_manager.start(first.id)

    with pytest.raises(ProcessConflictError, match="Системный прокси"):
        process_manager.start(second.id)


def test_tun_stops_running_mixed_profiles(store, app_paths):
    mixed = create_ready_profile(store, "mixed", InboundConfig(port=2080))
    tun = create_ready_profile(store, "tun", InboundConfig(kind="tun"))
    launcher = Launcher()
    process_manager = manager(store, app_paths, launcher)
    process_manager.start(mixed.id)

    process_manager.start(tun.id)

    assert launcher.processes[0].terminated is True
    assert process_manager.active_ids() == [tun.id]


def test_tun_requires_administrator_before_stopping_profiles(store, app_paths):
    mixed = create_ready_profile(store, "mixed", InboundConfig())
    tun = create_ready_profile(store, "tun", InboundConfig(kind="tun"))
    launcher = Launcher()
    process_manager = manager(store, app_paths, launcher, admin=False)
    process_manager.start(mixed.id)

    with pytest.raises(ProcessStartError, match="администратора"):
        process_manager.start(tun.id)

    assert process_manager.is_running(mixed.id)


def test_mixed_cannot_start_while_tun_is_active(store, app_paths):
    tun = create_ready_profile(store, "tun", InboundConfig(kind="tun"))
    mixed = create_ready_profile(store, "mixed", InboundConfig())
    process_manager = manager(store, app_paths)
    process_manager.start(tun.id)

    with pytest.raises(ProcessConflictError, match="активен TUN"):
        process_manager.start(mixed.id)


def test_successful_restart_clears_restart_flag(store, app_paths):
    profile = create_ready_profile(store, "mixed", InboundConfig())
    profile.needs_restart = True
    store.save(profile)
    process_manager = manager(store, app_paths)

    process_manager.start(profile.id)

    assert store.get(profile.id).needs_restart is False
    process_manager.stop_all()


def test_logs_are_persisted_and_limited(store, app_paths):
    profile = create_ready_profile(store, "mixed", InboundConfig())
    process_manager = manager(store, app_paths)
    lines = [f"line {index}" for index in range(510)]
    managed_process = FakeProcess(output="\n".join(lines) + "\n")
    process_manager.launcher = lambda *_args, **_kwargs: managed_process

    process_manager.start(profile.id)
    process_manager.stop(profile.id)

    persisted = store.load_log(profile.id)
    assert len(persisted) == 500
    assert persisted[0] == "line 10"
