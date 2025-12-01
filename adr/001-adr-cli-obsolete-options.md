# 001 — CLI review: obsolete/conflicting options and commands

Status: Proposed
Date: 2025-12-01

## Context

I reviewed `vectalab`'s CLI implementation (`vectalab/cli.py`) and the related CLI documentation (`docs/cli.md`, `README.md`, and several scripts). The goal was to identify commands and options that are obsolete, conflicting, or otherwise misleading and to recommend concrete cleanups.

## Findings (summary)

The codebase is stable and feature-rich, but there are several inconsistencies and leftover/legacy items in the CLI surface that make the UX confusing and increase maintenance cost.

Major issues found:

1. Overloaded `--quality / -q` flag
   - The meaning of `--quality` varies across commands:
     - `convert`, `logo`, `smart`, etc. use `--quality` as *presets* (enum strings such as `figma`, `balanced`, `ultra`).
     - `premium` uses `--quality` to mean *target SSIM* (a float between `0.90` and `1.0`) — this mismash is confusing (file refs: `vectalab/cli.py` around the `premium` function).
   - Scripts and docs contain both uses which makes automation error-prone (see `scripts/benchmark_runner.py`, `docs/cli.md`).

2. Documentation inconsistencies and stale examples
   - The `convert` doc string and CLI docs show an example using `-q fast` (line `vectalab/cli.py` example and `docs/cli.md`). There is no `fast` preset in the `Quality` enum — the valid presets are `figma`, `balanced`, `quality`, `ultra`.
   - `docs/cli.md` frequently documents `--quality` ranges and defaults that don't match implementation (e.g., `logo` documented as `--quality, -q` default `0.95` while `logo` code actually uses `LogoQuality` enum presets). Many sections mention flags that are not implemented (e.g., `--snap/--no-snap` in `docs/cli.md` for `logo`).

3. Redundant / overlapping commands
   - `optimal` overlaps significantly with `smart` / `premium` / `auto`. We should decide to keep either `optimal` or consolidate its functionality into `smart` or `premium` and mark the other as deprecated.

4. Hidden legacy alias: `hifi`
   - The CLI provides a hidden `hifi` alias (`@app.command('hifi', hidden=True)`) which wraps `convert`. This looks intentionally kept for backwards compatibility; if it is no longer needed it should be deprecated or surfaced with deprecation messaging.

5. `--device` option is unused for some methods
   - In `convert`, `--device`/`-d` is accepted but the HiFi flow calls `_run_hifi_conversion(...)` which does not accept a `device` argument. This means `--device` is silently ignored for `--method hifi` (a bug/behavior worth addressing), see `vectalab/cli.py` around `_run_hifi_conversion` and `convert`.

6. `--use-modal` and modality inconsistencies
   - `--use-modal` appears in a few places but support and documentation are inconsistent. Needs a unified policy and docs update.

7. `--quiet` limited scope
   - `--quiet` exists only in `convert`. Other commands lack a consistent global “quiet” option. Consider either standardizing this or removing it for convert.

8. Scripts and tests rely on different flag semantics
   - Some test harness scripts and benchmark scripts assume `--quality` is a string preset (e.g., `vectalab logo ... --quality ultra`) while others call `vectalab premium --quality 0.95` (float). This causes automation fragility.

## Concrete recommendations

1. Unify `--quality` semantics
   - Change `premium`'s `--quality` to `--target` or `--target-ssim` (explicit float name). Reserve `--quality/-q` for *preset* options (enum) only.
   - Update all scripts and docs (`scripts/*`, `docs/cli.md`, `README.md`, `benchmark.py`) to the new flag name.

2. Fix/clarify `convert` examples and Quality presets
   - Remove the `-q fast` example and replace with real preset names (e.g., `figma` for fastest preview
   - Document exact preset names and expected behaviors in `docs/cli.md`.

3. Deprecate / consolidate overlapping commands
   - Decide whether `optimal` is still required. If it's a legacy workflow, mark it as deprecated and route users to `smart` or `premium` instead.

4. Address `hifi` alias
   - If backward compatibility is needed, keep `hifi` but print a short deprecation notice. Otherwise remove the alias.

5. Fix `--device` behavior
   - Ensure device selection is honored for all methods. Either pass `device` to `_run_hifi_conversion` or clearly document that `--device` applies only to non-HiFi flows.

6. Standardize `--quiet` behavior or remove
   - Prefer returning `--quiet` as a global option (via app callback) or remove from `convert` and standardize with `--verbose` flag semantics.

7. Update docs & tests before release
   - Update `docs/cli.md`, `README.md`, and all `scripts/*` to use the final, consistent flags. Add tests that verify CLI invocation semantics for `--quality` vs `--target` to prevent regressions.

## Proposed next steps (implementation plan)

- Rename `premium` flag `--quality` -> `--target-ssim` (or `--ssim`) in the CLI function and supporting scripts/tests.
- Update docs and examples (special attention to `docs/cli.md` sections for `convert`, `logo`, and `premium`).
- Decide the fate of `optimal` and `hifi` – either deprecate (with warning) or remove. Add deprecation warnings before removal.
- Fix the `device` propagation bug for `convert` when `method==hifi`.
- Add unit tests for CLI argument parsing and small integration tests for scripts relying on CLI flags.

## References

- CLI implementation: `vectalab/cli.py` (see `convert`, `premium`, `logo`, `smart`, `auto`, `hifi` alias)
- Docs: `docs/cli.md`, `README.md` (examples)
- Automation: `scripts/benchmark_runner.py`, `vectalab/benchmark.py` and various `scripts/*` invoking `--quality`

---

If you want, I can follow up with a small code change implementing the top-priority fix (rename `premium`'s `--quality` flag to `--target-ssim` and update the docs/scripts accordingly) and add tests to prevent regressions.

> ADR created by repo review on 2025-12-01
