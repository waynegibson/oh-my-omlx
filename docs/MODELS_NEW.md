Yes — oMLX's admin dashboard (`/admin`) has a built-in HuggingFace search/download panel, so you can paste these repo IDs directly instead of using `huggingface-cli`. Exact paths to pull:

| Tier                            | HF repo                                                  | Size     | Notes                                                                                                                       |
| ------------------------------- | -------------------------------------------------------- | -------- | --------------------------------------------------------------------------------------------------------------------------- |
| **Sonnet** (agentic coding)     | `mlx-community/Qwen3-Coder-Next-4bit`                    | ~40GB    | Primary pick                                                                                                                |
| **Sonnet-alt**                  | `lmstudio-community/GLM-4.7-Flash-MLX-8bit`              | ~35GB    | Strong tool-calling/agentic alt                                                                                             |
| **Haiku** (fast)                | `mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit`        | ~18GB    |                                                                                                                             |
| **Haiku-alt**                   | `mlx-community/GLM-4.7-Flash-4bit`                       | ~20GB    | Z.AI's own "fast tier"                                                                                                      |
| **Opus** (reasoning/coursework) | `andrzejmontano/Qwen3.5-122B-A10B-Vision-MLX-Mixed-2bit` | ~24-30GB | The mixed-quant build — do **not** grab the standard `mlx-community/Qwen3.5-122B-A10B-4bit`, that one's ~74GB and won't fit |
| **Opus-alt**                    | `mlx-community/DeepSeek-R1-Distill-Llama-70B-4bit`       | ~40GB    | Dense, MIT-licensed, solid math/reasoning fallback                                                                          |

**Skip for now:** `gpt-oss-120b` — every quant sits at 65-66GB, which is over your usable headroom once macOS overhead is subtracted. Not worth the download until/unless you're testing on a bigger machine.

**Suggested order:** start with `Qwen3-Coder-Next-4bit` (Sonnet) since that's your primary agentic-coding need, verify tool-calling works cleanly in oMLX, then pull the Opus-tier reasoning model, then the Haiku fast model last since it's the least critical.

Want me to also pull down the exact `omlx serve` CLI commands (model-dir naming, memory-guard flags) tuned to load these back-to-back for testing, given you're going one-model-at-a-time?

API_KEY-OLD: sk-omlx-kqIDznUDT53avkK3GBAMKGiA
API_KEY-NEW: sk-omlx-zMYzqyi6EoJpejIwZkTPpRcQ

          "max_context_window": 65536,
          "max_tokens": 16384,

mlx-community/Qwen3-Coder-Next-4bit
lmstudio-community/GLM-4.7-Flash-MLX-8bit
mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit
mlx-community/GLM-4.7-Flash-4bit
andrzejmontano/Qwen3.5-122B-A10B-Vision-MLX-Mixed-2bit
mlx-community/DeepSeek-R1-Distill-Llama-70B-4bit

Please provide the exact and correct oMLX configuration for each of the below models. I have provided the configuration file "model_profiles.json" for the model "mlx-community/Qwen3-Coder-Next-4bit" that I setup initially with OMLX using your suggested configuration. You can use it as a reference to configure the models below. Make sure that the configuration is compatible with oMLX and includes all necessary parameters for optimal performance.

1. lmstudio-community/GLM-4.7-Flash-MLX-8bit
2. mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit
3. mlx-community/GLM-4.7-Flash-4bit
4. andrzejmontano/Qwen3.5-122B-A10B-Vision-MLX-Mixed-2bit
5. mlx-community/DeepSeek-R1-Distill-Llama-70B-4bit

google/gemma-4-E4B-it

lmstudio-community/Qwen3-VL-4B-Instruct-MLX-4bit - no
lmstudio-community/Qwen3-VL-4B-Instruct-MLX-8bit - no
lmstudio-community/Qwen3-VL-8B-Instruct-MLX-8bit - no
lmstudio-community/Qwen3-VL-32B-Instruct-MLX-6bit - yes
lmstudio-community/Qwen3-VL-32B-Instruct-MLX-8bit - no

