# oMLX Configuration & Admin UI — Research Findings

Source: direct reading of the `jundot/omlx` GitHub repository (`omlx/settings.py`, `omlx/config.py`,
`omlx/model_settings.py`, `omlx/model_profiles.py`, `omlx/model_registry.py`, `omlx/model_discovery.py`,
`omlx/admin/routes.py`, `omlx/admin/templates/`, `omlx/engine/`, and `tests/test_model_settings_profiles.py`),
cross-checked against the live `~/.omlx/settings.json` on this machine. Compiled 2026-07-08.

## Correction to initial assumption

Despite docstrings in both `settings.py` and `config.py` claiming "Pydantic validation," **neither file uses
Pydantic**. Every schema in this codebase (`settings.py`, `config.py`, `model_settings.py`, `model_profiles.py`)
is a plain stdlib `@dataclass`. There are no `Enum` classes, no `@validator`/`@field_validator` decorators.
Validation is done via hand-written `.validate() -> list[str]` methods that return error strings (not raised,
not auto-invoked). The one Pydantic model in the whole surface is `ModelSettingsRequest` in
`omlx/admin/routes.py` (the FastAPI request body for `PUT /admin/api/models/{id}/settings`).

## 1. `omlx/settings.py` — persisted to `~/.omlx/settings.json`

**Base path resolution** (`resolve_default_base_path()`): `OMLX_BASE_PATH` env var → macOS app's bootstrap
file (`~/Library/Application Support/oMLX/base-path`) → `~/.omlx`. Settings file is always
`{base_path}/settings.json`.

**Module constants:**
```python
SETTINGS_VERSION = "1.0"
DEFAULT_BASE_PATH = Path.home() / ".omlx"
BURST_DECODE_MODES = {"off": (1, 0.0), "light": (64, 0.05), "balanced": (64, 0.1), "aggressive": (64, 0.2)}
DEFAULT_BURST_DECODE_MODE = "balanced"
MemoryGuardTier = Literal["safe", "balanced", "aggressive", "custom"]
```

The live settings.json's 16 sections are confirmed exact and complete — `GlobalSettings` has exactly these
fields, in this order: `base_path, server, model, memory, scheduler, cache, auth, mcp, huggingface,
modelscope, network, sampling, logging, claude_code, integrations, ui, idle_timeout`. Nothing missing,
nothing extra.

### `ServerSettings` (`server`)
| field | type | default | purpose |
|---|---|---|---|
| `host` | str | `"127.0.0.1"` | bind address; UI offers localhost / public (`0.0.0.0`) / custom |
| `port` | int | `8000` | bind port |
| `log_level` | str | `"info"` | enum: `error, warning, info, debug, trace` |
| `cors_origins` | list[str] | `["*"]` | CORS allowlist |
| `server_aliases` | list[str] | `[]` | extra hostnames server trusts |
| `sse_keepalive_mode` | str | `"chunk"` | enum: `chunk, comment, off` — SSE stream keepalive strategy |
| `auto_start_on_launch` | bool | `True` | macOS app auto-start |
| `burst_decode_mode` | str | `"balanced"` | enum: `off, light, balanced, aggressive` — maps to `OMLX_DECODE_BURST_MAX_STEPS` / `OMLX_DECODE_BURST_BUDGET_SINGLE_S` env vars consumed by `EngineConfig`; controls how many decode steps coalesce per event-loop hand-off |
| `preserve_mid_system_cache` | bool | `True` | prefix-cache behavior around mid-conversation system messages |

`from_dict` migrates legacy `bind_address` → `host`.

### `ModelSettings` (`model`) — global model-directory config, NOT per-model settings
| field | type | default | purpose |
|---|---|---|---|
| `model_dirs` | list[str] | `[]` | scanned model directories; `[]` means `~/.omlx/models` |
| `model_dir` | str\|None | `None` | deprecated singular form, migrated into `model_dirs` |
| `model_fallback` | bool | `False` | serve default model if requested model_id not found |

### `SchedulerSettings` (`scheduler`)
| field | type | default | purpose |
|---|---|---|---|
| `max_concurrent_requests` | int | `8` | continuous-batching concurrency cap (migrated from legacy `max_num_seqs`/`completion_batch_size`) |
| `embedding_batch_size` | int | `32` | batch size for embedding requests |
| `chunked_prefill` | bool | `False` | interleave long prefills with decode steps — lowers TTFT for concurrent requests at some per-step overhead cost |

