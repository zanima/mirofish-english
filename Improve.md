# MiroFish Improvement Log
**Started:** 2026-03-27 | **Last updated:** 2026-03-28

---

## 1. Model Selector (DONE)
**Goal:** Let users choose which AI model to use from the UI before starting any step, and switch models mid-workflow.

### Supported Providers
| Provider | Type | Base URL | Env Key | Status |
|---|---|---|---|---|
| Ollama (Local) | local | `http://host.docker.internal:11434/v1` | — (key: `ollama`) | Working |
| NVIDIA API | cloud | `https://integrate.api.nvidia.com/v1` | `NVIDIA_API_KEY` | Working |
| Anthropic | cloud | `https://api.anthropic.com/v1/` | `ANTHROPIC_API_KEY` | Configured (not OpenAI-compatible natively) |
| Google Gemini | cloud | `https://generativelanguage.googleapis.com/v1beta/openai` | `GOOGLE_API_KEY` | Working |
| OpenAI | cloud | `https://api.openai.com/v1` | `OPENAI_API_KEY` | Needs API key |
| DeepSeek | cloud | `https://api.deepseek.com` | `DEEPSEEK_API_KEY` | Working |
| Kimi (Moonshot) | cloud | `https://api.moonshot.cn/v1` | `KIMI_API_KEY` | Working |

### Files Created
- `backend/app/services/model_registry.py` — Singleton registry, provider catalog, Ollama auto-discovery
- `backend/app/api/models.py` — REST endpoints: `GET /api/models/available`, `GET/POST /api/models/active`, `POST /api/models/test`
- `frontend/src/api/models.js` — API wrappers
- `frontend/src/store/modelStore.js` — Reactive state + localStorage persistence
- `frontend/src/components/ModelSelector.vue` — Dropdown component in navbar
- `frontend/src/composables/useModelFallback.js` — Detects LLM errors, prompts model switch

### Files Modified
- `backend/app/config.py` — Added cloud provider API key env vars
- `backend/app/__init__.py`, `backend/app/api/__init__.py` — Registered models blueprint
- `backend/app/utils/llm_client.py` — Added `from_active_model()` factory
- `backend/app/services/ontology_generator.py` — Uses `from_active_model()`
- `backend/app/services/zep_tools.py` — Uses `from_active_model()`
- `backend/app/services/oasis_profile_generator.py` — Reads from ModelRegistry
- `backend/app/services/simulation_config_generator.py` — Reads from ModelRegistry
- `backend/app/services/report_agent.py` — Uses `from_active_model()`
- `backend/app/services/graphiti_builder.py` — Lazy reads from ModelRegistry
- `backend/app/services/simulation_runner.py` — Injects active model env vars into subprocess
- All frontend views — ModelSelector integrated in navbar

### Design Decisions
- API keys stay server-side (frontend only sees `api_key_configured: true/false`)
- Single active model for all steps; user switches manually between steps
- Thread-local override via `contextvars` for concurrent requests
- Ollama auto-discovery via `/api/tags`
- localStorage persistence for selected model across page refreshes

### Known Issues
- Anthropic API is not natively OpenAI-compatible; needs adapter or direct SDK usage

---

## 2. Dark Mode (DONE)
**Goal:** Default dark theme that follows system preference via `prefers-color-scheme`.

### Implementation
- Home.vue uses CSS custom properties (`--bg`, `--fg`, `--border`, etc.) defaulting to dark
- `@media (prefers-color-scheme: light)` block overrides variables for light mode
- Removed "Low Cost ~$5" and "Scalable Millions of Agents" text

---

## 3. Home Page Redesign — Option A (DONE)
**Goal:** Action-focused layout with hero + console side-by-side, less scrolling.

### Implementation
- Hero column (left): tagline, title, description, workflow pills, logo accent
- Action console (right): source tabs, prompt textarea, launch button
- Responsive: stacks vertically below 900px

---

## 4. URL/Search Seed Data Input (DONE)
**Goal:** Allow users to paste URLs or enter search queries instead of only uploading files.

### How It Works
1. Home page has three source tabs: **Files** | **URL** | **Search**
2. Files tab: unchanged drag-and-drop for PDF/MD/TXT
3. URL tab: textarea for pasting URLs (one per line) — pages fetched and text extracted
4. Search tab: text input for search query — searches DuckDuckGo, fetches top 5 results
5. All three sources feed into the same text extraction pipeline (`document_texts[]` → `all_text`)
6. Files are now optional if URLs or search query is provided

### Files Created
- `backend/app/services/web_fetcher.py` — `fetch_url()`, `fetch_urls()`, `search_and_fetch()`, `_search_duckduckgo()`

### Files Modified
- `backend/app/api/graph.py` — `generate_ontology()` accepts `urls` and `search_query` form fields; three sources merged into pipeline
- `frontend/src/store/pendingUpload.js` — Added `urls` and `searchQuery` fields
- `frontend/src/views/Home.vue` — Three source tabs (Files/URL/Search) with reactive state, CSS
- `frontend/src/views/MainView.vue` — Guard updated to accept any source; passes `urls`/`search_query` to backend FormData
- `frontend/src/views/Process.vue` — Same guard and FormData updates (backup route)

