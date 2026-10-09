# Browser Workflows

## Form interaction

```bash
pw open https://example.com/form
pw snapshot
pw fill e1 "user@example.com"
pw replace e2 "0" --submit
pw click e3
pw snapshot
```

Use `replace` for controlled or formatted inputs; use `fill` for ordinary fields.

## Data extraction

```bash
pw eval "() => document.title"
pw eval "element => element.textContent" e12
```

## Debugging

```bash
pw console warning
pw requests
pw trace start
# reproduce the issue
pw trace stop
```

Use `pw run-code --filename=/abs/path/script.js` for a trusted compound operation that cannot be expressed clearly with ordinary commands.

## Multiple pages

Use tabs within the current session for separate pages or tests:

```bash
pw open https://example.com
pw tab new https://example.com/checkout
pw tab list
```

Select the required tab before interacting. Commands within a session are serialized; retain the same session throughout the work.
