# Repository audit — 2026-11-02

What this repo does: It exposes 17 Czech eD system PUBLIC SOAP operations through MCP. The audit assumed one local client or a small trusted group using a shared HTTP process, including large catalogues. It did not assume anonymous public hosting or high-volume capacity.

The audit first read every runtime module, test, client recipe, packaging/container/CI file and existing document without changing code. The following fixes were then explicitly authorized as part of the same task.

## Must fix

1. **Overload and cancellation could multiply large SOAP work** (`src/edshop_mcp/server.py`).
   - What this is: Blocking calls run in worker threads and each catalogue is parsed in memory.
   - Problem: Requests could fill the executor and its waiting queue; cancelling an MCP caller did not stop the underlying worker, so retrying could add more work.
   - Fix: Fail-fast admission, default two active SOAP calls per server process. Keep the capacity slot until the worker actually exits, including after caller cancellation; consume abandoned exceptions safely.
   - If skipped: Concurrent catalogues or repeated retries could exhaust a small server's memory. **Resolved**, with overload, cancellation, failure-release and recovery regressions. The explicit user decision to have no response byte cap is preserved.

2. **The deployed image did not use the tested runtime lock** (`Dockerfile`, `uv.lock`).
   - What this is: Docker originally ran `pip install .` against version ranges.
   - Problem: A later image build could resolve different dependencies from the ones validated in the source checkout.
   - Fix: Build a non-editable environment with `uv sync --locked`, copy it into the runtime image, retain non-root execution and test the hardened container.
   - If skipped: A passing source test would not establish that the deployed dependency graph works. **Resolved** for runtime dependencies; the Python base image tag still updates and operators must retain a tested image for rollback.

## Should fix

3. **The synthetic input contract mirrored the implementation** (`tests/test_soap.py`).
   - What this is: The test WSDL was generated from the same operation table it tested.
   - Problem: An incorrect method name, parameter or type could make both implementation and fixture wrong together.
   - Fix: Record a separate, non-secret input contract from the official public WSDL and compare all 17 methods against it. Build synthetic WSDL from that independent fixture.
   - If skipped: Contract drift would be missed by the test suite. **Resolved**; fixture checked on 2026-11-02. It is an input-contract snapshot, not an exhaustive copy of all provider output schemas.

4. **Boundary protections lacked direct regressions** (`tests/test_hardening.py`, `tests/test_soap.py`).
   - What this is: The server promises Host/Origin restrictions, credential isolation and safe XML handling.
   - Problem: Several important rejection paths were not explicitly exercised, and non-ASCII/XML-special parameter values were absent.
   - Fix: Test foreign Host/Origin, malformed credential bytes, Unicode/XML escaping, failed-worker cleanup and cancellation alongside existing account-isolation, XXE, fault and secret-log tests.
   - If skipped: A future refactor could quietly remove a security boundary. **Resolved** for these cases; not a penetration test.

5. **Package and dependency checks stopped at the checkout** (`pyproject.toml`, `.github/workflows/ci.yml`).
   - What this is: Tests primarily used an editable installation on one Python version.
   - Problem: Broken distribution contents or a newly reported runtime dependency advisory could go undetected; directly imported libraries were only transitive dependencies.
   - Fix: Declare direct imports, build wheel from sdist, validate package metadata, test a fresh wheel installation outside the checkout, test Python 3.12–3.14, and audit the locked runtime graph. Pin GitHub Actions by commit, scan weekly and enable Action update PRs.
   - If skipped: Consumers could install a broken package despite passing checkout tests. **Resolved**; scans report known advisories only.

6. **Operational documentation was incomplete** (`README.md`, `docs/operations.md`, `SECURITY.md`).
   - What this is: Operators need to know what the server authenticates, how it fails and how to recover.
   - Problem: Update/rollback instructions, cancellation semantics, practical health checks, memory limits and license status were missing or unclear.
   - Fix: Add configuration and deployment guidance, an HTTPS proxy example, monitoring without bodies, rollback steps, verification limits and explicit license status.
   - If skipped: Operators could mistake tool discovery for dealer authentication or rely on a client timeout to stop upstream work. **Resolved in documentation**; no live deployment or license grant was made.

7. **Invalid date ranges reached the provider** (`src/edshop_mcp/server.py`).
   - What this is: Document-list tools accept date strings.
   - Problem: Impossible dates, noncanonical strings and reversed ranges passed the local schema and consumed upstream calls before failing.
   - Fix: Validate calendar dates and ordering, retaining the documented empty `dateTo` behavior.
   - If skipped: Avoidable provider calls and opaque upstream errors would remain. **Resolved**, with failing-before-fix regressions and valid-input coverage.

## Verification record

- 55 local tests pass, including all 17 operations and both MCP transports.
- The new overload/cancellation and invalid-date regressions failed against the old behavior before implementation.
- Independent runtime/build/test review found no material issues and reran all 55 tests.
- Wheel and sdist metadata pass Twine validation; a fresh wheel installation is checked through the official MCP SDK from an unrelated working directory.
- Locked runtime dependency audit found no known vulnerabilities on 2026-11-02.
- Fresh live configured stdio calls to `getSellerInfo` and `getProductList(onStock=true, limit=5)` succeeded after hardening; the latter returned five items out of 19,683 total products. Authenticated business responses and credentials are not committed.
- [GitHub Actions](https://github.com/thinkhome-org/edshop-mcp/actions) records the Python matrix, package checks, dependency audit and Docker HTTP smoke test for each published commit.

Verdict: The concrete audit findings above are addressed. Deployment still needs account-specific validation, trusted-client access controls and memory sizing for the actual catalogue.

Not checked: every operation against a real dealer account; native Claude Code, Cursor and Claude Desktop UIs; sustained load/capacity; a deployed HTTPS proxy; independent penetration testing; a separate container OS vulnerability scan. Local Docker daemon was unavailable, so container build/runtime checks run in CI. No PRIVATE API, OAuth service, hosted deployment or new software license was added.
