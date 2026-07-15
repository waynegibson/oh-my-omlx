# oMLX — Local LLM Inference Server

oMLX-based local inference server running Qwen 3.5/3.6 models on Apple Silicon. Replaces cloud APIs (Claude, GPT) with self-hosted models via MLX quantization.

## Models

| Model                          | Size              | Role                    | Profile              |
| ------------------------------ | ----------------- | ----------------------- | -------------------- |
| **Qwopus3.6-27B-Coder-8bit**   | ~27 GB (6 shards) | Coding / agentic (VLM)  | `coding` (temp 0.1)  |
| **Qwen3.6-35B-A3B-6bit** (MoE) | ~27 GB (6 shards) | General chat (VLM)      | `general` (temp 0.7) |

## Quick Start

```bash
# Set credentials (required)
export OMLX_API_KEY=<your_api_key>
export OMLX_SECRET_KEY=<your_secret_key>

# Start server (auto-starts on launch per config)
omlx serve
```

Server runs on `127.0.0.1:8055` by default.

## Architecture

- **Quantization**: 8-bit dense (coder) + 6-bit MoE (general)
- **Decoding**: MTP (multi-token prediction) + D-Flash draft speculation — TurboQuant KV compression disabled (mutually exclusive with MTP; see `HARDWARE_OPTIMIZATION_REPORT.md`)
- **KV Cache**: SSD-backed (92 GB max) + 12 GB RAM hot cache
- **Speculative Prefill**: 35B only, 35% keep ratio
- **Context Window**: 65,536 tokens (coder) / 32,768 tokens (general)

## Directory Structure

```
base/          — Server config, model profiles, usage stats
cache/         — SSD-backed KV cache blocks (~4 GB current)
models/        — Model weights (gitignored, ~54 GB total)
```

## Environment Variables

| Variable          | Default               | Description                       |
| ----------------- | --------------------- | --------------------------------- |
| `OMLX_API_KEY`    | `spacecomx`           | API key for client authentication |
| `OMLX_SECRET_KEY` | _(see settings.json)_ | HMAC secret for token signing     |

## Model Profiles

One active profile per model, derived from a global template of the same name:

| Profile   | Temperature | Model            | Use Case                             |
| --------- | ----------- | ---------------- | ------------------------------------ |
| `coding`  | 0.1         | Qwopus3.6-27B    | Deterministic code generation, tools |
| `general` | 0.7         | Qwen3.6-35B-A3B  | Balanced daily use                   |

## Integrations

Configured for: Claude Code, Codex, OpenCode, OpenClaw, Copilot, Pi.

## Stats

Usage telemetry tracked in `base/stats.json` — total tokens, cached tokens, request counts, and per-model breakdowns.
