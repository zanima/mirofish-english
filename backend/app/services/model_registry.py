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
from decimal import Decimal

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
        "base_url": "http://host.docker.internal:11434/v1",
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
            {"id": "openai/gpt-oss-120b", "name": "GPT-OSS 120B"},
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
        "base_url": "https://api.anthropic.com/v1/",
        "default_key": None,
        "env_key": "ANTHROPIC_API_KEY",
        "models": [
            {"id": "claude-sonnet-4-20250514", "name": "Claude Sonnet 4"},
            {"id": "claude-haiku-4-5-20251001", "name": "Claude Haiku 4.5"},
        ],
        "note": "Anthropic API requires x-api-key header; openai SDK may need compatibility layer",
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
            {"id": "moonshot-v1-auto", "name": "Kimi K2.5 (Auto)"},
        ],
    },
}

# ── cost catalog (per 1M tokens) ──────────────────────────────────────────────

COST_CATALOG = {
    # Ollama local — no cost
    "ollama": {"input": 0, "output": 0},
    # NVIDIA NIM — free tier for most models
    "nvidia": {"input": 0, "output": 0},
    # OpenAI
    "gpt-4o":         {"input": 2.50, "output": 10.00},
    "gpt-4o-mini":    {"input": 0.15, "output": 0.60},
    "gpt-4.1":        {"input": 2.00, "output": 8.00},
    "gpt-4.1-mini":   {"input": 0.40, "output": 1.60},
    # Anthropic
    "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
    "claude-haiku-4-5-20251001":  {"input": 0.80, "output": 4.00},
    # Google Gemini
    "gemini-2.5-flash": {"input": 0.15, "output": 0.60},
    "gemini-2.5-pro":   {"input": 1.25, "output": 10.00},
    # DeepSeek
    "deepseek-chat":     {"input": 0.27, "output": 1.10},
    "deepseek-reasoner": {"input": 0.55, "output": 2.19},
    # Kimi
    "kimi-k2-0711":      {"input": 0.00, "output": 0.00},
    "moonshot-v1-auto":  {"input": 0.00, "output": 0.00},
}

# ── step names ────────────────────────────────────────────────────────────────
STEP_NAMES = ["ontology", "graph", "simulation", "report", "interaction"]

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

        # Per-step overrides: {"ontology": ModelSelection, "report": ModelSelection, ...}
        self._step_overrides: Dict[str, ModelSelection] = {}

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

    # ── per-step overrides ───────────────────────────────────────────────

    def set_step_override(self, step: str, selection: ModelSelection) -> None:
        """Set a per-step model override."""
        with self._active_lock:
            self._step_overrides[step] = selection
        logger.info("Step '%s' model override → %s / %s", step, selection.provider_id, selection.model_name)

    def clear_step_override(self, step: str) -> None:
        with self._active_lock:
            self._step_overrides.pop(step, None)
        logger.info("Step '%s' model override cleared", step)

    def get_step_overrides(self) -> Dict[str, ModelSelection]:
        with self._active_lock:
            return dict(self._step_overrides)

    def get_for_step(self, step: str) -> ModelSelection:
        """Return step-specific model if overridden, else the global active model."""
        with self._active_lock:
            override = self._step_overrides.get(step)
            if override is not None:
                return override
        return self.get_active()

    # ── cost estimation ──────────────────────────────────────────────────

    @staticmethod
    def estimate_cost(model_name: str, provider_id: str, input_tokens: int = 50000, output_tokens: int = 20000) -> Dict[str, Any]:
        """Estimate cost for a given model/provider. Returns per-run cost estimate."""
        pricing = COST_CATALOG.get(model_name) or COST_CATALOG.get(provider_id, {"input": 0, "output": 0})
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        total = round(input_cost + output_cost, 4)
        return {
            "model_name": model_name,
            "provider_id": provider_id,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "input_cost_usd": round(input_cost, 4),
            "output_cost_usd": round(output_cost, 4),
            "total_cost_usd": total,
            "is_free": total == 0,
            "pricing_per_1m": pricing,
        }

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
