from __future__ import annotations

import ctypes
import sys

from PySide6.QtWidgets import QWidget


def apply_windows_11_backdrop(widget: QWidget) -> None:
    """Enable rounded corners and Mica on supported Windows 11 builds."""
    if sys.platform != "win32":
        return
    try:
        hwnd = int(widget.winId())
        dwmapi = ctypes.windll.dwmapi
        _set_int_attribute(dwmapi, hwnd, 33, 2)  # DWMWA_WINDOW_CORNER_PREFERENCE
        _set_int_attribute(dwmapi, hwnd, 38, 2)  # DWMWA_SYSTEMBACKDROP_TYPE: Mica
        _set_int_attribute(dwmapi, hwnd, 20, 0)  # DWMWA_USE_IMMERSIVE_DARK_MODE
    except (AttributeError, OSError, TypeError, ValueError):
        # Older Windows versions simply keep the native Qt window frame.
        return


def _set_int_attribute(dwmapi, hwnd: int, attribute: int, value: int) -> None:
    data = ctypes.c_int(value)
    dwmapi.DwmSetWindowAttribute(
        ctypes.c_void_p(hwnd),
        ctypes.c_uint(attribute),
        ctypes.byref(data),
        ctypes.sizeof(data),
    )
