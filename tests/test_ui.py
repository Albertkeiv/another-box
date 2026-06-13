from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialogButtonBox,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QToolButton,
)

from another_box.configuration import SingBoxValidator
from another_box.models import (
    INBOUND_TAG,
    MIN_AUTO_UPDATE_MINUTES,
    InboundConfig,
    Profile,
    SingBoxLogConfig,
)
from another_box.paths import AppPaths
from another_box.processes import ProcessManager
from another_box.storage import ProfileStore
from another_box.subscriptions import ProfileService, SubscriptionClient
from another_box.ui.dialogs import ProfileDialog
from another_box.ui.elided_label import ElidedLabel
from another_box.ui.main_window import MainWindow
from another_box.ui.profile_card import ProfileCard
from another_box.ui.sizing import fit_button_to_text
from another_box.ui.styles import preferred_windows_style


def test_profile_dialog_russian_buttons_fit_text(qtbot):
    dialog = ProfileDialog()
    qtbot.addWidget(dialog)

    box = dialog.findChild(QDialogButtonBox)
    for button in box.buttons():
        required = button.fontMetrics().horizontalAdvance(button.text()) + 24
        assert button.minimumWidth() >= required

    assert all(
        line_edit.text() != INBOUND_TAG
        for line_edit in dialog.findChildren(QLineEdit)
    )
    assert dialog.auto_update_interval.minimum() == MIN_AUTO_UPDATE_MINUTES
    assert dialog.auto_update_interval.isEnabled() is False
    assert dialog.auto_update_hint.text() == "Минимум 30 минут"


def test_auto_update_controls_restore_profile_values(qtbot):
    profile = Profile(
        id="auto",
        name="Auto",
        url="https://example.test/config",
        auto_update_enabled=True,
        auto_update_interval_minutes=90,
    )
    dialog = ProfileDialog(profile)
    qtbot.addWidget(dialog)

    assert dialog.auto_update_check.isChecked() is True
    assert dialog.auto_update_interval.isEnabled() is True
    assert dialog.auto_update_interval.value() == 90


def test_sing_box_log_controls_restore_profile_values(qtbot):
    profile = Profile(
        id="logging",
        name="Logging",
        url="https://example.test/config",
        sing_box_log=SingBoxLogConfig(
            enabled=False,
            level="error",
            timestamp=False,
        ),
    )
    dialog = ProfileDialog(profile)
    qtbot.addWidget(dialog)

    assert dialog.logging_enabled_check.isChecked() is False
    assert dialog.logging_level_combo.currentData() == "error"
    assert dialog.logging_level_combo.isEnabled() is False
    assert dialog.logging_timestamp_check.isChecked() is False
    assert dialog.logging_timestamp_check.isEnabled() is False

    dialog.logging_enabled_check.setChecked(True)

    assert dialog.logging_level_combo.isEnabled() is True
    assert dialog.logging_timestamp_check.isEnabled() is True


def test_auto_update_interval_below_minimum_is_marked_invalid(qtbot):
    dialog = ProfileDialog()
    qtbot.addWidget(dialog)
    dialog.auto_update_check.setChecked(True)

    dialog.auto_update_interval.lineEdit().setText("15")

    assert dialog.auto_update_interval.property("invalid") is True
    assert dialog.auto_update_hint.objectName() == "error"
    assert dialog.save_button.isEnabled() is False

    dialog.auto_update_interval.lineEdit().setText("30")

    assert dialog.auto_update_interval.property("invalid") is False
    assert dialog.auto_update_hint.objectName() == "muted"
    assert dialog.save_button.isEnabled() is True

def test_profile_card_action_button_fits_longer_label(qtbot):
    profile = Profile(
        id="test",
        name="Основной профиль",
        url="https://example.test/config",
        inbound=InboundConfig(),
    )
    card = ProfileCard(profile, running=False, updating=False, runtime_error=None)
    qtbot.addWidget(card)

    button = next(
        widget
        for widget in card.findChildren(QPushButton)
        if widget.text() == "Запустить"
    )
    assert button.minimumWidth() >= button.sizeHint().width()


def test_running_profile_uses_short_stop_label_and_fits(qtbot):
    profile = Profile(
        id="running",
        name="Рабочий профиль",
        url="https://example.test/config",
        inbound=InboundConfig(),
    )
    card = ProfileCard(profile, running=True, updating=False, runtime_error=None)
    qtbot.addWidget(card)

    button = next(
        widget for widget in card.findChildren(QPushButton) if widget.text() == "Стоп"
    )
    assert button.minimumWidth() >= button.sizeHint().width()


