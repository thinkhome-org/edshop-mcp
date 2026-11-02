# Security

This server handles dealer credentials, commercial data, token responses and private export URLs. Use dedicated eDshop API accounts with only the required permissions. Keep credentials out of prompts, tool arguments, Git, Docker images, support issues and CI variables unless a controlled live test specifically requires them.

The current `main` branch receives fixes; there is no published release support schedule. Use reviewed commits and the committed dependency lock. No hosted service is operated by this repository.

Report a suspected vulnerability privately through [GitHub private vulnerability reporting](https://github.com/thinkhome-org/edshop-mcp/security/advisories/new) **if the repository has it enabled**. If unavailable, contact the organization maintainers through an established private channel. Do not open a public issue containing credentials, dealer data or exploit details. Rotate exposed credentials with the provider; deleting a Git commit is not credential revocation.

Reports should include the affected commit, transport, sanitized reproduction, expected and observed behavior. Do not include a real API password, e-shop token, exported business document or raw SOAP response.

See [the operating guide](docs/operations.md) for the authentication boundary, HTTPS proxy setup, concurrency/cancellation behavior and resource limits. XML DTDs/entities/external references and upstream HTTP redirects are refused. HTTP credentials are scoped to each request and never fall back to server environment credentials. These controls do not replace trusted-client access controls, host capacity planning or client transcript protection.
