# oMLX — Local LLM Inference Server

oMLX-based local inference server running Qwen 3.6 models on Apple Silicon. Replaces cloud APIs (Claude, GPT) with self-hosted MLX-quantized models.

## Models

| Model                             | Location              | Quantization     | MTP     | Profiles                                                |
| --------------------------------- | --------------------- | ---------------- | ------- | ------------------------------------------------------- |
| **Qwen3.6-27B-oQ8e-fp16-mtp**     | `spacecomx/` (~29 GB) | 8-bit (oQ8e)     | enabled | `general` (active), `coder`, `agentic`, `prose`, `quiz` |
| **Qwen3.6-35B-A3B-oQ8e-fp16-mtp** | `spacecomx/` (~37 GB) | 8-bit MoE (oQ8e) | enabled | `coder` (active), `general`, `agentic`, `prose`, `quiz` |
| **Qwen3.6-35B-A3B-oQ6e-fp16-mtp** | `spacecomx/` (~29 GB) | 6-bit MoE (oQ6e) | enabled | `general` (active), `coder`, `agentic`, `prose`, `quiz` |

Source models in `Qwen/`: `Qwen3.6-27B` (~52 GB), `Qwen3.6-35B-A3B` (~67 GB).

## Quick Start

```bash
# Server auto-starts on launch (per settings.json)
omlx serve
```

Server runs on `127.0.0.1:8055` by default. API key verification is bypassed locally (`skip_api_key_verification: true`).

## Architecture

- **Quantization**: 8-bit oQ8e (coder) + 6-bit/8-bit MoE variants
- **Decoding**: MTP (multi-token prediction) on most models; D-Flash disabled
- **KV Cache**: Hot cache only (8 GB RAM), SSD cache available but not configured
- **Burst Decode**: Aggressive mode with preserved mid-system cache
- **Scheduler**: 2 concurrent requests, chunked prefill (priority: context)

## Directory Structure

```
base/          — Server config, model profiles, usage stats
  bin/         — omlx launcher script
  cache/       — KV cache blocks (~31 GB current)
  logs/        — Runtime logs
  models/      — Model weights (~214 GB total)
    spacecomx/ — Quantized models (~95 GB: 27B-oQ8e, 35B-oQ6e, 35B-oQ8e)
    Qwen/      — Source models (~119 GB: 27B, 35B-A3B)
  model_profiles.json   — Per-model profile definitions (settings per use case)
  model_settings.json   — Model-level defaults + active profile assignments
  settings.json         — Server configuration
  stats.json            — Usage telemetry
```

## Environment Variables

| Variable       | Default           | Description                       |
| -------------- | ----------------- | --------------------------------- |
| `OMLX_API_KEY` | `sk-local-bypass` | API key for client authentication |

## Server Aliases

| Alias               |
| ------------------- |
| `localhost`         |
| `127.0.0.1`         |
| `spacestudio.local` |
| `192.168.10.99`     |

## Model Profiles

Each model has 5 profiles derived from its global settings:

| Profile   | Temperature | Thinking          | Max Output    | Use Case                                          |
| --------- | ----------- | ----------------- | ------------- | ------------------------------------------------- |
| `general` | 1.0         | on (8K budget)    | 16,384        | Balanced default: thinking on, budgeted           |
| `coder`   | 0.6         | on (8–16K budget) | 16,384–32,768 | Python/TS/SQL, code review. Low temp, thinking on |
| `agentic` | 0.6         | on (4K budget)    | 16,384        | Tool-calling / multi-step agent loops             |
| `prose`   | 0.8         | off               | 8,192         | Documents, writing. Mild presence penalty         |
| `quiz`    | 0.0         | off               | 4,096         | Rigid-template ML quiz output. Near-deterministic |

Active profiles (from `model_settings.json`):

- **Qwen3.6-27B-oQ8e** → `general`
- **Qwen3.6-35B-A3B-oQ8e** → `coder`

## Integrations

Configured for: Claude Code, Codex, OpenCode, OpenClaw, Pi, Copilot.

**Markitdown**: Enabled — PDF/file processing (25 MB max, 5 files per request).
