# Features and technical behavior

This page describes capabilities inspected in the **existing internal Playwright skill**. It is documentation groundwork—not proof that the upcoming extracted release works independently.

| Capability | Current mechanism | What it enables |
|---|---|---|
| Browser actions | Microsoft's Playwright CLI with a task-aware `pw` adapter | Navigation, snapshots, element actions and screenshots |
| Text replacement | `pw replace` with editing-specific checks | More controlled updates of reactive inputs |
| Temporal observation | `pw observe` | View an element/viewport changing over several seconds as frames and contact sheets |
| Diagnostics | `pw doctor`, `pw diagnose`, console, requests, Playwright trace | Understand failures before retrying blindly |
| Browser sessions | Session ownership, scoped tabs/locks, lifecycle records | Reduce accidental interference between independent tasks |
| Human guidance | Separate Chrome popup, native messaging, local queue | Route queued user instructions to the owning session |

## Observe a changing interface

```bash
pw observe 'video' --duration 8s --fps 4
pw observe --duration 30s --frames-per-sheet 24 --columns 4
```

`observe` captures sampled frames, not a continuous live video stream. The existing implementation produces numbered image/contact sheets and a `manifest.json` with requested vs achieved frame rates, timing, and warnings. The default observation is 10 seconds at one sample per second, and frame limits apply.

Useful for: loading states, videos, animation transitions, interactive dashboards, carousels and problems that a single snapshot cannot explain.

## Diagnose and inspect

```bash
pw doctor
pw snapshot
pw screenshot
pw console warning
pw requests
pw trace start
# Reproduce the issue, then:
pw trace stop
```

Target refs for commands must come from the current browser snapshot; don't copy an arbitrary example element ID and assume it points to the right thing. The agent should verify important UI effects after an action.

## Keep sessions separate

The existing adapter scopes browsers and tabs to the owning task/session, with lock and reconnect checks. These are **coordination safeguards**, not a hard security sandbox. Arbitrary Playwright code execution can access sensitive data and is intended only for trusted tasks.

## Human guidance and delivery boundaries

The optional Guide extension checks tab/session ownership and queues a bounded message. The agent receives it at a supported command boundary, not as an unsolicited model turn. Users can cancel pending messages, but cannot retract messages already delivered. Local persistent messages can be retried using the same ID after connection failures.

**Detailed setup:** [Skill](install-skill.md) · [Guidance extension](install-extension.md) · [One-time Chrome pairing](../skills/playwright/references/setup.md).
