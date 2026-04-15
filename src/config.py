"""
config.py — WhisperTray backend configuration.

Edit this file to switch between transcription backends and tune model
settings. No other source file needs to be changed.

Backend options
---------------
  "openai"   — Original openai-whisper (the one we shipped with v1.x).
               Pros: battle-tested, easy install.
               Cons: slower on CPU, occasionally hallucinates rare words.

  "faster"   — faster-whisper (community CTranslate2 port).
               Pros: 4-8× faster on CPU/GPU, generally better word accuracy,
               full multilingual support, lower memory footprint.
               Cons: requires `pip install faster-whisper`.

Model names
-----------
  openai   : tiny | base | small | medium | large  (+".en" for English-only)
               e.g. "small.en", "medium", "large-v2"

  faster   : tiny | base | small | medium | large-v2 | large-v3
              (no ".en" suffix — set LANGUAGE below instead)
               e.g. "small", "medium", "large-v3"

Compute settings (faster-whisper only)
---------------------------------------
  DEVICE           : "cpu" or "cuda"  (auto-falls back to cpu if cuda missing)
  COMPUTE_TYPE     : "int8" (fast CPU), "float16" (GPU), "float32" (safe CPU)
"""

# ┌─────────────────────────────────────────────────────────────────────────┐
# │  CHOOSE YOUR BACKEND                                                    │
# └─────────────────────────────────────────────────────────────────────────┘

# "openai"  ← original OpenAI Whisper
# "faster"  ← Faster-Whisper (recommended — more accurate, faster)
BACKEND: str = "faster"


# ┌─────────────────────────────────────────────────────────────────────────┐
# │  MODEL SELECTION                                                        │
# └─────────────────────────────────────────────────────────────────────────┘

# Model used when BACKEND == "openai"
OPENAI_MODEL: str = "small.en"

# Model used when BACKEND == "faster"
# "small"  → good balance of speed & accuracy (≈ 470 MB)
# "medium" → better accuracy, noticeably slower on CPU
# "large-v3" → best accuracy, requires a good GPU
FASTER_MODEL: str = "small"


# ┌─────────────────────────────────────────────────────────────────────────┐
# │  LANGUAGE                                                               │
# └─────────────────────────────────────────────────────────────────────────┘

# Language hint sent to both backends.
# Set to None to let Whisper auto-detect (slightly slower first pass).
# Examples: "en", "fr", "de", "hi", None
LANGUAGE: str = None


# ┌─────────────────────────────────────────────────────────────────────────┐
# │  FASTER-WHISPER COMPUTE SETTINGS                                        │
# └─────────────────────────────────────────────────────────────────────────┘

# "cpu"  — works everywhere, use "int8" for best CPU speed
# "cuda" — needs NVIDIA GPU + CUDA 11/12; use "float16"
DEVICE: str = "cpu"

# "int8"    → fastest CPU inference, tiny accuracy drop
# "float16" → best for GPU
# "float32" → safest fallback (automatic when int8 unavailable)
COMPUTE_TYPE: str = "int8"


# ┌─────────────────────────────────────────────────────────────────────────┐
# │  TRANSCRIPTION QUALITY KNOBS (shared by both backends)                  │
# └─────────────────────────────────────────────────────────────────────────┘

# Probability threshold below which a segment is considered silence.
# Range 0.0–1.0.  Higher → stricter; lower → keeps more borderline audio.
NO_SPEECH_THRESHOLD: float = 0.5

# Beam size for decoding (faster-whisper only).
# 1 = greedy (fastest), 5 = beam search (more accurate, slower)
BEAM_SIZE: int = 5
