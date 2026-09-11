# oMLX — Local LLM Inference Server

oMLX-based local inference server running Qwen 3.6 and 3.8 models on Apple Silicon (M1 Max / 64 GB). Replaces cloud APIs with self-hosted MLX-quantized models. Installed version: oMLX 0.7.0.dev1 (`/Applications/oMLX.app`).

## Models

Only `spacecomx/` oQ-quantized checkpoints are served. The live inventory is `base/model_settings.json` (or `GET /v1/models`); this file describes the model *families* in use, not the exact set, which changes over time.

| Family              | Architecture                                                            | Vision | Weights (oQ8e / oQ6e) |
| ------------------- | ----------------------------------------------------------------------- | ------ | --------------------- |
| **Qwen3.6-35B-A3B** | `qwen3_5_moe` — 40 layers, 256 experts, ~3 B active, 10 full-attn, 2 KV heads | yes    | ~37 GB / ~29 GB       |
| **Qwen3.8-27B**     | `qwen3_5` — 64 layers, dense, 16 full-attn, 4 KV heads                  | no     | ~27 GB / ~21 GB       |

Checkpoint names encode the build: `-oQ8e`/`-oQ6e` is the oQ level (`e` = enhanced, imatrix-calibrated on `oqe_code_multilingual`), `-fp16` is the compute dtype, `-mtp` means the MTP head was preserved for native speculative decoding. All served models have `mtp_enabled: true`.

Weight quantization (baked into the checkpoint) and KV-cache quantization (`turboquant_kv_bits`, a runtime setting) are independent. `turboquant_kv_enabled: false` means the cache is kept at **fp16**, not that there is no cache.

The unquantized sources used as oQ quantiser inputs live in the Hugging Face cache (`~/.cache/huggingface/hub/models--Qwen--*`), outside the scanned model tree, so they cannot be loaded by mistake.

## Performance

Measured all-time averages from `base/stats.json` as of 2026-09-11 (oMLX ≤ 0.7.0.dev1, M1 Max 64 GB, MTP on, fp16 KV). These are cumulative counters mixing context lengths and cache hits — order-of-magnitude, not a benchmark.

| Model                  | Uncached prefill | Generation | Requests |
| ---------------------- | ---------------- | ---------- | -------- |
| Qwen3.6-35B-A3B-oQ8e   | ~470 tok/s       | ~55 tok/s  | 207      |
| Qwen3.8-27B-oQ8e       | ~95 tok/s        | ~13 tok/s  | 83       |
| Qwen3.8-27B-oQ6e       | ~135 tok/s       | ~14 tok/s  | 6        |

From 0.7.0 the dashboard's **Usage** tab shows per-model output tok/s over selectable ranges (backed by `usage.sqlite3`, see below); prefer that over these figures once it has accumulated history.

**The dense 27B is significantly slower to decode and prefill than the MoE**, despite having fewer total parameters. This is arithmetic, not misconfiguration: the 27B activates all 27 B parameters per token while the A3B MoE activates ~3 B.

Practical consequence: a cold 50k-token prefill costs the 27B roughly 6–9 minutes versus under two on the MoE. Prefix caching hides most of this within a session (~84 % cache hit rate on both), but **the MoE is the better choice for long-context agent work** — it is faster on both axes _and_ its KV cache is ~3× cheaper per token.

The 0.7.0 headline speedups (gathered QSA, Lightning MTP, SSD-backed PLE) apply only to the `qwen4_exp` family (Qwen3.8-Flash-Next, 180 B parameters) and do not affect these models.

## Memory model

The process memory enforcer computes `ceiling = min(static, dynamic, metal_cap)`; the scheduler then sizes prefill chunks against `ceiling × 0.90` and throttles chunk size when usage approaches it.

| Component          | Value        | Source                                                                  |
| ------------------ | ------------ | ----------------------------------------------------------------------- |
| `static`           | 62 GiB       | total RAM − 2 GiB (`custom` tier reserve)                               |
| `dynamic`          | 52 GiB       | `memory_guard_custom_ceiling_gb` verbatim                               |
| `metal_cap`        | 51.8 GiB     | Apple `max_recommended_working_set_size` (`iogpu.wired_limit_mb` unset) |
| **ceiling**        | **51.8 GiB** | min of the above                                                        |
| **prefill target** | **~46 GiB**  | ceiling × 0.90                                                          |

`memory_guard_custom_ceiling_gb` is **only read when `memory_guard_tier` is `"custom"`** — setting it under any other tier silently does nothing. Under `safe`/`balanced`/`aggressive` the `dynamic` ceiling is instead recomputed from live host memory statistics on every poll, so the effective ceiling drifts with system memory pressure and prefills can be rejected unpredictably. The `custom` tier trades that adaptivity for a stable, predictable ceiling.