### `CacheSettings` (`cache`)
| field | type | default | purpose |
|---|---|---|---|
| `enabled` | bool | `True` | master cache toggle |
| `hot_cache_only` | bool | `False` | disable SSD paged cache tier, RAM only |
| `ssd_cache_dir` | str\|None | `None` | `None` → `{base_path}/cache` |
| `ssd_cache_max_size` | str | `"auto"` | `"auto"` = 10% of disk capacity; else `parse_size()` string like `"100GB"` |
| `hot_cache_max_size` | str | `"0"` | `"0"` disables in-RAM hot cache; else e.g. `"8GB"` |
| `initial_cache_blocks` | int | `256` | starting paged-cache block count (grows dynamically) |

### `MemorySettings` (`memory`)
| field | type | default | purpose |
|---|---|---|---|
| `prefill_memory_guard` | bool | `True` | enables prefill memory estimation + admission deferral |
| `memory_guard_tier` | enum | `"balanced"` | `safe \| balanced \| aggressive \| custom` — reclaim-ratio tier |
| `memory_guard_custom_ceiling_gb` | float | `0.0` | only used when tier=`custom`; `0` = unset |
| `soft_threshold` | float | `0.85` | triggers admission pause + LRU eviction |
| `hard_threshold` | float | `0.95` | triggers in-flight request abort |
| `prefill_safe_zone_ratio` | float | `0.80` | adaptive prefill chunk-size throttle ratio |
| `prefill_min_chunk_tokens` | int | `32` | minimum prefill chunk before aborting instead |

### `ModelIdleTimeoutSettings` (`idle_timeout`)
| field | type | default | purpose |
|---|---|---|---|
| `idle_timeout_seconds` | int\|None | `None` | global auto-unload timer; UI dropdown offers None/15m/30m/1h/2h/8h/24h |

### `AuthSettings` (`auth`) — includes nested `SubKeyEntry`
| field | type | default | purpose |
|---|---|---|---|
| `api_key` | str\|None | `None` | primary bearer key (`sk-omlx-...`) |
| `secret_key` | str\|None | `None` | internal signing secret |
| `skip_api_key_verification` | bool | `False` | disables auth entirely (UI warns if `host != 127.0.0.1`) |
| `sub_keys` | list[SubKeyEntry] | `[]` | additional scoped API-only keys; `SubKeyEntry{key, name="", created_at=""}` |

### `MCPSettings` (`mcp`)
| field | type | default | purpose |
|---|---|---|---|
| `config_path` | str\|None | `None` | path to an MCP server config file |

### `HuggingFaceSettings` (`huggingface`) / `ModelScopeSettings` (`modelscope`)
| field | type | default | purpose |
|---|---|---|---|
| `huggingface.endpoint` | str | `""` | custom HF mirror endpoint |
| `huggingface.hf_cache_enabled` | bool | `True` | reuse existing `~/.cache/huggingface` snapshots |
| `modelscope.endpoint` | str | `""` | custom ModelScope mirror |

### `NetworkSettings` (`network`)
`http_proxy`, `https_proxy`, `no_proxy`, `ca_bundle` — all `str`, default `""`.

### `SamplingSettings` (`sampling`) — global generation defaults
| field | type | default | purpose |
|---|---|---|---|
| `max_context_window` | int | `32768` | fallback context length when no per-model/discovered value exists |
| `max_context_window_policy` | int\|None | `None` | operator hard cap: effective context = `min(native, policy)` |
| `max_tokens` | int | `32768` | default max generation tokens |
| `temperature` | float | `1.0` | |
| `top_p` | float | `0.95` | |
| `top_k` | int | `0` | `0` = disabled |
| `repetition_penalty` | float | `1.0` | `1.0` = disabled |

### `LoggingSettings` (`logging`)
`log_dir` (str\|None, default `None` → `{base_path}/logs`), `retention_days` (int, default `7`).

### `UISettings` (`ui`)
`language` (str, default `"en"`) — enum from UI: `en, zh, zh-TW, ko, ja, ru, es, fr, pt-BR`.

