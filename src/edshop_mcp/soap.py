"""Credential-scoped SOAP calls to the Czech PUBLIC service."""
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
import logging

from requests import Session
from zeep import Client, Settings
from zeep.helpers import serialize_object
from zeep.transports import Transport

MAX_RESPONSE_BYTES = 32 * 1024 * 1024


class BoundedSession(Session):
    def request(self, method, url, **kwargs):
        kwargs.update(stream=True, allow_redirects=False)
        response = super().request(method, url, **kwargs)
        try:
            if 300 <= response.status_code < 400:
                raise EdshopError('Upstream redirect refused.')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > MAX_RESPONSE_BYTES:
                    raise EdshopError('SOAP response exceeds 32 MiB. Use an export operation instead.')
                chunks.append(chunk)
            response._content = b''.join(chunks)
            response._content_consumed = True
            return response
        finally:
            response.close()


WSDL = 'https://public-ws-cz.elinkx.biz/service.asmx?WSDL'
LISTS = {
    'getProductList': ('ProductList', 'Product'),
    'getInvoiceList': ('InvoiceList', 'InvoiceHead'),
    'getOrderList': ('OrderList', 'OrderHead'),
    'getDeliveryList': ('DeliveryList', 'DeliveryHead'),
    'getExpeditionList': ('ExpeditionList', 'ExpeditionHead'),
    'getClaimList': ('ClaimList', 'Claim'),
}


class EdshopError(Exception):
    """Only safe, application-authored messages belong in this exception."""


@dataclass(frozen=True, repr=False)
class Credentials:
    login: str
    password: str
    eshop_login: str = ''
    eshop_password: str = ''


def normalize(value):
    if isinstance(value, dict):
        if value.get('StatusCode') == 'ERROR':
            raise EdshopError('Upstream rejected the request. Check credentials and API permissions.')
        return {k: normalize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [normalize(v) for v in value]
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def paginate(data, method, offset, limit):
    container, item = LISTS[method]
    data = dict(data)
    rows = (data.get(container) or {}).get(item) or []
    total = len(rows)
    data[container] = {item: rows[offset:offset + limit]}
    return {'data': data, 'total': total, 'offset': offset,
            'nextOffset': offset + limit if offset + limit < total else None,
            'pagination': 'local; SOAP retrieves the entire matching list'}


def call(method, arguments, auth):
    params = dict(arguments)
    offset, limit = params.pop('offset', 0), params.pop('limit', 50)
    params.update(login=auth.login, password=auth.password)
    if method == 'getAuthTokenEshop':
        if not auth.eshop_login or not auth.eshop_password:
            raise EdshopError('Missing e-shop credentials.')
        params.update(loginEshop=auth.eshop_login, passwordEshop=auth.eshop_password)
    # Each call owns its session: cookies and credentials never cross accounts.
    try:
        logging.getLogger('zeep').setLevel(logging.CRITICAL)
        logging.getLogger('zeep.transports').setLevel(logging.CRITICAL)
        with BoundedSession() as session:
            session.trust_env = False
            client = Client(WSDL, transport=Transport(session=session, timeout=20, operation_timeout=60),
                            settings=Settings(forbid_dtd=True, forbid_entities=True, forbid_external=True))
            data = normalize(serialize_object(client.service[method](**params)))
    except EdshopError:
        raise
    except Exception:
        # SOAP faults and HTTP exceptions can contain request credentials or tokens.
        raise EdshopError('SOAP request failed. Check connectivity, credentials and request parameters.') from None
    if not isinstance(data, dict):
        raise EdshopError('Unexpected SOAP response.')
    return paginate(data, method, offset, limit) if method in LISTS else data
