# Security Policy

## Reporting a Vulnerability

If you find a security issue in this repository, please report it privately
via [GitHub's private vulnerability reporting](https://github.com/amitnahum18/Cruisea/security/advisories/new)
rather than opening a public issue.

Please include:
- A description of the issue and its potential impact
- Steps to reproduce
- Any relevant logs or proof-of-concept code

## What's already automated

Every push and pull request against `main` runs:
- `ruff` (lint) and the pytest suite, including a property-based/fuzz test
  suite (Hypothesis) targeting the input-validation layer
- `gitleaks` (secret scanning)
- `pip-audit` (dependency vulnerability scanning)
- `bandit` (static analysis)

Dependencies are pinned by hash (`pip install --require-hashes`) and kept
current via Dependabot.
