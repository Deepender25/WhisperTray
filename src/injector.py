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


def is_text_field_focused() -> bool:
    """
    Check if the current focused UI element appears to be a text input.
    Returns True if a text field is focused, False otherwise.
    """
    try:
        import uiautomation as auto
    except ImportError:
        logger.warning("uiautomation not installed; assuming text focus.")
        return True

    try:
        control = auto.GetFocusedControl()
        if not control:
            return False

        # Common text control types
        c_type = control.ControlType
        if c_type in (auto.ControlType.EditControl, auto.ControlType.DocumentControl, auto.ControlType.ComboBoxControl):
            return True

        # Fallback: check if the control supports Text or Value patterns
        # Some custom apps (like Chromium/Electron) might expose TextPattern 
        # on their main document element.
        try:
            if hasattr(control, 'GetSupportedPatternIds'):
                patterns = control.GetSupportedPatternIds()
                if auto.PatternId.TextPattern in patterns or auto.PatternId.ValuePattern in patterns:
                    return True
        except Exception as exc:
            pass # Gracefully ignore 

        # Edge cases for some web browsers or terminals where control is generic
        # but class name implies text.
        c_class = control.ClassName.lower()
        if "edit" in c_class or "scintilla" in c_class or "text" in c_class:
            return True
        
        # Chromium / Electron applications (VS Code, Chrome, Edge, Obsidian, Discord)
        if "chrome_renderwidgethost" in c_class or "chrome_widget" in c_class or "intermediate d3d" in c_class:
            return True

        # Windows Terminal and Console
        if "console" in c_class or "tty" in c_class or "pty" in c_class or "term" in c_class or "cascadia" in c_class:
            return True
            
        # Parent check often helps for complex WPF or UIA apps where focus is deep inside
        try:
            parent = control.GetParentControl()
            if parent and parent.ControlType in (auto.ControlType.EditControl, auto.ControlType.DocumentControl):
                return True
        except Exception:
            pass

        return False
    except Exception as exc:
        logger.warning("Failed to determine text focus: %s", exc)
        return True  # Fallback to allow if determination errors out


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
