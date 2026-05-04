"""Groq-only LLM factory for the lightweight AI-Datanalysis build.

Active model configuration:
  LLM_PROVIDER=groq
  GROQ_API_KEY=...
  GROQ_MODEL=llama-3.3-70b-versatile | qwen/qwen3-32b
  LLM_TEMPERATURE=0.0
"""
from __future__ import annotations

import os
from typing import Any


GROQ_AVAILABLE_MODELS = [
    "llama-3.3-70b-versatile",
    "qwen/qwen3-32b",
]

# Per-model config: max_tokens, timeout_seconds, max_retries.
# Qwen fails fast because cold starts are handled by the app warmup path.
_GROQ_MODEL_CONFIG: dict[str, dict[str, int]] = {
    "llama-3.3-70b-versatile": {"max_tokens": 2048, "timeout": 60, "max_retries": 1},
    "qwen/qwen3-32b": {"max_tokens": 4096, "timeout": 90, "max_retries": 0},
}


def build_llm(model_override: str | None = None) -> Any:
    provider = os.getenv("LLM_PROVIDER", "groq").strip().lower()
    if provider != "groq":
        raise RuntimeError(
            "Only LLM_PROVIDER=groq is supported in this lightweight build. "
            "Other providers and deprecated Groq models have been removed."
        )

    try:
        from langchain_groq import ChatGroq
    except Exception as e:
        raise RuntimeError(
            "LLM_PROVIDER=groq but 'langchain-groq' is not installed."
        ) from e

    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Missing GROQ_API_KEY. Please set it as an environment variable.")

    model = (model_override or os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")).strip()
    if model not in GROQ_AVAILABLE_MODELS:
        raise RuntimeError(
            f"Unsupported Groq model '{model}'. Supported models: "
            + ", ".join(GROQ_AVAILABLE_MODELS)
        )

    model_cfg = _GROQ_MODEL_CONFIG[model]
    return ChatGroq(
        model_name=model,
        groq_api_key=api_key,
        temperature=float(os.getenv("LLM_TEMPERATURE", "0.0")),
        max_tokens=model_cfg["max_tokens"],
        timeout=model_cfg["timeout"],
        max_retries=model_cfg["max_retries"],
    )
