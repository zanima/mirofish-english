# MiroFish Improvement Plan: Model Selector Feature
**Date:** 2026-03-27

## Goal
Let users choose which AI model to use from the UI before starting any step, and switch models mid-workflow if errors, stale state, or token exhaustion occurs.

## Supported Providers
| Provider | Type | Base URL | Env Key |
|---|---|---|---|
| Ollama (Local) | local | `http://localhost:11434/v1` | — (key: `ollama`) |
| NVIDIA API | cloud | `https://integrate.api.nvidia.com/v1` | `NVIDIA_API_KEY` |
| Anthropic | cloud | `https://api.anthropic.com/v1` | `ANTHROPIC_API_KEY` |
| Google Gemini | cloud | `https://generativelanguage.googleapis.com/v1beta/openai` | `GOOGLE_API_KEY` |
| OpenAI | cloud | `https://api.openai.com/v1` | `OPENAI_API_KEY` |
| DeepSeek | cloud | `https://api.deepseek.com/v1` | `DEEPSEEK_API_KEY` |
| Kimi (Moonshot) | cloud | `https://api.moonshot.cn/v1` | `KIMI_API_KEY` |

## Architecture

### How it works today
- `config.py` reads `LLM_MODEL_NAME`, `LLM_API_BASE`, `LLM_API_KEY` from `.env` at import time
- Fallback chains: `REPORT_LLM_* → GRAPHITI_* → LLM_*` and `SIMULATION_LLM_* → GRAPHITI_* → LLM_*`
- All LLM calls go through OpenAI-compatible API via `llm_client.py`

### How it will work
- A new `ModelRegistry` singleton holds the active model selection at runtime
- The frontend sends the selected model with each API call (or sets it globally)
- `LLMClient` gets a `.from_active_model()` factory that reads from `ModelRegistry`
- All services that create LLM clients switch to using this factory
- The frontend shows a model selector dropdown in the header, always accessible

## Implementation Phases

### Phase 1 — Backend: Model Registry & API
1. Create `backend/app/services/model_registry.py` — `ModelSelection` dataclass, `ModelRegistry` singleton, provider catalog, Ollama model discovery
2. Create `backend/app/api/models.py` — `GET /api/models/available`, `POST /api/models/active`, `POST /api/models/test`
3. Register new blueprint in `backend/app/__init__.py` and `backend/app/api/__init__.py`
4. Add cloud provider env vars to `backend/app/config.py`

### Phase 2 — Backend: Wire Services to Registry
5. Add `LLMClient.from_active_model()` to `backend/app/utils/llm_client.py`
6. Update `backend/app/services/ontology_generator.py` → use `from_active_model()`
7. Update `backend/app/services/zep_tools.py` → use `from_active_model()`
8. Update `backend/app/services/oasis_profile_generator.py` → consult `ModelRegistry`
9. Update `backend/app/services/simulation_config_generator.py` → consult `ModelRegistry`
10. Update `backend/app/services/report_agent.py` → consult `ModelRegistry`
11. Update `backend/app/services/graphiti_builder.py` → convert module-level vars to lazy reads from `ModelRegistry`

### Phase 3 — Frontend: Model Selector UI
12. Create `frontend/src/api/models.js` — API wrapper
13. Create `frontend/src/store/modelStore.js` — reactive state + localStorage persistence
14. Create `frontend/src/components/ModelSelector.vue` — dropdown component
15. Integrate into `Home.vue` (replace static "Engine: MiroFish-V1.0" badge)
16. Integrate into `MainView.vue` header (always visible during workflow)
17. Integrate into `SimulationView.vue`, `SimulationRunView.vue`, `ReportView.vue`

### Phase 4 — Error Recovery
18. Create `frontend/src/composables/useModelFallback.js` — detect LLM errors, prompt model switch
19. Wire error-triggered model switch into step components

## Design Decisions
- **API keys stay server-side** — frontend only sees `api_key_configured: true/false`
- **Single active model** — one model at a time for all steps (user switches manually between steps)
- **Thread-local override** — concurrent requests can use different models via request context
- **Ollama auto-discovery** — local models detected by calling Ollama API at `/api/tags`
- **localStorage persistence** — selected model survives page refresh
