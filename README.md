<p align="center">
  <a href="https://veer376.github.io/browser-agent-guide/">
    <img src="website/favicon.svg" width="76" height="76" alt="Browser Agent Guide cursor icon">
  </a>
</p>

<p align="center"><sub>BROWSER / AGENT / GUIDE &nbsp; — &nbsp; MACOS FIRST</sub></p>

<h1 align="center">Your agent is browsing.<br>Stay in the loop.</h1>

<p align="center">
  A Playwright-powered browser skill, with an optional way to guide your agent<br>
  right from the Chrome tab where it's working.
</p>

<p align="center">
  <a href="https://veer376.github.io/browser-agent-guide/"><strong>Explore the website ↗</strong></a>
  &nbsp; · &nbsp;
  <a href="#04--get-started"><strong>Get started</strong></a>
  &nbsp; · &nbsp;
  <a href="docs/features.md"><strong>Explore capabilities</strong></a>
</p>

<p align="center">
  <a href="https://github.com/Veer376/browser-agent-guide/actions/workflows/ci.yml"><img src="https://github.com/Veer376/browser-agent-guide/actions/workflows/ci.yml/badge.svg" alt="Continuous integration status"></a>
  &nbsp;
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-3b4a49" alt="Apache-2.0 license"></a>
  &nbsp;
  <img src="https://img.shields.io/badge/platform-macOS-3b4a49" alt="macOS">
</p>

---

### 01 / Two independent layers

<table>
  <tr>
    <td width="50%" valign="top">
      <p><sub>01 / FOUNDATION &nbsp; — &nbsp; AVAILABLE NOW</sub></p>
      <h3>Browser skill</h3>
      <p>Your coding agent navigates, inspects and debugs real browsers through Microsoft's Playwright CLI and a session-aware adapter.</p>
      <p><code>pw snapshot</code> &nbsp; <code>pw observe</code> &nbsp; <code>pw screenshot</code></p>
      <p><a href="docs/install-skill.md">Install the browser skill ↗</a></p>
    </td>
    <td width="50%" valign="top">
      <p><sub>02 / HUMAN LAYER &nbsp; — &nbsp; EXPERIMENTAL</sub></p>
      <h3>Chrome guidance</h3>
      <p>Leave a note from a Chrome toolbar popup while an agent works on a tab. Messages are queued for the owning agent session.</p>
      <p><code>draft</code> → <code>queued</code> → <code>delivered</code></p>
      <p><a href="docs/install-extension.md">Explore the optional extension ↗</a></p>
    </td>
  </tr>
</table>

### 02 / The experience

You notice a detail the agent might miss. Instead of switching back to chat, you leave a note in Chrome:

> **Check the appointment date before submitting.**

The optional Guide extension routes the note to the relevant session. The note is available at the **next supported browser-command boundary**—not as an instant interruption.

<p align="center"><sub>HUMAN INTENT &nbsp; → &nbsp; LOCAL QUEUE &nbsp; → &nbsp; NEXT BROWSER COMMAND</sub></p>

**The distinction matters:** queued does not mean delivered; delivered does not mean read or followed. Guidance cannot wake an idle agent. The live extension's fresh-install path is still being validated; the <a href="https://veer376.github.io/browser-agent-guide/#experience">website demo</a> is an explicitly labeled interactive illustration, not a connected agent.

### 03 / Beyond browser clicks

| Capability | What it adds |
|:--|:--|
| **Navigate & inspect** | Page snapshots, element actions, screenshots and browser diagnostics |
| **Observe change** | `pw observe` samples transient UI states and creates timestamped contact sheets |
| **Keep context** | Scoped browser sessions, tab ownership and guarded recovery |
| **Guide in place** | Optional tab/session-aware guidance queue and cancellation |

Read the [feature reference](docs/features.md), [architecture](docs/architecture.md), or [human guidance protocol](docs/guidance.md).

### 04 / Get started

<p><sub>MACOS &nbsp; / &nbsp; PUBLIC SKILL &nbsp; / &nbsp; NO CUSTOM NPM PACKAGE</sub></p>

Install the `playwright` skill with the [Skills CLI](https://github.com/vercel-labs/skills):

```bash
npx skills add Veer376/browser-agent-guide --skill playwright
```

Choose your coding agent and project/global scope. The skill is usable **without** the separate Guide extension. Setup will check browser/runtime prerequisites; successful skill placement alone does not install Chrome or the Playwright runtime.

**Requirements:** macOS, an Agent Skills-compatible coding agent, Node.js/npm, Python and a compatible browser. `Pillow` is additionally needed for `pw observe`. See the [full installation guide](docs/install-skill.md).

<table>
  <tr>
    <td width="33%" valign="top"><p><sub>01 / INSTALL</sub></p><strong>Add the skill</strong><p>Choose Codex, Claude Code or another compatible agent and install scope.</p></td>
    <td width="33%" valign="top"><p><sub>02 / VERIFY</sub></p><strong>Check prerequisites</strong><p>Run the installed adapter's <code>doctor --json</code> and verify a harmless browser snapshot.</p></td>
    <td width="33%" valign="top"><p><sub>03 / OPTIONAL</sub></p><strong>Connect Chrome</strong><p>Authorize your existing Chrome profile or request a separate automation browser.</p></td>
  </tr>
</table>

## Guided first-time setup

For a guided first run, paste this into your coding agent:

> Read my installed `playwright` skill and `references/setup.md`. Guide me through setup on macOS. Check prerequisites using the installed `scripts/pw.py doctor --json`; ask before downloading software, connecting to my personal Chrome profile or reading the clipboard. I can use a separate browser instead. Verify control with a harmless snapshot, and offer the optional Browser Agent Guide Chrome extension only if I want in-browser guidance. Never print or ask me to paste connection tokens into chat.

The default browser mode uses your existing Chrome through **Microsoft's official Playwright extension**, with your permission on first attachment. A separate standalone browser can be requested instead. Microsoft's connection token can reduce repeated **connection approval** prompts, but does **not** bypass agent approvals, website permissions or confirmation for consequential actions. The Browser Agent Guide popup is a *different* extension.

**[First-run setup](skills/playwright/references/setup.md) ↗** &nbsp; · &nbsp; **[Guide extension](docs/install-extension.md) ↗**

---

### Project notes

This is an independent community project built around [Microsoft Playwright CLI](https://github.com/microsoft/playwright-cli) and [Playwright](https://github.com/microsoft/playwright). It is **not affiliated with Microsoft**, not a standalone AI model, and does not provide a security sandbox. Browser sessions can access authenticated sites; supervise sensitive actions. Never publish session tokens, cookies, traces or private screenshots.

The browser skill has passed isolated macOS installation, browser-operation and session tests, including hosted CI. The optional human-guidance extension is still experimental; there is **no Chrome Web Store listing** or tested Windows/Linux release. [Security policy](SECURITY.md) · [License](LICENSE) · [Upstream attribution](NOTICE).

<p align="center">
  <a href="CONTRIBUTING.md">Contribute</a> &nbsp; · &nbsp;
  <a href="ROADMAP.md">Roadmap</a> &nbsp; · &nbsp;
  <a href="https://veer376.github.io/browser-agent-guide/">Website ↗</a>
</p>
