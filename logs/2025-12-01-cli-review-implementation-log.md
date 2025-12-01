Actions: Reviewed CLI, created ADR, and implemented the primary recommendation: renaming `premium`'s `--quality` flag to `--target-ssim`.

Decisions: Renamed flag to avoid semantic conflict with preset-based `--quality` in other commands. Updated all docs and scripts to match.

Next steps: Consider deprecating `optimal` and `hifi` commands in a future release.

Lessons: Proactive cleanup of CLI inconsistencies prevents user confusion and script fragility.

Saved: /adr/001-adr-cli-obsolete-options.md
