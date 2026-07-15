# Model Guide — Ranked Lineup for M1 Max / 64 GB

**Date:** 2026-07-02 · Ranked per category. "Speed feel" is relative decode speed on this hardware (memory-bandwidth-bound; MoE ≫ dense).

## Coding

| Rank | Model | Size | Speed feel | When to use it | Notes |
|------|-------|------|------------|----------------|-------|
| 1 | **Qwopus3.6-35B-A3B-Coder-6bit** | 29.1 GB | ★★★★★ (MoE, ~3B active) | **Daily driver.** Claude Code sessions, refactors, everyday coding. Start here for everything. | MTP head ✓ — use MTP only, TurboQuant off |
| 2 | **Qwopus3.6-27B-Coder-8bit** *(installed)* | 27 GB | ★★☆☆☆ (dense) | **Hard problems only.** When #1 gets stuck or produces sloppy logic — tricky algorithms, subtle bugs, architecture decisions. Quality ceiling of the lineup. | MTP head ✓ — already configured |
| 3 | **Qwen-AgentWorld-35B-A3B-oQ4** | 20.4 GB | ★★★★★ (MoE) | **Tool-heavy agent runs.** Long autonomous sessions where tool-call reliability matters more than code elegance (file ops, shell work, multi-step automation). | MTP head ✓ · text-only |
| 4 | **gemma-4-12b-coder-fable5-composer2.5-8bit** | 12.7 GB | ★★★★☆ (small dense) | **Quick hits.** One-file edits, boilerplate, explaining code, or when you want RAM free for other apps. | **No MTP** — configure with TurboQuant instead |

## General

| Rank | Model | Size | Speed feel | When to use it | Notes |
|------|-------|------|------------|----------------|-------|
| 1 | **Qwen3.6-35B-A3B-6bit** *(installed)* | 27 GB | ★★★★★ (MoE) | **Default for everything non-code.** Writing, Q&A, summarizing, brainstorming, image understanding. | MTP head ✓ — already configured |
| 2 | **gemma-4-31B-it-OptiQ-4bit** | 23.5 GB | ★★☆☆☆ (dense) | **Second opinion & careful writing.** Different model family = different blind spots. Use when #1's answer feels off, or for polished long-form writing. Strong vision. | **No MTP** — configure with TurboQuant instead |
| 3 | **gemma-4-26B-A4B-it-OptiQ-4bit** | 18.8 GB | ★★★★☆ (MoE) | Optional. Faster Gemma if #2 feels too slow. Skippable — overlaps heavily with #1. | No MTP |

## Rules of thumb (while you're learning)

1. **MoE beats dense for speed** on Apple Silicon: only active parameters are read per token. Dense 27-31B models will always feel slow here regardless of quantization.
2. **One model hot at a time.** Two ~27 GB models resident together ≈ 54 GB — right at the memory ceiling. The 300 s idle timeout unloads the inactive one; don't pin multiple large models.
3. **One speculative path per model** — omlx rejects the whole settings entry otherwise (check `server.log` for "Failed to load settings"). Qwen3.6/Qwopus family: `mtp_enabled: true` only (no D-Flash, no TurboQuant, no vlm_mtp). Gemma family (no MTP head): `turboquant_kv_enabled: true` only.
4. **Start at rank 1, escalate on failure.** Speed compounds over a session; quality only matters when the fast model actually fails.
5. Total lineup ≈ 131 GB on disk if you download everything — fine on the 1 TB SSD.

## Post-grad ML / TensorFlow work (offline)

No extra model needed — TensorFlow, Keras, scikit-learn, and pandas are core coder training data. Split the work like this:

| Task | Model | Why |
|------|-------|-----|
| Writing/debugging TensorFlow & Keras code, building networks | **Qwopus3.6-35B-A3B-Coder-6bit** (coding) | Daily driver; thinking mode helps with tuning logic |
| Concepts & theory — "why is my validation loss diverging?", backprop, regularization | **Qwen3.6-35B-A3B-6bit** (general) | Higher temperature + thinking suits explanation |
| Reading plots — loss curves, confusion matrices, EDA charts | **Qwen3.6-35B-A3B-6bit** | Vision model: paste a chart screenshot, fully offline |
| Quick cell fixes, boilerplate (train/test split, preprocessing) | **gemma-4-12b** (quick) | Low latency for small asks |
| Gnarly bugs the daily driver can't crack | **Qwopus3.6-27B-Coder-8bit** | Quality escalation |

### Notebook assignments

- **Claude Code offline**: `omlx claude` from the assignment directory (it prompts for a model, or pass one explicitly). To pin the tiers instead, set `base/settings.json` → `claude_code` to `"mode": "local"` with sonnet → `Qwopus3.6-35B-A3B-Coder-6bit` (daily work), opus → `Qwopus3.6-27B-Coder-8bit` (hard problems), haiku → `gemma-4-12b-coder-fable5-composer2.5-8bit` (lightweight background subtasks). Keep `"mode": "cloud"` with null tiers when using real Claude models online. Claude Code edits `.ipynb` files natively either way.
- **JupyterLab alternative**: point `jupyter-ai` (or similar) at the OpenAI-compatible endpoint `http://127.0.0.1:8055/v1`.

### Coursework caveats

1. **Always run the generated code.** Local models hallucinate API details (argument names, deprecated Keras calls) more than frontier models. The run-and-fix loop catches it — and is good practice anyway.
2. **Don't fight your own hardware — and know when to leave it.** Install `tensorflow-metal` so TF trains on the M1 Max GPU. A big local LLM and a training run compete for the same 64 GB of unified memory — during heavy training, use the 12B Gemma for help, or let the 300 s idle timeout unload the big model first.
   **Local vs Colab rule:** develop, debug, and iterate locally (assignment-scale models train in seconds-to-minutes here, offline, with the LLM at your side); escalate to Colab for genuinely heavy runs — transformer fine-tuning, large CNNs, long hyperparameter sweeps — or when the assignment assumes CUDA (`tensorflow-metal` has op gaps that silently fall back to CPU, and course notebooks are usually tested on Colab). Colab needs internet, so it's the escalation path, not the default. Bonus: running graded notebooks in the graders' environment avoids "works on my machine" surprises.
3. **Known gap**: local models won't match frontier models on subtle conceptual review (e.g., methodological flaws in experiment design). When online, a frontier-model sanity pass on graded work is worth it; offline, this stack covers everything else.

## Download commands

```bash
cd /Volumes/SSDSCX_DATA/workspace/applications/omlx/models

hf download mlx-community/Qwopus3.6-35B-A3B-Coder-6bit          --local-dir mlx-community/Qwopus3.6-35B-A3B-Coder-6bit
hf download mlx-community/Qwen-AgentWorld-35B-A3B-oQ4           --local-dir mlx-community/Qwen-AgentWorld-35B-A3B-oQ4
hf download mlx-community/gemma-4-12b-coder-fable5-composer2.5-8bit --local-dir mlx-community/gemma-4-12b-coder-fable5-composer2.5-8bit
hf download mlx-community/gemma-4-31B-it-OptiQ-4bit             --local-dir mlx-community/gemma-4-31B-it-OptiQ-4bit
```
