"""
Provider-specific compatibility helpers for OpenAI-compatible APIs.
"""

from typing import Any, Dict


def is_moonshot_kimi_k25(model: str | None, base_url: str | None) -> bool:
    model_name = (model or "").strip().lower()
    endpoint = (base_url or "").strip().lower()
    return model_name.startswith("kimi-k2.5") and "moonshot" in endpoint


def normalize_chat_completion_kwargs(
    *,
    model: str | None,
    base_url: str | None,
    kwargs: Dict[str, Any],
) -> Dict[str, Any]:
    normalized = dict(kwargs)

    # Moonshot's kimi-k2.5 currently only accepts temperature=1.
    if is_moonshot_kimi_k25(model, base_url) and "temperature" in normalized:
        normalized["temperature"] = 1

    return normalized
