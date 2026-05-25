"""
BaseAgent — supports three providers:
  • "anthropic"  → Anthropic SDK (Claude Sonnet / Opus)
  • "groq"       → OpenAI-compatible SDK → Groq cloud (free, fast)
  • "ollama"     → OpenAI-compatible SDK → Ollama local server

Provider is read from os.environ["AI_PROVIDER"] at call time,
so the sidebar can switch it without restarting the app.
"""

import os
import time
from typing import Generator

# ── Model constants (Anthropic) ───────────────────────────────────────────────
MODEL_FAST  = "claude-sonnet-4-6"
MODEL_DEEP  = "claude-opus-4-7"
MODEL_LITE  = "claude-haiku-4-5-20251001"

# ── Groq ──────────────────────────────────────────────────────────────────────
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

# Map Anthropic model tiers → best Groq equivalents
# MODEL_FAST / MODEL_DEEP → 70B (best quality on Groq free tier)
# MODEL_LITE              → 8B instant  (fast, lightweight tasks)
_GROQ_MODEL_MAP = {
    MODEL_FAST: "llama-3.3-70b-versatile",
    MODEL_DEEP: "llama-3.3-70b-versatile",
    MODEL_LITE: "llama-3.1-8b-instant",
}
_GROQ_DEFAULT_MODEL = "llama-3.3-70b-versatile"

# ── Ollama ────────────────────────────────────────────────────────────────────
OLLAMA_DEFAULT_MODEL = "qwen2.5:7b"
OLLAMA_BASE_URL      = "http://localhost:11434/v1"
# Local models are slow — cap output tokens so each call finishes quickly.
_OLLAMA_MAX_TOKENS   = 280


def _get_provider() -> str:
    return os.environ.get("AI_PROVIDER", "anthropic")

def _get_ollama_model() -> str:
    return os.environ.get("OLLAMA_MODEL", OLLAMA_DEFAULT_MODEL)

def _get_groq_model(anthropic_model: str) -> str:
    return _GROQ_MODEL_MAP.get(anthropic_model, _GROQ_DEFAULT_MODEL)

def _get_groq_api_key() -> str:
    return os.environ.get("GROQ_API_KEY", "")


class BaseAgent:
    def __init__(self, name: str, emoji: str, description: str,
                 model: str = MODEL_FAST):
        self.name        = name
        self.emoji       = emoji
        self.description = description
        self.model       = model
        self.last_output = ""

    # ── Internal clients ─────────────────────────────────────────────────────
    @staticmethod
    def _anthropic_client():
        from anthropic import Anthropic
        return Anthropic()

    @staticmethod
    def _openai_client(base_url: str, api_key: str):
        from openai import OpenAI
        return OpenAI(base_url=base_url, api_key=api_key)

    # ── Public run methods ────────────────────────────────────────────────────
    def run(self, system: str, prompt: str, max_tokens: int = 1500) -> str:
        provider = _get_provider()
        if provider == "groq":
            return self._run_groq(system, prompt, max_tokens)
        if provider == "ollama":
            return self._run_ollama(system, prompt, min(max_tokens, _OLLAMA_MAX_TOKENS))
        return self._run_anthropic(system, prompt, max_tokens)

    def stream_run(self, system: str, prompt: str,
                   max_tokens: int = 1500) -> Generator[str, None, None]:
        provider = _get_provider()
        if provider == "groq":
            # Groq doesn't need streaming — return full response as one chunk
            yield self._run_groq(system, prompt, max_tokens)
        elif provider == "ollama":
            yield from self._stream_ollama(system, prompt, max_tokens)
        else:
            yield from self._stream_anthropic(system, prompt, max_tokens)

    # ── Anthropic ─────────────────────────────────────────────────────────────
    def _run_anthropic(self, system: str, prompt: str, max_tokens: int) -> str:
        client = self._anthropic_client()
        msg = client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        self.last_output = msg.content[0].text
        return self.last_output

    def _stream_anthropic(self, system: str, prompt: str,
                          max_tokens: int) -> Generator[str, None, None]:
        client = self._anthropic_client()
        self.last_output = ""
        with client.messages.stream(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            for text in stream.text_stream:
                self.last_output += text
                yield text

    # ── Groq (OpenAI-compatible, cloud, free) ─────────────────────────────────
    def _run_groq(self, system: str, prompt: str, max_tokens: int) -> str:
        from openai import RateLimitError
        client = self._openai_client(GROQ_BASE_URL, _get_groq_api_key())
        groq_model = _get_groq_model(self.model)

        # Groq free-tier limits:
        #   llama-3.3-70b-versatile : 6,000 TPM  · 30 RPM
        #   llama-3.1-8b-instant    : 20,000 TPM · 30 RPM
        # Exponential backoff: 15s → 30s → 60s → 90s → 120s → 150s (7 attempts)
        _BACKOFF = [15, 30, 60, 90, 120, 150]
        max_attempts = len(_BACKOFF) + 1   # 7 total

        for attempt in range(max_attempts):
            try:
                resp = client.chat.completions.create(
                    model=groq_model,
                    max_tokens=max_tokens,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user",   "content": prompt},
                    ],
                )
                self.last_output = resp.choices[0].message.content or ""
                return self.last_output
            except RateLimitError:
                if attempt < len(_BACKOFF):
                    wait = _BACKOFF[attempt]
                    time.sleep(wait)
                else:
                    raise
            except Exception:
                raise
        return ""

    # ── Ollama (OpenAI-compatible, local) ─────────────────────────────────────
    def _run_ollama(self, system: str, prompt: str, max_tokens: int) -> str:
        client = self._openai_client(
            os.environ.get("OLLAMA_URL", OLLAMA_BASE_URL), "ollama"
        )
        resp = client.chat.completions.create(
            model=_get_ollama_model(),
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": prompt},
            ],
        )
        self.last_output = resp.choices[0].message.content or ""
        return self.last_output

    def _stream_ollama(self, system: str, prompt: str,
                       max_tokens: int) -> Generator[str, None, None]:
        client = self._openai_client(
            os.environ.get("OLLAMA_URL", OLLAMA_BASE_URL), "ollama"
        )
        self.last_output = ""
        stream = client.chat.completions.create(
            model=_get_ollama_model(),
            max_tokens=max_tokens,
            stream=True,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": prompt},
            ],
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                self.last_output += delta
                yield delta
