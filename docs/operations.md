# Operating edshop-mcp

This guide targets one local client or a small, trusted group sharing an HTTP process. It is not a claim of high-volume capacity or a hosted service SLA. Start with [client configuration](clients.md).

## Deployment choices

| Use | Recommended setup |
|---|---|
| One local agent | stdio, dedicated API account, private environment file |
| Several trusted clients | Loopback Docker HTTP behind an HTTPS reverse proxy |
| Internet-facing service | Add network restrictions or gateway access control, rate limits and monitoring before allowing traffic |

HTTP requires dealer credentials on **every** request. The middleware checks presence and encoding; eD system authenticates them only when a tool calls SOAP. Initialization and tool discovery do not validate the account. This is not a public anonymous gateway. It stores no account database, persistent sessions or response cache.

## Configuration

| Setting | Default / meaning |
|---|---|
| `--transport stdio\|http` | `stdio` |
| `--host`, `--port` | `127.0.0.1`, `8000`; Docker listens inside its container on `0.0.0.0` |
| `EDSHOP_LOGIN`, `EDSHOP_PASSWORD` | Required for stdio; ignored for HTTP authentication |
| `EDSHOP_ESHOP_LOGIN`, `EDSHOP_ESHOP_PASSWORD` | Extra stdio account pair only for `getAuthTokenEshop` |
| `EDSHOP_ALLOWED_HOSTS` | Comma-separated additional Host values; localhost/127.0.0.1 are already allowed |
| `EDSHOP_MAX_CONCURRENT_CALLS` | `2`; positive integer, per process and across all accounts/transports |

The last setting limits **simultaneous SOAP work**, not response size. There is no fixed SOAP response byte cap. Overload returns an MCP tool error containing `Server busy`; no work is queued and no automatic retry happens. Choose a value after measuring peak memory for your catalogue. Multiple processes/replicas multiply capacity and memory use; this is not a distributed limiter or per-account quota.

A disconnected or cancelled caller cannot stop an already-running blocking SOAP request. Its capacity slot remains occupied until the worker exits. Requests has connection/read inactivity timeouts (20 seconds for WSDL, 60 seconds for an operation), not a strict total wall-clock deadline; a slow response that keeps delivering bytes can take longer. Avoid repeated retries after a client timeout, particularly for export generation and token issuance.

## Container

```sh
docker compose up --build -d
docker compose ps
```

The image installs the runtime dependency graph from `uv.lock`, runs as UID 10001 and contains no API credentials. Compose binds only `127.0.0.1:8000`, uses a read-only filesystem, drops Linux capabilities and disallows privilege escalation. No writable data volume is required. Docker's build and base-image tools still require network access; the Python base tag receives upstream updates, so retain a tested image digest for rollback.

For a low-impact local health check:

```sh
curl --silent --output /dev/null --write-out '%{http_code}\n' http://127.0.0.1:8000/mcp
```

Expected: `401`. This checks the HTTP process and credential middleware, not dealer authentication or upstream health. Separately test MCP initialization and a permitted live tool with your client. Do not put credentials in a health-check command or probe definition.

## HTTPS reverse proxy

Use an existing HTTPS proxy; do not open port 8000 directly to the Internet. Set `EDSHOP_ALLOWED_HOSTS=mcp.example.com` on the server. If the forwarded Host retains a port, include that exact host:port. Browser Origin requests are denied; these examples target native clients.

An Nginx configuration fragment (replace the hostname and certificate paths) is below. Place the zone declarations in the `http` block and the `server` block alongside your existing sites. Validate with `nginx -t` before applying it. This is an example, not an automatic deployment.

```nginx
limit_req_zone $binary_remote_addr zone=edshop_rate:10m rate=5r/s;
limit_conn_zone $binary_remote_addr zone=edshop_connections:10m;

server {
    listen 443 ssl;
    server_name mcp.example.com;
    ssl_certificate /path/to/fullchain.pem;
    ssl_certificate_key /path/to/privkey.pem;

    location = /mcp {
        limit_req zone=edshop_rate burst=20 nodelay;
        limit_conn edshop_connections 10;
        client_max_body_size 64k;
        access_log off;
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host mcp.example.com;
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 150s;
        proxy_send_timeout 150s;
    }
}
```

Nginx forwards the custom credential headers by default. The request-body setting limits incoming MCP arguments, not upstream SOAP responses. Adjust proxy/client timeouts together. Rate limits are illustrative; test them with the number of clients you intend to support. Restrict access with your existing firewall/VPN or gateway policy. No OAuth service is included.

Do not log credential headers, request/response bodies, tokens or export URLs at the proxy, APM agent or MCP client. Server dependency debug logs are suppressed, but client transcripts may intentionally store tool results. Treat that storage as dealer data.

## Capacity, data and failure behavior

- Each list call downloads and parses the full matching SOAP list. `limit` reduces returned MCP data only. Large catalogues consume memory even for a one-item page; no stress-tested capacity number is claimed.
- Pagination is not a snapshot. Upstream refreshes between calls can move items between offsets. Use exports when a full catalogue file is useful; the server returns export metadata and never downloads or polls it.
- Prices remain decimal strings. Stock is precomputed provider data, not a reservation guarantee.
- SOAP faults, invalid XML, application errors and network failures produce sanitized errors. Do not enable body logging to diagnose credentials. Use timestamps, operation names and provider-side support to investigate.
- Monitor process restarts, memory, busy errors, proxy status codes and latency without recording bodies. A single response can exhaust the host's available memory; provision capacity or use exports. The server intentionally does not impose a byte ceiling.

## Update and rollback

1. Record the running Git commit and container image ID/digest. Keep the previous image locally or in your registry.
2. Pull reviewed changes and run `uv sync --locked --extra test` and `uv run pytest -q` in a checkout. Verify the commit's CI, including package and container checks.
3. Build a new image with a distinct tag. Test initialization, discovery and a small authenticated request in your own environment before replacing the running service.
4. Recreate the service with the tested image/configuration. Watch memory, error rates and client compatibility.
5. To roll back, restore the previous image and matching configuration. There is no application database migration or persistent response state to reverse. An upstream export already requested is outside this rollback.

For a local stdio installation, record the commit, stop its clients, update the checkout and run `uv sync --locked`; restart clients. To roll back, check out the recorded commit and sync its lockfile. Keep private credential files outside the checkout.

## Verification and maintenance

CI tests Python 3.12–3.14, synthetic SOAP contracts, cancellation/load boundaries and both MCP transports. It builds an sdist/wheel, installs the wheel into a fresh environment, checks distribution metadata, audits the locked runtime dependencies against known advisories, and tests the built container. Scheduled CI repeats these checks weekly; Dependabot checks GitHub Actions updates.

A clean dependency scan is a dated advisory check, not proof that dependencies have no vulnerabilities. Review dependency updates with `uv lock --upgrade`, rerun the complete checks, and commit `pyproject.toml` and `uv.lock` together when both change. Current fixtures record the public WSDL input contract checked on 2026-11-02; provider changes require a deliberate contract review rather than silently replacing fixtures.

References: [uv Docker integration](https://docs.astral.sh/uv/guides/integration/docker/), [Docker Compose service options](https://docs.docker.com/reference/compose-file/services/), [Nginx proxy module](https://nginx.org/en/docs/http/ngx_http_proxy_module.html).
