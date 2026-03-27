# MiroFish Handoff
**Date:** 2026-03-27  
**Status:** Local Graphiti graph build, simulation preparation, simulation runtime, and report generation are all running on `192.168.1.173`. After a controlled local benchmark on `2026-03-27`, the stack remains intentionally unified around `qwen2.5:14b` as the safe full-stack default, with `gemma3:12b-it-qat` kept as the main alternate candidate.

## Current Runtime State
- Remote host: `192.168.1.173`
- Main verified project: `proj_62a91485b4b3`
- Main verified simulation: `sim_7b58160805f4`
- Main verified graph id: `mirofish_d838b8ea0f3c4286`
- Current local Ollama models intentionally kept on the Mac Studio:
  - `qwen2.5:14b`
  - `gemma3:12b-it-qat`
  - `nomic-embed-text:latest`
- Current preparation state:
  - `status: ready`
  - `progress: 100`
  - `already_prepared: true`
  - `config_generated: true`
  - existing files:
    - `state.json`
    - `simulation_config.json`
    - `reddit_profiles.json`
    - `twitter_profiles.csv`
- The simulation has already completed successfully for this verified path.
- The earlier active report rerun was intentionally stopped during later model benchmarking.

## Important Conclusion
- The old blocker from the previous handoff is no longer true.
- Graphiti is no longer failing at chunk ingestion for the tested path.
- The main graph path works locally with Ollama-served `qwen2.5:14b`.
- Step 2 simulation preparation is no longer blocked on Zep.
- The simulation runtime is using the same single-model path instead of bypassing it with a separate raw `LLM_MODEL_NAME` read.
- `qwen3.5:9b` was tested and rejected for this workload.
- `qwen3:14b`, `mistral-small3.2:latest`, and `gemma3:12b-it-qat` were benchmarked locally in a controlled report-generation comparison.
- `gemma3:12b-it-qat` was the fastest report-stage challenger, but `qwen2.5:14b` remains the safe default because it is already proven on Graphiti graph build.
- Report generation is improved but not “perfectly fast”: the remaining main cost is report-stage dual-platform agent interviews.
- The frontend can still show stale state after backend restarts, but the backend workflow itself is functional.

## What Was Fixed

### 1. Graphiti local build path now works
In [backend/app/services/graphiti_builder.py](/Volumes/asfoora/MiroFish/backend/app/services/graphiti_builder.py):
- added a tolerant Graphiti LLM client instead of relying on Graphiti's strict default parse path
- normalized fenced/prose-wrapped JSON
- wrapped top-level list outputs into the expected object shape
- unwrapped schema-style payloads like `{"properties": {...}}`
- kept Graphiti running against local Neo4j and Ollama-compatible endpoints

Result:
- graph builds completed successfully on the remote host
- local model `qwen2.5:14b` was the first stable end-to-end Graphiti model in this stack

### 2. The stack is now unified to one primary local LLM
Current verified remote direction:
- primary model: `qwen2.5:14b`
- endpoint: local Ollama-compatible endpoint on the Mac Studio
- `.env` direction:
  - `LLM_MODEL_NAME=qwen2.5:14b`
  - `GRAPHITI_MODEL_NAME=`
  - `REPORT_INTERVIEW_MAX_AGENTS=3`
  - `REPORT_INTERVIEW_TIMEOUT_SECONDS=420`

In code:
- [backend/app/config.py](/Volumes/asfoora/MiroFish/backend/app/config.py)
  - report path resolves `REPORT_LLM_* -> GRAPHITI_* -> LLM_*`
  - simulation-prep path resolves `SIMULATION_LLM_* -> GRAPHITI_* -> LLM_*`
- [backend/scripts/run_parallel_simulation.py](/Volumes/asfoora/MiroFish/backend/scripts/run_parallel_simulation.py)
- [backend/scripts/run_twitter_simulation.py](/Volumes/asfoora/MiroFish/backend/scripts/run_twitter_simulation.py)
- [backend/scripts/run_reddit_simulation.py](/Volumes/asfoora/MiroFish/backend/scripts/run_reddit_simulation.py)
  - runtime simulation now also resolves `SIMULATION_LLM_* -> GRAPHITI_* -> LLM_*`

This replaced prior unsuccessful attempts with:
- `qwen3.5:4b`
- `qwen2.5-coder:7b`
- `qwen2.5:7b`
- NVIDIA-hosted trials that either rate-limited or did not support Graphiti's JSON mode reliably

Direct comparison result:
- `qwen3.5:9b` was tested in the same single-model configuration and failed report generation early
- verified failure:
  - report: `report_4bb79a7f1b68`
  - task: `1555ff90-b147-4323-855a-0922874827be`
  - failure: upstream `EOF`
  - elapsed: about `182s`
- conclusion: keep `qwen2.5:14b` as the single active model

