"""MCP transports and the explicit PUBLIC API allowlist."""
import argparse
import asyncio
from contextlib import asynccontextmanager
from contextvars import ContextVar
import logging
import os

import jsonschema
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import Tool, ToolAnnotations, CallToolResult, TextContent
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
import uvicorn

from . import soap
from .soap import Credentials, EdshopError, LISTS

request_auth = ContextVar('edshop_credentials', default=None)
STRING = {'type': 'string', 'minLength': 1}
BOOL = {'type': 'boolean'}
ENCODING = {'type': 'string', 'enum': ['UTF-8', 'windows-1250']}
PRODUCT_TRANSFORM = {'type': 'string', 'enum': ['EDLINKOLDXML', 'EDLINKOLDCSV', 'EDLINKXLS']}
OPERATIONS = {
    'getClaimList': {'dateFrom': STRING, 'dateTo': {'type': 'string'}},
    'getDeliveryList': {'dateFrom': STRING, 'dateTo': {'type': 'string'}},
    'getDeliveryDetail': {'deliverySymbol': STRING},
    'getExpeditionList': {'dateFrom': STRING, 'dateTo': {'type': 'string'}},
    'getExpeditionDetail': {'expeditionSymbol': STRING},
    'getOrderList': {'dateFrom': STRING, 'dateTo': {'type': 'string'}},
    'getOrderDetail': {'orderSymbol': STRING},
    'getInvoiceList': {'dateFrom': STRING, 'dateTo': {'type': 'string'}},
    'getInvoiceDetail': {'invoiceSymbol': STRING},
    'getInvoiceDetailDownloadXMLWithTransform': {
        'invoiceSymbol': STRING, 'transformation': {'type': 'string', 'enum': ['INVOICEOLD', 'ISDOC_5', 'ISDOC_6']},
        'encoding': ENCODING},
    'getProductList': {'onStock': BOOL},
    'getProductListDownloadXML': {'encoding': ENCODING, 'onStock': BOOL},
    'getProductListDownloadZIP': {'encoding': ENCODING, 'onStock': BOOL},
    'getProductListDownloadXMLWithTransform': {'transformation': PRODUCT_TRANSFORM, 'encoding': ENCODING, 'onStock': BOOL,
                                             'fileFormat': {'type': 'string', 'enum': ['XML', 'CSV', 'XLS']}},
    'getProductListDownloadZIPWithTransform': {'transformation': PRODUCT_TRANSFORM, 'encoding': ENCODING, 'onStock': BOOL,
                                             'fileFormat': {'type': 'string', 'enum': ['XML', 'CSV', 'XLS']}, 'soldItemsOnly': BOOL},
    'getSellerInfo': {},
    'getAuthTokenEshop': {'idEshop': {'type': 'integer'}},
}


def tools():
    result = []
    for name, params in OPERATIONS.items():
        properties = dict(params)
        description = f'eD system PUBLIC SOAP {name}. Credentials are supplied outside tool arguments.'
        if name in LISTS:
            properties.update(offset={'type': 'integer', 'minimum': 0, 'default': 0},
                              limit={'type': 'integer', 'minimum': 1, 'maximum': 200, 'default': 50})
            description += ' Pagination is local over the full SOAP list. Dates use YYYY-MM-DD; history is limited by the provider (approximately 30 days).'
        if 'Download' in name:
            description += ' Returns isReady, url and fileName; does not download or poll. Export may be cached upstream.'
        if name.startswith('getProductList'):
            description += ' Catalogue is precomputed; prices and stock are not real-time.'
        if name == 'getAuthTokenEshop':
            description += ' Returns a sensitive e-shop token, not OAuth. Requires separate e-shop credentials.'
        result.append(Tool(name=name, description=description,
                           inputSchema={'type': 'object', 'properties': properties, 'required': list(params), 'additionalProperties': False},
                           annotations=ToolAnnotations(readOnlyHint='Download' not in name and name != 'getAuthTokenEshop',
                                                       destructiveHint=False, openWorldHint=True)))
    return result


