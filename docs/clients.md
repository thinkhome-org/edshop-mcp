# Connect Codex, Claude Code, Cursor and Claude Desktop

All clients connect to the same 17 PUBLIC tools. Prefer **stdio for one local client**; use HTTP when clients share a server. This repository is a runnable MCP server, not a published plugin-store listing or a PyPI release.

## Install once

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then:

```sh
git clone https://github.com/thinkhome-org/edshop-mcp.git
cd edshop-mcp
uv sync --locked
uv run edshop-mcp --help
```

`uv` installs Python 3.12+ when needed. Use the installed executable's **absolute path** in client configuration: `/your/path/edshop-mcp/.venv/bin/edshop-mcp`, or `C:\your\path\edshop-mcp\.venv\Scripts\edshop-mcp.exe` on Windows. Replace every `/ABSOLUTE/PATH/...` placeholder below. No source-code modification is needed.

## Credentials

Use an eDshop **API account**, not an mPOHODA key. API credentials do not go in prompts or command arguments. The examples reference environment variables; set them before starting the client. Example for a fresh macOS/Linux terminal:

```sh
read -r EDSHOP_LOGIN
read -rs EDSHOP_PASSWORD
export EDSHOP_LOGIN EDSHOP_PASSWORD
```

Enter the login, then the password at the two prompts (password input is hidden). Start `codex`, `claude`, or Cursor from this same environment. A GUI app already running from the Dock/Start menu may **not** inherit new terminal variables. Fully quit it first, or use the credential-file launcher below. Do not add secrets to shell history, shared dotfiles, or project configuration.

For the optional `getAuthTokenEshop`, also set `EDSHOP_ESHOP_LOGIN` and `EDSHOP_ESHOP_PASSWORD`. This method returns a sensitive token; other tools do not need those variables.

## Client recipes

Merge the `edshop` entry into existing settings rather than replacing the entire file. Choose **one** transport per client.

| Client | stdio example | HTTP example | Destination |
|---|---|---|---|
| Codex | [TOML](../examples/clients/codex-stdio.toml) | [TOML](../examples/clients/codex-http.toml) | `~/.codex/config.toml` |
| Claude Code | [JSON](../examples/clients/claude-code-stdio.json) | [JSON](../examples/clients/claude-code-http.json) | Project `.mcp.json` |
| Cursor | [JSON](../examples/clients/cursor-stdio.json) | [JSON](../examples/clients/cursor-http.json) | `~/.cursor/mcp.json` or project `.cursor/mcp.json` |
| Claude Desktop | [JSON](../examples/clients/claude-desktop-stdio.json) | Not claimed by this guide | Developer → Edit Config |

### Codex

The stdio example uses `env_vars`; HTTP uses `env_http_headers`. These are environment-variable **names**, not values and not `${...}` interpolation. The sample tool timeout is 120 seconds to accommodate upstream WSDL loading plus a SOAP request.

After saving, restart the client and inspect `/mcp` (CLI) or the MCP server settings. `codex mcp get edshop` checks the saved entry; discovery should expose 17 tools. Do not run `codex mcp login edshop`: this server does not implement OAuth.

For token generation over HTTP extend `env_http_headers` with:

```toml
"X-Edshop-Eshop-Login" = "EDSHOP_ESHOP_LOGIN"
"X-Edshop-Eshop-Password" = "EDSHOP_ESHOP_PASSWORD"
```

Add these entries inside the existing inline table, separated by commas, or convert that table to TOML's expanded table syntax.

### Claude Code

The project `.mcp.json` examples use `${EDSHOP_LOGIN:-}` and `${EDSHOP_PASSWORD:-}`. Empty defaults prevent an unset variable becoming the literal placeholder sent upstream. Approve the project MCP server when Claude Code prompts, then inspect `/mcp`. `claude mcp list` reports connection status.

For token generation add `EDSHOP_ESHOP_LOGIN` / `EDSHOP_ESHOP_PASSWORD` to the stdio `env` map with `${EDSHOP_ESHOP_LOGIN:-}` / `${EDSHOP_ESHOP_PASSWORD:-}`. For HTTP use `X-Edshop-Eshop-Login` / `X-Edshop-Eshop-Password` headers with those same values. No `claude mcp add --header ...password...` command is necessary.

### Cursor

Cursor uses `${env:EDSHOP_LOGIN}` syntax, which differs from Claude Code. Set both variables before launch. For stdio, Cursor also supports `envFile`; a private absolute file path can replace the sample `env` map. Its HTTP configuration does not support `envFile`; use the supplied `headers` and launch Cursor with the variables available.

