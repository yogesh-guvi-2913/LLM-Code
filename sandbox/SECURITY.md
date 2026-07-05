# Security Policy

## Reporting a vulnerability

If you find a security vulnerability in this project, please **do not open a
public GitHub issue**. Instead, report it privately:

- Email **arun@hclguvi.com** with a description of the issue, steps to
  reproduce, and its potential impact.
- Alternatively, use [GitHub Security
  Advisories](https://github.com/guvi-geek/flash/security/advisories/new)
  to report privately.

We'll acknowledge your report as soon as possible and work with you on a fix
and disclosure timeline before any public details are shared.

## Scope

This project runs untrusted, candidate-supplied code inside Docker
containers. Reports of particular interest include:

- Container escapes or sandbox isolation bypasses (rootfs, capabilities,
  seccomp, gVisor).
- Authentication/authorization bypasses (org API keys, session tokens).
- Cross-session or cross-org data leakage.
- Privilege escalation from the candidate plane (playground, terminal,
  preview) to the operator plane.
- Injection or traversal in file/exec APIs (e.g. escaping the sandboxed work
  directory).

## Supported versions

This project is pre-1.0 and does not yet maintain multiple supported release
lines. Security fixes are applied to the `main` branch.
