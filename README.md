# oMLX — Local LLM Inference Server

oMLX-based local inference server running Qwen 3.6 models on Apple Silicon (M1 Max / 64 GB). Replaces cloud APIs with self-hosted MLX-quantized models.

## Models

Only the three `spacecomx/` quantized models are served. All are VLM-capable (text + image) with native MTP speculative decoding.

| Model | Size | Weights | KV cache | Context | Active profile |
| --- | --- | --- | --- | --- | --- |
| **Qwen3.6-27B-oQ8e-fp16-mtp** | 29 GB | 8-bit dense | fp16 | 131,072 | `coder` (server default) |
| **Qwen3.6-35B-A3B-oQ6e-fp16-mtp** | 29 GB | 6-bit MoE | fp16 | 131,072 | `general` |
| **Qwen3.6-35B-A3B-oQ8e-fp16-mtp** | 37 GB | 8-bit MoE | TurboQuant 8-bit | 131,072 | `coder` |

Weight quantization (`oQ8e`/`oQ6e`, baked into the checkpoint) and KV-cache quantization (`turboquant_kv_bits`, a runtime setting) are independent. `turboquant_kv_enabled: false` means the cache is kept at **fp16**, not that there is no cache.

The unquantized fp16 sources (`Qwen3.6-27B` 52 GB, `Qwen3.6-35B-A3B` 67 GB) were only ever oQ quantiser inputs. They live in `base/quant-sources/` — outside the scanned model tree, so they cannot be loaded — and are kept for re-quantizing at other bit widths.

## Performance

Measured on M1 Max / 64 GB, one model resident at a time, 300-token generations and a 7.5k-token uncached prefill. Median of 3 decode runs.

| Model | Load | Decode | Prefill | Active params/token |
| --- | --- | --- | --- | --- |
| Qwen3.6-27B-oQ8e | 13.1 s | **15.4 tok/s** | **144 tok/s** | 27 B (dense) |
| Qwen3.6-35B-A3B-oQ6e | 15.5 s | **55.1 tok/s** | **909 tok/s** | 3 B (MoE) |
| Qwen3.6-35B-A3B-oQ8e | 22.2 s | **45.8 tok/s** | **925 tok/s** | 3 B (MoE) |

**The dense 27B is 3.6× slower to decode and 6.3× slower to prefill than either MoE**, despite having fewer total parameters. This is arithmetic, not misconfiguration: the 27B activates all 27 B parameters per token while the A3B MoE activates ~3 B. The 27B run measures 7.8 TFLOP/s effective, already near the M1 Max ceiling.

Practical consequence: a cold 50k-token prefill costs the 27B roughly 6 minutes versus under a minute on the MoE models. Prefix caching hides most of this within a session, but **the MoE models are the better choice for long-context agent work** — they are faster on both axes *and* their KV cache is 3.2× cheaper per token.

TurboQuant 8-bit KV costs no measurable throughput: the oQ8e benched 44–48 tok/s with it enabled, matching its fp16 sibling's range.

## Memory model

The prefill guard computes `hard_limit = min(static, dynamic, metal_cap)`, then applies a further ×0.90 safety factor for prefill.

| Component | Value | Source |
| --- | --- | --- |
| `static` | 62 GiB | total RAM − 2 GB (`custom` tier reserve) |
| `dynamic` | 56 GiB | `memory_guard_custom_ceiling_gb` verbatim |
| `metal_cap` | 58 GiB | `sysctl iogpu.wired_limit_mb=59392` |
| **hard limit** | **56 GiB** | min of the above |
| **prefill cap** | **50.4 GiB** | hard limit × 0.90 |

`memory_guard_custom_ceiling_gb` is **only read when `memory_guard_tier` is `"custom"`** — setting it under any other tier silently does nothing. Under `safe`/`balanced`/`aggressive` the `dynamic` ceiling is instead recomputed from live `vm_stat` pages on every call, so the effective ceiling drifts with system memory pressure and prefills can be rejected unpredictably. The `custom` tier trades that adaptivity for a stable, predictable ceiling.

> `iogpu.wired_limit_mb` resets to a 51.8 GB Metal cap on reboot. Re-apply `sudo sysctl iogpu.wired_limit_mb=59392` (or make it persistent), otherwise the 56 GiB ceiling exceeds what Metal will accept.

### KV cache sizing

These are hybrid-attention models — only full-attention layers grow a KV cache; linear-attention layers hold a fixed-size recurrent state.

| Model | Layers | Full-attn | KV heads | KV/token | Budget | Need @ 131k+16k | Margin |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 27B-oQ8e | 64 | 16 | 4 | 67 KB (fp16) | 11.55 GiB | 9.41 GiB | +2.14 |
| 35B-A3B-oQ6e | 40 | 10 | 2 | 21 KB (fp16) | 11.30 GiB | 2.94 GiB | +8.36 |
| 35B-A3B-oQ8e | 40 | 10 | 2 | 11.5 KB (tq8b) | 3.17 GiB | 1.62 GiB | +1.55 |

`max_context_window` is the **prompt** cap, so the KV budget must cover `context + max_tokens`. The oQ8e is the heaviest model (37 GB of weights), leaving it the least room for cache — at fp16 it would need 2.94 GiB against a 3.17 GiB budget, a 7% margin. TurboQuant 8-bit KV restores a comfortable +1.55 GiB at no throughput cost.

`hot_cache_max_size` is charged against the **same** ceiling as the KV cache, so it directly trades off against usable context. It is set to `4GB`.

> `hot_cache_max_size` goes through `parse_size()`: a bare `"8"` means 8 **bytes**, not 8 GB. Always include the unit.

## Model profiles

