"""
tray.py — System tray icon with right-click menu.

Runs pystray in its own daemon thread; calls back to the main app
via the on_quit() callable when the user selects Quit.
"""

import logging
import threading
from typing import Callable

from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)


def _create_tray_icon() -> Image.Image:
    """
    Draw a simple microphone icon (64 × 64 RGBA) programmatically.
    No external asset files needed.
    """
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Mic capsule body
    body_x0, body_y0 = 20, 6
    body_x1, body_y1 = 44, 36
    d.rounded_rectangle(
        [body_x0, body_y0, body_x1, body_y1],
        radius=12,
        fill=(255, 255, 255, 255),
    )

    # Mic stand arc
    arc_margin = 10
    d.arc(
        [arc_margin, 28, size - arc_margin, 50],
        start=0,
        end=180,
        fill=(255, 255, 255, 220),
        width=3,
    )

    # Stand line + base
    d.line([(32, 50), (32, 58)], fill=(255, 255, 255, 220), width=3)
    d.line([(22, 58), (42, 58)], fill=(255, 255, 255, 220), width=3)

    return img


class TrayApp:
    """Manages the Windows system-tray icon and menu."""

    def __init__(self, on_quit: Callable[[], None]) -> None:
        self._on_quit = on_quit
        self._icon = None

    def run_in_thread(self) -> None:
        """Spawn the tray loop in a background daemon thread."""
        thread = threading.Thread(target=self._run, daemon=True, name="tray")
        thread.start()

    def stop(self) -> None:
        if self._icon:
            self._icon.stop()

    # ── internals ─────────────────────────────────────────────────────────

    def _run(self) -> None:
        import pystray  # imported here to keep startup fast

        icon_img = _create_tray_icon()

        menu = pystray.Menu(
            pystray.MenuItem("WhisperTray", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Dictate  (Ctrl+Shift+Q)",
                None,
                enabled=False,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._quit_handler),
        )

        self._icon = pystray.Icon(
            name="WhisperTray",
            icon=icon_img,
            title="WhisperTray — press Ctrl+Shift+Q to dictate",
            menu=menu,
        )

        logger.info("Tray icon running.")
        self._icon.run()

    def _quit_handler(self, icon, _item) -> None:
        icon.stop()
        self._on_quit()
