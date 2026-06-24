# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.x     | Yes       |

## Reporting a Vulnerability

Do not open a public GitHub issue for security vulnerabilities.

Email: security@breakdown-project.dev (replace with actual address before publishing)

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix if known

You will receive a response within 72 hours. We will coordinate a fix and disclosure timeline with you.

## Known Scope

- API keys in .env files: never commit .env; it is in .gitignore by default
- The token server binds to 127.0.0.1 only and is not reachable from the network
- Code sent to LLM/TTS/STT providers is subject to those providers' privacy policies
- The .breakdown/ index directory may contain code snippets; it is gitignored by default
