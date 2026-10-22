# Security Policy

## Supported Versions

Security fixes are applied to the latest release on the default branch.

## Reporting a Vulnerability

Please report vulnerabilities through this repository's GitHub Security
Advisories. Do not open a public issue for an undisclosed vulnerability.

Include the affected version, reproduction steps, impact, and any suggested
mitigation. Remove credentials, personal data, recordings, and local absolute
paths from logs and screenshots before submitting.

## API Keys and Local Data

- Store `DASHSCOPE_API_KEY` only in a local `.env` file.
- Never commit `.env`, terminal output containing a key, or screenshots of the
  configuration screen.
- If a key is exposed, revoke or rotate it in the provider console immediately.
- The application is a local gateway. Do not expose port `8000` directly to the
  public internet without adding authentication, TLS, and network controls.
- Review changes before running scripts from forks or pull requests.

## Scope

This policy covers code in this repository. It does not cover the security,
availability, billing, or data handling of third-party cloud services.
