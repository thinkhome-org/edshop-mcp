"""Load, cancellation and HTTP boundary regressions; no live API calls."""
import asyncio
import threading

import httpx
import pytest
from mcp.types import CallToolRequest, CallToolRequestParams

from edshop_mcp import soap
from edshop_mcp.server import create_http_app, create_server


def tool_request(name='getSellerInfo', arguments=None):
    return CallToolRequest(method='tools/call', params=CallToolRequestParams(name=name, arguments=arguments or {}))


@pytest.mark.parametrize('cancel_first', [False, True])
async def test_overload_does_not_start_another_call_even_after_cancellation(monkeypatch, cancel_first):
    monkeypatch.setenv('EDSHOP_MAX_CONCURRENT_CALLS', '1')
    monkeypatch.setenv('EDSHOP_LOGIN', 'synthetic')
    monkeypatch.setenv('EDSHOP_PASSWORD', 'synthetic')
    started, release, finished = threading.Event(), threading.Event(), threading.Event()
    calls = []
    def blocked_call(name, arguments, auth):
        calls.append(auth.login)
        started.set()
        release.wait(3)
        finished.set()
        return {'ok': True}
    monkeypatch.setattr(soap, 'call', blocked_call)
    handler = create_server().request_handlers[CallToolRequest]
    first = asyncio.create_task(handler(tool_request()))
    try:
        assert await asyncio.to_thread(started.wait, 1)
        if cancel_first:
            first.cancel()
            with pytest.raises(asyncio.CancelledError):
                await first
        second = await asyncio.wait_for(handler(tool_request()), timeout=0.5)
        assert second.root.isError
        assert 'busy' in second.root.content[0].text
        assert calls == ['synthetic']
    finally:
        release.set()
        await asyncio.gather(first, return_exceptions=True)
        assert await asyncio.to_thread(finished.wait, 1)
        await asyncio.sleep(0.02)
    recovered = await handler(tool_request())
    assert not recovered.root.isError


@pytest.mark.parametrize('arguments', [
    {'dateFrom': 'not-a-date', 'dateTo': ''},
    {'dateFrom': '2026-02-30', 'dateTo': ''},
    {'dateFrom': '2026-11-02', 'dateTo': '2026-11-01'},
])
async def test_invalid_dates_never_reach_provider(monkeypatch, arguments):
    monkeypatch.setenv('EDSHOP_LOGIN', 'synthetic')
    monkeypatch.setenv('EDSHOP_PASSWORD', 'synthetic')
    calls = []
    monkeypatch.setattr(soap, 'call', lambda *args: calls.append(args) or {})
    handler = create_server().request_handlers[CallToolRequest]
    result = await handler(tool_request('getInvoiceList', arguments))
    assert result.root.isError
    assert calls == []


@pytest.mark.parametrize('extra,status', [
    ({'Host': 'attacker.invalid'}, 421),
    ({'Origin': 'https://attacker.invalid'}, 403),
])
async def test_http_security_rejects_foreign_hosts_and_origins(extra, status):
    app = create_http_app()
    async with app.app.router.lifespan_context(app.app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://localhost') as client:
            response = await client.post('/mcp', headers={
                'X-Edshop-Login': 'synthetic', 'X-Edshop-Password': 'synthetic', **extra,
            }, json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'})
            assert response.status_code == status


async def test_invalid_utf8_credential_header_is_sanitized():
    app = create_http_app()
    async with app.app.router.lifespan_context(app.app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://localhost') as client:
            response = await client.post('/mcp', headers=[(b'x-edshop-login', b'\xff'), (b'x-edshop-password', b'secret')])
            assert response.status_code == 400
            assert response.json() == {'error': 'Invalid credential headers.'}


@pytest.mark.parametrize('value', ['0', '-1', 'invalid'])
def test_invalid_concurrency_fails_at_startup(monkeypatch, value):
    monkeypatch.setenv('EDSHOP_MAX_CONCURRENT_CALLS', value)
    with pytest.raises(ValueError, match='positive integer'):
        create_server()


async def test_failed_worker_releases_capacity(monkeypatch):
    monkeypatch.setenv('EDSHOP_MAX_CONCURRENT_CALLS', '1')
    monkeypatch.setenv('EDSHOP_LOGIN', 'synthetic')
    monkeypatch.setenv('EDSHOP_PASSWORD', 'synthetic')
    def failure(*args):
        raise soap.EdshopError('Upstream rejected the request.')
    monkeypatch.setattr(soap, 'call', failure)
    handler = create_server().request_handlers[CallToolRequest]
    first = await handler(tool_request())
    assert first.root.isError
    monkeypatch.setattr(soap, 'call', lambda *args: {'ok': True})
    assert not (await handler(tool_request())).root.isError


async def test_empty_date_to_and_unicode_symbol_remain_valid(monkeypatch):
    monkeypatch.setenv('EDSHOP_LOGIN', 'synthetic')
    monkeypatch.setenv('EDSHOP_PASSWORD', 'synthetic')
    monkeypatch.setattr(soap, 'call', lambda name, args, auth: args)
    handler = create_server().request_handlers[CallToolRequest]
    for name, args in [('getInvoiceList', {'dateFrom': '2026-11-02', 'dateTo': ''}),
                       ('getInvoiceDetail', {'invoiceSymbol': 'Číslo & <1>'})]:
        result = (await handler(tool_request(name, args))).root
        assert not result.isError
        assert result.structuredContent == args
