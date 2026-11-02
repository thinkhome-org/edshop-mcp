"""Run against an already-started container; never call the upstream service."""
import asyncio
import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

async def main():
    async with httpx.AsyncClient(headers={
        'X-Edshop-Login': 'synthetic-ci-user',
        'X-Edshop-Password': 'synthetic-ci-password',
    }) as http:
        async with streamable_http_client('http://127.0.0.1:8000/mcp', http_client=http) as (read,write,_):
            async with ClientSession(read,write) as session:
                assert (await session.initialize()).serverInfo.name == 'edshop-mcp'
                assert len((await session.list_tools()).tools) == 17
                result = await session.call_tool('getAuthTokenEshop', {'idEshop': 1})
                assert result.isError
                assert result.content[0].text == 'Missing e-shop credentials.'
    print('Container SDK handshake, discovery and credential-scoped call passed.')

if __name__ == '__main__':
    asyncio.run(main())
