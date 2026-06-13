from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
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
from another_box.ui.elided_label import ElidedLabel
from another_box.ui.sizing import fit_button_to_text


class ProfileCard(QFrame):
    start_requested = Signal(str)
    stop_requested = Signal(str)
    update_requested = Signal(str)
    edit_requested = Signal(str)
    delete_requested = Signal(str)
    logs_requested = Signal(str)
    logs_folder_requested = Signal(str)

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
        type_label = ElidedLabel(
            f"{profile.inbound.kind.upper()} · {profile.inbound.endpoint}"
        )
        type_label.setObjectName("muted")

        status = ElidedLabel()
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

        updated = ElidedLabel(self._updated_text(profile))
        updated.setObjectName("muted")
        auto_update = ElidedLabel(self._auto_update_text(profile))
        auto_update.setObjectName("muted")

        info_grid = QGridLayout()
        info_grid.setContentsMargins(0, 0, 0, 0)
        info_grid.setHorizontalSpacing(16)
        info_grid.setVerticalSpacing(2)
        info_grid.setColumnStretch(0, 1)
        info_grid.setColumnStretch(1, 1)
        info_grid.setColumnMinimumWidth(0, 1)
        info_grid.setColumnMinimumWidth(1, 1)
        info_grid.addWidget(type_label, 0, 0)
        info_grid.addWidget(updated, 0, 1)
        info_grid.addWidget(status, 1, 0)
        info_grid.addWidget(auto_update, 1, 1)

        details = QVBoxLayout()
        details.setSpacing(2)
        details.addWidget(name)
        details.addLayout(info_grid)

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

        logs_folder_button = QToolButton()
        logs_folder_button.setObjectName("logsFolderButton")
        logs_folder_button.setToolTip("Открыть папку с логами sing-box")
        logs_folder_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon)
        )
        folder_button_size = menu_button.sizeHint().height()
        logs_folder_button.setFixedSize(folder_button_size, folder_button_size)
        logs_folder_button.clicked.connect(
            lambda: self.logs_folder_requested.emit(profile.id)
        )

        control_width = max(
            action.minimumWidth(),
            menu_button.minimumWidth() + logs_folder_button.width() + 6,
            self._action_button_width(action),
        )
        action.setFixedWidth(control_width)
        menu_button.setFixedWidth(control_width - logs_folder_button.width() - 6)
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
        secondary_controls = QHBoxLayout()
        secondary_controls.setContentsMargins(0, 0, 0, 0)
        secondary_controls.setSpacing(6)
        secondary_controls.addWidget(logs_folder_button)
        secondary_controls.addWidget(menu_button)
        controls.addLayout(secondary_controls)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 12, 15, 12)
        layout.setSpacing(16)
        layout.addLayout(details, 1)
        layout.addLayout(controls)

    @staticmethod
    def _action_button_width(button: QPushButton) -> int:
        original_text = button.text()
        widths: list[int] = []
        for text in ("Запустить", "Стоп"):
            button.setText(text)
            button.ensurePolished()
            widths.append(button.sizeHint().width() + 16)
        button.setText(original_text)
        return max(widths)

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
    def _auto_update_text(profile: Profile) -> str:
        if not profile.auto_update_enabled:
            return "Автообновление выключено"
        return (
            "Автообновление: каждые "
            f"{profile.auto_update_interval_minutes} мин"
        )

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
            if runtime_error.startswith("sing-box неожиданно завершился"):
                return "sing-box завершился с ошибкой", "error"
            return "Не удалось запустить sing-box", "error"
        if update_failed:
            return "Не удалось обновить подписку", "error"
        if running and needs_restart:
            return "Работает · требуется перезапуск", "warning"
        if running:
            return "Работает", "success"
        return "Остановлен", "muted"
