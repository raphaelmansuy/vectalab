Actions:
- Applied conservative branch protection to `main` via `gh api` (require 1 PR review, strict status checks w/ empty contexts, enforce_admins=false, disallow force-push & deletion).
- Updated README.md with a `Repository protections` section and example gh command used.

Decisions:
- Conservative policy chosen per request: helps prevent accidental direct pushes while avoiding failures from missing CI contexts.

Next steps:
- Optionally tighten rules (enforce admin, add required CI contexts when workflows exist, restrict pushes to teams).
