# Changelog

All notable changes to AZTM will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2024-11-10

### Added
- Initial release of AZTM (Agentic Zero Trust Mesh)
- Core XMPP session management with automatic reconnection
- HTTP request interception for `requests` library
- FastAPI server integration with auto-detection
- Wire protocol for HTTP over XMPP transport
- URL to JID mapping system
- Configuration via environment variables
- Docker support with Openfire XMPP server
- Comprehensive test suite
- Client and server examples
- GitHub Actions CI/CD pipeline

### Features
- Zero code change HTTP transport replacement
- No inbound ports required on API servers
- Full HTTP semantics preservation
- Support for all payload sizes (inline, streaming, upload slots)
- TLS and SASL authentication
- Automatic FastAPI detection and hooking

### Security
- TLS 1.2+ enforcement
- SASL authentication
- Bearer token preservation
- Optional JOSE signing/encryption support (planned)
- Optional OMEMO E2E encryption (planned)

[Unreleased]: https://github.com/eladrave/aztm/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/eladrave/aztm/releases/tag/v0.1.0