### `ClaudeCodeSettings` (`claude_code`)
| field | type | default | purpose |
|---|---|---|---|
| `context_scaling_enabled` | bool | `False` | rescale Claude Code's context window expectations to fit local model |
| `target_context_size` | int | `200000` | Claude Code's native 200k assumption |
| `mode` | str | `"cloud"` | `cloud` (native claude.ai) vs `local` (route through omlx) — live `settings.json` on this machine shows `"local"` |
| `opus_model` / `sonnet_model` / `haiku_model` | str\|None | `None` | per-tier local model mapping, populated from loaded LLM list |

### `IntegrationSettings` (`integrations`)
| field | type | default | purpose |
|---|---|---|---|
| `codex_model`, `opencode_model`, `openclaw_model`, `hermes_model`, `pi_model`, `copilot_model` | str\|None | `None` | per-tool local model routing, same pattern as Claude Code |
| `openclaw_tools_profile` | str | `"coding"` | tool profile for OpenClaw integration |
| `markitdown_enabled` | bool | `True` | enable PDF/DOCX/PPTX → text conversion |
| `markitdown_expose_model` | bool | `False` | expose MarkItDown as a virtual `/v1/models` entry |
| `markitdown_max_file_size_mb` | int | `25` | |
| `markitdown_max_files_per_request` | int | `5` | |
| `markitdown_pdf_processing_engine` | str | `"markitdown"` | `"markitdown"` or an OCR-capable model ID from the loaded model list |

### Load/save mechanics
- Precedence: **file < env (`OMLX_*`, ~25 vars) < CLI args.**
- `_load_from_file`: missing sections keep defaults; corrupt JSON is caught, logged, and silently falls back
  to defaults (does not raise).
- `save()`: plain `json.dump(..., indent=2)` — **not atomic** (no temp-file+rename, unlike
  model_settings.py/model_profiles.py which are atomic).
- Singleton access: `init_settings()` / `get_settings()` (raises `RuntimeError` if uninitialized) /
  `reset_settings()` (test-only).

## 2. `omlx/config.py` — legacy/parallel config system, NOT what backs settings.json

This file also claims "Pydantic" in its docstring but is pure dataclasses. It defines `ServerConfig`,
`ModelConfig`, `GenerationConfig`, a `SchedulerConfig` (name-collides with, and is unrelated to, the real
`omlx/scheduler.py` one), `CacheConfig` (empty/deprecated), `PagedSSDCacheConfig`, `MCPConfig`, aggregated
into `OMLXConfig` with `from_env()`/`from_cli_args()`/`to_dict()`/`validate()`. It reads `OMLX_HOST`,
`OMLX_PORT`, `OMLX_MODEL`, `OMLX_TRUST_REMOTE_CODE`, `OMLX_MAX_TOKENS`, `OMLX_TEMPERATURE`,
`OMLX_PAGED_SSD_CACHE_DIR`, `OMLX_MCP_CONFIG`, etc.

**The only thing `settings.py` actually imports from `config.py` is the `parse_size()` helper.**
`OMLXConfig` and its dataclasses are not instantiated anywhere in `settings.py`, `cli.py`, `server.py`, or
`engine_core.py`. Defaults sometimes diverge (config.py's `host="0.0.0.0"` vs settings.py's `"127.0.0.1"`).
Treat `config.py` as a largely superseded parallel system — not the active constants layer for
`~/.omlx/settings.json`.

## 3. `omlx/model_settings.py` — persisted to `~/.omlx/model_settings.json`

The `ModelSettings` dataclass is the per-model schema (this is what the "Model Settings" gear icon in the
admin UI edits):

**Sampling overrides** (all `Optional`, `None` = inherit global default): `max_context_window`, `max_tokens`,
`temperature`, `top_p`, `top_k`, `repetition_penalty`, `min_p`, `presence_penalty`, `force_sampling` (bool,
default `False` — forces sampling even at temperature=0), `max_tool_result_tokens`.

