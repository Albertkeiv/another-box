from __future__ import annotations

from PySide6.QtWidgets import QAbstractButton, QSizePolicy


def fit_button_to_text(button: QAbstractButton, extra_width: int = 16) -> None:
    """Keep button text and icon visible with the active Windows style and DPI."""
    button.ensurePolished()
    button.adjustSize()
    button.setMinimumWidth(button.sizeHint().width() + extra_width)
    button.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
