# MiroFish Installation Assessment — Mac Studio

**Date:** 2026-03-24
**Target Machine:** Mac Studio (Apple Silicon) with Ollama

## What Is MiroFish?

MiroFish is a **multi-agent AI prediction engine** that constructs "high-fidelity parallel digital worlds" from seed information (news, financial signals, etc.). Thousands of AI agents — each with independent personalities, behavioral logic, and memory — interact and evolve socially within a simulated environment. Users inject variables dynamically to simulate future outcomes.

- Built on the **CAMEL-AI OASIS framework**
- Users upload seed materials, describe predictions in natural language
- Returns detailed forecast reports and interactive digital environments
- Use cases: policy testing, PR strategy, speculative exploration
- License: AGPL-3.0

## System Requirements vs Local Environment

| Requirement    | Needed         | Available        | Status              |
|----------------|----------------|------------------|---------------------|
| Node.js        | >= 18.0.0      | v25.8.1          | OK                  |
| Python         | 3.11 – 3.12   | 3.14 (system)    | Install 3.12 via uv |
| uv             | latest         | 0.10.9           | OK                  |
| Docker         | optional       | 29.2.1           | OK                  |
| Ollama         | not required   | 0.18.2           | OK (OpenAI-compat)  |

## Ollama Integration

MiroFish uses the **OpenAI SDK** (`openai>=1.0.0`) with configurable `LLM_BASE_URL` and `LLM_MODEL_NAME`. Since Ollama exposes an OpenAI-compatible API at `http://localhost:11434/v1`, MiroFish can be pointed to Ollama.

### Available Ollama Models for Testing

#### Local Models
| Model                          | Size   | Notes                    |
|--------------------------------|--------|--------------------------|
| glm-4.7-flash                  | 19 GB  | Local, good for testing  |
| qwen3.5:35b-a3b-q4_K_M        | 23 GB  | Local, strong reasoning  |
| gpt-oss:20b                    | 13 GB  | Local                    |
| nomic-embed-text               | 274 MB | Embeddings only          |

#### Ollama Cloud Models
| Model                | Notes                          |
|----------------------|--------------------------------|
| kimi-k2.5:cloud      | Cloud-hosted via Ollama        |
| glm-5:cloud          | Cloud-hosted via Ollama        |
| gpt-oss:120b-cloud   | Cloud-hosted, largest available|
| minimax-m2.5:cloud   | Cloud-hosted via Ollama        |

### Performance Warning

MiroFish runs **thousands of concurrent LLM calls** across many agents. Local models will be slow for large simulations. Recommended approach:
- **Testing/small runs:** Local models (glm-4.7-flash, qwen3.5:35b)
- **Larger simulations:** Ollama cloud models (kimi-k2.5, gpt-oss:120b-cloud)
- Keep iterations **under 40** even with fast endpoints

## Dependencies

### Python Backend
- flask, flask-cors — web framework
- openai — LLM client (OpenAI SDK format)
- zep-cloud — agent memory management (requires free Zep Cloud API key)
- camel-oasis / camel-ai — OASIS social simulation engine
- PyMuPDF — PDF parsing
- python-dotenv, pydantic — config and validation

### External Services Required
- **Zep Cloud API key** (free tier sufficient) — mandatory for agent memory

## .env Configuration for Ollama

```env
LLM_API_KEY=ollama
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL_NAME=qwen3.5:35b-a3b-q4_K_M

# Optional: use cloud model for acceleration
LLM_BOOST_API_KEY=ollama
LLM_BOOST_BASE_URL=http://localhost:11434/v1
LLM_BOOST_MODEL_NAME=kimi-k2.5:cloud

ZEP_API_KEY=z_1dWlkIjoiZTI4N2FmY2YtYzhjNS00NjA3LTljYzUtZDYwMDM4YTRkYTlhIn0.ALg0V5cLuU96rhN3yu-cXcA7d8CfN4kb4EAdwua8w1m5PZio2eCxlvycChGHxJcVu8qN17-8SeP6hAMkjw5p7w
```

## Installation Steps

```bash
# 1. Install Python 3.12
uv python install 3.12

# 2. Clone the repo
git clone https://github.com/666ghj/MiroFish.git .

# 3. Configure environment
cp .env.example .env
# Edit .env with Ollama settings above

# 4. Install all dependencies
npm run setup:all

# 5. Start dev servers (frontend :3000 + backend :5001)
npm run dev
```
