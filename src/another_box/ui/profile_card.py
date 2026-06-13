from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSizePolicy,
    QStyle,
    QToolButton,
    QVBoxLayout,
)

from another_box.models import Profile
from another_box.ui.sizing import fit_button_to_text


class ProfileCard(QFrame):
    start_requested = Signal(str)
    stop_requested = Signal(str)
    update_requested = Signal(str)
    edit_requested = Signal(str)
    delete_requested = Signal(str)
    logs_requested = Signal(str)

    def __init__(
        self,
        profile: Profile,
        running: bool,
        updating: bool,
        runtime_error: str | None,
        parent=None,
    ):
        super().__init__(parent)
        self.profile = profile
        self.setObjectName("profileCard")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        name = QLabel(profile.name)
        name.setObjectName("profileName")
        type_label = QLabel(
            f"{profile.inbound.kind.upper()} · {profile.inbound.endpoint}"
        )
        type_label.setObjectName("muted")
        type_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        status = QLabel()
        status_text, status_style = self._status(
            running,
            updating,
            runtime_error,
            profile.needs_restart,
            profile.last_update_ok is False,
        )
        status.setText(status_text)
        status.setObjectName(status_style)
        status.setToolTip(runtime_error or profile.last_error or "")

        updated = QLabel(self._updated_text(profile))
        updated.setObjectName("muted")

        details = QVBoxLayout()
        details.setSpacing(3)
        details.addWidget(name)
        details.addWidget(type_label)
        details.addWidget(status)
        details.addWidget(updated)

        action = QPushButton("Стоп" if running else "Запустить")
        action.setObjectName("primary" if not running else "")
        action.setIcon(
            self.style().standardIcon(
                QStyle.StandardPixmap.SP_MediaStop
                if running
                else QStyle.StandardPixmap.SP_MediaPlay
            )
        )
        action.setEnabled(not updating)
        action.clicked.connect(
            lambda: (
                self.stop_requested.emit(profile.id)
                if running
                else self.start_requested.emit(profile.id)
            )
        )
        fit_button_to_text(action)

        menu_button = QToolButton()
        menu_button.setObjectName("moreButton")
        menu_button.setText("Ещё...")
        menu_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        fit_button_to_text(menu_button)
        menu = QMenu(menu_button)
        update_action = menu.addAction("Обновить подписку")
        edit_action = menu.addAction("Изменить профиль")
        log_action = menu.addAction("Открыть журнал")
        menu.addSeparator()
        delete_action = menu.addAction("Удалить профиль")
        update_action.setEnabled(not updating)
        edit_action.setEnabled(not updating)
        update_action.triggered.connect(lambda: self.update_requested.emit(profile.id))
        edit_action.triggered.connect(lambda: self.edit_requested.emit(profile.id))
        log_action.triggered.connect(lambda: self.logs_requested.emit(profile.id))
        delete_action.triggered.connect(lambda: self.delete_requested.emit(profile.id))
        menu_button.setMenu(menu)

        controls = QVBoxLayout()
        controls.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        controls.addWidget(action)
        controls.addWidget(menu_button)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 15, 15, 15)
        layout.setSpacing(16)
        layout.addLayout(details, 1)
        layout.addLayout(controls)

    @staticmethod
    def _updated_text(profile: Profile) -> str:
        if not profile.last_updated_at:
            return "Подписка еще не обновлялась"
        try:
            value = datetime.fromisoformat(profile.last_updated_at).astimezone()
            return f"Обновлено: {value:%d.%m.%Y %H:%M}"
        except ValueError:
            return f"Обновлено: {profile.last_updated_at}"

    @staticmethod
    def _status(
        running: bool,
        updating: bool,
        runtime_error: str | None,
        needs_restart: bool,
        update_failed: bool,
    ) -> tuple[str, str]:
        if updating:
            return "Обновление подписки...", "warning"
        if runtime_error:
            return "Ошибка процесса", "error"
        if update_failed:
            return "Ошибка обновления · доступна сохраненная версия", "error"
        if running and needs_restart:
            return "Работает · требуется перезапуск", "warning"
        if running:
            return "Работает", "success"
        return "Остановлен", "muted"