mlx-community/Qwen3.6-35B-A3B-4bit
mlx-community/Qwen3.6-35B-A3B-6bit

Fetched 2 resources

Fetched 2 resources

Now I have everything needed. Here's the analysis:

---

## Model Facts (Qwen3-35B-A3B)

This is a **MoE model**: 35B total parameters, **only 3B active** per forward pass. At 6-bit quantization:

- Model weights: ~26 GB
- macOS overhead: ~8–10 GB
- Available for KV cache + activations: **~28–30 GB**

Native context: **128K tokens**. Official recommended context for local inference: **40960 (40K)**.

---

## What's Wrong in Your Current Settings

### The Freeze Root Cause

Both `max_context_window` and `max_tokens` are set to **65536**. oMLX pre-allocates KV cache at startup based on context window size. At 65K context + 65K output budget, the combined allocation (~131K token buffer) can exhaust 64GB RAM before a single token is generated — especially with `enable_thinking: true`.

### Per-Profile Issues

| Setting              | Profile  | Current | Problem                                  | Official Recommendation             |
| -------------------- | -------- | ------- | ---------------------------------------- | ----------------------------------- |
| `max_context_window` | all      | 65536   | RAM exhaustion at startup                | 32768–40960                         |
| `max_tokens`         | all      | 65536   | Massively oversized output buffer        | 32768 (thinking) / 16384 (instruct) |
| `temperature`        | general  | 1.0     | Too high — erratic outputs               | 0.7                                 |
| `repetition_penalty` | general  | 1.5     | Very aggressive — causes degenerate text | 1.0                                 |
| `presence_penalty`   | instruct | 1.5     | Very high — Qwen3 doesn't recommend this | 0                                   |
| `presence_penalty`   | general  | 1.0     | Not recommended by Qwen3 team            | 0                                   |

---

## Optimal Settings for M1 Max 64GB

Official Qwen3 sampling params (from `llama.cpp` and `mlx-lm` docs):
`--temp 0.6 --top-k 20 --top-p 0.95 --min-p 0 -c 40960 -n 32768`

**general** (thinking mode — for reasoning/quiz tasks):

```json
"temperature": 0.7,
"top_k": 20,
"top_p": 0.95,
"min_p": 0,
"presence_penalty": 0,
"repetition_penalty": 1.0,
"max_context_window": 32768,
"max_tokens": 16384,
"thinking_budget_tokens": 4096,
"enable_thinking": true
```

**coder** (already mostly correct):

```json
"temperature": 0.6,
"top_k": 20,
"top_p": 0.95,
"min_p": 0,
"presence_penalty": 0,
"repetition_penalty": 1.0,
"max_context_window": 32768,
"max_tokens": 16384,
"enable_thinking": true
```

**instruct** (non-thinking, fast responses):

```json
"temperature": 0.7,
"top_k": 20,
"top_p": 0.8,
"min_p": 0,
"presence_penalty": 0,
"repetition_penalty": 1.0,
"max_context_window": 32768,
"max_tokens": 8192,
"enable_thinking": false
```

---

## Key Tradeoffs to Know

| Context Window | RAM Pressure      | Use When                                                       |
| -------------- | ----------------- | -------------------------------------------------------------- |
| 32768 (32K)    | Low — stable      | Daily use, quiz assistant, most tasks                          |
| 40960 (40K)    | Moderate          | Longer documents, if stable                                    |
| 65536 (64K)    | High — may freeze | Only if you need very long context and nothing else is running |

For your quiz assistant use case (short system prompt + exam question), **32K context is more than sufficient** and will run without freezing. The `thinking_budget_tokens` of 4096 is plenty for exam-style reasoning — you don't need 8192 unless doing multi-step math proofs.
