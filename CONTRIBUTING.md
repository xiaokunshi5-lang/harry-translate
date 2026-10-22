# Contributing

## Development Setup

```bash
git clone https://github.com/xiaokunshi5-lang/harry-translate.git
cd harry-translate
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill in a local DashScope key in `.env`. Never commit that file.

## Pull Requests

1. Keep changes focused on one problem.
2. Preserve the local-first security model and do not add bundled credentials.
3. Add or update tests for behavior changes.
4. Run `python -m compileall -q server.py float_app.py core engines tests`.
5. Run `python -m unittest discover -s tests -p 'test_*.py'`.
6. Describe user-visible behavior, security impact, and verification in the PR.

Use the issue templates for bugs and feature requests. Report vulnerabilities
privately through GitHub Security Advisories as described in `SECURITY.md`.
