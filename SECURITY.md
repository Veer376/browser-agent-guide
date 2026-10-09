# Security policy

Browser Agent Guide can operate authenticated browser sessions. Treat the Playwright connection token, guidance broker pairing data, traces, screenshots, cookies and local browser profiles as sensitive.

## Report a vulnerability

Please **do not open a public issue containing an exploit, credentials, session tokens or captured private data**. Use the repository’s [private vulnerability reporting](https://github.com/Veer376/browser-agent-guide/security/advisories) through **Security → Advisories → Report a vulnerability**. If the private reporting option is missing, do not post sensitive details publicly; ask the maintainer to enable secure reporting without including exploit details.

Include the affected version/commit, platform, reproduction steps with disposable credentials, and potential impact. Do not test against other users' sessions or production accounts without permission.

## Threat boundaries

- The optional Chrome extension communicates with a restricted native-messaging host and authenticated loopback broker. Keep the Chrome extension ID allowlist and session/tab ownership checks intact.
- The token for attaching to existing Chrome is held in a private local file. Never print, log, upload, commit or ask a user to paste it into chat.
- Local session coordination is **not** an isolation sandbox. A coding agent with arbitrary code execution already has significant local authority.
- No remote telemetry, remote token collection or public API listener is required for the intended local guidance workflow.

The repository is public but versioned releases and formal security support guarantees are not yet established.