For token generation add the two optional credential variables to stdio `env` or their corresponding HTTP headers using `${env:EDSHOP_ESHOP_LOGIN}` / `${env:EDSHOP_ESHOP_PASSWORD}`. Inspect the server in Cursor MCP settings and enable its tools for the agent.

### Claude Desktop and other GUI clients

Do not assume shell-variable interpolation works in Claude Desktop's JSON. The provided recipe starts `uv run --no-project --env-file /private/edshop.env /absolute/edshop-mcp`; only paths appear in the client config.

1. Copy `.env.example` to a private location **outside the repository**, edit its credential values locally, and restrict its permissions (for example `chmod 600 /private/edshop.env` on macOS/Linux; an account-only ACL on Windows). This is a plaintext credential file, not a keychain.
2. Locate uv with `command -v uv` (Windows: `where uv`). Put its absolute path in `command`.
3. Replace the credential-file and executable paths in the recipe. On Windows use escaped JSON backslashes or forward slashes.
4. Merge the example under `mcpServers` in Developer → Edit Config, then fully quit and reopen Claude Desktop.

This launcher can also be used for the other clients' stdio entries when GUI environment inheritance is inconvenient. The server itself still does not auto-load `.env`; uv explicitly loads only the file named in the recipe. Existing process environment values take precedence over the file, so remove conflicting `EDSHOP_*` values when switching accounts.

## HTTP server first

Start the server separately:

```sh
uv run edshop-mcp --transport http
# Or:
docker compose up --build -d
```

The local examples point to `http://127.0.0.1:8000/mcp`. For remote use replace that URL with your **HTTPS** endpoint and configure the server's `EDSHOP_ALLOWED_HOSTS` as described in [README](../README.md#streamable-http). `localhost` means the machine running the client; a cloud-hosted client cannot reach your laptop's loopback endpoint.

Every request supplies the two API headers; each client may use a different dealer account. The server never substitutes a shared environment account. A client that only supports OAuth, or cannot send custom headers, cannot use this HTTP setup directly. No compatibility with Claude.ai/ChatGPT cloud connector UIs is claimed.

## Verify and troubleshoot

1. Discover **17 tools**. This checks installation and MCP compatibility, not dealer authorization.
2. With your API account configured, ask the client to call `getSellerInfo`. A successful seller response is the first authenticated live check.
3. Then try a small recent invoice range or a limited product page. An API permission error still requires checking the dealer account.

| Symptom | Check |
|---|---|
| Executable not found / ENOENT | Absolute executable path; on Windows use `.venv/Scripts/edshop-mcp.exe`. |
| Missing API credentials / HTTP 401 | Client process environment, correct interpolation syntax and both credential headers. |
| Missing e-shop credentials | Only token generation needs the extra e-shop account pair. |
| Invalid Host / HTTP 421 | Add the exact remote host (and port when present) to `EDSHOP_ALLOWED_HOSTS`. |
| SOAP request failed / rejected | Upstream connectivity, API account status and rights; errors deliberately hide raw provider text. |
| Tool timeout | Codex/Claude examples allow 120 seconds; increase the corresponding client limit if needed. |
| Server busy | Wait for active SOAP calls to finish, then retry intentionally; see [capacity](operations.md#configuration). |
| Invalid dates | Use real `YYYY-MM-DD` dates; `dateTo` may be empty or on/after `dateFrom`. |
| Large result | Lower `limit` to reduce MCP output; the full SOAP response is still loaded into memory. Export is optional. |

## Verification evidence and limits

Automated recipe tests parse all seven example files, substitute **synthetic** credentials, and exercise MCP initialization, discovery and calls. stdio recipes run the installed executable from an unrelated working directory, including the GUI credential-file launcher. HTTP recipes use the official SDK client with synthetic SOAP results. CI separately exercises a real TCP connection to the built Docker container.

Codex CLI 0.154.0 accepted both configuration shapes using non-persistent command-line overrides. Native Claude Code, Claude Desktop and Cursor UI sessions have not been exercised. These recipes are based on their official configuration documentation; protocol tests are not a substitute for those UI checks. A real authenticated `getProductList(onStock=true, limit=5)` call through the existing Codex stdio configuration succeeded on 2026-11-02. Live account validation of the HTTP clients and other operations remains outside this check.

Official references (checked 2026-11-02): [Codex MCP](https://developers.openai.com/codex/mcp), [Claude Code MCP](https://code.claude.com/docs/en/mcp), [Cursor MCP](https://cursor.com/docs/mcp), [Claude Desktop local MCP setup](https://modelcontextprotocol.io/docs/develop/connect-local-servers), [uv environment files](https://docs.astral.sh/uv/reference/environment/#uv_env_file).
