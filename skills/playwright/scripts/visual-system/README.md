# Cursor & agent visual system

Reusable, **monochrome** visuals for Playwright's injected browser cursor.
The cursor, attached agent, theme tokens and animations are separate modules:

| Module | Responsibility |
| --- | --- |
| `cursor.cjs` | 46×48 vector cursor silhouette; **single white outline**. Original PNG remains in `../assets/` as a fallback |
| `agent.cjs` | Two-eye black pill, directional gaze, typing/read/scroll reactions, two staggered sleeping Z marks, wake and idle lifecycle |
| `theme.cjs` | Light, dark and automatic monochrome palettes (`PW_AGENT_THEME=auto\|light\|dark`) |
| `motion.cjs` | Shadow-root stylesheet, accessibility/reduced-motion support, motion timing |
| `../pw-action-visuals.cjs` | Adapter-specific integration with the **pinned** Playwright CLI's screen-action overlay |

The modules can be used independently: `attachAgent(cursor, document, window)`
accepts a cursor element in any page or shadow root. CSS and cursor paths are
exported without requiring the Playwright CLI.

The **default** pill uses a black fill, two white 6px eyes and one white 2px
border. **No outer black border, drop shadow or extra third dot.** The agent
never displays typed content or JavaScript arguments. Screenshot commands hide
the overlay during image capture, then restore it.

The Playwright integration uses its automation-owned browser/profile and
already-established session identity. The companion only exists while
`PW_ACTION_VISUALS=1`; setting `PW_ACTION_VISUALS=0` disables this
experimental visual layer.

## Tests

```sh
python -m unittest discover -s skills/playwright/tests -p 'test_action_visuals.py' -v
PW_TEST_PLAYWRIGHT_MODULE=/path/to/playwright node tests/visual_system_browser.cjs
```

The browser smoke test launches **isolated Chrome**, checks typing focus,
directional eyes, clean screenshot behavior, automatic dark theme, reduced
motion and overlapping sleep particles. Fresh installation of the pinned
Playwright CLI is a separate concern.
