# Implementation record

Approved scope: Python 3.12 PUBLIC API MCP, 17 documented operations, stdio and per-request-account Streamable HTTP, Docker, public repository. No PRIVATE operations, hosted deployment, database or custom OAuth.

Implementation boundaries: `soap.py` owns SOAP calls and response handling; `server.py` owns tool schemas, credential sources and MCP transports. Each SOAP request owns a session. HTTP never reads account credentials from environment.

Validation: synthetic SOAP contract tests for every operation, MCP protocol tests for stdio and HTTP, concurrent account isolation, schema errors, export readiness, decimal serialization and sanitized failures. Initial tests exposed absent modules; HTTP integration tests exposed ASGI routing and host allowlist issues before they were corrected.

Independent review found and resolved: secret-bearing DEBUG logs in imported usage, unbounded response bytes/full-catalog deep copy, and synthetic export field casing differing from live WSDL. Regression tests were added and the scoped re-review was clean.

Rulings:
- Use a 32 MiB decoded response ceiling and recommend export on overflow; never silently truncate upstream data.
- Preserve WSDL export field casing (`url`, `fileName`, `isReady`) rather than the PDF table's capitalization.
- No native OAuth was established by official API documentation or WSDL; API username/password remain the supported authentication.
- Local Docker daemon was unavailable. GitHub Actions builds and runs the container instead of changing local services.
- No real API-account authentication was tested. Synthetic fixtures contain no dealer data.
