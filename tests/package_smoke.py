"""Run with a fresh wheel-installed interpreter, without source-tree imports."""
import asyncio
from pathlib import Path
import sys
import tempfile

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    executable = Path(sys.executable).parent / ('edshop-mcp.exe' if sys.platform == 'win32' else 'edshop-mcp')
    with tempfile.TemporaryDirectory() as directory:
        async with stdio_client(StdioServerParameters(command=str(executable), cwd=directory,
                                env={'EDSHOP_LOGIN': '', 'EDSHOP_PASSWORD': ''})) as (read, write):
            async with ClientSession(read, write) as session:
                assert (await session.initialize()).serverInfo.name == 'edshop-mcp'
                assert len((await session.list_tools()).tools) == 17
                result = await session.call_tool('getSellerInfo', {})
                assert result.isError and result.content[0].text == 'Missing API credentials.'
    print('Installed wheel: stdio initialization, 17 tools, sanitized missing-credentials result passed.')


if __name__ == '__main__':
    asyncio.run(main())
