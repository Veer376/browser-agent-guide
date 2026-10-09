# Contributing to Browser Agent Guide

Thanks for considering a contribution. This project is an independent tool built around Microsoft's Playwright CLI. For the initial release, **macOS is the only supported platform**. Windows/Linux support is welcome, but a port is not complete until tested on the target OS.

## Find the right place

- `skills/playwright/` — agent skill, Python Playwright wrapper and reference documentation.
- `extension/` — Chrome Manifest V3 guidance popup.
- `skills/playwright/scripts/pw_guidance.py` and `pw_native_guidance.py` — local broker and native-messaging helper.
- `skills/playwright/tests/` — behavior and regression tests.
- `docs/` — architecture, installation and supported behavior.
- `website/` — lightweight landing page, not the agent runtime.

Check [ROADMAP.md](ROADMAP.md) and open or discuss a small issue before proposing broad architectural changes. Keep a pull request focused on one problem.

## Local development

Requirements: macOS, Python 3.11+, Node.js 20+ and Git. Browser integration tests also need compatible Playwright CLI/Chrome configuration.

```bash
git clone https://github.com/Veer376/browser-agent-guide.git
cd browser-agent-guide
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m unittest discover -s skills/playwright/tests -v
python -m unittest discover -s tests -v
python scripts/check_publication.py
node --check website/main.js
node --check extension/popup.js
node --check skills/playwright/scripts/pw-guidance.cjs
python -m json.tool extension/manifest.json > /dev/null
sh -n scripts/link-local-skill.sh
ruby -e 'require "yaml"; ARGV.each { |file| YAML.load_file(file) }' .github/workflows/ci.yml .github/ISSUE_TEMPLATE/*.yml
```

This uses the public repository URL. You can run the same commands from a local checkout. The unit tests do **not** require access to your personal browser profile, credentials, or live accounts. Test external integrations only with permission and disposable profiles.

**Test layers:** Both `unittest discover` commands run by default on pull requests, including the publication/contributor policy tests. Browser E2Es are an additional opt-in integration check; after reviewing the test isolation and installing the prerequisites, run `BAG_RUN_BROWSER_E2E=1 python -m unittest discover -s tests -p 'test_skill_install_e2e.py' -v` and `BAG_RUN_BROWSER_E2E=1 python -m unittest discover -s tests -p 'test_p0_portability.py' -v`. These use isolated temporary homes and browser profiles, not your daily Chrome profile. CI executes them on a dedicated macOS runner.

The publication preflight inspects Git-tracked and non-ignored untracked working files for known credential signatures, private filenames and developer home paths, without printing matching values. It is deliberately conservative, **not** a full secret scan or historical Git audit. Before publishing, also inspect `git status`, your staged diff, older commits, images and third-party notices; do not stage the ignored `notes.md` or browser state.

For a **local developer installation only**, `sh scripts/link-local-skill.sh` creates or verifies symlinks from your `~/.agents/skills/playwright` directory to this repo. It refuses to overwrite an unrelated skill installation. This is separate from the public Skills CLI installation.

The optional Chrome extension is loaded via `chrome://extensions` → Developer mode → **Load unpacked** → the repository's `extension/` directory. Read [installation](docs/install-extension.md) before testing native messaging. Never weaken origin checks or expose the local queue publicly to make a test pass.

## Pull request expectations

1. Explain the user problem and affected component; note any compatibility change.
2. Include regression tests and update the relevant documentation.
3. Run both unit test suites. For Chrome/native changes, describe a manual end-to-end check of session binding, guidance delivery, cancellation and reconnect.
4. Keep browser recordings, cookies, tokens, `.env` files, local artifacts and user data out of commits.
5. Keep any upstream license notices and clearly credit code adapted from other projects.
6. For a changed safety rule, contribute a focused regression test using synthetic data rather than real credentials. For a changed workflow, update its example and test on the platform you claim.

CI is configured to check unit tests, repository layout, and isolated macOS browser/installation E2Es. Hosted CI has not yet run for a published repository; passing these tests does not establish end-to-end Chrome popup and native-host compatibility.

## Contribution terms

The project uses [Apache License 2.0](LICENSE). By submitting a contribution, you agree to license your original contribution under those terms and to have the right to submit it. **No separate Contributor License Agreement (CLA) is required for the initial release.** See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) and [SECURITY.md](SECURITY.md).
