Actions: Created ADR documenting CLI inconsistencies/obsolete options, and recommended fixes.

Decisions: Prioritise unifying --quality semantics and renaming premium's flag to a clear float option (e.g., --target-ssim). Document and test changes before removal.

Next steps: (1) Implement `premium --quality` -> `--target-ssim` change and update docs/scripts; (2) Fix `convert` device propagation bug; (3) Decide deprecation timeline for `optimal` and `hifi`.

Lessons: CLI is feature-rich but has flag-name collisions and outdated examples in docs; a small, focused cleanup will reduce confusion and CI/test fragility.

Saved: /adr/001-adr-cli-obsolete-options.md
