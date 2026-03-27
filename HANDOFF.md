# MiroFish Handoff
**Date:** 2026-03-27  
**Status:** Local Graphiti graph build is working on `192.168.1.173`, Step 2 simulation preparation is fixed, and the current simulation moved past preparation into the running simulation flow.

## Current Runtime State
- Remote host: `192.168.1.173`
- Main verified project: `proj_62a91485b4b3`
- Main verified simulation: `sim_7b58160805f4`
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
- The user confirmed the UI advanced to simulation `Step 4/5`.

## Important Conclusion
- The old blocker from the previous handoff is no longer true.
- Graphiti is no longer failing at chunk ingestion for the tested path.
- The main graph path now works locally with Ollama-served `qwen2.5:14b`.
- Step 2 simulation preparation is no longer blocked on Zep.
- The frontend can still show stale progress after backend restarts, but the backend workflow itself is now functional.

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

### 2. Graphiti model/runtime selection is stabilized
Current effective remote direction:
- Graphiti model: `qwen2.5:14b`
- Graphiti endpoint: local Ollama-compatible endpoint on the Mac Studio

This replaced prior unsuccessful attempts with:
- `qwen3.5:4b`
- `qwen2.5-coder:7b`
- `qwen2.5:7b`
- NVIDIA-hosted trials that either rate-limited or did not support Graphiti's JSON mode reliably

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

### UI caveat
- after backend restarts, the frontend may temporarily display stale Step 2 progress
- the reliable source of truth is the backend prepare status API

## Files Changed In This Session
- [backend/app/config.py](/Volumes/asfoora/MiroFish/backend/app/config.py)
- [backend/app/services/graphiti_builder.py](/Volumes/asfoora/MiroFish/backend/app/services/graphiti_builder.py)
- [backend/app/services/zep_entity_reader.py](/Volumes/asfoora/MiroFish/backend/app/services/zep_entity_reader.py)
- [backend/app/services/oasis_profile_generator.py](/Volumes/asfoora/MiroFish/backend/app/services/oasis_profile_generator.py)
- [backend/app/services/simulation_config_generator.py](/Volumes/asfoora/MiroFish/backend/app/services/simulation_config_generator.py)
- [backend/app/services/simulation_manager.py](/Volumes/asfoora/MiroFish/backend/app/services/simulation_manager.py)
- [HANDOFF.md](/Volumes/asfoora/MiroFish/HANDOFF.md)

## Current Relevant `.env` Direction
See [.env](/Volumes/asfoora/MiroFish/.env).

Important current behavior:
- generic app LLM is still set separately
- simulation generation now falls back to Graphiti LLM settings if no `SIMULATION_LLM_*` env vars are defined
- Graphiti model currently needs to remain on the known-good local path

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

## Recommended Next Work
- fix frontend recovery so Step 2 can reattach to an in-flight prepare task after backend restart
- clean up any remaining stale progress/UI mismatch in `Step2EnvSetup.vue`
- if needed, introduce explicit `SIMULATION_LLM_*` entries in `.env` instead of relying on Graphiti fallback
- consider deduplicating weak/noisy entity labels in the graph-to-persona pipeline

## Backup Note
This workspace did not have an existing `.git` repository on this MacBook at the start of this handoff update. If a local git backup is required again, check the Nextcloud bare backup under:
- `/Users/zeidnima/Nextcloud/OpenClaw/gits/`
