"""
transcriber.py — Pluggable speech-to-text engine.

Supports two backends, switchable via src/config.py:

  BACKEND = "openai"   → original openai-whisper  (small.en by default)
  BACKEND = "faster"   → faster-whisper            (small by default)

Both backends:
  * Pre-load the model in a background thread at startup
  * Expose the same transcribe(audio_path) → str API
  * Are thread-safe (transcribe() blocks until the model is ready)
"""

import logging
import os
import threading
from typing import Optional

from . import config

logger = logging.getLogger(__name__)

# Suppress verbose third-party logs regardless of backend
os.environ.setdefault("WHISPER_DISABLE_PROGRESS", "1")

# ────────────────────────────────────────────────────────────────────────────
#  Filler tokens that both Whisper flavours occasionally emit
# ────────────────────────────────────────────────────────────────────────────
_FILLERS = (
    "[BLANK_AUDIO]",
    "(blank audio)",
    "[Music]",
    "[Applause]",
    "(Music)",
    "(Applause)",
    "[noise]",
    "(noise)",
)


def _strip_fillers(text: str) -> str:
    for filler in _FILLERS:
        text = text.replace(filler, "")
    return text.strip()


# ============================================================================
#  Backend A — openai-whisper
# ============================================================================

class _OpenAIBackend:
    """Wraps openai-whisper with pre-loading and thread safety."""

    def __init__(self) -> None:
        self._model = None
        self._ready = threading.Event()
        self._lock = threading.Lock()

    def preload(self) -> None:
        thread = threading.Thread(
            target=self._load,
            daemon=True,
            name="openai-whisper-loader",
        )
        thread.start()

    def transcribe(self, audio_path: str) -> str:
        logger.debug("Waiting for OpenAI Whisper model…")
        self._ready.wait()

        if self._model is None:
            logger.error("OpenAI Whisper model failed to load.")
            return ""

        try:
            result = self._model.transcribe(
                audio_path,
                language=config.LANGUAGE,
                fp16=False,                         # CPU-safe
                verbose=False,
                condition_on_previous_text=False,
                no_speech_threshold=config.NO_SPEECH_THRESHOLD,
                logprob_threshold=-1.0,
                compression_ratio_threshold=2.4,
            )
            text: str = result.get("text", "").strip()
            return _strip_fillers(text)
        except Exception as exc:
            logger.exception("OpenAI Whisper transcription failed: %s", exc)
            return ""

    def _load(self) -> None:
        try:
            import whisper
            logger.info(
                "Loading OpenAI Whisper model '%s'…", config.OPENAI_MODEL
            )
            with self._lock:
                self._model = whisper.load_model(config.OPENAI_MODEL)
            logger.info("OpenAI Whisper model ready.")
        except Exception as exc:
            logger.exception("Failed to load OpenAI Whisper: %s", exc)
            self._model = None
        finally:
            self._ready.set()


# ============================================================================
#  Backend B — faster-whisper
# ============================================================================

class _FasterBackend:
    """
    Wraps faster-whisper (CTranslate2 port) with pre-loading and thread
    safety.  Faster-whisper returns a generator of segments; we join them
    into a single string.
    """

    def __init__(self) -> None:
        self._model = None
        self._ready = threading.Event()
        self._lock = threading.Lock()

    def preload(self) -> None:
        thread = threading.Thread(
            target=self._load,
            daemon=True,
            name="faster-whisper-loader",
        )
        thread.start()

    def transcribe(self, audio_path: str) -> str:
        logger.debug("Waiting for Faster-Whisper model…")
        self._ready.wait()

        if self._model is None:
            logger.error("Faster-Whisper model failed to load.")
            return ""

        try:
            segments, info = self._model.transcribe(
                audio_path,
                language=config.LANGUAGE,
                beam_size=config.BEAM_SIZE,
                vad_filter=True,                    # skip silent chunks
                vad_parameters=dict(
                    min_silence_duration_ms=300,
                ),
                no_speech_threshold=config.NO_SPEECH_THRESHOLD,
                condition_on_previous_text=False,
                word_timestamps=False,
            )
            logger.debug(
                "Detected language: %s (probability %.2f)",
                info.language,
                info.language_probability,
            )
            # Generator → list → join
            text = " ".join(seg.text.strip() for seg in segments).strip()
            return _strip_fillers(text)
        except Exception as exc:
            logger.exception("Faster-Whisper transcription failed: %s", exc)
            return ""

    def _load(self) -> None:
        try:
            from faster_whisper import WhisperModel
            logger.info(
                "Loading Faster-Whisper model '%s' on %s (%s)…",
                config.FASTER_MODEL,
                config.DEVICE,
                config.COMPUTE_TYPE,
            )
            with self._lock:
                self._model = WhisperModel(
                    config.FASTER_MODEL,
                    device=config.DEVICE,
                    compute_type=config.COMPUTE_TYPE,
                )
            logger.info("Faster-Whisper model ready.")
        except Exception as exc:
            logger.exception("Failed to load Faster-Whisper: %s", exc)
            self._model = None
        finally:
            self._ready.set()


# ============================================================================
#  Public façade — selected at import time based on config.BACKEND
# ============================================================================

class Transcriber:
    """
    Public transcriber that delegates to whichever backend is configured in
    src/config.py.  Drop-in replacement for the previous single-backend class.
    """

    _BACKENDS = {
        "openai": _OpenAIBackend,
        "faster": _FasterBackend,
    }

    def __init__(self) -> None:
        backend_key = config.BACKEND.lower().strip()
        backend_cls = self._BACKENDS.get(backend_key)

        if backend_cls is None:
            known = ", ".join(f'"{k}"' for k in self._BACKENDS)
            raise ValueError(
                f"Unknown BACKEND '{config.BACKEND}' in config.py. "
                f"Valid options: {known}"
            )

        logger.info("Transcription backend: %s", backend_key)
        self._backend = backend_cls()

    def preload(self) -> None:
        """Start loading the model in a background daemon thread."""
        self._backend.preload()

    def transcribe(self, audio_path: str) -> str:
        """
        Transcribe a WAV file.
        Blocks until the model is loaded (should already be done by now).
        Returns cleaned transcript string, or "" on failure.
        """
        return self._backend.transcribe(audio_path)
