"""
WhisperTray — Main Entry Point
Press Ctrl+Shift+Q in any text box to start voice dictation.
"""

import sys
import os
from dotenv import load_dotenv

if sys.platform != "win32":
    print("WhisperTray currently supports Windows only.")
    sys.exit(1)

# Load environment variables from .env file
load_dotenv()

# Enable high-DPI awareness before Qt initialises
import ctypes
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-monitor DPI
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

# Silence PyTorch / Whisper verbose output
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

from src.app import WhisperTrayApp


def main() -> None:
    app = WhisperTrayApp()
    app.run()


if __name__ == "__main__":
    main()