def test_profile_controls_keep_same_width_between_states(qtbot):
    profile = Profile(
        id="stable",
        name="Стабильный профиль",
        url="https://example.test/config",
        inbound=InboundConfig(),
    )
    stopped = ProfileCard(
        profile, running=False, updating=False, runtime_error=None
    )
    running = ProfileCard(
        profile, running=True, updating=False, runtime_error=None
    )
    qtbot.addWidget(stopped)
    qtbot.addWidget(running)

    stopped_button = next(
        button
        for button in stopped.findChildren(QPushButton)
        if button.text() == "Запустить"
    )
    running_button = next(
        button
        for button in running.findChildren(QPushButton)
        if button.text() == "Стоп"
    )

    assert stopped_button.width() == running_button.width()
    assert stopped_button.minimumWidth() == running_button.minimumWidth()


def test_fit_button_uses_size_hint(qtbot):
    button = QPushButton("Очень длинная подпись кнопки")
    qtbot.addWidget(button)

    fit_button_to_text(button)

    assert button.minimumWidth() >= button.sizeHint().width()


def test_windows_style_is_preferred_when_available():
    assert preferred_windows_style().casefold() in {
        "windows11",
        "windowsvista",
        "windows",
        "fusion",
    }


def test_error_text_is_not_left_in_main_window(qtbot, monkeypatch, tmp_path):
    paths = AppPaths(tmp_path / "data", tmp_path / "sing-box.exe")
    store = ProfileStore(paths)
    validator = SingBoxValidator(paths.executable)
    processes = ProcessManager(store, validator, paths.executable)
    service = ProfileService(store, SubscriptionClient(), validator)
    window = MainWindow(store, service, processes, paths.application_log)
    qtbot.addWidget(window)
    critical_called = False

    def critical(*_args, **_kwargs):
        nonlocal critical_called
        critical_called = True

    monkeypatch.setattr(QMessageBox, "critical", critical)

    window.status_label.setText("Операция выполняется...")
    window._show_error("Подробная ошибка")

    assert window.status_label.text() == ""
    assert critical_called is False
    window.tray.hide()


def test_profile_logs_folder_button_opens_profile_directory(
    qtbot,
    monkeypatch,
    tmp_path,
):
    paths = AppPaths(tmp_path / "data", tmp_path / "sing-box.exe")
    store = ProfileStore(paths)
    validator = SingBoxValidator(paths.executable)
    processes = ProcessManager(store, validator, paths.executable)
    service = ProfileService(store, SubscriptionClient(), validator)
    window = MainWindow(store, service, processes, paths.application_log)
    qtbot.addWidget(window)
    profile = store.create(
        "Logs",
        "https://example.test/config",
        InboundConfig(),
    )
    window.refresh()
    opened_paths = []

    monkeypatch.setattr(
        QDesktopServices,
        "openUrl",
        lambda url: opened_paths.append(url.toLocalFile()) or True,
    )

    card = window.cards_widget.findChild(ProfileCard)
    button = card.findChild(QToolButton, "logsFolderButton")
    button.click()

    assert [Path(path) for path in opened_paths] == [store.profile_dir(profile.id)]
    assert store.profile_dir(profile.id).is_dir()
    assert button.toolTip() == "Открыть папку с логами sing-box"
    window.tray.hide()


def test_profile_card_uses_non_blocking_error_statuses():
    assert ProfileCard._status(False, False, "start failed", False, False) == (
        "Не удалось запустить sing-box",
        "error",
    )
    assert ProfileCard._status(False, False, None, False, True) == (
        "Не удалось обновить подписку",
        "error",
    )
    assert ProfileCard._status(
        False,
        False,
        "sing-box неожиданно завершился: код 1",
        False,
        False,
    ) == ("sing-box завершился с ошибкой", "error")


def test_profile_card_uses_compact_three_row_layout(qtbot):
    profile = Profile(
        id="compact",
        name="Компактный профиль",
        url="https://example.test/config",
        inbound=InboundConfig(),
        auto_update_enabled=True,
        auto_update_interval_minutes=60,
    )
    card = ProfileCard(profile, running=False, updating=False, runtime_error=None)
    qtbot.addWidget(card)

    details = card.layout().itemAt(0).layout()
    assert details.count() == 2
    info_grid = details.itemAt(1).layout()
    assert info_grid.rowCount() == 2
    assert info_grid.columnCount() == 2


def test_elided_label_keeps_full_text_in_tooltip(qtbot):
    text = "Очень длинная техническая информация о профиле"
    label = ElidedLabel(text)
    label.resize(40, 24)
    qtbot.addWidget(label)

    assert label.full_text() == text
    assert label.toolTip() == text