> The ceiling is currently bounded by Metal's default cap, not by the configured 52 GiB. Raising it requires *both* `sudo sysctl iogpu.wired_limit_mb=<MB>` (resets on reboot; the server log prints the suggested value at startup) *and* a higher `memory_guard_custom_ceiling_gb`. Leave at least ~6 GiB for macOS.

When usage nears the prefill target the log shows `Prefill throttled … chunk 4096 -> 1024`; prefill continues, just slower. This happens with the 37 GB oQ8e MoE at long context (37 GB weights + KV + prefill transients ≈ 43 GB seen on 2026-09-10). The oQ6e MoE build (~29 GB) leaves ~8 GB more headroom for the same profile.

### KV cache sizing

These are hybrid-attention models — only full-attention layers grow a KV cache; linear-attention layers hold a fixed-size recurrent state. KV/token = full-attn layers × KV heads × 2 (K,V) × head_dim 256 × 2 bytes (fp16).

| Family          | Full-attn | KV heads | KV/token | Need @ 131k + 16k | Headroom under ~46 GiB prefill target |
| --------------- | --------- | -------- | -------- | ----------------- | ------------------------------------- |
| Qwen3.6-35B-A3B | 10        | 2        | 20 KiB   | 2.8 GiB           | oQ8e: ~6 GiB · oQ6e: ~14 GiB          |
| Qwen3.8-27B     | 16        | 4        | 64 KiB   | 9.0 GiB           | oQ8e: ~10 GiB · oQ6e: ~16 GiB         |

`max_context_window` is the **prompt** cap, so the KV budget must cover `context + max_tokens`. Headroom is what remains for prefill transients after weights and a full-context KV cache; it is the figure that decides whether long prefills throttle.

## Model profiles

Four profiles per model, defined in `base/model_profiles.json`. `top_k 20`, `min_p 0` throughout; thinking mode uses `top_p 0.95`, non-thinking `top_p 0.8`/`0.9`.

| Profile   | Context                        | Max output | Temp | top_p | Thinking       | Tool results | Use case                                                     |
| --------- | ------------------------------ | ---------- | ---- | ----- | -------------- | ------------ | ------------------------------------------------------------ |
| `coder`   | 131,072                        | 16,384     | 0.6  | 0.95  | on (8K budget) | 16,384       | Python/ML notebooks, TS/SQL, code review, agentic tool loops |
| `general` | 131,072                        | 16,384     | 0.7  | 0.95  | on (4K budget) | 8,192        | Balanced default for Q&A and analysis                        |
| `prose`   | 65,536                         | 8,192      | 0.7  | 0.80  | off            | 0            | Documents, README, business-reader observations (presence penalty 0.5) |
| `quiz`    | 32,768 (27B) / 65,536 (35B-A3B) | 4,096     | 0.0  | 0.90  | off            | 0            | Rigid-template ML quiz/exam output, deterministic            |

`quiz` keeps thinking **off** deliberately — Qwen warns that greedy decoding combined with thinking mode causes endless repetition, so determinism and thinking are mutually exclusive here.

### Profile merge semantics

Applying a profile does **not** simply overlay the keys it defines. `apply_profile` (verified against 0.7.0 `model_profiles.py`) splits settings into two classes:

- **Universal fields** (20: context, sampling, penalties, thinking, reasoning parser, grammar, tool results, chat-template kwargs) are _authoritative_ — any key the profile omits is **reset to the ModelSettings default**.
- **Model-specific fields** (46: `turboquant_*`, `qwen35_ane_prefill_*`, `dflash_*`, `mtp_*`, `vlm_mtp_*`, `specprefill_*`, `index_cache_freq`) are an _additive overlay_ — any key the profile omits **persists from whichever profile was applied before it**.

Every profile in `model_profiles.json` therefore carries the full storable set (47 keys) so switching is order-independent. Omitting a model-specific key is the classic footgun: a `coder` profile that enables a feature will leak it into a later `prose` switch that never mentions it — keep engine toggles explicit in every profile.

`None` and `""` are dropped by the settings sanitiser, so "unset" cannot be stored in a profile.

### Feature exclusivity

| Combination                                                                   | Result                                                                                                          |
| ----------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| `mtp_enabled` + `dflash_enabled`                                              | rejected at construction                                                                                        |
| `vlm_mtp_enabled` + any of `dflash` / `specprefill` / `mtp` / `turboquant_kv` | rejected at construction                                                                                        |
| `vlm_mtp_enabled` + `repetition_penalty ≠ 1` or `presence_penalty ≠ 0`        | rejected at construction via the settings API; on profile apply, `vlm_mtp` is cleared instead (thinking budget is exempt) |
| **`mtp_enabled` + `turboquant_kv_enabled`**                                   | **supported** — TurboQuant's attention patch routes MTP's multi-row verify through the quantized decode kernels |

