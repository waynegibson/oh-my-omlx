# Agent instructions

## Scope and sources of truth

This repository maintains configuration, a launcher, and operational documentation for a local oMLX installation on macOS / Apple Silicon. The oMLX application source and model weights are maintained outside the tracked repository.

- Read `base/settings.json` for persisted server settings, `base/model_settings.json` for per-model settings and active profile assignments, and `base/model_profiles.json` for saved profiles.
- Treat these files as persisted state; verify the running server separately when a task concerns effective runtime behavior.
- `README.md` is awaiting refactoring. Verify its claims against current configuration and the installed oMLX version before using them as instructions.
- For configuration schema or admin API work, verify version-dependent behavior against the installed application or current upstream sources.
- For performance investigations, verify model identities, hardware assumptions, and measurements before applying recommendations.

## Configuration changes

1. Inspect `git status --short` and the relevant diff before editing. Preserve pre-existing changes and distinguish them from the task's changes.
2. Establish which base directory the installation actually uses. `base/bin/omlx` reads `$HOME/Library/Application Support/oMLX/base-path` and delegates to `/Applications/oMLX.app/Contents/MacOS/omlx-cli`; invoking it from this checkout does not select this checkout automatically.
3. Before editing live configuration files, establish whether oMLX is running and whether it can rewrite them. Use verified admin API operations for live changes, or edit files while the application is stopped. Re-read affected settings afterward to confirm persistence.
4. Keep edits targeted. Preserve JSON formatting, schema versions, unknown fields, model identifiers, and profile metadata unless the requested change requires updating them.
5. When changing profiles, inspect both saved profiles and active model settings. Verify the installed version's merge/reset behavior, supported fields, and feature compatibility; omitted fields may persist across profile switches. Keep feature controls explicit where needed to make switching predictable.
6. Validate the result and inspect the final diff. Report any runtime checks that could not be performed.

Keep runtime artifacts out of commits: model weights, quantization inputs, caches, logs, usage databases, and machine-specific cluster identity files. Check `.gitignore` and untracked files before staging; an unignored file is not necessarily project source. Keep credentials and tokens out of documentation, diagnostics, and commits.

## Validation

There is no repository-local build system or automated test suite. Run checks appropriate to the changed files from the repository root.

For configuration edits, validate JSON syntax:

```sh
python3 -m json.tool base/settings.json > /dev/null
python3 -m json.tool base/model_settings.json > /dev/null
python3 -m json.tool base/model_profiles.json > /dev/null
```

Also verify affected model/profile references, value types, and supported settings against the installed schema. JSON parsing alone does not establish that oMLX accepts or applies a setting. For active-profile changes, confirm that the named profile exists for the same model and that intended values were applied.

For launcher edits, check POSIX shell syntax:

```sh
sh -n base/bin/omlx
```

For every change, run `git diff --check` and review the affected files, including newly created files. For documentation-only work, verify referenced paths and commands; starting the inference server is unnecessary.

When runtime validation is part of the task, derive connection details from current settings and check the affected behavior with a small request. Record the model, relevant settings, and observed result for performance claims. Treat service restarts, model downloads, and system memory tuning as operational changes, not routine syntax checks.

## Documentation maintenance

Keep `AGENTS.md` focused on agent workflow and `README.md` focused on setup and usage. Avoid copying changing model inventories, profile tables, ports, or memory limits into this file. When updating user documentation, derive examples from current configuration, distinguish measured results from estimates, and label historical findings by version or date when known.
