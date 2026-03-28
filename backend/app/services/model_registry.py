"""
Model Registry — runtime model selection for MiroFish.

Holds the active model (provider + model name + base URL + API key) and a
catalog of known providers.  Thread-safe: each request can override the active
model via a context variable without affecting other threads.
"""

import os
import threading
import contextvars
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any

import requests as _requests

from ..utils.logger import get_logger

logger = get_logger('mirofish.model_registry')

# ── dataclass ────────────────────────────────────────────────────────────────

@dataclass
class ModelSelection:
    provider_id: str
    model_name: str
    base_url: str
    api_key: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ── provider catalog ─────────────────────────────────────────────────────────

PROVIDER_CATALOG: Dict[str, Dict[str, Any]] = {
    "ollama": {
        "name": "Ollama (Local)",
        "type": "local",
        "base_url": "http://localhost:11434/v1",
        "default_key": "ollama",
        "env_key": None,
        "models": [],  # auto-discovered
    },
    "nvidia": {
        "name": "NVIDIA API",
        "type": "cloud",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "default_key": None,
        "env_key": "NVIDIA_API_KEY",
        "models": [
            {"id": "nvidia/llama-3.1-nemotron-ultra-253b-v1", "name": "Nemotron Ultra 253B"},
            {"id": "meta/llama-3.3-70b-instruct", "name": "Llama 3.3 70B"},
            {"id": "deepseek-ai/deepseek-r1", "name": "DeepSeek R1 (via NVIDIA)"},
        ],
    },
    "openai": {
        "name": "OpenAI",
        "type": "cloud",
        "base_url": "https://api.openai.com/v1",
        "default_key": None,
        "env_key": "OPENAI_API_KEY",
        "models": [
            {"id": "gpt-4o", "name": "GPT-4o"},
            {"id": "gpt-4o-mini", "name": "GPT-4o Mini"},
            {"id": "gpt-4.1", "name": "GPT-4.1"},
            {"id": "gpt-4.1-mini", "name": "GPT-4.1 Mini"},
        ],
    },
    "anthropic": {
        "name": "Anthropic",
        "type": "cloud",
        "base_url": "https://api.anthropic.com/v1",
        "default_key": None,
        "env_key": "ANTHROPIC_API_KEY",
        "models": [
            {"id": "claude-sonnet-4-20250514", "name": "Claude Sonnet 4"},
            {"id": "claude-haiku-4-5-20251001", "name": "Claude Haiku 4.5"},
        ],
    },
    "google": {
        "name": "Google Gemini",
        "type": "cloud",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "default_key": None,
        "env_key": "GOOGLE_API_KEY",
        "models": [
            {"id": "gemini-2.5-flash", "name": "Gemini 2.5 Flash"},
            {"id": "gemini-2.5-pro", "name": "Gemini 2.5 Pro"},
        ],
    },
    "deepseek": {
        "name": "DeepSeek",
        "type": "cloud",
        "base_url": "https://api.deepseek.com",
        "default_key": None,
        "env_key": "DEEPSEEK_API_KEY",
        "models": [
            {"id": "deepseek-chat", "name": "DeepSeek V3"},
            {"id": "deepseek-reasoner", "name": "DeepSeek R1"},
        ],
    },
    "kimi": {
        "name": "Kimi (Moonshot)",
        "type": "cloud",
        "base_url": "https://api.moonshot.cn/v1",
        "default_key": None,
        "env_key": "KIMI_API_KEY",
        "models": [
            {"id": "kimi-k2-0711", "name": "Kimi K2"},
        ],
    },
}

# ── registry singleton ───────────────────────────────────────────────────────

_request_override: contextvars.ContextVar[Optional[ModelSelection]] = contextvars.ContextVar(
    'model_override', default=None,
)


class ModelRegistry:
    """Thread-safe singleton that manages the active model."""

    _instance: Optional['ModelRegistry'] = None
    _lock = threading.Lock()

    def __new__(cls) -> 'ModelRegistry':
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._active_lock = threading.Lock()

        # Default: whatever .env says
        from ..config import Config
        self._active = ModelSelection(
            provider_id=self._detect_provider(Config.LLM_BASE_URL),
            model_name=Config.LLM_MODEL_NAME,
            base_url=Config.LLM_BASE_URL,
            api_key=Config.LLM_API_KEY or "ollama",
        )

    # ── public API ───────────────────────────────────────────────────────

    def get_active(self) -> ModelSelection:
        """Return current active model, respecting per-request overrides."""
        override = _request_override.get(None)
        if override is not None:
            return override
        with self._active_lock:
            return self._active

    def set_active(self, selection: ModelSelection) -> None:
        with self._active_lock:
            self._active = selection
        logger.info("Active model changed → %s / %s", selection.provider_id, selection.model_name)

    def set_request_override(self, selection: ModelSelection) -> None:
        _request_override.set(selection)

    def clear_request_override(self) -> None:
        _request_override.set(None)

    # ── provider helpers ─────────────────────────────────────────────────

    def list_providers(self) -> List[Dict[str, Any]]:
        """Return provider catalog with key-configured status and live Ollama models."""
        result = []
        for pid, info in PROVIDER_CATALOG.items():
            entry: Dict[str, Any] = {
                "id": pid,
                "name": info["name"],
                "type": info["type"],
                "base_url": info["base_url"],
            }

            if pid == "ollama":
                entry["api_key_configured"] = True
                entry["models"] = self._list_ollama_models(info["base_url"])
            else:
                env_key = info.get("env_key")
                api_key = os.environ.get(env_key) if env_key else None
                entry["api_key_configured"] = bool(api_key)
                entry["models"] = list(info.get("models", []))

            result.append(entry)
        return result

    def get_api_key_for_provider(self, provider_id: str) -> Optional[str]:
        info = PROVIDER_CATALOG.get(provider_id)
        if not info:
            return None
        if info.get("default_key"):
            return info["default_key"]
        env_key = info.get("env_key")
        return os.environ.get(env_key) if env_key else None

    def get_base_url_for_provider(self, provider_id: str) -> Optional[str]:
        info = PROVIDER_CATALOG.get(provider_id)
        return info["base_url"] if info else None

    # ── private ──────────────────────────────────────────────────────────

    @staticmethod
    def _detect_provider(base_url: str) -> str:
        if not base_url:
            return "ollama"
        url = base_url.lower()
        for pid, info in PROVIDER_CATALOG.items():
            if info["base_url"] and info["base_url"].lower() in url:
                return pid
        if "11434" in url or "ollama" in url:
            return "ollama"
        return "custom"

    @staticmethod
    def _list_ollama_models(base_url: str) -> List[Dict[str, str]]:
        """Query Ollama's /api/tags endpoint to get locally available models."""
        try:
            # base_url is like http://localhost:11434/v1, strip the /v1
            host = base_url.rstrip("/")
            if host.endswith("/v1"):
                host = host[:-3]
            resp = _requests.get(f"{host}/api/tags", timeout=5)
            resp.raise_for_status()
            data = resp.json()
            models = []
            for m in data.get("models", []):
                name = m.get("name", "")
                if name:
                    models.append({"id": name, "name": name})
            return models
        except Exception as exc:
            logger.warning("Could not list Ollama models: %s", exc)
            return []
