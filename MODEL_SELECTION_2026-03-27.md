# Model Selection Reference
**Date:** 2026-03-27  
**Host:** `192.168.1.173` Mac Studio  
**Purpose:** Choose the best local Ollama model for MiroFish and record the reasoning for future reference.

## Scope
This benchmark was designed to answer a practical question:

- Which local model is the best fit for the current MiroFish workflow on the Mac Studio?

The current workflow has four relevant phases:

1. Graph build with Graphiti
2. Simulation preparation
3. Simulation runtime
4. Report generation

Important constraint:
- Only `qwen2.5:14b` was already proven end-to-end for Graphiti graph construction on this stack before this benchmark.
- The new benchmark below was a controlled **report-generation benchmark** on the same completed simulation and graph, because that is the slowest and most model-sensitive phase to compare quickly and fairly.

So the conclusion is split into:
- **safe full-stack default**
- **best report-stage challenger**

## Candidate Models
Tested in this benchmark:
- `qwen2.5:14b`
- `qwen3:14b`
- `mistral-small3.2:latest`
- `gemma3:12b-it-qat`

Already known from earlier work:
- `qwen3.5:9b` was not good enough for this workload and failed earlier on the report path with `EOF`
- `qwen3.5:4b`, `qwen2.5:7b`, and `qwen2.5-coder:7b` were not competitive enough to keep as primary options

## Method
All models were tested on the same Mac Studio with the same backend workflow.

Fixed settings:
- same remote host: `192.168.1.173`
- same simulation: `sim_7b58160805f4`
- same graph: `mirofish_d838b8ea0f3c4286`
- same report path: `POST /api/report/generate`
- same interview settings:
  - `REPORT_INTERVIEW_MAX_AGENTS=3`
  - `REPORT_INTERVIEW_TIMEOUT_SECONDS=420`
- same env direction:
  - `LLM_MODEL_NAME=<candidate>`
  - `GRAPHITI_MODEL_NAME=`

Benchmark window:
- each model got a fresh backend restart
- each model was given a **10-minute report-generation window**
- if still running at the end of the window, the backend was restarted to stop the in-process report task cleanly

What was measured:
- progress reached within the fixed window
- whether outline planning succeeded
- whether the model entered interview tool calls
- whether interview batches timed out
- whether the model hit `EOF`
- whether the model forced sections early

## Results

| Model | Progress at 10 min | Outline | Interview batch | Timeout seen | EOF seen | Practical read |
|---|---:|---|---|---|---|---|
| `qwen2.5:14b` | `34%` | Yes | `3 agents` | Yes | No | Stable baseline, completed chapter 1 and moved into chapter 2 |
| `qwen3:14b` | `34%` | Yes | `3 agents` | No, within window | No | Promising, but spent most of the window inside first interview batch |
| `mistral-small3.2:latest` | `34%` | Yes | `3 agents` | Yes | No | No advantage over baseline in this workflow |
| `gemma3:12b-it-qat` | `52%` | Yes | `2 agents` | Yes | No | Fastest report-stage performer in this benchmark |

### Per-model notes

#### `qwen2.5:14b`
Strengths:
- already proven on Graphiti graph build
- already proven on simulation prep/runtime path
- report path is stable enough to keep moving after interview problems

Weakness:
- report generation remains slow, especially around interviews

#### `qwen3:14b`
Strengths:
- clean start
- no `EOF`
- no immediate failure

Weakness:
- in the current app behavior, it did not beat `qwen2.5:14b`
- it reached the same `34%` window ceiling and spent a lot of time in the first interview batch

Interpretation:
- worth retesting later if the app adds explicit non-thinking control or more model-specific tuning
- not enough evidence to replace the baseline today

#### `mistral-small3.2:latest`
Strengths:
- compatible enough to run the workflow
- no `EOF`

Weakness:
- reached only `34%`
- first interview batch hit the full `420s` timeout
- no practical advantage over `qwen2.5:14b`

Interpretation:
- not worth keeping as a primary candidate on this Mac Studio for this app

#### `gemma3:12b-it-qat`
Strengths:
- best throughput in the fixed report window
- reached `52%`, clearly ahead of the other three
- no `EOF`
- recovered after interview timeout and kept advancing
- smaller footprint than the 14B/24B alternatives

Weakness:
- not yet proven on Graphiti graph build in this stack
- the model chose a smaller `2-agent` interview batch, which helped throughput but may slightly reduce breadth

Interpretation:
- strongest challenger for report generation
- not yet enough evidence to replace `qwen2.5:14b` as the **single full-stack default**

## Decision

### Safe full-stack default
Keep:
- `qwen2.5:14b`

Why:
- it is the only model in this set already proven end-to-end for graph build + simulation + report path on this stack

### Best alternate / fastest report-stage challenger
Keep:
- `gemma3:12b-it-qat`

Why:
- it was clearly the fastest report-stage model in the controlled benchmark
- it may become the better report-only or future general model after a dedicated Graphiti build retest

### Not selected as primary models
Do not keep as primary:
- `qwen3:14b`
- `mistral-small3.2:latest`

Why:
- neither beat the baseline in the current app workflow

## Recommended Operating Policy
For now:
- Use `qwen2.5:14b` as the main single model in `.env`
- Keep `gemma3:12b-it-qat` installed as the main fallback / next challenger

If a future test is run:
1. Re-test `gemma3:12b-it-qat` on a full Graphiti build, not just report generation
2. Re-test `qwen3:14b` only if the app adds explicit non-thinking control
3. Do not spend more time on `mistral-small3.2` unless requirements change

## Cleanup Recommendation
Safe models to keep:
- `qwen2.5:14b`
- `gemma3:12b-it-qat`
- `nomic-embed-text:latest`

Safe models to remove for space recovery:
- `qwen3:14b`
- `mistral-small3.2:latest`
- `gemma3:12b`
- `qwen2.5:7b`
- `qwen2.5-coder:7b`
- `qwen3.5:4b`
- `qwen3.5:9b`

Optional later cleanup if you want aggressive disk recovery:
- other unused cloud aliases and large image models that are not part of the current MiroFish workflow

## Raw Benchmark Artifacts
- [model_benchmark_results_2026-03-27.json](/Volumes/asfoora/MiroFish/model_benchmark_results_2026-03-27.json)
- [HANDOFF.md](/Volumes/asfoora/MiroFish/HANDOFF.md)
