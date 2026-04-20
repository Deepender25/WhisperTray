"""
app.py — WhisperTray application orchestrator.

Thread map
----------
  Qt main thread      — UI, capsule widget, signal dispatch
  tray thread         — pystray event loop (daemon)
  hotkey thread       — pynput listener (daemon)
  recorder thread     — sounddevice capture (daemon)
  transcriber thread  — Whisper inference (daemon, spawned per session)

All cross-thread communication flows through AppSignals.
"""

import logging
import os
import sys
import threading
import time
from typing import Optional

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QApplication

from .capsule import CapsuleWidget
from .hotkey import HotkeyListener
from .injector import get_foreground_hwnd, inject_text, is_text_field_focused
from .recorder import AudioRecorder
from .signals import AppSignals
from .tray import TrayApp
from .transcriber import Transcriber

logger = logging.getLogger(__name__)


class WhisperTrayApp:
    """Top-level application class — owns all sub-systems."""

    def __init__(self) -> None:
        # Qt app (must exist before any QWidget)
        self._qt = QApplication.instance() or QApplication(sys.argv)
        self._qt.setQuitOnLastWindowClosed(False)

        # Signals (created on Qt thread)
        self.signals = AppSignals()
        self._connect_signals()

        # Sub-systems
        self._transcriber = Transcriber()
        self._recorder = AudioRecorder(
            on_amplitude=self._emit_amplitude,
            on_auto_stop=self._on_auto_stop,
        )
        self._hotkey = HotkeyListener(
            callback=self._on_hotkey_fired,
            on_any_press=self._on_any_key,
        )
        self._tray = TrayApp(on_quit=self._quit)

        # State
        self._capsule: Optional[CapsuleWidget] = None
        self._active = False            # is a session in progress?
        self._active_lock = threading.Lock()
        self._target_hwnd: Optional[int] = None
        self._session_start_time: float = 0.0

    # ── startup / shutdown ────────────────────────────────────────────────

    def run(self) -> None:
        """Start all sub-systems, then hand control to the Qt event loop."""
        _configure_logging()

        logger.info("WhisperTray starting…")

        # Background pre-load of Whisper model
        self._transcriber.preload()

        # System tray (own thread)
        self._tray.run_in_thread()

        # Global hotkey listener (own thread)
        self._hotkey.start()

        logger.info("Press Ctrl+Shift+Q in any text box to begin dictation.")

        # Block here until quit()
        sys.exit(self._qt.exec_())

    def _quit(self) -> None:
        logger.info("Shutting down.")
        self._hotkey.stop()
        self._tray.stop()
        self._qt.quit()

    # ── signal wiring ─────────────────────────────────────────────────────

    def _connect_signals(self) -> None:
        s = self.signals
        s.show_capsule.connect(self._show_capsule, Qt.QueuedConnection)
        s.close_capsule.connect(self._close_capsule, Qt.QueuedConnection)
        s.set_processing.connect(self._on_set_processing, Qt.QueuedConnection)
        s.set_refining.connect(self._on_set_refining, Qt.QueuedConnection)
        s.amplitude_update.connect(self._on_amplitude, Qt.QueuedConnection)
        s.text_ready.connect(self._on_text_ready, Qt.QueuedConnection)
        s.show_toast.connect(self._show_toast, Qt.QueuedConnection)
        s.quit_app.connect(self._quit, Qt.QueuedConnection)

    # ── hotkey & session control (may be called from any thread) ──────────

    def _on_hotkey_fired(self) -> None:
        with self._active_lock:
            if self._active:
                # Second press → stop recording
                self.signals.set_processing.emit()
            else:
                if not is_text_field_focused():
                    self.signals.show_toast.emit("No text box selected")
                    return
                
                self._active = True
                self._session_start_time = time.time()
                # Capture focused window *now*, before capsule steals focus
                self._target_hwnd = get_foreground_hwnd()
                self.signals.show_capsule.emit()

    def _on_any_key(self, key) -> None:
        """Called on any keypress to prematurely abort and submit."""
        with self._active_lock:
            if not self._active:
                return
            
            from pynput.keyboard import Key, KeyCode
            
            # Grace period: ignore all keypresses within 0.8 seconds of activation.
            # This prevents the initial hotkey (and its auto-repeats or release bounces) 
            # from instantly terminating the session.
            if time.time() - self._session_start_time < 0.8:
                return
            
            # Ignore the hotkey modifiers themselves when holding them
            if key in (Key.ctrl, Key.ctrl_l, Key.ctrl_r, Key.shift, Key.shift_l, Key.shift_r, Key.alt, Key.alt_l, Key.alt_r, Key.cmd, Key.cmd_l, Key.cmd_r):
                return
            
            # Avoid the target key 'q' or 'Q' or '\x11' (Ctrl+Q) if the user is holding it
            if getattr(key, 'char', None) in ('q', 'Q', '\x11'):
                return

            # Note: Emit stop recording and process text
            self.signals.set_processing.emit()

    def _on_auto_stop(self) -> None:
        """Recorder detected end-of-speech; trigger stop."""
        with self._active_lock:
            if self._active:
                self.signals.set_processing.emit()

    # ── Qt-thread slots ───────────────────────────────────────────────────

    def _show_capsule(self) -> None:
        if self._capsule is not None:
            return   # guard against double-fire

        self._capsule = CapsuleWidget()
        self._capsule.closed.connect(self._on_capsule_dismissed)
        self._capsule.show()

        # Start recording after capsule is visible
        self._recorder.start()

    def _on_set_processing(self) -> None:
        """Stop recording and switch capsule to processing state."""
        # Prevent double-firing set_processing
        if not self._recorder._recording and self._capsule and self._capsule.is_processing:
            return
            
        self._recorder.stop()
        if self._capsule:
            self._capsule.set_processing()
        # Transcribe in background
        threading.Thread(
            target=self._run_transcription,
            daemon=True,
            name="transcriber",
        ).start()

    def _on_set_refining(self) -> None:
        """Switch capsule to LLM refining state."""
        if self._capsule:
            self._capsule.set_refining()

    def _on_amplitude(self, value: float) -> None:
        if self._capsule:
            self._capsule.update_amplitude(value)

    def _on_text_ready(self, text: str) -> None:
        hwnd = self._target_hwnd
        # Close capsule first, then inject (so focus moves to target)
        self._close_capsule()
        if text:
            # Small delay so capsule fully closes
            QTimer.singleShot(
                180,
                lambda: inject_text(text, hwnd),
            )

    def _close_capsule(self) -> None:
        if self._capsule:
            self._capsule.close_animated()
            # Widget destroys itself after fade; clear ref via its closed signal

    def _on_capsule_dismissed(self) -> None:
        """Called when capsule finishes closing (fade-out complete)."""
        self._capsule = None
        with self._active_lock:
            self._active = False

    def _show_toast(self, msg: str) -> None:
        from .toast import ToastWidget
        self._toast = ToastWidget(msg)
        self._toast.show()

    # ── background transcription ──────────────────────────────────────────

    def _run_transcription(self) -> None:
        audio_path = self._recorder.save_wav()
        text = ""
        if audio_path:
            try:
                text = self._transcriber.transcribe(audio_path)
            finally:
                try:
                    os.unlink(audio_path)
                except OSError:
                    pass
                    
        # Apply optional LLM refinement
        from . import config
        from .llm import refine_text
        if text and getattr(config, "LLM_ENABLED", False):
            self.signals.set_refining.emit()
            text = refine_text(text)

        self.signals.text_ready.emit(text)

    # ── helpers ───────────────────────────────────────────────────────────

    def _emit_amplitude(self, value: float) -> None:
        """Called from recorder thread; route to Qt via signal."""
        self.signals.amplitude_update.emit(value)


# ── logging setup ─────────────────────────────────────────────────────────────

def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )
    # Silence noisy third-party loggers
    for noisy in ("whisper", "torch", "numba", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
