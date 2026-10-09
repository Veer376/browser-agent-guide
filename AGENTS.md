# Browser Agent Guide: project instructions

Read `README.md`, `ROADMAP.md`, and `docs/architecture.md` before substantial changes. Treat `skills/playwright/SKILL.md` and its references as the installed agent's runtime contract.

Preserve the existing skill name `playwright`, its public commands and the symlink-based local installation created by `scripts/link-local-skill.sh`. Keep the optional guidance extension independent of skill-only browser use. No browser/profile attachment, token collection, external posting, or public repository creation without user authorization.

Make changes in small, independently testable increments. Before claiming compatibility, run the focused unit tests, documentation checks and appropriate live integration test. Never print tokens, browser content, or captured user session data in debugging output.

Update `ROADMAP.md` after significant progress or changed decisions; link to evidence rather than duplicating it in chat. Public publishing, releasing, Chrome Web Store submissions, and deploying the website require explicit authorization.
