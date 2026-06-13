from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QThreadPool, QTimer, Qt, QUrl
from PySide6.QtGui import (
    QColor,
    QCloseEvent,
    QDesktopServices,
    QIcon,
    QPainter,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSystemTrayIcon,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from another_box.auto_update import auto_update_due
from another_box.models import Profile
from another_box.logging_config import LOGGER_NAME, read_application_log
from another_box.processes import ProcessManager
from another_box.storage import ProfileStore
from another_box.subscriptions import ProfileService
from another_box.ui.dialogs import LogDialog, ProfileDialog
from another_box.ui.profile_card import ProfileCard
from another_box.ui.sizing import fit_button_to_text
from another_box.ui.workers import Worker
from another_box.ui.windows import apply_windows_11_backdrop

logger = logging.getLogger(f"{LOGGER_NAME}.ui")


class MainWindow(QMainWindow):
    def __init__(
        self,
        store: ProfileStore,
        service: ProfileService,
        processes: ProcessManager,
        application_log: Path | None = None,
    ):
        super().__init__()
        self.store = store
        self.service = service
        self.processes = processes
        self.application_log = application_log
        self.thread_pool = QThreadPool.globalInstance()
        self._workers: set[Worker] = set()
        self._updating: set[str] = set()
        self._quitting = False
        self._first_show = True
        self._last_runtime_signature = None

        self.setWindowTitle("Another Box")
        self.resize(780, 620)
        self.setMinimumSize(620, 420)
        self.setWindowIcon(self._make_icon())

        title = QLabel("Профили")
        title.setObjectName("pageTitle")
        subtitle = QLabel("Управление подписками и процессами sing-box")
        subtitle.setObjectName("muted")

        heading = QVBoxLayout()
        heading.setSpacing(1)
        heading.addWidget(title)
        heading.addWidget(subtitle)

        self.update_all_button = QPushButton("Обновить все")
        self.update_all_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload)
        )
        self.add_button = QPushButton("Добавить профиль")
        self.add_button.setObjectName("primary")
        self.add_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogNewFolder)
        )
        self.application_log_button = QPushButton("Журнал")
        self.application_log_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)
        )
        for button in (
            self.application_log_button,
            self.update_all_button,
            self.add_button,
        ):
            fit_button_to_text(button)

        header = QHBoxLayout()
        header.addLayout(heading, 1)
        header.addWidget(self.application_log_button)
        header.addWidget(self.update_all_button)
        header.addWidget(self.add_button)

        self.status_label = QLabel("")
        self.status_label.setObjectName("muted")
        self.status_label.setWordWrap(True)

        self.cards_widget = QWidget()
        self.cards_widget.setObjectName("cardsSurface")
        self.cards_layout = QVBoxLayout(self.cards_widget)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(10)
        self.cards_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.cards_widget)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        central = QWidget()
        central.setObjectName("mainSurface")
        layout = QVBoxLayout(central)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(14)
        layout.addLayout(header)
        layout.addWidget(self.status_label)
        layout.addWidget(scroll, 1)
        self.setCentralWidget(central)

        self.add_button.clicked.connect(self.add_profile)
        self.update_all_button.clicked.connect(self.update_all)
        self.application_log_button.clicked.connect(self.show_application_log)

        self.tray = QSystemTrayIcon(self.windowIcon(), self)
        self.tray.setToolTip("Another Box")
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()
        self._rebuild_tray_menu()

        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(1000)
        self.poll_timer.timeout.connect(self._poll_runtime)
        self.poll_timer.start()

        self.auto_update_timer = QTimer(self)
        self.auto_update_timer.setInterval(60_000)
        self.auto_update_timer.timeout.connect(self._run_due_auto_updates)
        self.auto_update_timer.start()
        self.refresh()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        apply_windows_11_backdrop(self)
        if not self._first_show:
            return
        self._first_show = False
        profiles = self.store.list_profiles()
        if profiles:
            QTimer.singleShot(0, self.update_all)
        else:
            QTimer.singleShot(0, self.add_profile)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._quitting or not self.tray.isVisible():
            event.accept()
            return
        event.ignore()
        self.hide()

    def refresh(self) -> None:
        profiles = self.store.list_profiles()
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if not profiles:
            empty = QWidget()
            empty.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
            )
            empty_layout = QVBoxLayout(empty)
            empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label = QLabel("Профилей пока нет")
            label.setObjectName("emptyTitle")
            hint = QLabel("Добавьте ссылку на JSON-подписку sing-box.")
            hint.setObjectName("muted")
            hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_layout.addWidget(label, alignment=Qt.AlignmentFlag.AlignCenter)
            empty_layout.addWidget(hint, alignment=Qt.AlignmentFlag.AlignCenter)
            self.cards_layout.addWidget(empty)
        else:
            for profile in profiles:
                card = ProfileCard(
                    profile=profile,
                    running=self.processes.is_running(profile.id),
                    updating=profile.id in self._updating,
                    runtime_error=self.processes.runtime_error(profile.id),
                )
                card.start_requested.connect(self.start_profile)
                card.stop_requested.connect(self.stop_profile)
                card.update_requested.connect(self.update_profile)
                card.edit_requested.connect(self.edit_profile)
                card.delete_requested.connect(self.delete_profile)
                card.logs_requested.connect(self.show_logs)
                card.logs_folder_requested.connect(self.open_profile_logs_folder)
                self.cards_layout.addWidget(card)

        busy = bool(self._updating)
        self.update_all_button.setEnabled(bool(profiles) and not busy)
        self._rebuild_tray_menu()
        self._last_runtime_signature = self._runtime_signature(profiles)

    def add_profile(self) -> None:
        dialog = ProfileDialog(parent=self)
        if dialog.exec() != ProfileDialog.DialogCode.Accepted:
            return
        (
            name,
            url,
            inbound,
            auto_enabled,
            auto_interval,
            log_config,
        ) = dialog.values()
        self.status_label.setText(f"Добавление профиля «{name}»...")
        self.add_button.setEnabled(False)

        self._run(
            lambda: self.service.create_profile(
                name,
                url,
                inbound,
                auto_enabled,
                auto_interval,
                log_config,
            ),
            on_success=lambda _result: self._show_status(
                "Профиль создан. Запустите его вручную после проверки настроек."
            ),
            on_finished=lambda: self.add_button.setEnabled(True),
        )

    def edit_profile(self, profile_id: str) -> None:
        try:
            profile = self.store.get(profile_id)
        except Exception as error:
            self._show_error(str(error))
            return
        dialog = ProfileDialog(profile, self)
        if dialog.exec() != ProfileDialog.DialogCode.Accepted:
            return
        (
            name,
            url,
            inbound,
            auto_enabled,
            auto_interval,
            log_config,
        ) = dialog.values()
        self._updating.add(profile_id)
        self.status_label.setText(f"Сохранение профиля «{name}»...")
        self.refresh()
        self._run(
            lambda: self.service.edit(
                profile_id,
                name,
                url,
                inbound,
                auto_enabled,
                auto_interval,
                log_config,
            ),
            on_success=lambda _result: self._show_status("Профиль сохранен."),
            on_finished=lambda: self._finish_update(profile_id),
        )

    def update_profile(self, profile_id: str) -> None:
        if profile_id in self._updating:
            return
        profile = self.store.get(profile_id)
        self._updating.add(profile_id)
        self.status_label.setText(f"Обновление профиля «{profile.name}»...")
        self.refresh()
        self._run(
            lambda: self.service.update(profile_id),
            on_success=lambda _result: self._show_status("Подписка обновлена."),
            on_finished=lambda: self._finish_update(profile_id),
        )

    def update_all(self) -> None:
        profiles = self.store.list_profiles()
        if not profiles:
            return
        ids = [profile.id for profile in profiles]
        self._updating.update(ids)
        self.status_label.setText("Обновление всех подписок...")
        self.refresh()

        def operation():
            errors: list[str] = []
            for profile in profiles:
                try:
                    self.service.update(profile.id)
                except Exception as error:
                    errors.append(f"{profile.name}: {error}")
            return errors

        def completed(errors: list[str]) -> None:
            if errors:
                self._show_error(
                    "Не все подписки удалось обновить:\n\n" + "\n".join(errors)
                )
            else:
                self._show_status("Все подписки обновлены.")

        self._run(
            operation,
            on_success=completed,
            on_finished=lambda: self._finish_updates(ids),
            show_error=False,
        )

    def _run_due_auto_updates(self) -> None:
        for profile in self.store.list_profiles():
            if profile.id in self._updating or not auto_update_due(profile):
                continue
            self._updating.add(profile.id)
            logger.info(
                "Automatic subscription update started for profile %s",
                profile.name,
            )
            self._run(
                lambda pid=profile.id: self.service.update(pid),
                on_finished=lambda pid=profile.id: self._finish_update(pid),
                show_error=False,
            )
        self.refresh()

    def start_profile(self, profile_id: str) -> None:
        profile = self.store.get(profile_id)
        self.status_label.setText(f"Запуск профиля «{profile.name}»...")
        self._run(
            lambda: self.processes.start(profile_id),
            on_success=lambda _result: self._show_status(
                f"Профиль «{profile.name}» запущен."
            ),
            on_failure=lambda text: self._record_start_error(profile_id, text),
        )

    def stop_profile(self, profile_id: str) -> None:
        profile = self.store.get(profile_id)
        self.status_label.setText(f"Остановка профиля «{profile.name}»...")
        self._run(
            lambda: self.processes.stop(profile_id),
            on_success=lambda _result: self._show_status(
                f"Профиль «{profile.name}» остановлен."
            ),
        )

    def delete_profile(self, profile_id: str) -> None:
        profile = self.store.get(profile_id)
        answer = QMessageBox.question(
            self,
            "Удалить профиль",
            f"Удалить профиль «{profile.name}» и его локальные файлы?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.processes.stop(profile_id)
            self.store.delete(profile_id)
        except Exception as error:
            self._show_error(str(error))
        else:
            self._show_status("Профиль удален.")
        self.refresh()

    def show_logs(self, profile_id: str) -> None:
        profile = self.store.get(profile_id)
        LogDialog(profile.name, self.processes.logs(profile_id), self).exec()

    def show_application_log(self) -> None:
        text = (
            read_application_log(self.application_log)
            if self.application_log is not None
            else ""
        )
        LogDialog("Приложение", text, self).exec()

    def open_profile_logs_folder(self, profile_id: str) -> None:
        logs_dir = self.store.profile_dir(profile_id)
        try:
            logs_dir.mkdir(parents=True, exist_ok=True)
            opened = QDesktopServices.openUrl(QUrl.fromLocalFile(str(logs_dir)))
        except OSError as error:
            logger.error(
                "Failed to open logs folder for profile %s: %s",
                profile_id,
                error,
            )
            return
        if not opened:
            logger.error(
                "Failed to open logs folder for profile %s: %s",
                profile_id,
                logs_dir,
            )

    def quit_application(self) -> None:
        self._quitting = True
        self.status_label.setText("Остановка активных профилей...")
        self.processes.stop_all()
        self.tray.hide()
        QApplication.instance().quit()

    def _run(
        self,
        operation: Callable,
        on_success: Callable | None = None,
        on_failure: Callable[[str], None] | None = None,
        on_finished: Callable | None = None,
        show_error: bool = True,
    ) -> None:
        worker = Worker(operation)
        self._workers.add(worker)
        if on_success:
            worker.signals.succeeded.connect(on_success)
        if on_failure:
            worker.signals.failed.connect(on_failure)
        elif show_error:
            worker.signals.failed.connect(self._show_error)
        if on_finished:
            worker.signals.finished.connect(on_finished)
        worker.signals.finished.connect(lambda: self._worker_finished(worker))
        worker.signals.finished.connect(self.refresh)
        self.thread_pool.start(worker)

    def _worker_finished(self, worker: Worker) -> None:
        self._workers.discard(worker)

    def _finish_update(self, profile_id: str) -> None:
        self._updating.discard(profile_id)
        self.refresh()

    def _finish_updates(self, profile_ids: list[str]) -> None:
        self._updating.difference_update(profile_ids)
        self.refresh()

    def _show_status(self, text: str) -> None:
        self.status_label.setText(text)
        self.refresh()

    def _show_error(self, text: str) -> None:
        logger.error("%s", text)
        self.status_label.clear()
        self.refresh()

    def _record_start_error(self, profile_id: str, text: str) -> None:
        logger.error("Failed to start profile %s: %s", profile_id, text)
        self.processes.set_runtime_error(profile_id, text)
        self.status_label.clear()
        self.refresh()

    def _rebuild_tray_menu(self) -> None:
        menu = QMenu(self)
        show_action = menu.addAction("Показать окно")
        show_action.triggered.connect(self._show_window)
        log_action = menu.addAction("Журнал приложения")
        log_action.triggered.connect(self.show_application_log)
        running = self.processes.active_profiles()
        if running:
            menu.addSeparator()
            header = menu.addAction("Активные профили")
            header.setEnabled(False)
            for profile in running:
                action = menu.addAction(f"Остановить «{profile.name}»")
                action.triggered.connect(
                    lambda _checked=False, pid=profile.id: self.stop_profile(pid)
                )
        menu.addSeparator()
        quit_action = menu.addAction("Выход")
        quit_action.triggered.connect(self.quit_application)
        self.tray_menu = menu
        self.tray.setContextMenu(menu)

    def _poll_runtime(self) -> None:
        profiles = self.store.list_profiles()
        signature = self._runtime_signature(profiles)
        if signature != self._last_runtime_signature:
            self.refresh()

    def _runtime_signature(self, profiles: list[Profile]):
        return (
            tuple(sorted(self.processes.active_ids())),
            tuple(
                (profile.id, self.processes.runtime_error(profile.id))
                for profile in profiles
            ),
            tuple(sorted(self._updating)),
        )

    def _tray_activated(self, reason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self._show_window()

    def _show_window(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    @staticmethod
    def _make_icon() -> QIcon:
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor("#2563c7"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(4, 4, 56, 56, 14, 14)
        painter.setPen(QColor("white"))
        font = painter.font()
        font.setBold(True)
        font.setPixelSize(30)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "A")
        painter.end()
        return QIcon(pixmap)
