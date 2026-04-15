# 🎙 WhisperTray

**Voice dictation for any Windows text box — powered by OpenAI Whisper.**

Press **Ctrl+Shift+Q** anywhere → speak → text appears. That's it.

![WhisperTray capsule UI — a minimal black pill with an animated voice wave](docs/preview.png)

---

## Features

- **System-tray resident** — runs silently in the background, zero chrome
- **Universal** — works in any text field: browsers, IDEs, Office, Notepad, chat apps
- **Accurate** — Whisper `small.en` model, optimised for English
- **Auto-stop** — detects silence and stops recording automatically
- **Minimal UI** — a sleek black capsule with an animated voice wave, nothing else
- **No API key** — fully local, your audio never leaves your machine

---

## Requirements

| Component | Minimum |
|-----------|---------|
| OS | Windows 10 / 11 (64-bit) |
| Python | 3.10 or newer |
| RAM | 4 GB (8 GB recommended) |
| Disk | ~600 MB (PyTorch + Whisper model) |
| Microphone | Any working input device |
| GPU | Optional — CPU works fine |

---

## Installation

### Option A — Batch script (simplest)

```bat
setup.bat
```

### Option B — PowerShell

```powershell
powershell -ExecutionPolicy Bypass -File setup.ps1
```

### Option C — Manual

```bash
# 1. Create and activate a virtual environment (recommended)
python -m venv .venv
.venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. (Optional) GPU acceleration — replace cu121 with your CUDA version
#    Check your CUDA version: nvidia-smi
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

> **First-run note:** Whisper will automatically download the `small.en` model (~250 MB) the first time it loads. This happens in the background while the tray icon appears.

---

## Usage

1. **Start the app**
   ```bat
   python main.py
   ```
   A microphone icon appears in the system tray.

2. **Click into any text box** (browser address bar, email body, code editor, etc.)

3. **Press `Ctrl+Shift+Q`**  
   A black capsule appears at the bottom of your screen with an animated wave.  
   The red dot indicates recording is active.

4. **Speak clearly** — the wave reacts to your voice in real time.

5. **Stop recording** — choose any method:
   - Stop speaking (auto-detects ~3 seconds of silence)
   - Press `Ctrl+Shift+Q` again
   - Press `Escape`

6. **Transcription appears** in your text box. The amber dot shows processing.

---

## Keyboard Reference

| Shortcut | Action |
|----------|--------|
| `Ctrl+Shift+Q` | Start / stop dictation |
| `Escape` | Cancel (discard recording) |

---

## Configuration

Open `src/recorder.py` to adjust:

```python
SILENCE_THRESHOLD = 0.012   # RMS level that counts as silence (lower = more sensitive)
MIN_SPEECH_SECS   = 0.6     # Minimum speech before auto-stop can fire
SILENCE_SECS      = 2.8     # Seconds of silence before auto-stop
```

Open `src/hotkey.py` to change the activation key combo:

```python
HOTKEY_COMBO = "<ctrl>+<shift>+q"   # Change to e.g. "<ctrl>+<alt>+space"
```

---

## Project Structure

```
whispertray/
├── main.py               ← Entry point
├── requirements.txt
├── setup.bat             ← Windows quick-setup
├── setup.ps1             ← PowerShell setup
├── .gitignore
└── src/
    ├── app.py            ← Application orchestrator
    ├── capsule.py        ← Floating capsule UI (PyQt5)
    ├── recorder.py       ← Audio capture + amplitude streaming
    ├── transcriber.py    ← Whisper speech-to-text
    ├── hotkey.py         ← Global Ctrl+Shift+Q listener
    ├── tray.py           ← System-tray icon + menu
    ├── injector.py       ← Text injection via clipboard
    └── signals.py        ← Qt cross-thread signal bus
```

---

## Troubleshooting

### "No module named 'whisper'" after installation
Run `pip install openai-whisper` — note the `openai-` prefix.

### Hotkey doesn't trigger
- Some applications (games, certain admin-level apps) capture all keyboard input. Try it in a standard app like Notepad first.
- If running WhisperTray from an elevated terminal, the hotkey may not fire in non-elevated apps. Run `python main.py` from a regular (non-admin) terminal.

### Text appears in the wrong window
The app captures the focused window handle at the moment you press `Ctrl+Shift+Q`. Make sure your cursor is in the correct text box *before* pressing the hotkey.

### Transcription is slow
- **CPU** — `small.en` takes 2–5 seconds. This is expected.
- **GPU** — Install the CUDA version of PyTorch (see installation step 3) for ~4× speedup.
- For near-instant results, you can switch to `tiny.en` in `src/transcriber.py` (edit `MODEL_NAME = "tiny.en"`), though accuracy is lower.

### "PortAudio not found" / sounddevice error
Install PortAudio: download the binary from https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio or run:
```bat
pip install pipwin
pipwin install pyaudio
```

---

## How It Works

```
Ctrl+Shift+Q pressed
       │
       ├─ Capture foreground window handle (HWND)
       ├─ Show capsule widget (PyQt5, translucent, always-on-top)
       └─ Start audio capture (sounddevice @ 16 kHz)
              │
              ├─ Every 64 ms: emit RMS amplitude → animate wave bars
              └─ Silence detected (or user stops)
                     │
                     ├─ Stop recording, save temp WAV
                     ├─ Switch capsule to "processing" state (amber dot)
                     └─ Run Whisper small.en transcription
                            │
                            ├─ Close capsule (fade out)
                            └─ Restore focus to original window
                                   │
                                   └─ Ctrl+V (clipboard paste)
```

---

## License

MIT — free for personal and commercial use.
