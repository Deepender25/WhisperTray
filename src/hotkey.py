"""
hotkey.py — Global hotkey listener (Ctrl+Shift+Q by default).

Uses pynput which works without elevated privileges on Windows.
The callback fires on a background thread — callers must be thread-safe.
"""

import logging
import threading
from typing import Callable

from pynput import keyboard as _kb

logger = logging.getLogger(__name__)

HOTKEY_COMBO = "<ctrl>+<shift>+q"


class HotkeyListener:
    """Registers a global hotkey and calls `callback` when it fires."""

    def __init__(self, callback: Callable[[], None], on_any_press: Callable[[any], None] = None) -> None:
        self._callback = callback
        self._on_any_press = on_any_press
        self._hotkey: _kb.HotKey | None = None
        self._listener: _kb.Listener | None = None
        self._lock = threading.Lock()

    def start(self) -> None:
        self._hotkey = _kb.HotKey(
            _kb.HotKey.parse(HOTKEY_COMBO),
            self._on_activate,
        )
        self._listener = _kb.Listener(
            on_press=self._handle_press,
            on_release=self._handle_release,
            suppress=False,   # don't swallow keystrokes
        )
        self._listener.daemon = True
        self._listener.start()
        logger.info("Hotkey listener started (%s)", HOTKEY_COMBO)

    def stop(self) -> None:
        if self._listener:
            self._listener.stop()
            self._listener = None
        logger.info("Hotkey listener stopped.")

    # ── internals ─────────────────────────────────────────────────────────

    def _handle_press(self, key) -> None:
        with self._lock:
            if self._hotkey:
                try:
                    self._hotkey.press(self._listener.canonical(key))
                except Exception:
                    pass   # pynput can raise on some special keys
            
            if self._on_any_press:
                self._on_any_press(key)

    def _handle_release(self, key) -> None:
        with self._lock:
            if self._hotkey:
                try:
                    self._hotkey.release(self._listener.canonical(key))
                except Exception:
                    pass

    def _on_activate(self) -> None:
        logger.debug("Hotkey activated.")
        try:
            self._callback()
        except Exception as exc:
            logger.exception("Hotkey callback error: %s", exc)
