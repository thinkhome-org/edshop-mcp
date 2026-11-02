from decimal import Decimal
import pytest
from edshop_mcp.soap import normalize, paginate, Credentials, EdshopError
from edshop_mcp.server import tools, credentials


def test_public_catalog():
    catalog = tools()
    assert len(catalog) == 17
    assert not any(t.name.endswith('_INT') for t in catalog)
    for tool in catalog:
        assert 'login' not in tool.inputSchema['properties']
        assert 'password' not in str(tool.inputSchema)


def test_money_and_errors():
    assert normalize({'Price': Decimal('123.4500')}) == {'Price': '123.4500'}
    with pytest.raises(EdshopError, match='Upstream rejected'):
        normalize({'Status': {'StatusCode': 'ERROR', 'ErrorText': 'secret'}})


def test_pagination():
    data = {'Status': {'StatusCode': 'DONE'}, 'ProductList': {'Product': list(range(205))}}
    result = paginate(data, 'getProductList', 200, 50)
    assert result['data']['ProductList']['Product'] == list(range(200,205))
    assert result['total'] == 205
    assert result['nextOffset'] is None
    assert paginate(data, 'getProductList', 0, 50)['nextOffset'] == 50
    assert paginate({'ProductList': None}, 'getProductList', 0, 50)['total'] == 0


def test_http_never_falls_back(monkeypatch):
    monkeypatch.setenv('EDSHOP_LOGIN', 'environment-user')
    monkeypatch.setenv('EDSHOP_PASSWORD', 'environment-password')
    with pytest.raises(EdshopError): credentials('http')
    assert credentials('stdio').login == 'environment-user'

async def test_http_concurrent_accounts_and_missing_headers(monkeypatch):
    import asyncio
    import time
    import httpx
    from edshop_mcp.server import create_http_app
    from edshop_mcp import soap
    def fake_call(name, args, auth):
        time.sleep(0.02)
        return {'account': auth.login}
    monkeypatch.setattr(soap, 'call', fake_call)
    app = create_http_app()
    async with app.app.router.lifespan_context(app.app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://localhost') as c:
            async def invoke(user):
                return await c.post('/mcp', headers={'Accept':'application/json, text/event-stream',
                    'X-Edshop-Login': user, 'X-Edshop-Password':'secret'},
                    json={'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'getSellerInfo','arguments':{}}})
            a,b = await asyncio.gather(invoke('alice'),invoke('bob'))
            assert a.json()['result']['structuredContent']['account'] == 'alice'
            assert b.json()['result']['structuredContent']['account'] == 'bob'
            missing = await c.post('/mcp',json={'jsonrpc':'2.0','id':2,'method':'tools/list'})
            assert missing.status_code == 401

async def test_stdio_protocol():
    import os, sys
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    params = StdioServerParameters(command=sys.executable, args=['-m','edshop_mcp.server'],
        env={'PYTHONPATH':os.path.abspath('src')})
    async with stdio_client(params) as (read,write):
        async with ClientSession(read,write) as session:
            result = await session.initialize()
            assert result.serverInfo.name == 'edshop-mcp'
            catalog = await session.list_tools()
            assert len(catalog.tools) == 17
            response = await session.call_tool('getSellerInfo',{})
            assert response.isError
            assert 'Missing API credentials' in response.content[0].text

async def test_http_protocol_and_validation(monkeypatch, caplog):
    import logging
    import httpx
    from edshop_mcp.server import create_http_app
    from edshop_mcp import soap
    caplog.set_level(logging.DEBUG)
    calls = []
    def fake_call(name,args,auth):
        calls.append((name,args,auth))
        return {'Status':{'StatusCode':'DONE'}}
    monkeypatch.setattr(soap,'call',fake_call)
    app=create_http_app()
    headers={'Accept':'application/json, text/event-stream','X-Edshop-Login':'test-user',
             'X-Edshop-Password':'private-api-password','X-Edshop-Eshop-Login':'shop',
             'X-Edshop-Eshop-Password':'private-shop-password'}
    async with app.app.router.lifespan_context(app.app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://localhost',headers=headers) as c:
            async def rpc(method,params):
                r=await c.post('/mcp',json={'jsonrpc':'2.0','id':1,'method':method,'params':params})
                assert r.status_code==200
                return r.json()['result']
            init=await rpc('initialize',{'protocolVersion':'2025-03-26','capabilities':{},'clientInfo':{'name':'test','version':'1'}})
            assert init['serverInfo']['name']=='edshop-mcp'
            assert len((await rpc('tools/list',{}))['tools'])==17
            await rpc('tools/call',{'name':'getAuthTokenEshop','arguments':{'idEshop':1}})
            assert calls[-1][2].eshop_password=='private-shop-password'
            for name,args in [
                ('getProductList',{'onStock':True,'limit':201}),
                ('getProductList',{'onStock':True,'offset':-1}),
                ('getProductListDownloadXML',{'onStock':True,'encoding':'invalid'}),
                ('getProductListDownloadXMLWithTransform',{'onStock':True,'encoding':'UTF-8','transformation':'EDLINKOLDXML','fileFormat':'CSV'}),
                ('getSellerInfo',{'password':'private-injected-password'}),
                ('getInvoiceListDownloadXMLWithTransform_INT',{}),
            ]:
                out=await rpc('tools/call',{'name':name,'arguments':args})
                assert out['isError']
                assert 'private-injected-password' not in str(out)
            assert len(calls)==1
    assert 'private-api-password' not in caplog.text
    assert 'private-shop-password' not in caplog.text
    assert 'private-injected-password' not in caplog.text
