# Security Policy

## Supported Versions

Use a current Skillware release to receive security fixes. We patch vulnerabilities only for supported versions.

| Installed version | Security support | CLI advisory |
| :--- | :--- | :--- |
| **>= 0.3.1** | Supported. Security reports accepted and patched here. | Silent |
| **0.2.6 – 0.3.0** | No security fixes. Upgrade recommended. | Silent (no upgrade spam) |
| **< 0.2.6** (e.g. 0.2.5) | Unsupported. | One dim stderr message at CLI startup (in releases that ship this check) |

Thresholds are defined in `skillware/version_policy.py` (`MIN_SECURITY_SUPPORTED`, `MIN_UNSUPPORTED`) and bumped by maintainers when support windows change.

**Note:** PyPI releases are immutable. Users on very old wheels will not see the CLI advisory until they upgrade to a release that includes this logic at least once. That is expected for OSS packaging.

## Reporting a Vulnerability

We take security seriously. If you discover a vulnerability in Skillware (e.g., standard library skills leaking data, or loader bypasses):

1.  **Do NOT create a public GitHub issue.**
2.  Email us at `security@arpacorp.net` (or contact a maintainer directly).
3.  Include a proof of concept if possible.

We will acknowledge your report within 48 hours and provide a timeline for a fix.