Four profiles per model. Sampling follows Qwen guidance: thinking mode `temp 0.6 / top_p 0.95`, non-thinking `temp 0.7 / top_p 0.8`, `top_k 20`, `min_p 0` throughout.

| Profile | Context | Max output | Temp | top_p | Thinking | Tool results | Use case |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `coder` | 131,072 | 16,384 | 0.6 | 0.95 | on (8K budget) | 16,384 | Python/ML notebooks, TS/SQL, code review, agentic tool loops |
| `general` | 131,072 | 16,384 | 0.7 | 0.95 | on (4K budget) | 8,192 | Balanced default for Q&A and analysis |
| `prose` | 65,536 | 8,192 | 0.7 | 0.80 | off | 0 | Documents, README, business-reader observations |
| `quiz` | 32,768 | 4,096 | 0.0 | 0.90 | off | 0 | Rigid-template ML quiz/exam output, deterministic |

`quiz` keeps thinking **off** deliberately — Qwen warns that greedy decoding combined with thinking mode causes endless repetition, so determinism and thinking are mutually exclusive here.

### Profile merge semantics

Applying a profile does **not** simply overlay the keys it defines. `apply_profile` splits settings into two classes:

- **Universal fields** (context, sampling, thinking, grammar, tool results) are *authoritative* — any key the profile omits is **reset to the ModelSettings default**.
- **Model-specific fields** (`turboquant_*`, `dflash_*`, `mtp_*`, `specprefill_*`, `index_cache_freq`) are an *additive overlay* — any key the profile omits **persists from whichever profile was applied before it**.

Every profile therefore writes an identical 29-key set, which makes profile switching order-independent. Omitting a model-specific key is the classic footgun: a `coder` profile that enables a feature will leak it into a later `prose` switch that never mentions it.

`None` and `""` are dropped by the settings sanitiser, so "unset" cannot be stored in a profile.

### Feature exclusivity

| Combination | Result |
| --- | --- |
| `mtp_enabled` + `dflash_enabled` | rejected at construction |
| `vlm_mtp_enabled` + any of `dflash` / `specprefill` / `mtp` / `turboquant_kv` | rejected at construction |
| `vlm_mtp_enabled` + `repetition_penalty ≠ 1`, `presence_penalty ≠ 0`, `thinking_budget_enabled`, or `guided_grammar_enabled` | `vlm_mtp` silently disabled |
| **`mtp_enabled` + `turboquant_kv_enabled`** | **supported** — TurboQuant's attention patch routes MTP's multi-row verify through the quantized decode kernels |

All three models use native `mtp_enabled` with `vlm_mtp_enabled: false`; DFlash and SpecPrefill are disabled everywhere.

## Quick Start

```bash
omlx serve
```

Server runs on `127.0.0.1:8055`. API key verification is bypassed locally (`skip_api_key_verification: true`). Auto-starts on launch per `settings.json`.

### Admin API

The app UI rewrites the JSON config files, so hand edits are only safe while the server is stopped. Use the admin API while it runs:

```bash
# List / create / delete / apply profiles  (GET returns a LIST, not a name-keyed dict)
curl 127.0.0.1:8055/admin/api/models/{model_id}/profiles
curl -X POST 127.0.0.1:8055/admin/api/models/{model_id}/profiles/{name}/apply

# Update model-level settings (partial body accepted)
curl -X PUT 127.0.0.1:8055/admin/api/models/{model_id}/settings \
  -H 'Content-Type: application/json' -d '{"is_hidden":true}'
```

> `PUT .../settings` accepts a partial body but **resets `active_profile_name` to null** unless it is included. Pass it explicitly to preserve it.

Profiles can only be managed for models that exist in the registry — a stale profile block for a removed model returns 404 on `DELETE` and must be cleaned out of `model_profiles.json` by hand with the server stopped.

## Architecture

- **Decoding**: native MTP on all models; DFlash and SpecPrefill disabled
- **KV cache**: fp16 on the 27B and oQ6e, TurboQuant 8-bit (`skip_last`) on the oQ8e
- **Caching**: 4 GB hot cache, 64 GB SSD tier available, `preserve_mid_system_cache` on
- **Burst decode**: aggressive, with `idle_timeout_seconds: 3600`
- **Scheduler**: 2 concurrent requests, chunked prefill (priority: context)
- **Memory guard**: `custom` tier, 56 GB ceiling

## Directory Structure

```
base/
  bin/                  — omlx launcher script
  cache/                — KV cache blocks (gitignored)
  logs/                 — Runtime logs (gitignored)
  models/               — Served weights, ~95 GB (gitignored)
    spacecomx/          — 27B-oQ8e, 35B-oQ6e, 35B-oQ8e
    .oqe_imatrix/       — oQ calibration matrices, keyed to the fp16 sources
  quant-sources/        — Unquantized fp16 inputs, ~119 GB (gitignored, never served)
  model_profiles.json   — Per-model profile definitions
  model_settings.json   — Model-level defaults + active profile assignments
  settings.json         — Server configuration
  stats.json            — Usage telemetry (gitignored)
```

## Environment Variables

| Variable | Default | Description |
| --- | --- | --- |
| `OMLX_API_KEY` | `sk-local-bypass` | API key for client authentication |

## Server Aliases

`localhost` · `127.0.0.1` · `spacestudio.local` · `192.168.10.99`

## Integrations

Integration model slots (Claude Code, Codex, OpenCode, OpenClaw, Hermes, Pi, Copilot) exist in `settings.json` but are currently unset — clients select models by id over the OpenAI-compatible API. The `oh-my-pi` client is configured in `oh-my-pi/base/agent/models.json`; keep its `contextWindow` / `maxTokens` in step with the profiles above, or the client will pace its context against a budget the server will not honour.

**Markitdown**: enabled — PDF/file processing (25 MB max, 5 files per request).
