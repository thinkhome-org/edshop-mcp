"""Synthetic WSDL and responses: no dealer data or credentials required."""
from xml.etree import ElementTree as ET
from requests import Response, Timeout
import pytest
from edshop_mcp import soap
from edshop_mcp.server import OPERATIONS

NS = 'urn:edshop-test'

def wsdl():
    elements, messages, ops, bindings = [], [], [], []
    for name, fields in OPERATIONS.items():
        params = {'login': {'type':'string'}, 'password': {'type':'string'}, **fields}
        if name == 'getAuthTokenEshop':
            params.update(loginEshop={'type':'string'}, passwordEshop={'type':'string'})
        fields_xml = ''.join(f'<x:element name="{k}" type="x:{ {"integer":"int", "boolean":"boolean"}.get(v["type"], "string")}"/>' for k,v in params.items())
        elements.append(f'<x:element name="{name}"><x:complexType><x:sequence>{fields_xml}</x:sequence></x:complexType></x:element>')
        elements.append(f'<x:element name="{name}Response"><x:complexType><x:sequence><x:element name="{name}Result" type="t:Result"/></x:sequence></x:complexType></x:element>')
        messages.append(f'<message name="{name}In"><part name="parameters" element="t:{name}"/></message><message name="{name}Out"><part name="parameters" element="t:{name}Response"/></message>')
        ops.append(f'<operation name="{name}"><input message="t:{name}In"/><output message="t:{name}Out"/></operation>')
        bindings.append(f'<operation name="{name}"><s:operation soapAction="{NS}/{name}"/><input><s:body use="literal"/></input><output><s:body use="literal"/></output></operation>')
    return f'''<definitions xmlns="http://schemas.xmlsoap.org/wsdl/" xmlns:x="http://www.w3.org/2001/XMLSchema" xmlns:s="http://schemas.xmlsoap.org/wsdl/soap/" xmlns:t="{NS}" targetNamespace="{NS}">
    <types><x:schema targetNamespace="{NS}" elementFormDefault="qualified">
    <x:complexType name="Result"><x:sequence>
    <x:element name="Status"><x:complexType><x:sequence><x:element name="StatusCode" type="x:string"/><x:element name="ErrorText" type="x:string" minOccurs="0"/></x:sequence></x:complexType></x:element>
    <x:element name="Price" type="x:decimal" minOccurs="0"/>
    <x:element name="ProductListStatus" minOccurs="0"><x:complexType><x:sequence><x:element name="url" type="x:string"/><x:element name="fileName" type="x:string"/><x:element name="isReady" type="x:boolean"/></x:sequence></x:complexType></x:element>
    </x:sequence></x:complexType>{''.join(elements)}</x:schema></types>
    {''.join(messages)}<portType name="Port">{''.join(ops)}</portType>
    <binding name="Binding" type="t:Port"><s:binding style="document" transport="http://schemas.xmlsoap.org/soap/http"/>{''.join(bindings)}</binding>
    <service name="Service"><port name="Port" binding="t:Binding"><s:address location="https://public-ws-cz.elinkx.biz/service.asmx"/></port></service></definitions>'''.encode()


def response(content, status=200):
    r = Response(); r.status_code = status; r._content = content; r._content_consumed = True
    r.headers['Content-Type'] = 'text/xml; charset=utf-8'
    return r


def envelope(name, content):
    return f'<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"><soap:Body><{name}Response xmlns="{NS}"><{name}Result>{content}</{name}Result></{name}Response></soap:Body></soap:Envelope>'.encode()

@pytest.fixture
def wire(monkeypatch):
    state = {'requests': [], 'body': '<Status><StatusCode>DONE</StatusCode></Status><Price>123.4500</Price>', 'failure': None}
    def request(self, method, url, **kwargs):
        if method.upper() == 'GET': return response(wsdl())
        if state['failure']: raise state['failure']
        request = ET.fromstring(kwargs['data'])
        operation = list(request.find('{http://schemas.xmlsoap.org/soap/envelope/}Body'))[0]
        name = operation.tag.split('}')[-1]
        params = {e.tag.split('}')[-1]: e.text for e in operation}
        state['requests'].append((name, params))
        return response(state.get('raw') or envelope(name, state['body']), state.get('status',200))
    monkeypatch.setattr(soap.Session, 'request', request)
    return state

