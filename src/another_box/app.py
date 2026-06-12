from __future__ import annotations

import sys

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QMessageBox

from another_box.configuration import SingBoxValidator
from another_box.logging_config import configure_logging, install_exception_hook
from another_box.paths import AppPaths
from another_box.processes import ProcessManager
from another_box.single_instance import SingleInstance
from another_box.storage import ProfileStore
from another_box.subscriptions import ProfileService, SubscriptionClient
from another_box.ui.main_window import MainWindow
from another_box.ui.styles import APP_STYLE, preferred_windows_style


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Another Box")
    app.setApplicationDisplayName("Another Box")
    app.setOrganizationName("AnotherBox")
    app.setQuitOnLastWindowClosed(False)
    app.setStyle(preferred_windows_style())
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(APP_STYLE)

    paths = AppPaths.default()
    paths.ensure()
    configure_logging(paths.application_log)
    install_exception_hook()
    instance = SingleInstance(str(paths.lock_file))
    if not instance.acquire():
        QMessageBox.information(
            None,
            "Another Box",
            "Another Box уже запущен.",
        )
        return 0

    store = ProfileStore(paths)
    validator = SingBoxValidator(paths.executable)
    processes = ProcessManager(store, validator, paths.executable)
    service = ProfileService(
        store,
        SubscriptionClient(),
        validator,
        is_running=processes.is_running,
    )
    window = MainWindow(store, service, processes, paths.application_log)
    window.show()

    app.aboutToQuit.connect(processes.stop_all)
    app.aboutToQuit.connect(instance.release)
    return app.exec()
