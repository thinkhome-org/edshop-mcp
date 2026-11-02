# edshop-mcp

[![CI](https://github.com/thinkhome-org/edshop-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/thinkhome-org/edshop-mcp/actions/workflows/ci.yml)

MCP server for the Czech eD system **PUBLIC** data-exchange API. All 17 documented operations, stdio and stateless Streamable HTTP, with a separate dealer account per HTTP request.

PUBLIC means the basic API variant, **not anonymous data access**. Obtain a dedicated API account through eDshop dealer administration. This project is unofficial and is not affiliated with eD system or ELINKX.

## Start here

- [Client setup](docs/clients.md): Codex, Claude Code, Cursor and Claude Desktop.
- [Operating guide](docs/operations.md): deployment, capacity, HTTPS, monitoring, updates and rollback.
- [Security policy](SECURITY.md) and [audit findings/resolutions](docs/audit.md).

The server is tested for local use and small trusted HTTP deployments. It is not a managed service, high-volume benchmark or guarantee that every provider operation works for every account. The repository is public; no PyPI package or plugin-store installation is published.

## Install and run

Start with the [client setup guide](docs/clients.md) for **Codex, Claude Code, Cursor and Claude Desktop**, including seven ready-to-edit stdio/HTTP configurations and credential handling.

```sh
git clone https://github.com/thinkhome-org/edshop-mcp.git
cd edshop-mcp
uv sync --locked
uv run edshop-mcp --help
```

Requires [uv](https://docs.astral.sh/uv/getting-started/installation/); it provisions Python 3.12+. Alternatively install this checkout with Python 3.12+: `python -m pip install .`. The default transport is stdio. `.env` is not automatically loaded. Supply credentials through the client environment or the explicit private-file launcher in the guide.

For a local smoke check, create a private credential file outside the checkout from [.env.example](.env.example), restrict its permissions and configure your client using the [stdio recipe](docs/clients.md#claude-desktop-and-other-gui-clients). Discover 17 tools, then call `getSellerInfo` with your permitted API account. Discovery alone does not verify dealer access. Never paste real credentials into a command line or an issue.

For `getAuthTokenEshop`, additionally provide `EDSHOP_ESHOP_LOGIN` and `EDSHOP_ESHOP_PASSWORD`; `idEshop` is an ordinary tool argument. The returned token is deliberately delivered to the requesting MCP client and is sensitive. It is **not OAuth**.

## Streamable HTTP

```sh
uv run edshop-mcp --transport http
```

Endpoint: `http://127.0.0.1:8000/mcp`. Every request, including initialization and listing tools, must supply:

| Header | Meaning |
|---|---|
| `X-Edshop-Login` | Dealer API login |
| `X-Edshop-Password` | Dealer API password |
| `X-Edshop-Eshop-Login` | Additional e-shop login, only for token generation |
| `X-Edshop-Eshop-Password` | Additional e-shop password, only for token generation |

There is no server-side account database, credential cache, shared cookie jar, or fallback to stdio environment credentials. The API provider validates credentials on tool execution; providing headers alone does not prove an account is valid. Metadata discovery does not call the provider.

Clients must support custom headers. Native upstream OAuth was not found in the supplied documentation or WSDL; an OAuth-only MCP client cannot use this server directly.

For remote access use **HTTPS** through a trusted reverse proxy and set `EDSHOP_ALLOWED_HOSTS=mcp.example.com` (include the port if your proxy retains a non-default port in Host). Preserve the listed headers; do not log them, SOAP bodies, export URLs, or tool responses. Browser origins are denied by default. Do not expose the plain HTTP listener directly to the Internet. The proxy should provide request-rate and connection limits. See the [proxy example and operating boundaries](docs/operations.md#https-reverse-proxy).

## Docker

```sh
docker compose up --build -d
```

Compose binds **127.0.0.1:8000** only. The image installs `uv.lock` runtime dependencies, runs as a non-root user, and Compose uses a read-only filesystem with dropped capabilities. No dealer credentials belong in the image or Compose file. HTTP clients supply their own headers.

For stdio:

```sh
docker build -t edshop-mcp .
docker run --rm -i -e EDSHOP_LOGIN -e EDSHOP_PASSWORD edshop-mcp --transport stdio
```

## Tools

Names and business parameters follow the official WSDL. Credentials never appear in tool argument schemas.

| Tools | Parameters (besides credentials) |
|---|---|
| `getClaimList`, `getDeliveryList`, `getExpeditionList`, `getOrderList`, `getInvoiceList` | `dateFrom`, `dateTo`, optional `offset`, `limit` |
| `getDeliveryDetail` | `deliverySymbol` |
| `getExpeditionDetail` | `expeditionSymbol` |
| `getOrderDetail` | `orderSymbol` |
| `getInvoiceDetail` | `invoiceSymbol` |
| `getInvoiceDetailDownloadXMLWithTransform` | `invoiceSymbol`, `transformation`, `encoding` |
| `getProductList` | `onStock`, optional `offset`, `limit` |
| `getProductListDownloadXML`, `getProductListDownloadZIP` | `encoding`, `onStock` |
| `getProductListDownloadXMLWithTransform` | `transformation`, `encoding`, `onStock`, `fileFormat` |
| `getProductListDownloadZIPWithTransform` | Same, plus `soldItemsOnly` |
| `getSellerInfo` | None |
| `getAuthTokenEshop` | `idEshop` |

- Dates: valid `YYYY-MM-DD`, with `dateTo` on/after `dateFrom`; an empty `dateTo` delegates the end date to the provider. Document list history is limited by the provider: the PDF says 31 days, the live service description says 30. This is not an arbitrary historical archive.
- List pagination is **local over the whole SOAP response**, default `limit=50`, maximum 200. The wrapper returns `data`, `total`, `offset`, `nextOffset`, and a pagination notice. This limits MCP output, not upstream download cost. A changing upstream list can change offsets between calls.
- Original upstream field names and metadata are retained. Decimal amounts are JSON strings to preserve precision; dates use ISO formatting. Do not interpret default-valued list fields as authoritative detail data: use the detail operation.
- Catalogue data is precomputed (documented refreshes twice daily, prices/availability hourly), not a live stock reservation.
- Export tools return provider status and `isReady`, `url`, `fileName` within their original response structure. `isReady=false` means not ready. No automatic file download or polling occurs. Repeated exports can return already-generated data. Treat export URLs as private.
- Encodings: `UTF-8`, `windows-1250`. Product transformations: `EDLINKOLDXML` / `XML`, `EDLINKOLDCSV` / `CSV`, `EDLINKXLS` / `XLS`; mismatched pairs are rejected. Invoice transformations: `INVOICEOLD`, `ISDOC_5` (5.3.1), `ISDOC_6` (6.0.1).
- SOAP/application errors are sanitized; raw provider error text is not returned because it can contain secrets. Network connection/read inactivity timeouts are 20 seconds for WSDL and 60 seconds for an operation; they are not total wall-clock deadlines. No automatic retries. No fixed response byte cap is imposed; full SOAP responses are loaded into memory before local pagination. Redirects are refused to avoid forwarding credentials.

- SOAP work is limited to two simultaneous calls per process by default (`EDSHOP_MAX_CONCURRENT_CALLS`). Additional calls fail fast with `Server busy`. Cancellation keeps the slot occupied until the blocking worker finishes. This is a concurrency setting, **not a response byte cap**.

## Development and verification

```sh
uv sync --extra test --locked
uv run pytest -q
uv build --no-sources
```

Tests use synthetic SOAP payloads and an independently captured public WSDL input-contract fixture, not real dealer data. They cover all 17 methods, XML/Unicode serialization, precision, sanitized errors, exports, pagination, stdio/HTTP, account isolation, overload and cancellation. CI checks Python 3.12–3.14, builds and validates wheel/sdist packages, exercises a fresh wheel installation, audits locked dependencies and builds/runs the hardened Docker image. See [audit evidence and remaining limits](docs/audit.md).

Real authenticated `getSellerInfo` and `getProductList(onStock=true, limit=5)` calls through the configured stdio MCP client succeeded on 2026-11-02, including after the hardening changes. Other operations have synthetic contract coverage; this does not verify every operation against a live account. Never use credentials for another product such as mPOHODA.

## Sources and boundaries

- [PUBLIC service and WSDL](https://public-ws-cz.elinkx.biz/)
- [PUBLIC documentation](https://public-ws-cz.elinkx.biz/doc/publicdoc.pdf), version 2.22; service observed as 4.3.20.0.

The two `_INT` operations are excluded. No PRIVATE API, order creation, database, OAuth service, hosted deployment, or speculative extension framework. Full PRIVATE support is future work. Supplied PDFs, credentials, and business responses are not distributed in this repository.

## Contributing and license

Keep changes focused on the 17 PUBLIC methods and their documented contracts. Add a regression for changed behavior, run the checks above, and include sanitized verification evidence in a pull request. Do not commit dealer payloads, supplied PDFs, `.env` files or private keys. Dependency upgrades must include their lockfile changes and a complete CI run.

A software license has not been selected or added to this repository. No new license grant is made by these documentation changes; the maintainers must decide licensing separately.