@pytest.mark.parametrize('method', OPERATIONS)
def test_each_method_serializes_and_parses(method, wire):
    args = {key: (v.get('enum', ['example'])[0] if v['type']=='string' else (True if v['type']=='boolean' else 1)) for key,v in OPERATIONS[method].items()}
    result = soap.call(method,args,soap.Credentials('api-user','api-secret','eshop-user','eshop-secret'))
    payload = result['data'] if method in soap.LISTS else result
    assert payload['Price'] == '123.4500'
    name, sent = wire['requests'][0]
    assert name == method
    assert sent['login'] == 'api-user' and sent['password'] == 'api-secret'
    for key,value in args.items(): assert sent[key] == (str(value).lower() if isinstance(value,bool) else str(value))
    if method == 'getAuthTokenEshop': assert sent['passwordEshop'] == 'eshop-secret'


def test_export_not_ready(wire):
    wire['body'] = '<Status><StatusCode>DONE</StatusCode></Status><ProductListStatus><url>https://example.invalid/file.xml</url><fileName>file.xml</fileName><isReady>false</isReady></ProductListStatus>'
    data = soap.call('getProductListDownloadXML',{'encoding':'UTF-8','onStock':True},soap.Credentials('a','b'))
    assert data['ProductListStatus']['isReady'] is False
    assert data['ProductListStatus']['fileName'] == 'file.xml'
    assert len(wire['requests']) == 1

@pytest.mark.parametrize('kind', ['application','fault','malformed','timeout','entity'])
def test_safe_errors(kind,wire,caplog):
    if kind == 'application': wire['body'] = '<Status><StatusCode>ERROR</StatusCode><ErrorText>api-secret token-secret</ErrorText></Status>'
    if kind == 'fault':
        wire['raw'] = b'<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body><s:Fault><faultcode>s:Server</faultcode><faultstring>api-secret token-secret</faultstring></s:Fault></s:Body></s:Envelope>'
        wire['status'] = 500
    if kind == 'malformed': wire['raw'] = b'<broken>api-secret'
    if kind == 'timeout': wire['failure'] = Timeout('api-secret token-secret')
    if kind == 'entity': wire['raw'] = b'<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><foo>&xxe;</foo>'
    with pytest.raises(soap.EdshopError) as exc:
        soap.call('getSellerInfo',{},soap.Credentials('a','api-secret'))
    assert 'api-secret' not in str(exc.value) + caplog.text
    assert 'token-secret' not in str(exc.value) + caplog.text

def test_library_usage_does_not_log_secrets(wire, caplog):
    import logging
    caplog.set_level(logging.DEBUG)
    soap.call('getSellerInfo',{},soap.Credentials('a','never-log-this-password'))
    assert 'never-log-this-password' not in caplog.text


def test_large_response_is_not_rejected(monkeypatch):
    import io
    from requests import Session
    payload = b'x' * (32 * 1024 * 1024 + 1)
    r = Response(); r.status_code = 200; r.raw = io.BytesIO(payload)
    closed = []
    monkeypatch.setattr(r, 'close', lambda: closed.append(True))
    def request(self, method, url, **kwargs):
        assert kwargs['allow_redirects'] is False
        return r
    monkeypatch.setattr(Session, 'request', request)
    with soap.SoapSession() as session:
        result = session.get('https://example.invalid')
        assert result.content == payload
    assert closed == [True]


def test_redirect_is_refused_and_response_closed(monkeypatch):
    import io
    from requests import Session
    r = Response(); r.status_code = 307; r.raw = io.BytesIO(b'')
    monkeypatch.setattr(Session, 'request', lambda *a, **k: r)
    with soap.SoapSession() as session:
        with pytest.raises(soap.EdshopError, match='redirect refused'):
            session.post('https://example.invalid')
    assert r.raw.closed