def credentials(mode):
    if mode == 'http':
        auth = request_auth.get()
    else:
        auth = Credentials(os.getenv('EDSHOP_LOGIN', ''), os.getenv('EDSHOP_PASSWORD', ''),
                           os.getenv('EDSHOP_ESHOP_LOGIN', ''), os.getenv('EDSHOP_ESHOP_PASSWORD', ''))
    if auth is None or not auth.login or not auth.password:
        raise EdshopError('Missing API credentials.')
    return auth


def create_server(mode='stdio'):
    logging.getLogger('mcp').setLevel(logging.CRITICAL)
    server = Server('edshop-mcp', version='0.1.0')
    catalog = {t.name: t for t in tools()}

    @server.list_tools()
    async def list_tools():
        return list(catalog.values())

    @server.call_tool(validate_input=False)
    async def call_tool(name, arguments):
        try:
            if name not in catalog:
                raise EdshopError('Unknown tool.')
            try:
                jsonschema.validate(arguments, catalog[name].inputSchema)
            except jsonschema.ValidationError:
                raise EdshopError('Invalid tool parameters. Consult the tool schema.') from None
            if 'fileFormat' in arguments:
                expected = {'EDLINKOLDXML': 'XML', 'EDLINKOLDCSV': 'CSV', 'EDLINKXLS': 'XLS'}[arguments['transformation']]
                if arguments['fileFormat'] != expected:
                    raise EdshopError('fileFormat does not match transformation.')
            return await asyncio.to_thread(soap.call, name, arguments, credentials(mode))
        except EdshopError as exc:
            return CallToolResult(isError=True, content=[TextContent(type='text', text=str(exc))])
        except Exception:
            return CallToolResult(isError=True, content=[TextContent(type='text', text='Request failed.')])
    return server


class CredentialMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        headers = dict(scope['headers'])
        def value(key):
            return headers.get(key, b'').decode('utf-8', errors='strict')
        try:
            auth = Credentials(value(b'x-edshop-login'), value(b'x-edshop-password'),
                               value(b'x-edshop-eshop-login'), value(b'x-edshop-eshop-password'))
        except UnicodeDecodeError:
            return await JSONResponse({'error': 'Invalid credential headers.'}, status_code=400)(scope, receive, send)
        if not auth.login or not auth.password:
            return await JSONResponse({'error': 'Missing API credentials.'}, status_code=401)(scope, receive, send)
        token = request_auth.set(auth)
        try:
            await self.app(scope, receive, send)
        finally:
            request_auth.reset(token)


def create_http_app():
    manager = StreamableHTTPSessionManager(create_server('http'), stateless=True, json_response=True,
        security_settings=TransportSecuritySettings(enable_dns_rebinding_protection=True,
            allowed_hosts=['localhost', '127.0.0.1', 'localhost:*', '127.0.0.1:*'] + os.getenv('EDSHOP_ALLOWED_HOSTS', '').split(','),
            allowed_origins=[]))

    @asynccontextmanager
    async def lifespan(app):
        async with manager.run():
            yield

    class MCPHandler:
        async def __call__(self, scope, receive, send):
            await manager.handle_request(scope, receive, send)

    return CredentialMiddleware(Starlette(routes=[Route('/mcp', endpoint=MCPHandler(), methods=['GET','POST','DELETE'])], lifespan=lifespan))


def main():
    parser = argparse.ArgumentParser(description='eDshop PUBLIC MCP server')
    parser.add_argument('--transport', choices=['stdio', 'http'], default='stdio')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()
    # Dependency debug logging can include SOAP bodies and sensitive MCP results.
    for name in ('zeep', 'mcp', 'httpx', 'httpcore', 'urllib3'):
        logging.getLogger(name).setLevel(logging.CRITICAL)
    if args.transport == 'http':
        uvicorn.run(create_http_app(), host=args.host, port=args.port, access_log=False)
    else:
        async def run():
            server = create_server()
            async with stdio_server() as (read, write):
                await server.run(read, write, server.create_initialization_options())
        asyncio.run(run())


if __name__ == '__main__':
    main()
