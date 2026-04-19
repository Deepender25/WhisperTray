import json
import logging
import os
import time
import urllib.request

from . import config

logger = logging.getLogger(__name__)

def refine_text(raw_text: str) -> str:
    """Uses the configured LLM API (e.g., Groq) to refine transcription text."""
    if not raw_text or not raw_text.strip():
        return raw_text

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        api_key = os.environ.get("LLM_API_KEY") # fallback

    if not api_key:
        logger.error("LLM_API_KEY or GROQ_API_KEY missing from environment. Skipping refinement.")
        return raw_text

    url = f"{config.LLM_BASE_URL.rstrip('/')}/chat/completions"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "User-Agent": "WhisperTray/1.0"
    }

    payload = {
        "model": config.LLM_MODEL,
        "messages": [
            {"role": "system", "content": config.LLM_SYSTEM_PROMPT},
            {"role": "user", "content": raw_text}
        ],
        "temperature": 0.1,  # Low temp for deterministic fixing
        "max_tokens": 1024,
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")

    logger.info("Sending transcribed text to LLM (%s) for refinement...", config.LLM_MODEL)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode("utf-8"))
            improved_text = result["choices"][0]["message"]["content"].strip()
            elapsed = time.time() - t0
            logger.info("LLM refinement complete in %.2fs", elapsed)
            return improved_text
    except Exception as e:
        logger.exception("LLM Refinement failed: %s", e)
        return raw_text