Controlled local benchmark result on `2026-03-27`:
- see [MODEL_SELECTION_2026-03-27.md](/Volumes/asfoora/MiroFish/MODEL_SELECTION_2026-03-27.md)
- raw artifact: [model_benchmark_results_2026-03-27.json](/Volumes/asfoora/MiroFish/model_benchmark_results_2026-03-27.json)
- fixed-window report benchmark outcome:
  - `qwen2.5:14b`: `34%`
  - `qwen3:14b`: `34%`
  - `mistral-small3.2:latest`: `34%`
  - `gemma3:12b-it-qat`: `52%`
- operational decision:
  - keep `qwen2.5:14b` as the default full-stack model
  - keep `gemma3:12b-it-qat` as the main alternate
  - remove the other tested local models to recover disk space

### 3. Simulation Step 2 no longer depends on Zep for local `mirofish_*` graphs
In [backend/app/services/zep_entity_reader.py](/Volumes/asfoora/MiroFish/backend/app/services/zep_entity_reader.py):
- added local Graphiti/Neo4j reads for `mirofish_*` graphs
- node/entity reads now come from Neo4j instead of Zep Cloud for local graphs
- edge/context reads now come from Neo4j instead of Zep Cloud for local graphs
- entity typing now falls back sensibly for `Entity`-only local nodes

In [backend/app/services/oasis_profile_generator.py](/Volumes/asfoora/MiroFish/backend/app/services/oasis_profile_generator.py):
- disabled Zep hybrid search for local Graphiti graphs

Result:
- `/api/simulation/prepare` no longer blocks for minutes on Zep `404` / rate-limit failures
- the endpoint now returns quickly with a task id and expected entity count

### 4. Simulation persona generation was stabilized
In [backend/app/config.py](/Volumes/asfoora/MiroFish/backend/app/config.py) and [backend/app/services/oasis_profile_generator.py](/Volumes/asfoora/MiroFish/backend/app/services/oasis_profile_generator.py):
- simulation persona generation now defaults to simulation-specific LLM settings
- if no dedicated simulation env vars are set, it falls back to Graphiti's model/runtime
- local Ollama persona generation parallelism is capped to a safer level
- persona output is bounded with explicit token and timeout limits
- persona prompts were shortened to avoid excessively long local generations

Result:
- all `28` agent profiles were generated successfully for `sim_7b58160805f4`

### 5. Simulation config generation now uses the same bounded simulation LLM path
In [backend/app/services/simulation_config_generator.py](/Volumes/asfoora/MiroFish/backend/app/services/simulation_config_generator.py):
- switched config generation to the simulation LLM settings instead of the generic app LLM
- added explicit token and timeout limits

In [backend/app/services/simulation_manager.py](/Volumes/asfoora/MiroFish/backend/app/services/simulation_manager.py):
- wired config-generation substep progress into the overall task progress callback

Result:
- Step 2 can complete end-to-end instead of stalling after persona generation
- task progress now reflects config-generation substeps more accurately

### 6. Report generation was hardened and moved onto the same stronger model path
In [backend/app/utils/llm_client.py](/Volumes/asfoora/MiroFish/backend/app/utils/llm_client.py):
- retries transient API failures such as `EOF`
- retries once without JSON mode if JSON mode returns empty content

In [backend/app/services/report_agent.py](/Volumes/asfoora/MiroFish/backend/app/services/report_agent.py):
- report generation now uses the report-configured LLM fallback chain instead of the weak generic path
- mixed `tool call + Final Answer` responses are handled more cleanly
- report interview tool descriptions now advertise the real configured cap
- report interview requests are clamped to the configured cap instead of trusting model-suggested larger values

In [backend/app/services/zep_tools.py](/Volumes/asfoora/MiroFish/backend/app/services/zep_tools.py):
- report interview timeout is now config-driven
- report interview max agents is now config-driven and enforced

Result:
- older report failure mode `LLM returned empty content in JSON mode` is no longer the main blocker
- older report failure mode `EOF` on the weak model path was materially reduced on the `qwen2.5:14b` path
- verified live rerun now issues:
  - `max_agents: 3`
  - selected agents: `3`
  - dual-platform interview batch: `3 Agents`

## Key Verified Outcomes

### Graph build
- Remote graph builds completed successfully with local `qwen2.5:14b`
- Graphiti parser/timeout failures from the old handoff were addressed

### Simulation preparation
For `sim_7b58160805f4`:
- expected entities: `28`
- agent profiles generated: `28`
- config file generated successfully
- backend status now reports preparation as complete / reusable

### Simulation runtime
- the verified simulation path completed successfully on the Mac Studio
- OASIS remains the runtime simulation layer
- Graphiti remains the graph-building / graph-reading layer

### Report generation
- `qwen3.5:9b` is not suitable as the single-model choice for this workload
- `qwen2.5:14b` remains the verified winner
- `gemma3:12b-it-qat` was the fastest report-stage performer in the controlled benchmark
- report generation still spends most of its time inside interview batches when it decides to call that tool
- the current code now limits those report interviews to `3` agents instead of allowing `5`

### UI caveat
- after backend restarts, the frontend may temporarily display stale step or report state
- the reliable source of truth is the backend API plus remote logs

