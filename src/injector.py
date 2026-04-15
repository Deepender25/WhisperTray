"""
injector.py — Injects transcribed text into the previously focused window.

Strategy
--------
1. Capture the foreground window HWND *before* the capsule appears.
2. After transcription, refocus that window.
3. Copy text to clipboard, send Ctrl+V, restore old clipboard.

This approach works across virtually all Windows text inputs
(browsers, IDEs, Notepad, chat apps, etc.) without requiring
any injection-level access or keyboard emulation per character.
"""

import ctypes
import logging
import time
from ctypes import wintypes
from typing import Optional

import pyperclip
import pyautogui

logger = logging.getLogger(__name__)

# Win32 constants
SW_SHOW = 5
_user32 = ctypes.windll.user32


def get_foreground_hwnd() -> Optional[int]:
    """Return the handle of the currently active/focused window."""
    hwnd = _user32.GetForegroundWindow()
    return hwnd if hwnd else None


def _restore_focus(hwnd: int) -> None:
    """Bring a window back to the foreground."""
    # IsIconic = minimised; restore first
    if _user32.IsIconic(hwnd):
        ctypes.windll.user32.ShowWindow(hwnd, SW_SHOW)
    _user32.SetForegroundWindow(hwnd)
    time.sleep(0.12)   # allow OS to finish focus transition


def inject_text(text: str, target_hwnd: Optional[int] = None) -> None:
    """
    Paste `text` into the active text field.

    Parameters
    ----------
    text         : The transcription to insert.
    target_hwnd  : HWND captured before capsule appeared.
                   If None, pastes into whatever is currently focused.
    """
    if not text:
        return

    # Restore focus to the original window
    if target_hwnd:
        try:
            _restore_focus(target_hwnd)
        except Exception as exc:
            logger.warning("Could not restore focus: %s", exc)

    # Preserve existing clipboard content
    try:
        old_clip = pyperclip.paste()
    except Exception:
        old_clip = ""

    try:
        pyperclip.copy(text)
        time.sleep(0.05)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.08)
    except Exception as exc:
        logger.exception("Text injection failed: %s", exc)
    finally:
        # Restore clipboard (small delay so paste finishes first)
        time.sleep(0.15)
        try:
            pyperclip.copy(old_clip)
        except Exception:
            pass
