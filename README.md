# edshop-mcp

MCP server for the Czech eD system **PUBLIC** data-exchange API. All 17 documented operations, stdio and stateless Streamable HTTP, with a separate dealer account per HTTP request.

PUBLIC means the basic API variant, **not anonymous data access**. Obtain a dedicated API account through eDshop dealer administration. This project is unofficial and is not affiliated with eD system or ELINKX.

## Install and run

Start with the [client setup guide](docs/clients.md) for **Codex, Claude Code, Cursor and Claude Desktop**, including seven ready-to-edit stdio/HTTP configurations and credential handling.

```sh
git clone https://github.com/thinkhome-org/edshop-mcp.git
cd edshop-mcp
uv sync --locked
uv run edshop-mcp --help
```

Requires [uv](https://docs.astral.sh/uv/getting-started/installation/); it provisions Python 3.12+. Alternatively install this checkout with Python 3.12+: `python -m pip install .`. The default transport is stdio. `.env` is not automatically loaded. Supply credentials through the client environment or the explicit private-file launcher in the guide.

For `getAuthTokenEshop`, additionally provide `EDSHOP_ESHOP_LOGIN` and `EDSHOP_ESHOP_PASSWORD`; `idEshop` is an ordinary tool argument. The returned token is deliberately delivered to the requesting MCP client and is sensitive. It is **not OAuth**.

## Streamable HTTP

```sh
edshop-mcp --transport http
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

For remote access use **HTTPS** through a trusted reverse proxy and set `EDSHOP_ALLOWED_HOSTS=mcp.example.com` (include the port if your proxy retains a non-default port in Host). Preserve the listed headers; do not log them, SOAP bodies, export URLs, or tool responses. Browser origins are denied by default. Do not expose the plain HTTP listener directly to the Internet. The proxy should provide request-rate and connection limits.

## Docker

```sh
docker compose up --build -d
```

Compose binds **127.0.0.1:8000** only. No dealer credentials belong in the image or Compose file. HTTP clients supply their own headers.

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

- Dates: `YYYY-MM-DD`; an empty `dateTo` delegates the end date to the provider. Document list history is limited by the provider: the PDF says 31 days, the live service description says 30. This is not an arbitrary historical archive.
- List pagination is **local over the whole SOAP response**, default `limit=50`, maximum 200. The wrapper returns `data`, `total`, `offset`, `nextOffset`, and a pagination notice. This limits MCP output, not upstream download cost. A changing upstream list can change offsets between calls.
- Original upstream field names and metadata are retained. Decimal amounts are JSON strings to preserve precision; dates use ISO formatting. Do not interpret default-valued list fields as authoritative detail data: use the detail operation.
- Catalogue data is precomputed (documented refreshes twice daily, prices/availability hourly), not a live stock reservation.
- Export tools return provider status and `isReady`, `url`, `fileName` within their original response structure. `isReady=false` means not ready. No automatic file download or polling occurs. Repeated exports can return already-generated data. Treat export URLs as private.
- Encodings: `UTF-8`, `windows-1250`. Product transformations: `EDLINKOLDXML` / `XML`, `EDLINKOLDCSV` / `CSV`, `EDLINKXLS` / `XLS`; mismatched pairs are rejected. Invoice transformations: `INVOICEOLD`, `ISDOC_5` (5.3.1), `ISDOC_6` (6.0.1).
- SOAP/application errors are sanitized; raw provider error text is not returned because it can contain secrets. Network timeouts are 20 seconds for WSDL and 60 seconds for an operation. No automatic retries. Responses over 32 MiB are rejected with an export recommendation; no silent truncation. Redirects are refused to avoid forwarding credentials.

## Development and verification

```sh
uv sync --extra test --locked
uv run pytest -q
```

Tests use synthetic WSDL/SOAP payloads, not real dealer data. They cover the operation catalog, parameter serialization, precision, error handling, exports, stdio, HTTP and concurrent account separation. CI also builds and starts the Docker image.

A real authenticated call has **not** been verified without a dedicated eDshop API account. A live smoke check should start with `getSellerInfo`; never use credentials for another product such as mPOHODA.

## Sources and boundaries

- [PUBLIC service and WSDL](https://public-ws-cz.elinkx.biz/)
- [PUBLIC documentation](https://public-ws-cz.elinkx.biz/doc/publicdoc.pdf), version 2.22; service observed as 4.3.20.0.

The two `_INT` operations are excluded. No PRIVATE API, order creation, database, OAuth service, hosted deployment, or speculative extension framework. Full PRIVATE support is future work. Supplied PDFs, credentials, and business responses are not distributed in this repository.