All served models use native `mtp_enabled` with `vlm_mtp_enabled: false`; DFlash and SpecPrefill are disabled everywhere.

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
- **KV cache**: fp16 on all models
- **Burst decode**: aggressive, with `idle_timeout_seconds: 3600`
- **Scheduler**: 1 concurrent request, chunked prefill (priority: context)
- **Memory guard**: `custom` tier, 52 GiB ceiling (effective 51.8 GiB, see above)
- **Usage history**: on (`usage.usage_history`), hourly per-model aggregates in `usage.sqlite3`

### Telemetry files

Both are written by the server after every request; neither stores prompts or responses.

- `stats.json` — all-time cumulative totals (overall and per model). Loaded at startup, saved periodically and at shutdown.
- `usage.sqlite3` — added in 0.7.0. One table, `model_usage_hourly`, keyed `(hour, model_id)`: requests, prompt/completion/cached tokens, prefill/generation/request seconds. Flushed every 5 s from a background thread, 400-day retention, WAL mode (`-wal`/`-shm` sidecars). Feeds the dashboard **Usage** tab. Toggle with `usage.usage_history` or `OMLX_USAGE_HISTORY`; disabling keeps the file. It does not replace `stats.json`.

## Directory Structure

Two model directories are scanned (`model.model_dirs` in `settings.json`): `base/models/` and `/Volumes/SSDSCX_DATA/LLM_SSD/models/omlx/`. Both hold a `spacecomx/` subfolder of served checkpoints.

```
base/
  bin/                  — omlx launcher script (+ omlx-cluster-python shim, gitignored)
  cache/                — KV cache blocks (gitignored)
  cluster/              — machine-specific cluster identity (never commit)
  logs/                 — Runtime logs (gitignored)
  models/spacecomx/     — Served weights (gitignored)
  model_profiles.json   — Per-model profile definitions
  model_settings.json   — Model-level defaults + active profile assignments
  settings.json         — Server configuration
  stats.json            — All-time usage totals (gitignored)
  usage.sqlite3[-wal|-shm] — Hourly usage history (never commit)
```

`~/.omlx` is a symlink to `base/`; `base/bin/omlx` resolves the base path from `~/Library/Application Support/oMLX/base-path` and delegates to `/Applications/oMLX.app/Contents/MacOS/omlx-cli`.

## Environment Variables

| Variable             | Effect                                                            |
| -------------------- | ----------------------------------------------------------------- |
| `OMLX_API_KEY`       | Overrides `auth.api_key` (configured: `local-bypass`, unverified) |
| `OMLX_USAGE_HISTORY` | Overrides `usage.usage_history`                                   |
| `OMLX_BASE_PATH`     | Overrides the base directory (set by `bin/omlx` from the bootstrap file) |

## Server Aliases

`localhost` · `127.0.0.1` · `spacestudio.local` · `192.168.10.99`

## Integrations

**Claude Code** runs in `local` mode with the opus/sonnet/haiku slots mapped to served model ids in `settings.json` (`claude_code.*_model`). Keep those ids in step with the inventory — a removed model leaves a dangling slot. The other integration slots (Codex, OpenCode, OpenClaw, Hermes, Pi, Copilot) are unset; those clients select models by id over the OpenAI-compatible API.

The `pi` client is configured in `pi-config/base/agent/models.json`; keep its `contextWindow` / `maxTokens` in step with the profiles above, or the client will pace its context against a budget the server will not honour.

**Markitdown**: enabled — PDF/file processing (25 MB max, 5 files per request).

## VS Code Custom Local Models

Substitute any served model id. `contextWindow` = `max_context_window + max_tokens` of the profile in use.

With authentication:

```json
[
  {
    "name": "oMLX",
    "vendor": "customendpoint",
    "apiKey": "${input:omlxApiKey}",
    "apiType": "chat-completions",
    "models": [
      {
        "id": "Qwen3.8-27B-oQ8e-fp16-mtp",
        "name": "Qwen3.8-27B",
        "url": "http://127.0.0.1:8055/v1/chat/completions",
        "apiType": "chat-completions",
        "toolCalling": true,
        "vision": false,
        "contextWindow": 147456,
        "maxInputTokens": 131072,
        "maxOutputTokens": 16384,
        "requestHeaders": { "Authorization": "Bearer ${apiKey}" }
      }
    ]
  }
]
```

Without authentication:

```json
[
  {
    "name": "oMLX",
    "vendor": "customendpoint",
    "apiType": "chat-completions",
    "models": [
      {
        "id": "Qwen3.8-27B-oQ8e-fp16-mtp",
        "name": "Qwen3.8-27B",
        "url": "http://127.0.0.1:8055/v1/chat/completions",
        "apiType": "chat-completions",
        "toolCalling": true,
        "vision": false,
        "contextWindow": 147456,
        "maxInputTokens": 131072,
        "maxOutputTokens": 16384
      }
    ]
  }
]
```