### Key Fix
- Router maps "Process" route to `MainView.vue` (not `Process.vue`) — both files needed the guard fix

---

## 5. Per-Step Model Selection (DONE)
**Goal:** Allow different LLM models for each workflow step (ontology, graph build, simulation, report, interaction).

### Implementation
- `ModelRegistry` extended with `_step_overrides` dict and `get_for_step(step)` method
- New API endpoints: `GET/POST/DELETE /api/models/steps/<step>`
- `ModelSelector.vue` rebuilt with **Global** / **Per-Step** tabs
- Per-Step tab shows 5 steps with dropdown selects for each
- Clearing a step override reverts to global active model

### Files Modified
- `backend/app/services/model_registry.py` — `set_step_override()`, `clear_step_override()`, `get_for_step()`, `STEP_NAMES`, `COST_CATALOG`
- `backend/app/api/models.py` — 3 new endpoints: steps GET, steps POST, steps DELETE
- `frontend/src/components/ModelSelector.vue` — Full rewrite with tabs
- `frontend/src/api/models.js` — Added `getStepOverrides`, `setStepOverride`, `clearStepOverride`

---

## 6. Streaming Responses — SSE (DONE)
**Goal:** Show report generation progress in real-time via Server-Sent Events.

### Implementation
- New endpoint: `GET /api/report/<report_id>/stream`
- Returns SSE events: `section_complete`, `done`, `error`
- Reads `agent_log.jsonl` incrementally (2s poll loop)
- Frontend can connect with `EventSource` to receive live section content

### Files Modified
- `backend/app/api/report.py` — Added `stream_report()` SSE endpoint at bottom

---

## 7. Batch URL Fetch (DONE)
**Goal:** Parallel fetching for multiple URLs using ThreadPoolExecutor.

### Implementation
- `fetch_urls()` now uses `ThreadPoolExecutor(max_workers=5)` instead of sequential loop
- Each URL is fetched concurrently; errors are caught per-URL
- Falls through gracefully with error dict for failed URLs

### Files Modified
- `backend/app/services/web_fetcher.py` — Rewrote `fetch_urls()` to use parallel execution

---

## 8. CSV File Support (DONE)
**Goal:** Accept CSV files as seed data input.

### Implementation
- `FileParser._extract_from_csv()` reads CSV and renders as markdown table
- Headers become table headers, data rows limited to 500
- Added `.csv` to `SUPPORTED_EXTENSIONS` and `ALLOWED_EXTENSIONS`
- Frontend file input now accepts `.csv`

### Files Modified
- `backend/app/utils/file_parser.py` — Added `_extract_from_csv()` method
- `backend/app/config.py` — Added `csv` to `ALLOWED_EXTENSIONS`
- `frontend/src/views/Home.vue` — Updated `accept` attribute, filter, and label

---

## 9. Cost Estimation (DONE)
**Goal:** Show estimated token cost before launching with cloud providers.

### Implementation
- `COST_CATALOG` dict in model_registry with pricing per 1M tokens for all providers
- `ModelRegistry.estimate_cost()` static method calculates per-run cost
- New API endpoint: `POST /api/models/estimate`
- ModelSelector shows cost badge next to each model (FREE or ~$X.XXX)

### Files Modified
- `backend/app/services/model_registry.py` — Added `COST_CATALOG` and `estimate_cost()`
- `backend/app/api/models.py` — Added `/estimate` endpoint
- `frontend/src/api/models.js` — Added `estimateCost()` wrapper
- `frontend/src/components/ModelSelector.vue` — Displays cost badges

---

## 10. Simulation History Cards Dark Mode (DONE)
**Goal:** Fix white/gray simulation history cards to match the dark page background.

### Implementation
- Card background: `#FFFFFF` → `#1a1a1a`
- Card border: `#E5E7EB` → `#2a2a2a`
- File section: light gradients → dark gradients (`#111` → `#161616`)
- File tags: light Morandi colors → dark counterparts
- Modal: fully dark themed (`#1a1a1a` background, dark borders)
- Hover accent: blue → `#FF4500` (orange-red brand color)
- Grid pattern: dark-on-light → light-on-dark (`rgba(255,255,255,0.04)` grid lines)

### Files Modified
- `frontend/src/components/HistoryDatabase.vue` — Complete CSS rewrite for dark theme

---

## 11. Future Improvements (TODO)
- [ ] Anthropic adapter — wrap Anthropic SDK behind OpenAI-compatible interface
- [ ] Model performance tracking — log latency/token counts per model per step
- [ ] Frontend recovery after backend restarts (auto-reattach to report/simulation state)
- [ ] Report interview optimization (fewer questions, single-platform mode)
- [ ] Entity label deduplication in graph-to-persona pipeline
- [ ] DOCX and JSON seed data support

