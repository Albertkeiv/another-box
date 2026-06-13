from __future__ import annotations

from PySide6.QtWidgets import QStyleFactory


def preferred_windows_style() -> str:
    available = {name.casefold(): name for name in QStyleFactory.keys()}
    for candidate in ("windows11", "windowsvista", "windows"):
        if candidate in available:
            return available[candidate]
    return available.get("fusion", "Fusion")


# Keep native widgets native. The stylesheet only supplies the Fluent surface,
# hierarchy, and accent treatment that Qt's Windows style does not provide.
APP_STYLE = """
QWidget {
    font-size: 10pt;
}
QMainWindow, QDialog {
    background: #f3f3f3;
}
QWidget#mainSurface, QWidget#cardsSurface {
    background: transparent;
}
QFrame#profileCard {
    background: #fbfbfb;
    border: 1px solid #e5e5e5;
    border-radius: 7px;
}
QFrame#profileCard:hover {
    background: #ffffff;
    border-color: #d5d5d5;
}
QLabel#pageTitle {
    color: #1a1a1a;
    font-family: "Segoe UI Variable Display", "Segoe UI";
    font-size: 20pt;
    font-weight: 600;
}
QLabel#emptyTitle, QLabel#profileName {
    color: #1a1a1a;
    font-weight: 600;
}
QLabel#emptyTitle {
    font-size: 14pt;
}
QLabel#profileName {
    font-size: 12pt;
}
QLabel#muted {
    color: #5d5d5d;
}
QLabel#success {
    color: #0f7b0f;
    font-weight: 600;
}
QLabel#warning {
    color: #9d5d00;
    font-weight: 600;
}
QLabel#error {
    color: #c42b1c;
    font-weight: 600;
}
QPushButton, QToolButton {
    min-height: 30px;
    padding-left: 12px;
    padding-right: 12px;
}
QPushButton#primary {
    color: white;
    background: #0067c0;
    border: 1px solid #0067c0;
    border-radius: 4px;
    font-weight: 600;
}
QPushButton#primary:hover {
    background: #1975c5;
    border-color: #1975c5;
}
QPushButton#primary:pressed {
    background: #005a9e;
    border-color: #005a9e;
}
QPushButton#primary:disabled {
    color: #8a8a8a;
    background: #e5e5e5;
    border-color: #d8d8d8;
}
QToolButton#moreButton {
    color: #1a1a1a;
    background: #fbfbfb;
    border: 1px solid #d1d1d1;
    border-radius: 4px;
}
QToolButton#moreButton:hover {
    background: #f0f0f0;
}
QToolButton#moreButton:pressed {
    background: #e5e5e5;
}
QLineEdit, QSpinBox, QComboBox {
    min-height: 28px;
}
QSpinBox[invalid="true"] {
    border: 1px solid #c42b1c;
}
QScrollArea {
    border: none;
    background: transparent;
}
QScrollArea > QWidget > QWidget {
    background: transparent;
}
QGroupBox {
    margin-top: 10px;
    padding-top: 8px;
    font-weight: 600;
}
QGroupBox QLabel, QGroupBox QCheckBox {
    font-weight: 400;
}
QPlainTextEdit {
    background: #ffffff;
    border: 1px solid #d6d6d6;
}
"""
