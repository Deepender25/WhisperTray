"""
signals.py — Qt signal bus for safe cross-thread UI updates.

All threads communicate with the Qt main thread exclusively
through these signals, keeping Qt operations off non-Qt threads.
"""

from PyQt5.QtCore import QObject, pyqtSignal


class AppSignals(QObject):
    """Singleton signal bus used throughout the application."""

    # Emitted by the hotkey thread → Qt thread: show the capsule
    show_capsule = pyqtSignal()

    # Emitted by the transcription thread → Qt thread: hide the capsule
    close_capsule = pyqtSignal()

    # Emitted by the recorder thread → Qt thread: update wave animation
    amplitude_update = pyqtSignal(float)

    # Emitted when recording stops and processing begins
    set_processing = pyqtSignal()

    # Emitted when transcription is ready → inject into target window
    text_ready = pyqtSignal(str)

    # Emitted by tray "Quit" action → shut everything down
    quit_app = pyqtSignal()
