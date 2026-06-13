from __future__ import annotations

from urllib.parse import urlparse

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase, QTextCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from another_box.models import (
    DEFAULT_AUTO_UPDATE_MINUTES,
    INBOUND_TAG,
    LOG_LEVELS,
    MIN_AUTO_UPDATE_MINUTES,
    OUTBOUND_TAG,
    InboundConfig,
    Profile,
    SingBoxLogConfig,
)
from another_box.ui.sizing import fit_button_to_text
from another_box.ui.windows import apply_windows_11_backdrop


class ProfileDialog(QDialog):
    def __init__(self, profile: Profile | None = None, parent=None):
        super().__init__(parent)
        self.profile = profile
        self.setWindowTitle("Изменить профиль" if profile else "Добавить профиль")
        self.setMinimumWidth(540)

        self.name_edit = QLineEdit(profile.name if profile else "")
        self.name_edit.setPlaceholderText("Например, Основной")
        self.url_edit = QLineEdit(profile.url if profile else "")
        self.url_edit.setPlaceholderText("https://example.com/subscription.json")

        inbound = profile.inbound if profile else InboundConfig()
        self.type_combo = QComboBox()
        self.type_combo.addItem("Mixed (SOCKS/HTTP)", "mixed")
        self.type_combo.addItem("TUN", "tun")
        self.type_combo.setCurrentIndex(0 if inbound.kind == "mixed" else 1)
        tag_label = QLabel(
            f"Обязательные tag: inbound — {INBOUND_TAG}, outbound — {OUTBOUND_TAG}."
        )
        tag_label.setObjectName("muted")
        tag_label.setWordWrap(True)

        identity_group = QGroupBox("Профиль")
        identity_form = QFormLayout(identity_group)
        identity_form.addRow("Название:", self.name_edit)
        identity_form.addRow("Ссылка подписки:", self.url_edit)
        identity_form.addRow("Тип inbound:", self.type_combo)
        identity_form.addRow("", tag_label)

        auto_update_group = QGroupBox("Автообновление подписки")
        auto_update_form = QFormLayout(auto_update_group)
        self.auto_update_check = QCheckBox("Включить автообновление")
        self.auto_update_check.setChecked(
            profile.auto_update_enabled if profile else False
        )
        self.auto_update_interval = QSpinBox()
        self.auto_update_interval.setRange(MIN_AUTO_UPDATE_MINUTES, 10080)
        self.auto_update_interval.setValue(
            profile.auto_update_interval_minutes
            if profile
            else DEFAULT_AUTO_UPDATE_MINUTES
        )
        self.auto_update_interval.setEnabled(self.auto_update_check.isChecked())
        self.auto_update_check.toggled.connect(
            self.auto_update_interval.setEnabled
        )
        self.auto_update_hint = QLabel(
            f"Минимум {MIN_AUTO_UPDATE_MINUTES} минут"
        )
        self.auto_update_hint.setObjectName("muted")
        auto_update_form.addRow("", self.auto_update_check)
        auto_update_form.addRow("Интервал, минут:", self.auto_update_interval)
        auto_update_form.addRow("", self.auto_update_hint)

        logging_group = QGroupBox("Логирование sing-box")
        logging_form = QFormLayout(logging_group)
        self.logging_enabled_check = QCheckBox("Включить логирование")
        self.logging_enabled_check.setChecked(
            profile.sing_box_log.enabled if profile else True
        )
        self.logging_level_combo = QComboBox()
        for level in LOG_LEVELS:
            self.logging_level_combo.addItem(level, level)
        current_log = profile.sing_box_log if profile else SingBoxLogConfig()
        self.logging_level_combo.setCurrentIndex(
            max(0, self.logging_level_combo.findData(current_log.level))
        )
        self.logging_timestamp_check = QCheckBox("Добавлять время к строкам")
        self.logging_timestamp_check.setChecked(current_log.timestamp)
        self.logging_level_combo.setEnabled(self.logging_enabled_check.isChecked())
        self.logging_timestamp_check.setEnabled(
            self.logging_enabled_check.isChecked()
        )
        self.logging_enabled_check.toggled.connect(
            self.logging_level_combo.setEnabled
        )
        self.logging_enabled_check.toggled.connect(
            self.logging_timestamp_check.setEnabled
        )
        logging_form.addRow("", self.logging_enabled_check)
        logging_form.addRow("Уровень:", self.logging_level_combo)
        logging_form.addRow("", self.logging_timestamp_check)

        self.inbound_stack = QStackedWidget()
        self.inbound_stack.addWidget(self._mixed_page(inbound))
        self.inbound_stack.addWidget(self._tun_page(inbound))
        self.type_combo.currentIndexChanged.connect(self.inbound_stack.setCurrentIndex)
        self.inbound_stack.setCurrentIndex(self.type_combo.currentIndex())

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Сохранить")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Отмена")
        self.save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        for button in buttons.buttons():
            fit_button_to_text(button)
        self.auto_update_interval.lineEdit().textChanged.connect(
            self._update_auto_update_validation
        )
        self.auto_update_check.toggled.connect(
            lambda _checked: self._update_auto_update_validation()
        )
        self._update_auto_update_validation()
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.addWidget(identity_group)
        layout.addWidget(auto_update_group)
        layout.addWidget(logging_group)
        layout.addWidget(self.inbound_stack)
        layout.addWidget(buttons)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        apply_windows_11_backdrop(self)

    def _update_auto_update_validation(self, _text: str = "") -> None:
        raw_value = self.auto_update_interval.lineEdit().text().strip()
        try:
            value = int(raw_value)
        except ValueError:
            value = 0
        invalid = (
            self.auto_update_check.isChecked()
            and value < MIN_AUTO_UPDATE_MINUTES
        )
        self.auto_update_interval.setProperty("invalid", invalid)
        self.auto_update_interval.style().unpolish(self.auto_update_interval)
        self.auto_update_interval.style().polish(self.auto_update_interval)
        self.auto_update_hint.setObjectName("error" if invalid else "muted")
        self.auto_update_hint.style().unpolish(self.auto_update_hint)
        self.auto_update_hint.style().polish(self.auto_update_hint)
        self.save_button.setEnabled(not invalid)

    def _mixed_page(self, inbound: InboundConfig) -> QWidget:
        group = QGroupBox("Параметры mixed")
        form = QFormLayout(group)
        self.listen_edit = QLineEdit(inbound.listen)
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(inbound.port)
        self.system_proxy_check = QCheckBox("Настраивать системный прокси Windows")
        self.system_proxy_check.setChecked(inbound.set_system_proxy)
        form.addRow("Адрес:", self.listen_edit)
        form.addRow("Порт:", self.port_spin)
        form.addRow("", self.system_proxy_check)
        return group

    def _tun_page(self, inbound: InboundConfig) -> QWidget:
        group = QGroupBox("Параметры TUN")
        form = QFormLayout(group)
        self.interface_edit = QLineEdit(inbound.interface_name)
        self.address_edit = QLineEdit(inbound.address)
        self.mtu_spin = QSpinBox()
        self.mtu_spin.setRange(1280, 65535)
        self.mtu_spin.setValue(inbound.mtu)
        self.stack_combo = QComboBox()
        for value in ("mixed", "system", "gvisor"):
            self.stack_combo.addItem(value, value)
        self.stack_combo.setCurrentIndex(
            max(0, self.stack_combo.findData(inbound.stack))
        )
        self.auto_route_check = QCheckBox("Добавлять системные маршруты")
        self.auto_route_check.setChecked(inbound.auto_route)
        self.strict_route_check = QCheckBox("Строгая маршрутизация и защита DNS")
        self.strict_route_check.setChecked(inbound.strict_route)
        form.addRow("Имя интерфейса:", self.interface_edit)
        form.addRow("Адрес (CIDR):", self.address_edit)
        form.addRow("MTU:", self.mtu_spin)
        form.addRow("Стек:", self.stack_combo)
        form.addRow("", self.auto_route_check)
        form.addRow("", self.strict_route_check)
        return group

    def values(
        self,
    ) -> tuple[str, str, InboundConfig, bool, int, SingBoxLogConfig]:
        kind = self.type_combo.currentData()
        if kind == "mixed":
            inbound = InboundConfig(
                kind="mixed",
                listen=self.listen_edit.text().strip(),
                port=self.port_spin.value(),
                set_system_proxy=self.system_proxy_check.isChecked(),
            )
        else:
            inbound = InboundConfig(
                kind="tun",
                interface_name=self.interface_edit.text().strip(),
                address=self.address_edit.text().strip(),
                mtu=self.mtu_spin.value(),
                stack=self.stack_combo.currentData(),
                auto_route=self.auto_route_check.isChecked(),
                strict_route=self.strict_route_check.isChecked(),
            )
        return (
            self.name_edit.text().strip(),
            self.url_edit.text().strip(),
            inbound,
            self.auto_update_check.isChecked(),
            self.auto_update_interval.value(),
            SingBoxLogConfig(
                enabled=self.logging_enabled_check.isChecked(),
                level=self.logging_level_combo.currentData(),
                timestamp=self.logging_timestamp_check.isChecked(),
            ),
        )

    def _accept_if_valid(self) -> None:
        (
            name,
            url,
            inbound,
            _auto_enabled,
            _auto_interval,
            _log_config,
        ) = self.values()
        parsed = urlparse(url)
        problems: list[str] = []
        if not name:
            problems.append("Введите название профиля.")
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            problems.append("Введите корректную HTTP/HTTPS-ссылку подписки.")
        if inbound.kind == "mixed" and not inbound.listen:
            problems.append("Введите адрес прослушивания.")
        if inbound.kind == "tun":
            if not inbound.interface_name:
                problems.append("Введите имя TUN-интерфейса.")
            if "/" not in inbound.address:
                problems.append("Введите адрес TUN в формате CIDR.")
        if problems:
            QMessageBox.warning(self, "Проверьте данные", "\n".join(problems))
            return
        self.accept()


class LogDialog(QDialog):
    def __init__(self, profile_name: str, text: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Журнал · {profile_name}")
        self.resize(760, 460)
        editor = QPlainTextEdit()
        editor.setReadOnly(True)
        editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        editor.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        editor.setPlainText(text or "Журнал пока пуст.")
        editor.moveCursor(QTextCursor.MoveOperation.End)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText("Закрыть")
        fit_button_to_text(buttons.button(QDialogButtonBox.StandardButton.Close))
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(editor)
        layout.addWidget(buttons)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        apply_windows_11_backdrop(self)