**Chat template / thinking**: `chat_template_kwargs` (dict, extra kwargs passed to the tokenizer's chat
template — e.g. `{"enable_thinking": true, "reasoning_effort": "low"}`), `forced_ct_kwargs` (list[str], keys
that cannot be overridden by API requests — the UI's "Force" checkbox per kwarg entry), `enable_thinking`
(`Optional[bool]`, `None` = auto), `preserve_thinking` (`Optional[bool]` — keep `<think>` blocks across
turns, Qwen 3.6+), `thinking_budget_enabled` (bool), `thinking_budget_tokens` (`Optional[int]`),
`reasoning_parser` (`Optional[str]` — xgrammar builtin: `"qwen"`, `"harmony"`, `"llama"`, etc.),
`guided_grammar_enabled`/`guided_grammar` (EBNF constrained decoding).

**Identity/management** (excluded from profiles/templates): `ttl_seconds` (`Optional[int]`, auto-unload
after idle seconds, disabled while `is_pinned`), `model_type_override` (`Optional[str]`:
`"llm"|"vlm"|"embedding"|"reranker"|"audio_stt"|"audio_tts"|"audio_sts"`, `None` = auto-detect),
`model_alias` (`Optional[str]`, API-visible alternative name), `is_pinned` (bool — keeps model resident;
multiple models can be pinned), `is_default` (bool — exactly one model can be default, enforced by
manager), `trust_remote_code` (bool, security opt-in), `display_name`, `description`,
`active_profile_name`.

**Experimental/speculative-decoding** (model-specific, engine-construction fields): `index_cache_freq`
(DeepSeek DSA IndexCache); TurboQuant KV (`turboquant_kv_enabled`, `turboquant_kv_bits`: 2/2.5/3/3.5/4/6/8,
`turboquant_skip_last`); SpecPrefill (`specprefill_enabled`, `specprefill_draft_model`,
`specprefill_keep_pct` 0.1–0.5, `specprefill_threshold`); DFlash (`dflash_enabled`, `dflash_draft_model`,
quant sub-fields, `dflash_max_ctx`, in-memory/SSD L1/L2 cache knobs, `dflash_draft_window_size`,
`dflash_draft_sink_size`, `dflash_verify_mode`: `dflash|adaptive|ddtree|off`); native MTP (`mtp_enabled`,
`mtp_num_draft_tokens`); VLM MTP (`vlm_mtp_enabled`, `vlm_mtp_draft_model`, `vlm_mtp_draft_block_size`).

`__post_init__` raises `ValueError` for mutually-exclusive combos (mtp vs dflash vs turboquant vs vlm_mtp —
only one speculative-decoding path per model). `to_dict()` drops `None`-valued fields only (zero/False
survive, so e.g. `temperature=0.0` round-trips correctly).

**`ModelSettingsManager`** — persists three sibling files under `base_path` (i.e. `~/.omlx/`):
```python
self.settings_file  = base_path / "model_settings.json"
self.profiles_file  = base_path / "model_profiles.json"
self.templates_file = base_path / "global_templates.json"
```
All three use atomic writes (temp file + `Path.replace()`), unlike `settings.json`. Format:
`{"version": 1, "models": {model_id: {...ModelSettings.to_dict()...}}}`.

Manager also implements the exclusive-`is_default` constraint, `get_pinned_model_ids()`, and cascading
`delete_settings()` (removes both settings and any profiles when a model is deleted, freeing its alias for
reuse).

## 4. `omlx/model_profiles.py` — schema + field allowlists for Profiles/Templates

Defines three field tiers used to filter what can go into a profile vs a template:

- **`UNIVERSAL_PROFILE_FIELDS`** (19 fields — eligible for BOTH templates and profiles):
  `max_context_window, max_tokens, temperature, top_p, top_k, min_p, repetition_penalty,
  presence_penalty, force_sampling, enable_thinking, preserve_thinking, thinking_budget_enabled,
  thinking_budget_tokens, reasoning_parser, guided_grammar_enabled, guided_grammar,
  max_tool_result_tokens, chat_template_kwargs, forced_ct_kwargs`
- **`MODEL_SPECIFIC_PROFILE_FIELDS`** (24 fields — profiles ONLY, never templates): all the
  turboquant/dflash/mtp/vlm_mtp/specprefill/`index_cache_freq` fields
- **`EXCLUDED_FROM_PROFILES`** (never in either): `is_pinned, is_default, display_name, description,
  model_alias, model_type_override, active_profile_name, ttl_seconds, trust_remote_code`

```python
@dataclass
class ModelProfile:
    name: str; display_name: str; created_at: datetime; updated_at: datetime
    api_name: str | None = None
    settings: dict[str, Any] = field(default_factory=dict)
    description: str | None = None
    source_template: str | None = None   # tracks which template it was seeded from

@dataclass
class GlobalTemplate:
    name: str; display_name: str; created_at: datetime; updated_at: datetime
    settings: dict[str, Any] = field(default_factory=dict)
    description: str | None = None
```

**Note:** both dataclasses exist but `ModelSettingsManager` actually stores/manipulates profiles and
templates as plain dicts, never instantiating these classes directly — they mainly document the intended
shape.

**Profile name validation**: `^[a-z0-9][a-z0-9_-]{0,31}$` (1–32 chars, slug).
`slugify_profile_api_name()` derives an API-safe name from a display name (NFKD → ASCII-fold → lowercase →
strip → truncate 32 → fallback `"profile"`).

**Storage format** (`model_profiles.json`):
```json
{"version": 1, "profiles": {"<model_id>": {"<profile_name>": {
  "name": "...", "display_name": "...", "api_name": "...",
  "description": "...", "created_at": "...", "updated_at": "...",
  "settings": {"...universal+model-specific fields..."},
  "source_template": null, "expose_as_model": false
}}}}
```
Note `expose_as_model` is a real field but is added dynamically by `ModelSettingsManager.save_profile()` /
`update_profile()` — it isn't declared on the `ModelProfile` dataclass itself.

**`global_templates.json`**: `{"version": 1, "templates": {"<name>": {"name", "display_name",
"description", "created_at", "updated_at", "settings"}}}` — universal fields only. The file is created
lazily; if you have zero user-created templates, the file does not exist (confirmed by
`tests/test_model_settings_profiles.py::test_no_file_created_when_empty`). A code comment claims a bundled
`omlx/default_global_templates.json` seeds built-ins at read-time, but `TestTemplatesCRUD` /
`TestTemplatesPersistence` show this was **retired** — `list_templates()` returns purely user-created
entries now, no `is_builtin` flag. The **"Preset" scope** in the model-settings modal (separate from
"Global"/Template scope) is a *third*, read-only tier sourced from a static client-side JSON bundle at
`omlx/admin/static/omlx_preset.json` (curated per-model-family sampling recipes like `qwen3-r-general`,
`gemma4`, `minimax-m27`), fetched fresh via `POST /admin/api/presets/refresh`.

### `<model>:<profile>` resolution (the README-documented naming)

Lives entirely in `ModelSettingsManager` (not in `model_registry.py` — that file is unrelated, see below).
`_profile_model_id()` builds `f"{model_id}:{api_name}"` (not a literal split — candidate strings are
constructed and compared for equality against both the model's directory name and its `model_alias`). Only
profiles with `expose_as_model: true` are matched.

Two distinct overlay paths:
- `get_settings_for_request()` — non-persisting, **universal fields only**, used for ordinary per-request
  sampling overlay.
- `get_exposed_profile_runtime_settings_for_request()` — non-persisting, **includes model-specific engine
  fields** (dflash/mtp/etc.), used to trigger a transient engine-variant reload for an exposed profile,
  without ever mutating the base model's saved `model_settings.json`.
- `apply_profile()` — the **persisting** variant, invoked from the admin UI's "Apply" action: merges into
  the model's live settings, sets `active_profile_name`, saves to disk, with rollback-on-failure via a
  `copy.deepcopy` snapshot.

## 5. `omlx/model_registry.py` and `omlx/model_discovery.py`

**Correction to the initial assumption:** `model_registry.py` is **not** a model catalog. It's a small
singleton (`ModelRegistry`) that tracks which `EngineCore` instance currently "owns" a loaded MLX model
object (via `id(model)` + weakref), solely to prevent `BatchKVCache` conflicts when the same model is
shared across engines. No model-type or config fields live there.

The actual type system is in `model_discovery.py`:
```python
ModelType  = Literal["llm", "vlm", "embedding", "reranker", "audio_stt", "audio_tts", "audio_sts"]
EngineType = Literal["batched", "vlm", "embedding", "reranker", "audio_stt", "audio_tts", "audio_sts"]

@dataclass
class DiscoveredModel:
    model_id: str
    model_path: str
    model_type: ModelType
    engine_type: EngineType
    estimated_size: int
    config_model_type: str = ""       # raw HF config.json "model_type" (e.g. "deepseekocr_2")
    thinking_default: bool | None = None
    preserve_thinking_default: bool | None = None
    model_context_length: int | None = None
    source_type: str = "local"        # "local" or "hf_cache"
    source_repo_id: str | None = None
```
Type detection cascades through several heuristics: `config.json` `architectures`/`model_type` fields,
directory-name substring matching for CausalLM-based rerankers/embeddings (e.g. dirs containing
"reranker"/"embed"), and `modules.json` inspection for sentence-transformers pipelines. There's also an
`_is_unsupported_model()` gate that skips known-incompatible architectures. OCR models are not a separate
`ModelType` — they show up via `config_model_type` (raw string) while `model_type` normalizes to `vlm` or
similar.

## 6. `omlx/admin/routes.py` — full route map (85 routes, all under `/admin` prefix)

Single file, ~6,362 lines, `router = APIRouter(prefix="/admin")`. No dedicated MCP routes — MCP is just the
`mcp.config_path` field inside the general global-settings GET/POST.

**Pages:** `GET /`, `GET /dashboard`, `GET /chat`, `GET /static/{path}`
**Auth:** `POST /api/login`, `/api/setup-api-key`, `/api/logout`, `GET /auto-login`, `POST/DELETE /api/sub-keys`
**Models:** `GET /api/models`, `POST /api/models/{id}/unload`, `/load`, `POST /api/reload`
**Model settings:** `PUT /api/models/{id}/settings` (backed by `ModelSettingsRequest`, ~45 fields matching
`ModelSettings` 1:1), `GET /api/models/{id}/generation_config`
**Profiles:** `GET/POST /api/models/{id}/profiles`, `PUT/DELETE .../profiles/{name}`,
`POST .../profiles/{name}/apply`, `GET /api/profile-fields`
**Templates:** `GET/POST /api/profile-templates`, `PUT/DELETE /api/profile-templates/{name}`
**Presets:** `POST /api/presets/refresh`
**Server:** `GET /api/server-info`, `POST /api/server/restart`
**Global settings:** `GET/POST /api/global-settings` (the POST handler is ~680 lines covering every
settings.py section)
**Logs/Stats:** `GET /api/logs`, `/api/stats`, `POST /api/stats/clear[-alltime]`
**Cache:** `POST /api/ssd-cache/clear`, `/api/hot-cache/clear`, `/api/cache/probe`
**HF downloader:** `/api/hf/download|tasks|cancel|retry|task|recommended|search|model-info|models`
**ModelScope downloader:** `/api/ms/status|download|tasks|cancel|retry|task|recommended|search|model-info`
**Benchmark (accuracy + throughput):** `/api/bench/accuracy/*`, `/api/bench/*` (SSE streaming for both)
**Other:** `/api/device-info`, `/api/update-check`, oQ quantizer `/api/oq/*`, uploader `/api/upload/*`

The `ModelSettingsRequest` Pydantic body (lines ~101–160 of routes.py) mirrors `ModelSettings` field-for-field,
confirming there's no drift between the API contract and the persisted dataclass.

## 7. Admin UI menu/submenu structure (Alpine.js SPA, one `dashboard()` component)

```
Status | Models ▾ | Settings ▾ | Logs | Bench ▾ | Chat
```

- **Status** — no submenu. Contains: Speed/throughput cards, Active Models, API info, **Claude Code
  section** (mode toggle cloud/local, per-tier Opus/Sonnet/Haiku model pickers, context-scaling
  toggle+target size — this is where `claude_code.*` settings actually live in the UI, not under Settings),
  Integrations/Applications card (codex/opencode/openclaw/hermes/pi/copilot pickers), Engines section.
- **Models ▾** → Manager (list/load/unload/delete/reload local models), Downloader (HF + ModelScope
  search/download/queue), Quantizer (oQ on-device quantization), Uploader (push quantized models back to
  HF/MS).
- **Settings ▾** → three sub-tabs:
  - **Global**: Language, Auth & Info (API key, skip-verification toggle, Sub Keys CRUD), Server
    (host/port/log_level), Model (fallback toggle, model_dirs list, HF cache toggle), Memory Management
    (prefill_memory_guard + tier + custom ceiling, hot-cache-size slider, SSD-cache-size slider,
    max_concurrent_requests, embedding_batch_size, chunked_prefill, idle_timeout dropdown), Cache (enabled,
    hot_cache_only, ssd_cache_dir), Sampling Defaults (all `sampling.*` fields), MCP (config_path,
    restart-required badge), Network (proxy/CA bundle), Advanced collapsible (burst_decode_mode,
    preserve_mid_system_cache, initial_cache_blocks, sse_keepalive_mode).
  - **Models** (per-model settings table + gear-icon modal): sortable table with pin/default/status
    toggles, chip badges showing active per-field overrides, and the **Model Settings modal** — this is the
    single richest surface, covering Basic (alias, model_type_override, reasoning_parser,
    ctx/tokens/temperature/top_p/top_k/min_p/rep_penalty/presence_penalty, TTL) and Advanced (thinking
    toggle+budget, guided grammar, tool-result token limit, force_sampling, trust_remote_code,
    chat_template_kwargs editor with per-kwarg Force checkbox, then an Experimental section: TurboQuant KV,
    IndexCache (DSA models only), SpecPrefill, DFlash (with nested quant/cache/long-context sub-panels),
    native MTP, VLM MTP) — plus the three-scope Profiles/Templates/Presets picker at the top
    (Preset=read-only curated bundle, Global=user templates, Model=per-model profiles with API-expose
    toggle).
  - **Integrations**: MarkItDown (enabled, expose-as-model, max file size/count, PDF engine picker).
- **Logs** — no submenu, plain log viewer/filter.
- **Bench ▾** → Performance (throughput benchmarking, SSE live results) and Accuracy (eval-suite queue +
  results).
- **Chat** — full-page link (not an SPA tab) to a standalone playground at `/admin/chat`.

Templates directory: `omlx/admin/templates/` = `base.html`, `chat.html`, `dashboard.html`, `login.html`,
`dashboard/` (`_navbar.html`, `_status.html`, `_settings.html`, `_models.html`, `_logs.html`, `_bench.html`,
`_bench_accuracy.html`, `_modal_model_settings.html`). `dashboard.html` extends `base.html` and includes the
partials in that order.

## 8. `omlx/engine/` — engines take settings as constructor args, no separate config files

`base.py` (`BaseEngine` abstract class), `batched.py` (`BatchedEngine` — continuous batching for text LLMs,
wraps `AsyncEngineCore`), `vlm.py`, `embedding.py`, `reranker.py`, plus `dflash.py`, `sts.py`, `stt.py`,
`tts.py`, `audio_utils.py`. None persist their own config files — each engine's `__init__` accepts
`model_settings: ModelSettings | None` (the per-model dataclass from `model_settings.py`) plus a shared
`scheduler_config`, so all engine-specific behavior (DFlash, MTP, TurboQuant, SpecPrefill, etc.) is driven
entirely by the `ModelSettings` fields documented above — there is no
`BatchedEngineConfig`/`VLMEngineConfig` class hierarchy.

## Summary: files under `~/.omlx/`

| File | Written by | Contents |
|---|---|---|
| `settings.json` | `GlobalSettings.save()` | global server/model/memory/scheduler/cache/auth/mcp/hf/modelscope/network/sampling/logging/claude_code/integrations/ui/idle_timeout — 16 sections, non-atomic write |
| `model_settings.json` | `ModelSettingsManager._save()` | `{"version": 1, "models": {model_id: ModelSettings}}` — atomic write |
| `model_profiles.json` | `ModelSettingsManager._save_profiles()` | `{"version": 1, "profiles": {model_id: {profile_name: {...}}}}` — atomic write |
| `global_templates.json` | `ModelSettingsManager._save_templates()` | `{"version": 1, "templates": {name: {...}}}` — atomic write, created lazily (absent until first user template) |
| `models/` | model downloader | local model directory tree, scanned by `model_discovery.py` |
| `cache/` | paged SSD cache | `_boundary_snapshots/`, `response-state/` subdirs |
| `logs/` | logging | default log dir when `logging.log_dir` unset |

Live `~/.omlx/settings.json` on this machine was cross-checked field-by-field against the source and
matches exactly with no drift; `model_settings.json`, `model_profiles.json`, and `global_templates.json`
don't exist yet on this machine since no per-model settings, profiles, or templates have been customized —
they'll be created automatically (atomically) the first time a model's gear-icon settings modal is saved,
or a profile/template is created.
