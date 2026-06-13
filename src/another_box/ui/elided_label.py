from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QSizePolicy


class ElidedLabel(QLabel):
    def __init__(self, text: str = "", parent=None):
        super().__init__(parent)
        self._full_text = text
        self.setToolTip(text)
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(0)
        self._update_elided_text()

    def full_text(self) -> str:
        return self._full_text

    def setText(self, text: str) -> None:
        self._full_text = text
        self.setToolTip(text)
        self._update_elided_text()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_elided_text()

    def _update_elided_text(self) -> None:
        width = max(0, self.contentsRect().width())
        text = self.fontMetrics().elidedText(
            self._full_text,
            Qt.TextElideMode.ElideRight,
            width,
        )
        QLabel.setText(self, text)
