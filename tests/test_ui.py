from __future__ import annotations

from PySide6.QtWidgets import QDialogButtonBox, QLineEdit, QMessageBox, QPushButton

from another_box.configuration import SingBoxValidator
from another_box.models import INBOUND_TAG, InboundConfig, Profile
from another_box.paths import AppPaths
from another_box.processes import ProcessManager
from another_box.storage import ProfileStore
from another_box.subscriptions import ProfileService, SubscriptionClient
from another_box.ui.dialogs import ProfileDialog
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
    monkeypatch.setattr(QMessageBox, "critical", lambda *_args, **_kwargs: None)

    window.status_label.setText("Операция выполняется...")
    window._show_error("Подробная ошибка")

    assert window.status_label.text() == ""
    window.tray.hide()
