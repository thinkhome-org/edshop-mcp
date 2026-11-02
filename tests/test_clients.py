"""Exercise the shipped launch recipes without touching users' client settings."""
import json
import os
from pathlib import Path
import shutil
import sys
import tomllib

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client
import pytest

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / 'examples' / 'clients'

@pytest.mark.parametrize('filename', ['codex-stdio.toml', 'claude-code-stdio.json', 'cursor-stdio.json', 'claude-desktop-stdio.json'])
async def test_client_stdio_recipe(filename, tmp_path):
    raw = (EXAMPLES / filename).read_text()
    executable = str(Path(sys.executable).parent / ('edshop-mcp.exe' if os.name == 'nt' else 'edshop-mcp'))
    assert Path(executable).exists(), 'Install the project before running compatibility tests.'
    credentials = tmp_path / 'edshop.env'
    credentials.write_text('EDSHOP_LOGIN=synthetic-user\nEDSHOP_PASSWORD=synthetic-password\n')
    credentials.chmod(0o600)
    raw = raw.replace('/ABSOLUTE/PATH/edshop-mcp/.venv/bin/edshop-mcp', executable)
    raw = raw.replace('/ABSOLUTE/PATH/private/edshop.env', str(credentials))
    raw = raw.replace('/ABSOLUTE/PATH/uv', shutil.which('uv') or 'uv')
    config = (tomllib.loads(raw)['mcp_servers'] if filename.endswith('.toml') else json.loads(raw)['mcpServers'])['edshop']
    # Emulate only documented client substitutions. Native UI behavior is a separate check.
    env = {'EDSHOP_LOGIN': 'synthetic-user', 'EDSHOP_PASSWORD': 'synthetic-password'}
    for key, value in config.get('env',{}).items():
        if value in ('${EDSHOP_LOGIN:-}', '${env:EDSHOP_LOGIN}'): value = env['EDSHOP_LOGIN']
        if value in ('${EDSHOP_PASSWORD:-}', '${env:EDSHOP_PASSWORD}'): value = env['EDSHOP_PASSWORD']
        env[key] = value
    if filename == 'claude-desktop-stdio.json': env = {}
    params = StdioServerParameters(command=config['command'],args=config.get('args',[]),env=env,cwd=str(tmp_path))
    async with stdio_client(params) as (read,write):
        async with ClientSession(read,write) as session:
            assert (await session.initialize()).serverInfo.name == 'edshop-mcp'
            assert len((await session.list_tools()).tools) == 17
            # This proves credentials reach the subprocess, without sending any upstream request.
            result = await session.call_tool('getAuthTokenEshop', {'idEshop': 1})
            assert result.isError and result.content[0].text == 'Missing e-shop credentials.'

@pytest.mark.parametrize('filename', ['codex-http.toml','claude-code-http.json','cursor-http.json'])
async def test_client_http_recipe(filename, monkeypatch):
    from edshop_mcp.server import create_http_app
    from edshop_mcp import soap
    raw=(EXAMPLES / filename).read_text()
    config=(tomllib.loads(raw)['mcp_servers'] if filename.endswith('.toml') else json.loads(raw)['mcpServers'])['edshop']
    env={'EDSHOP_LOGIN':'synthetic-user','EDSHOP_PASSWORD':'synthetic-password'}
    if 'env_http_headers' in config:
        headers={key:env[value] for key,value in config['env_http_headers'].items()}
    else:
        headers={key:value.replace('${EDSHOP_LOGIN:-}',env['EDSHOP_LOGIN']).replace('${EDSHOP_PASSWORD:-}',env['EDSHOP_PASSWORD']).replace('${env:EDSHOP_LOGIN}',env['EDSHOP_LOGIN']).replace('${env:EDSHOP_PASSWORD}',env['EDSHOP_PASSWORD']) for key,value in config['headers'].items()}
    def fake_call(name,args,auth):
        assert auth.login==env['EDSHOP_LOGIN'] and auth.password==env['EDSHOP_PASSWORD']
        return {'Status':{'StatusCode':'DONE'}}
    monkeypatch.setattr(soap,'call',fake_call)
    app=create_http_app()
    async with app.app.router.lifespan_context(app.app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),headers=headers) as http:
            async with streamable_http_client(config['url'], http_client=http) as (read,write,_):
                async with ClientSession(read,write) as session:
                    assert (await session.initialize()).serverInfo.name=='edshop-mcp'
                    assert len((await session.list_tools()).tools)==17
                    result=await session.call_tool('getSellerInfo',{})
                    assert not result.isError
                    assert result.structuredContent=={'Status':{'StatusCode':'DONE'}}
