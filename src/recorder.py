"""
recorder.py — Real-time audio capture with amplitude streaming.

* Records at 16 kHz mono (optimal for Whisper)
* Emits RMS amplitude on every chunk for the wave visualiser
* Auto-stops after configurable silence timeout (default 3 s)
* Saves to a temp WAV file for Whisper to consume
"""

import threading
import tempfile
import time
import wave
from typing import Callable, Optional

import numpy as np
import sounddevice as sd

# ── audio settings ───────────────────────────────────────────────────────────
SAMPLE_RATE = 16_000    # Hz  — Whisper's native rate
CHANNELS = 1
DTYPE = "int16"
BLOCK_SIZE = 1_024      # ~64 ms per chunk

# Silence auto-stop
SILENCE_THRESHOLD = 0.012   # normalised RMS below which counts as silence
MIN_SPEECH_SECS = 0.6        # must have this much speech before auto-stop fires
SILENCE_SECS = 2.8           # silence after speech before auto-stop


class AudioRecorder:
    """
    Usage
    -----
    rec = AudioRecorder(on_amplitude=my_callback, on_auto_stop=my_stop)
    rec.start()
    ...
    rec.stop()
    path = rec.save_wav()   # returns temp file path; caller must delete it
    """

    def __init__(
        self,
        on_amplitude: Optional[Callable[[float], None]] = None,
        on_auto_stop: Optional[Callable[[], None]] = None,
    ) -> None:
        self._on_amplitude = on_amplitude
        self._on_auto_stop = on_auto_stop

        self._recording = False
        self._frames: list[np.ndarray] = []
        self._thread: Optional[threading.Thread] = None

        self._speech_secs = 0.0
        self._silence_start: Optional[float] = None

    # ── public API ────────────────────────────────────────────────────────

    def start(self) -> None:
        self._recording = True
        self._frames = []
        self._speech_secs = 0.0
        self._silence_start = None
        self._thread = threading.Thread(target=self._loop, daemon=True, name="recorder")
        self._thread.start()

    def stop(self) -> None:
        self._recording = False
        if self._thread:
            self._thread.join(timeout=3.0)
            self._thread = None

    def save_wav(self) -> Optional[str]:
        """Write recorded audio to a temp WAV file and return its path."""
        if not self._frames:
            return None
        audio = np.concatenate(self._frames)
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.close()
        with wave.open(tmp.name, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(2)   # int16 = 2 bytes
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(audio.tobytes())
        return tmp.name

    # ── internals ─────────────────────────────────────────────────────────

    def _loop(self) -> None:
        chunk_secs = BLOCK_SIZE / SAMPLE_RATE

        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=DTYPE,
            blocksize=BLOCK_SIZE,
        ) as stream:
            while self._recording:
                data, _ = stream.read(BLOCK_SIZE)
                self._frames.append(data.copy())
                self._process_chunk(data, chunk_secs)

    def _process_chunk(self, data: np.ndarray, chunk_secs: float) -> None:
        # Compute normalised RMS
        rms_raw = float(np.sqrt(np.mean(data.astype(np.float64) ** 2)))
        rms = min(1.0, rms_raw / 32_768.0 * 28)   # scale so normal speech ≈ 0.4-0.8

        if self._on_amplitude:
            self._on_amplitude(rms)

        # Silence auto-stop logic
        if rms > SILENCE_THRESHOLD:
            self._speech_secs += chunk_secs
            self._silence_start = None
        else:
            if self._speech_secs >= MIN_SPEECH_SECS:
                if self._silence_start is None:
                    self._silence_start = time.monotonic()
                elif time.monotonic() - self._silence_start >= SILENCE_SECS:
                    self._recording = False
                    if self._on_auto_stop:
                        self._on_auto_stop()
