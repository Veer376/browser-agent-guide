# Project memory

Browser Agent Guide is a Playwright CLI-based browser skill with optional Chrome UI for human instructions during an agent's browser task. The public positioning is **“Guide your browser agent—right from Chrome.”**

The original Git repository and all 13 existing commits were migrated from `~/.agents/skills/playwright` to this directory. The installed `~/.agents/skills/playwright` directory links its skill files and subdirectories to `skills/playwright`; this preserves the existing `pw` launcher and lets Local System discover the skill (it skips symlinked skill directories).

Current scope: macOS only for the first external release. A standalone skill-only install, improved installation UX, website, Windows/Linux support, and Chrome Web Store submission are planned and require validation. License selected: Apache-2.0 with Microsoft Playwright CLI attribution preserved. No CLA initially.

The canonical task status and accepted constraints belong in `ROADMAP.md`. The public README is release-facing, not proof of deployed features; verify tests and demonstrations before updating release claims. Do not publish code or change external accounts unless explicitly requested.
