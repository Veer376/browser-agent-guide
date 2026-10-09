# Install the browser skill (macOS)

**Status:** GitHub skill installation guide for macOS. The optional Chrome guidance extension is a separate experimental component.

The browser skill is independent of Browser Agent Guide's **human-guidance extension**. You can use it with an automation browser without modifying your everyday Chrome profile.

## Prerequisites

- macOS and a terminal.
- A compatible coding agent with Agent Skills support (for example, Codex or Claude Code).
- Node.js/npm (`npx`) compatible with the [Skills CLI](https://github.com/vercel-labs/skills) and Microsoft's Playwright CLI (Node.js 20+ recommended).
- Python (3.11+ recommended) for the local `pw` adapter; a compatible Chrome/Playwright browser. A separate browser binary may need to be installed during first run.
- **Pillow is required for `pw observe` and full developer tests, but not for basic browser navigation.** Install it into the same Python environment that runs `pw`; prefer a virtual environment over modifying the system Python.

Check the prerequisites before configuring the skill:

```bash
node --version
npx --version
python3 --version
```

## Install the skill

```bash
npx skills add Veer376/browser-agent-guide --skill playwright
```

The interactive installer discovers skills and asks which agent(s) and which scope to use (this project or global). It installs the selected skill's `SKILL.md`, scripts and references. The command retrieves the public GitHub repository and installs the selected skill.

After installation, open your coding agent in the chosen project and use the starter prompt:

> Read the installed **playwright** skill and its `references/setup.md`. Guide me through Browser Agent Guide setup on macOS. Use my running Chrome profile by default, or a separate browser if requested. Locate the installed adapter and run `doctor --json`. Ask before installing software, attaching to personal Chrome for the first time, or reading the clipboard. Guide me through copying the official Playwright extension token myself and, with permission, saving it locally—never paste the token into chat. Verify browser/tab control with a harmless snapshot; offer the separate Guide toolbar extension only if I want human guidance.

**Fresh-copy launcher check:** The Skills CLI places the skill files but does **not** add `pw` to `PATH`. Run the adapter directly from the **installed** skill directory first, using its absolute path (the precise directory varies by agent and installation scope). The shared [first-time setup guide](../skills/playwright/references/setup.md) contains both human and agent instructions, including optional one-time trusted Chrome pairing:

**Permission before bootstrap:** `doctor` may use `npx --yes` to download the pinned Playwright CLI into the npm cache if it is missing. The setup agent must disclose this and ask before its first run. A missing Chrome executable is a separate prerequisite; after approval, install Chrome manually or with the official Playwright installer (`npx playwright install chrome`), then rerun `doctor`. No extension/native host is needed for standalone mode.

```bash
PW_BROWSER_MODE=existing python3 /path/to/installed/playwright/scripts/pw.py doctor --json
```

This checks the existing-Chrome default. For a requested separate browser, use `PW_BROWSER_MODE=standalone` so no token is needed. Review `launcherMatchesSkill`. If it is `false`, either no `pw` command exists or the command on `PATH` belongs to a different installation. Do not assume an existing `pw` is this skill; do not overwrite it. Continue with `python3 /path/to/installed/playwright/scripts/pw.py ...` and the chosen mode, or, with user approval, use the bundled `scripts/install_pw.sh` to install a non-conflicting launcher. This is a diagnostic/bootstrap step, **not proof of browser E2E**.

For an independent browser, opt in explicitly while the existing trusted Chrome workflow remains the adapter's default. Reuse the same unique session name for each command:

```bash
PW_BROWSER_MODE=standalone python3 /path/to/installed/playwright/scripts/pw.py --session=first-run open https://example.com
PW_BROWSER_MODE=standalone python3 /path/to/installed/playwright/scripts/pw.py --session=first-run snapshot
```

In standalone mode, the adapter launches a separate Playwright-controlled browser rather than attaching to Chrome; existing Chrome pairing tokens are deliberately not forwarded. `PW_BROWSER_MODE=existing` retains the established extension-attachment behavior. Isolated local macOS installation, interaction, session isolation and prerequisite recovery tests have passed. Verification from the **public GitHub repository URL** and hosted GitHub Actions can occur only after publication.

### Repeatable isolated smoke test (developers)

From the repository root, run this **opt-in** real-browser test after confirming the Skills CLI and browser prerequisites:

```bash
BAG_RUN_BROWSER_E2E=1 python3 -m unittest discover -s tests -p 'test_skill_install_e2e.py' -v
BAG_RUN_BROWSER_E2E=1 python3 -m unittest discover -s tests -p 'test_p0_portability.py' -v
```

Together these test real project and isolated-global installs, both **Codex and Claude Code**, default and `--copy` installation, direct skill path discovery, browser automation, missing-prerequisite recovery, non-destructive launcher setup, and separate-session browser state. They do not install the extension or modify the user's existing `pw` launcher/profile. A short `/tmp` socket-directory path is required on macOS due to Unix socket length limits; the tests create private short-lived directories. The macOS Agent GUI/TCC permission problem remains deferred, and live Chrome pairing is a separate P1 acceptance gate. CI is configured to run the same tests on macOS; do not claim hosted CI has passed until it actually runs.

**[The skill's canonical agent-readable setup reference →](../skills/playwright/references/setup.md)**

## Choosing the installation scope

- **Project:** use the skill only for a project. Good for testing an initial installation.
- **Global:** make it available to your supported agent across projects.
- **Selected agent(s):** avoid installing unnecessary copies for agents you do not use.

No custom Browser Agent Guide npm package is planned. The existing Skills CLI handles discovery and placement; it does **not** install or configure the browser runtime, Chrome extension, or native helper.

## Optional observation dependency: Pillow

`pw observe` uses [Pillow](https://pypi.org/project/pillow/) to create image contact sheets and compute visual statistics. From a **chosen virtual environment** (activated in your shell), run:

```bash
python -m pip install Pillow
```

The `pw` launcher uses the Python selected by its executable environment. Installing Pillow into an unrelated Python interpreter or virtual environment will not fix `pw observe`. Run `pw doctor --json` and check `pythonExecutable`; install Pillow into **that** environment (with permission), then rerun `pw doctor`. A missing-Pillow warning does **not** stop basic browser navigation, but observation cannot produce contact sheets.

## Expected first-use checks

The adapter supports `pw doctor` and has passed isolated macOS installation, browser and recovery tests. Run `doctor` in your own installed environment before relying on it, and do not assume successful skill placement alone proves the browser executable is ready.

### Want access to an existing Chrome profile?

That is a separate, optional setup using Microsoft's Playwright extension and a locally saved token. See [the agent-readable setup reference](../skills/playwright/references/setup.md). To send human guidance through a toolbar popup, also follow [Install the guidance extension](install-extension.md).
