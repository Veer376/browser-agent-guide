# Architecture

Browser Agent Guide combines an installed Playwright automation skill with an optional Chrome human-guidance interface. It is **not** a standalone AI model or an official Playwright offering.

## Repository and installed skill

```text
~/Projects/browser-agent-guide/      # Git repository, preserves existing history
├── skills/playwright/              # existing runtime skill and Python adapter
│   ├── SKILL.md
│   ├── scripts/
│   ├── references/
│   └── tests/
├── extension/                      # optional Chrome toolbar UI (MV3)
├── docs/                           # this file, setup and behavior
├── website/                        # static public landing page, not yet deployed
└── .github/                         # CI and contribution workflows

~/.agents/skills/playwright/         # real directory, for skill discovery
    SKILL.md ───────────────────────→ ~/Projects/browser-agent-guide/skills/playwright/SKILL.md
    scripts/ ───────────────────────→ ~/Projects/browser-agent-guide/skills/playwright/scripts/
    references/ ────────────────────→ ~/Projects/browser-agent-guide/skills/playwright/references/
~/.local/bin/pw ────────────────────→ ~/.agents/skills/playwright/scripts/pw.py
```

The existing Git repository was **moved**, not reinitialized or copied. Past commits retain the old repository-relative paths; Git rename detection can follow most moves through `git log --follow` on individual files. No existing browser state, screenshots or connection tokens belong in Git. Use `scripts/link-local-skill.sh` to set up the local installation after cloning or moving the repository.

**Why symlink individual entries?** Local System's skill discovery skips symlinked **directories** under `~/.agents/skills`, but it follows a linked `SKILL.md` inside a real skill directory. This structure retains one editable copy of each file in the project and keeps `playwright` discoverable.

## Runtime design

### Modular cursor companion

The `skills/playwright/scripts/visual-system/` directory contains reusable,
independent modules for the cursor's SVG silhouette, the two-eye agent, the
monochrome theme tokens, and motion/sleep CSS. `pw-action-visuals.cjs` is the
only Playwright-CLI-specific adapter: it attaches the separate agent pill to
the Playwright cursor inside its isolated overlay, and broadcasts non-pointer
tool lifecycle events. There are no user-page UI dependencies.

The default is **one white border** with no black outer rim. Browser operations
do not wait for visual animations. Normal screenshots suppress the overlay.
Color scheme follows the browser unless `PW_AGENT_THEME` is set to `light` or
`dark`; reduced-motion preferences disable decorative animation.

```text
Coding agent
   │ reads SKILL.md / references
   ▼
Playwright adapter (`pw.py`)
   ├── session ownership, diagnostics, guarded action helpers, observation
   └── Microsoft Playwright CLI → browser

Optional, when using Chrome human guidance:
Chrome guide popup (`extension/`)
   │  restricted Chrome Native Messaging
   ▼
Local native helper → authenticated loopback guidance broker
   │                     private SQLite queue, tab/session ownership
   └─────────────────────→ delivered at next supported `pw` command boundary
```

The **official Playwright browser extension** is distinct from this project's **human-guidance extension**. The former attaches to an existing Chrome session and uses a token; the latter sends guidance through native messaging. See [extension setup](install-extension.md) and [macOS token handling](../skills/playwright/references/setup.md).

For the message flow, component responsibilities, credentials and delivery guarantees, see [How browser guidance works](guidance.md).

## Capabilities and guarantees

The adapter adds temporal `observe` capture (sampled frames + contact sheets), browser diagnostics and lifecycle records, scoped sessions and guarded interactions. The guidance feature queues messages, routes them to the correct tab's owning session, and allows cancelling undelivered messages. **It does not instantly interrupt or wake an idle agent**, and delivered is not synonymous with followed.

Session locks coordinate the adapter's tasks. They do not prevent arbitrary external Playwright invocations or code running with the agent's OS permissions. All sensitive browser state remains local and must be treated as confidential.

## Distribution boundaries

The agent skill is independently installable without the human-guidance extension. Isolated macOS installation and standalone browser E2E tests pass locally; publication and verification from the future public GitHub URL remain pending. The [Skills CLI](https://github.com/vercel-labs/skills) installs skill files **only**, not browser binaries or native helpers. `pw guidance enable` can prepare the native host from a copied skill, but the Guide Chrome extension must be obtained separately.

The Chrome extension requires a separate setup path and a restricted native-messaging host. First release target is **macOS**. Windows and Linux are roadmap items until verified on those platforms. See [ROADMAP](../ROADMAP.md).

## Engineering constraints

Keep established `pw` invocation and `playwright` skill paths operational, preserve origin/session checks, make setup and recovery idempotent, never expose pairing tokens, and test behavior on real browsers before claiming integration support. Do not break existing local workflows merely to simplify publishing.
