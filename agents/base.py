"""
BaseAgent — supports two providers:
  • "anthropic"  → Anthropic SDK (Claude Sonnet / Opus)
  • "ollama"     → OpenAI-compatible SDK → Ollama local server

Provider is read from os.environ["AI_PROVIDER"] at call time,
so the sidebar can switch it without restarting the app.
"""

import os
from typing import Generator

# ── Model constants ───────────────────────────────────────────────────────────
MODEL_FAST  = "claude-sonnet-4-6"
MODEL_DEEP  = "claude-opus-4-7"
MODEL_LITE  = "claude-haiku-4-5-20251001"

# Ollama defaults (overridable via env)
OLLAMA_DEFAULT_MODEL  = "qwen2.5:7b"
OLLAMA_BASE_URL       = "http://localhost:11434/v1"
# Local models are slow — cap output tokens so each call finishes quickly.
# Anthropic calls use the full max_tokens passed by each agent.
_OLLAMA_MAX_TOKENS    = 280


def _get_provider() -> str:
    return os.environ.get("AI_PROVIDER", "anthropic")

def _get_ollama_model() -> str:
    return os.environ.get("OLLAMA_MODEL", OLLAMA_DEFAULT_MODEL)


class BaseAgent:
    def __init__(self, name: str, emoji: str, description: str,
                 model: str = MODEL_FAST):
        self.name        = name
        self.emoji       = emoji
        self.description = description
        self.model       = model          # used only for Anthropic
        self.last_output = ""

    # ── Internal clients (created lazily) ────────────────────────────────────
    @staticmethod
    def _anthropic_client():
        from anthropic import Anthropic
        return Anthropic()

    @staticmethod
    def _openai_client():
        from openai import OpenAI
        return OpenAI(
            base_url=os.environ.get("OLLAMA_URL", OLLAMA_BASE_URL),
            api_key="ollama",               # Ollama ignores this but SDK requires it
        )

    # ── Public run methods ────────────────────────────────────────────────────
    def run(self, system: str, prompt: str, max_tokens: int = 1500) -> str:
        if _get_provider() == "ollama":
            return self._run_ollama(system, prompt, min(max_tokens, _OLLAMA_MAX_TOKENS))
        return self._run_anthropic(system, prompt, max_tokens)

    def stream_run(self, system: str, prompt: str,
                   max_tokens: int = 1500) -> Generator[str, None, None]:
        if _get_provider() == "ollama":
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

    # ── Ollama (OpenAI-compatible) ────────────────────────────────────────────
    def _run_ollama(self, system: str, prompt: str, max_tokens: int) -> str:
        client = self._openai_client()
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
        client = self._openai_client()
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