## Files Changed In This Session
- [backend/app/config.py](/Volumes/asfoora/MiroFish/backend/app/config.py)
- [backend/app/services/graphiti_builder.py](/Volumes/asfoora/MiroFish/backend/app/services/graphiti_builder.py)
- [backend/app/services/zep_entity_reader.py](/Volumes/asfoora/MiroFish/backend/app/services/zep_entity_reader.py)
- [backend/app/services/oasis_profile_generator.py](/Volumes/asfoora/MiroFish/backend/app/services/oasis_profile_generator.py)
- [backend/app/services/simulation_config_generator.py](/Volumes/asfoora/MiroFish/backend/app/services/simulation_config_generator.py)
- [backend/app/services/simulation_manager.py](/Volumes/asfoora/MiroFish/backend/app/services/simulation_manager.py)
- [backend/app/services/report_agent.py](/Volumes/asfoora/MiroFish/backend/app/services/report_agent.py)
- [backend/app/services/zep_tools.py](/Volumes/asfoora/MiroFish/backend/app/services/zep_tools.py)
- [backend/app/utils/llm_client.py](/Volumes/asfoora/MiroFish/backend/app/utils/llm_client.py)
- [backend/scripts/run_parallel_simulation.py](/Volumes/asfoora/MiroFish/backend/scripts/run_parallel_simulation.py)
- [backend/scripts/run_twitter_simulation.py](/Volumes/asfoora/MiroFish/backend/scripts/run_twitter_simulation.py)
- [backend/scripts/run_reddit_simulation.py](/Volumes/asfoora/MiroFish/backend/scripts/run_reddit_simulation.py)
- [MODEL_SELECTION_2026-03-27.md](/Volumes/asfoora/MiroFish/MODEL_SELECTION_2026-03-27.md)
- [model_benchmark_results_2026-03-27.json](/Volumes/asfoora/MiroFish/model_benchmark_results_2026-03-27.json)
- [HANDOFF.md](/Volumes/asfoora/MiroFish/HANDOFF.md)

## Current Relevant `.env` Direction
See [.env](/Volumes/asfoora/MiroFish/.env).

Important current behavior:
- the intended single-model setup is now:
  - `LLM_MODEL_NAME=qwen2.5:14b`
  - `GRAPHITI_MODEL_NAME=`
- runtime simulation, simulation prep, graph build, and report generation all fall back to the same primary model path
- do not switch back to `qwen3.5:9b` unless it is re-benchmarked and proven on graph + report, which it was not in this session
- do not switch the main stack to `gemma3:12b-it-qat` until it is also re-tested on a full Graphiti graph build
- report interviews are currently tuned to:
  - `REPORT_INTERVIEW_MAX_AGENTS=3`
  - `REPORT_INTERVIEW_TIMEOUT_SECONDS=420`

## Useful Commands

### Backend health on remote host
```sh
curl -s http://192.168.1.173:5001/health
```

### Check prepare status
```sh
curl -s -X POST http://192.168.1.173:5001/api/simulation/prepare/status \
  -H 'Content-Type: application/json' \
  -d '{"simulation_id":"sim_7b58160805f4"}'
```

### Force-regenerate simulation preparation
```sh
curl -s -X POST http://192.168.1.173:5001/api/simulation/prepare \
  -H 'Content-Type: application/json' \
  -d '{"simulation_id":"sim_7b58160805f4","force_regenerate":true,"use_llm_for_profiles":true,"parallel_profile_count":5}'
```

### Tail remote app logs
```sh
ssh asfoora@192.168.1.173
cd /Users/asfoora/MiroFish
docker compose -f docker-compose.yml logs --tail=120 mirofish
```

### Check report task status
```sh
curl -s -X POST http://192.168.1.173:5001/api/report/generate/status \
  -H 'Content-Type: application/json' \
  -d '{"task_id":"<task_id>"}'
```

### Tail a report log
```sh
ssh asfoora@192.168.1.173
tail -n 120 /Users/asfoora/MiroFish/backend/uploads/reports/<report_id>/console_log.txt
```

## Recommended Next Work
- fix frontend recovery so report/simulation views reattach more cleanly after backend restarts
- if needed, make the report interview tool cheaper still:
  - fewer questions
  - single-platform interview mode for report use
  - tighter response length constraints
- if you want to promote `gemma3:12b-it-qat`, the next sensible test is a full Graphiti build benchmark
- consider deduplicating weak/noisy entity labels in the graph-to-persona pipeline
- clean up duplicate root-level files such as:
  - [backend/app/report_agent.py](/Volumes/asfoora/MiroFish/backend/app/report_agent.py)
  - [backend/app/zep_tools.py](/Volumes/asfoora/MiroFish/backend/app/zep_tools.py)
  These were preserved in backup commits and should be reviewed before deleting.

## Backup Note
Local git backup repo:
- `/Users/zeidnima/Nextcloud/OpenClaw/gits/MiroFish.git`

Recent backup commits created in this session:
- `08bccb7`
- `d1cd63a`
