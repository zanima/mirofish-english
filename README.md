<div align="center">

<img src="./static/image/MiroFish_logo_compressed.jpeg" alt="MiroFish Logo" width="70%"/>

# MiroFish English

English-maintained public derivative of the original `666ghj/MiroFish` project.

[GitHub](https://github.com/zanima/mirofish-english) | [Derivative Notice](./NOTICE.md) | [English README](./README-EN.md)

</div>

## Release Status

This repository is the first public derivative release of the English-maintained version.

What is ready now:

- source code is public and runnable
- local source deployment works
- Docker-based deployment is available
- Ollama and multiple cloud model providers are wired in
- Kimi / Moonshot compatibility was updated for the current API endpoint

What is not included:

- hosted SaaS service
- managed API keys
- one-click production deployment

## Derivative Notice

This repository is a derivative work of the original `MiroFish` project by `666ghj`.

- Upstream repository: `https://github.com/666ghj/MiroFish`
- License: `AGPL-3.0`
- Attribution details: [NOTICE.md](./NOTICE.md)

This version preserves upstream attribution while adding English maintenance, deployment fixes, compatibility updates, and release cleanup.

## Overview

MiroFish is a multi-agent prediction and simulation system. It takes seed material such as reports, articles, policy drafts, or narrative text, builds a graph-backed world model, generates agent personas, runs a social simulation, and produces a report plus an interactive environment for follow-up exploration.

## Current Public Scope

- Backend: Flask API for graph building, simulation, reporting, and model management
- Frontend: Vue/Vite UI for uploading seed data, running workflows, and viewing outputs
- Model support: Ollama plus OpenAI-compatible providers including NVIDIA, Google, DeepSeek, Anthropic, and Kimi
- Memory/graph stack: Neo4j, Zep, Graphiti

## Quick Start

### Prerequisites

- `Node.js` 18+
- `Python` 3.11 or 3.12
- `uv`
- optional: Docker / Docker Compose

### Source Deployment

```bash
cp .env.example .env
npm run setup:all
npm run dev
```

Default local URLs:

- frontend: `http://localhost:3000`
- backend: `http://localhost:5001`

### Docker Deployment

```bash
cp .env.example .env
docker compose up -d
```

## Environment Setup

Copy [`.env.example`](./.env.example) to `.env` and provide your own keys.

Minimum required variables:

```env
LLM_API_KEY=your_api_key_here
LLM_BASE_URL=https://your-openai-compatible-endpoint/v1
LLM_MODEL_NAME=your_model_name
ZEP_API_KEY=your_zep_api_key_here
```

No personal API keys are included in this repository.

## Release Notes

See [CHANGELOG.md](./CHANGELOG.md) for the current public release summary.

## License

This repository remains under `AGPL-3.0`. If you deploy a modified public network service based on this project, you must make the corresponding source code available under the license terms.

## Acknowledgments

- Original project: `666ghj/MiroFish`
- OASIS / CAMEL-AI for the simulation foundation used by the project
- AI-assisted derivative maintenance and release work in this repository included both `Codex` and `Claude`
