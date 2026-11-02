# Implementation record

Approved scope: Python 3.12 PUBLIC API MCP, 17 documented operations, stdio and per-request-account Streamable HTTP, Docker, public repository. No PRIVATE operations, hosted deployment, database or custom OAuth.

Implementation boundaries: `soap.py` owns SOAP calls and response handling; `server.py` owns tool schemas, credential sources and MCP transports. Each SOAP request owns a session. HTTP never reads account credentials from environment.

Validation: synthetic SOAP contract tests for every operation, MCP protocol tests for stdio and HTTP, concurrent account isolation, schema errors, export readiness, decimal serialization and sanitized failures. Initial tests exposed absent modules; HTTP integration tests exposed ASGI routing and host allowlist issues before they were corrected.

Initial independent review addressed secret-bearing DEBUG logs in imported usage, response buffering/full-catalog deep copy, and synthetic export field casing differing from live WSDL. The original byte cap was later removed at the user’s request (see below). Regression tests were added and the scoped re-review was clean.

Rulings:
- Do not impose a fixed response byte cap (explicit user request after the real catalogue exceeded the original limit). Preserve redirect refusal, response closure and XML protections.
- Preserve WSDL export field casing (`url`, `fileName`, `isReady`) rather than the PDF table's capitalization.
- No native OAuth was established by official API documentation or WSDL; API username/password remain the supported authentication.
- Local Docker daemon was unavailable. GitHub Actions builds and runs the container instead of changing local services.
- No real API-account authentication was tested. Synthetic fixtures contain no dealer data.

## Client readiness verification

Added seven client configuration examples for Codex, Claude Code, Cursor and Claude Desktop, plus installed-executable recipe tests and a real-SDK container HTTP smoke test. All 39 tests pass locally. Codex CLI 0.154.0 accepted both TOML configurations via non-persistent overrides. A fresh wheel installation in a separate virtual environment passed MCP initialization, 17-tool discovery and the expected missing-credentials error from an unrelated working directory. Independent review of the client guide, recipes and tests found no material issues.

Native Claude Code/Cursor/Claude Desktop UI sessions and real dealer authentication remain untested. No user client settings or credentials were modified. Python selection for uv is pinned to 3.12 for reproducible onboarding.

## Large catalogue correction

The real in-stock catalogue exceeded the original application byte limit. Removed that check without replacing it with another ceiling; retained local result pagination, timeouts, redirect refusal, response closure and XML security. Added a regression for a response larger than the old ceiling and verified redirect cleanup separately. Full SOAP responses still consume memory before pagination.

Validation: all 40 tests pass. A real MCP stdio call using the existing Codex configuration and API account successfully returned 19,684 in-stock products in total, with a five-item locally paginated response. No credentials or provider payloads are stored in this repository.
