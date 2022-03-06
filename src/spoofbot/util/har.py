import base64
import json
import os
from abc import ABC
from datetime import datetime, timedelta
from http.cookiejar import Cookie
from io import BytesIO
from itertools import repeat
from json import JSONDecodeError
from pathlib import Path
from typing import Union, TextIO
from urllib import request
from urllib.parse import urlparse

from cryptography import x509
from dateutil.parser import parse
# https://w3c.github.io/web-performance/specs/HAR/Overview.html
from requests import PreparedRequest, Response
from requests import Request
from requests.adapters import HTTPAdapter, CaseInsensitiveDict, HTTPResponse
from requests.cookies import RequestsCookieJar
from urllib3.util import Url, parse_url

from spoofbot.util.common import dict_to_dict_list, url_to_query_dict_list, \
    query_to_dict_list, dict_list_to_tuple_list, dict_list_to_dict
from spoofbot.util.file import MockHTTPResponse


class JsonObject(ABC):
    _custom_properties: dict

    def __init__(self):
        self._custom_properties = {}

    @classmethod
    def from_dict(cls, *args):
        """Create an instance from a json dict and possible additional args"""
        raise NotImplementedError()

    @property
    def custom_properties(self) -> dict:
        return self._custom_properties

    @custom_properties.setter
    def custom_properties(self, value: dict):
        self._test_are_custom_properties(value)
        self._custom_properties = value

    @staticmethod
    def _test_are_custom_properties(data: dict):
        if not all(map(str.startswith, zip(data, repeat('_')))):
            raise ValueError("All custom properties have to start with '_'.")

    def _setup_custom_properties(self, data: dict) -> 'JsonObject':
        self._custom_properties = self._extract_custom_properties(data)
        return self

    @staticmethod
    def _extract_custom_properties(data: dict) -> dict:
        props = {}
        for k, v in data.items():
            if k.startswith('_'):
                props[k] = v
        return props

    def to_dict(self) -> dict:
        """Serialize object to a json dict"""
        raise NotImplementedError()


# noinspection DuplicatedCode
class Creator(JsonObject):
    """Information about the log creator application"""

    name: str
    version: str
    comment: str  # optional

    def __init__(
            self,
            name: str,
            version: str,
            comment: str = None
    ):
        super().__init__()
        self.name = name
        self.version = version
        self.comment = comment

    @classmethod
    def from_dict(cls, data: dict) -> 'Creator':
        return cls(
            name=data['name'],
            version=data['version'],
            comment=data.get('comment', None)
        )._setup_custom_properties(data)

    def to_dict(self) -> dict:
        data = {
            'name': self.name,
            'version': self.version
        }
        if self.comment is not None:
            data['comment'] = self.comment
        data.update(self.custom_properties)
        return data

    def __str__(self) -> str:
        comment = f" {self.comment}" if self.comment is not None else ''
        return f"{self.name} {self.version}{comment}"


# noinspection DuplicatedCode
class Browser(JsonObject):
    """Information about the browser that created the log"""

    name: str
    version: str
    comment: str  # optional

    def __init__(
            self,
            name: str,
            version: str,
            comment: str = None
    ):
        super().__init__()
        self.name = name
        self.version = version
        self.comment = comment

    @classmethod
    def from_dict(cls, data: dict) -> 'Browser':
        return cls(
            name=data['name'],
            version=data['version'],
            comment=data.get('comment', None)
        )._setup_custom_properties(data)

    def to_dict(self) -> dict:
        data = {
            'name': self.name,
            'version': self.version
        }
        if self.comment is not None:
            data['comment'] = self.comment
        data.update(self.custom_properties)
        return data

    def __str__(self) -> str:
        comment = f" ({self.comment})" if self.comment is not None else ''
        return f"{self.name} {self.version}{comment}"


class PageTimings(JsonObject):
    """
    This object describes timings for various events (states) fired during the page load
    """

    on_content_load: timedelta  # optional
    on_load: timedelta  # optional
    comment: str  # optional

    def __init__(
            self,
            on_content_load: timedelta = None,
            on_load: timedelta = None,
            comment: str = None
    ):
        super().__init__()
        self.on_content_load = on_content_load
        self.on_load = on_load
        self.comment = comment

    @classmethod
    def from_dict(cls, data: dict) -> 'PageTimings':
        on_content_load = data.get('onContentLoad', None)
        if on_content_load is not None:
            on_content_load = timedelta(milliseconds=on_content_load)

        on_load = data.get('onLoad', None)
        if on_load is not None:
            on_load = timedelta(milliseconds=on_load)

        return cls(
            on_content_load=on_content_load,
            on_load=on_load,
            comment=data.get('comment', None)
        )._setup_custom_properties(data)

    def to_dict(self) -> dict:
        data = {}
        if self.on_content_load is not None:
            data['onContentLoad'] = self.on_content_load.total_seconds() * 1000
        if self.on_load is not None:
            data['onLoad'] = self.on_load.total_seconds() * 1000
        if self.comment is not None:
            data['comment'] = self.comment
        data.update(self.custom_properties)
        return data

    def __str__(self) -> str:
        strings = []
        if self.on_content_load is not None:
            if self.on_content_load.total_seconds() < 0.0:
                s = 'N/A'
            else:
                s = str(self.on_content_load)
            strings.append(f"onContentLoad: {s}")
        if self.on_load is not None:
            if self.on_load.total_seconds() < 0.0:
                s = 'N/A'
            else:
                s = str(self.on_load)
            strings.append(f"onLoad: {s}")
        if self.comment:
            strings.append(self.comment)
        return ", ".join(strings)


class Page(JsonObject):
    """Exported page"""

    started_datetime: datetime
    id: str
    title: str
    page_timings: PageTimings
    comment: str  # optional

    def __init__(
            self,
            started_datetime: datetime,
            page_id: str,
            title: str,
            page_timings: PageTimings,
            comment: str = None,
    ):
        super().__init__()
        self.started_datetime = started_datetime
        self.id = page_id
        self.title = title
        self.page_timings = page_timings
        self.comment = comment

    @classmethod
    def from_dict(cls, data: dict) -> 'Page':
        return cls(
            started_datetime=parse(data['startedDateTime']),
            page_id=data['id'],
            title=data.get('title', '<NO TITLE>'),  # Firefox be like...
            page_timings=PageTimings.from_dict(data['pageTimings']),
            comment=data.get('comment', None)
        )._setup_custom_properties(data)

    def to_dict(self) -> dict:
        data = {
            'startedDateTime': self.started_datetime.isoformat(),
            'id': self.id,
            'title': self.title,
            'pageTimings': self.page_timings.to_dict()
        }
        if self.comment is not None:
            data['comment'] = self.comment
        data.update(self.custom_properties)
        return data

    def __str__(self) -> str:
        comment = f" {self.comment}" if self.comment is not None else ''
        return f"{self.title} [{str(self.started_datetime)}]{comment}"


class CacheStats(JsonObject):
    expires: datetime  # optional
    last_access: datetime
    e_tag: str
    hit_count: int
    comment: str  # optional

    def __init__(
            self,
            last_access: datetime,
            e_tag: str,
            hit_count: int,
            expires: datetime = None,
            comment: str = None
    ):
        super().__init__()
        self.expires = expires
        self.last_access = last_access
        self.e_tag = e_tag
        self.hit_count = hit_count
        self.comment = comment

    @classmethod
    def from_dict(cls, data: dict) -> 'CacheStats':
        return cls(
            expires=parse(data['expires']) if 'expires' in data.keys() else None,
            last_access=parse(data['lastAccess']),
            e_tag=data['eTag'],
            hit_count=int(data['hitCount']),
            comment=data.get('comment', None)
        )._setup_custom_properties(data)

    def to_dict(self) -> dict:
        data = {}
        if self.expires is not None:
            data['expires'] = self.expires.isoformat()
        data['lastAccess'] = self.last_access.isoformat()
        data['eTag'] = self.e_tag
        data['hitCount'] = self.hit_count
        if self.comment is not None:
            data['comment'] = self.comment
        data.update(self.custom_properties)
        return data

    def __str__(self) -> str:
        if self.expires is not None:
            expires = f"EXP: {self.expires}, "
        else:
            expires = ''
        if self.comment is not None:
            comment = f". {self.comment}"
        else:
            comment = ''
        return f"{expires}Last access: {self.last_access}, " \
               f"Hits: {self.hit_count}{comment}"


class Cache(JsonObject):
    before_request: CacheStats  # optional
    after_request: CacheStats  # optional
    comment: str  # optional

    def __init__(
            self,
            before_request: CacheStats = None,
            after_request: CacheStats = None,
            comment: str = None
    ):
        super().__init__()
        self.before_request = before_request
        self.after_request = after_request
        self.comment = comment

    @classmethod
    def from_dict(cls, data: dict) -> 'Cache':
        return cls(
            before_request=CacheStats.from_dict(
                data['beforeRequest']) if 'beforeRequest' in data.keys() else None,
            after_request=CacheStats.from_dict(
                data['afterRequest']) if 'afterRequest' in data.keys() else None,
            comment=data.get('comment', None)
        )._setup_custom_properties(data)

    def to_dict(self) -> dict:
        data = {}
        if self.before_request is not None:
            data['beforeRequest'] = self.before_request.to_dict()
        if self.after_request is not None:
            data['afterRequest'] = self.after_request.to_dict()
        if self.comment is not None:
            data['comment'] = self.comment
        data.update(self.custom_properties)
        return data

    def __str__(self) -> str:
        s = []
        if self.before_request is not None:
            s.append(f"Before: ({self.before_request})")
        if self.after_request is not None:
            s.append(f"After: ({self.after_request})")
        if self.comment is not None:
            s.append(self.comment)
        return ', '.join(s)


class Timings(JsonObject):
    blocked: timedelta  # optional
    dns: timedelta  # optional
    connect: timedelta  # optional
    ssl: timedelta  # optional
    send: timedelta  # optional
    wait: timedelta  # optional
    receive: timedelta  # optional
    comment: str  # optional

    def __init__(
            self,
            send: timedelta,
            wait: timedelta,
            receive: timedelta,
            blocked: timedelta = timedelta(-1),
            dns: timedelta = timedelta(-1),
            connect: timedelta = timedelta(-1),
            ssl: timedelta = timedelta(-1),
            comment: str = None
    ):
        super().__init__()
        self.blocked = blocked
        self.dns = dns
        self.connect = connect
        self.ssl = ssl
        self.send = send
        self.wait = wait
        self.receive = receive
        self.comment = comment

    @property
    def total(self) -> timedelta:
        total = timedelta(seconds=0)
        if self.blocked is not None and self.blocked.total_seconds() > 0.0:
            total += self.blocked
        if self.dns is not None and self.dns.total_seconds() > 0.0:
            total += self.dns
        if self.connect is not None and self.connect.total_seconds() > 0.0:
            total += self.connect
        # NOTE: Google Chrome seems to not consider the ssl timespan to be part of
        # the overall request/response time
        if self.ssl is not None and self.ssl.total_seconds() > 0.0:
            total += self.ssl
        if self.send.total_seconds() > 0.0:
            total += self.send
        if self.wait.total_seconds() > 0.0:
            total += self.wait
        if self.receive.total_seconds() > 0.0:
            total += self.receive
        return total

    @classmethod
    def from_dict(cls, data: dict) -> 'Timings':
        blocked = timedelta(milliseconds=float(data.get('blocked', -1)))
        if blocked.total_seconds() < 0.0:
            blocked = -1
        dns = timedelta(milliseconds=float(data.get('dns', -1)))
        if dns.total_seconds() < 0.0:
            dns = -1
        connect = timedelta(milliseconds=float(data.get('connect', -1)))
        if connect.total_seconds() < 0.0:
            connect = -1
        ssl = timedelta(milliseconds=float(data.get('ssl', -1)))
        if ssl.total_seconds() < 0.0:
            ssl = -1
        # Firefox be like...
        send = timedelta(milliseconds=float(data.get('send', -1)))
        if send.total_seconds() < 0.0:
            send = -1
        wait = timedelta(milliseconds=float(data.get('wait', -1)))
        if wait.total_seconds() < 0.0:
            wait = -1
        receive = timedelta(milliseconds=float(data.get('receive', -1)))
        if receive.total_seconds() < 0.0:
            receive = -1
        return cls(
            blocked=blocked,
            dns=dns,
            connect=connect,
            ssl=ssl,
            send=send,
            wait=wait,
            receive=receive,
            comment=data.get('comment', None)
        )._setup_custom_properties(data)

    def to_dict(self) -> dict:
        data = {}
        if self.blocked is not None:
            if isinstance(self.blocked, int):
                data['blocked'] = self.blocked
            else:
                data['blocked'] = max(self.blocked.total_seconds() * 1000, -1)
        if self.dns is not None:
            if isinstance(self.dns, int):
                data['dns'] = self.dns
            else:
                data['dns'] = max(self.dns.total_seconds() * 1000, -1)
        if self.connect is not None:
            if isinstance(self.connect, int):
                data['connect'] = self.connect
            else:
                data['connect'] = max(self.connect.total_seconds() * 1000, -1)
        if self.ssl is not None:
            if isinstance(self.ssl, int):
                data['ssl'] = self.ssl
            else:
                data['ssl'] = max(self.ssl.total_seconds() * 1000, -1)
        if self.send is not None:
            if isinstance(self.send, int):
                data['send'] = self.send
            else:
                data['send'] = max(self.send.total_seconds() * 1000, -1)
        if self.wait is not None:
            if isinstance(self.wait, int):
                data['wait'] = self.wait
            else:
                data['wait'] = max(self.wait.total_seconds() * 1000, -1)
        if self.receive is not None:
            if isinstance(self.receive, int):
                data['receive'] = self.receive
            else:
                data['receive'] = max(self.receive.total_seconds() * 1000, -1)
        if self.comment is not None:
            data['comment'] = self.comment
        data.update(self.custom_properties)
        return data

    def __str__(self) -> str:
        total = self.total
        comment = self.comment if self.comment is not None else ''
        return f"total {str(total)} {comment}".strip()


class Entry(JsonObject):
    """Represents an array with all exported HTTP requests."""

    page_ref: str  # optional
    started_datetime: datetime
    time: timedelta
    request: PreparedRequest
    _request_props: dict
    _post_data_props: dict
    response: Response
    _response_props: dict
    _content_props: dict
    cache: dict
    _cache_props: dict
    timings: Timings
    _timings_props: dict
    server_ip_address: str  # optional
    connection: str  # optional
    comment: str  # optional

    def __init__(
            self,
            started_datetime: datetime,
            time: timedelta,
            request: PreparedRequest,
            response: Response,
            cache: dict,
            timings: Timings,
            page_ref: str = None,
            server_ip_address: str = None,
            connection: str = None,
            comment: str = None,
            request_props: dict = None,
            post_data_props: dict = None,
            response_props: dict = None,
            content_props: dict = None,
            cache_props: dict = None,
            timings_props: dict = None
    ):
        super().__init__()
        self.started_datetime = started_datetime
        self.time = time
        self.request = request
        if request_props is None:
            request_props = {}
        self._request_props = request_props
        if post_data_props is None:
            post_data_props = {}
        self._post_data_props = post_data_props
        self.response = response
        if response_props is None:
            response_props = {}
        self._response_props = response_props
        if content_props is None:
            content_props = {}
        self._content_props = content_props
        if cache is None:
            cache = {}
        self.cache = cache
        if cache_props is None:
            cache_props = {}
        self._cache_props = cache_props
        self.timings = timings
        if timings_props is None:
            timings_props = {}
        self._timings_props = timings_props
        self.page_ref = page_ref
        self.server_ip_address = server_ip_address
        self.connection = connection
        self.comment = comment

    @property
    def request_props(self) -> dict:
        return self._request_props

    @request_props.setter
    def request_props(self, value: dict):
        self._test_are_custom_properties(value)
        self._request_props = value

    @property
    def post_data_props(self) -> dict:
        return self._post_data_props

    @post_data_props.setter
    def post_data_props(self, value: dict):
        self._test_are_custom_properties(value)
        self._post_data_props = value

    @property
    def response_props(self) -> dict:
        return self._response_props

    @response_props.setter
    def response_props(self, value: dict):
        self._test_are_custom_properties(value)
        self._response_props = value

    @property
    def content_props(self) -> dict:
        return self._content_props

    @content_props.setter
    def content_props(self, value: dict):
        self._test_are_custom_properties(value)
        self._content_props = value

    @property
    def cache_props(self) -> dict:
        return self._cache_props

    @cache_props.setter
    def cache_props(self, value: dict):
        self._test_are_custom_properties(value)
        self._cache_props = value

    @property
    def timings_props(self) -> dict:
        return self._timings_props

    @timings_props.setter
    def timings_props(self, value: dict):
        self._test_are_custom_properties(value)
        self._timings_props = value

    @classmethod
    def from_dict(cls, data: dict, adapter: HTTPAdapter = None) -> 'Entry':
        if adapter is None:
            adapter = HTTPAdapter()
        req = cls._req_from_dict(data)
        httpver = data['request']['httpVersion'].upper()
        preq = req.prepare()
        hresp = cls._resp_from_dict(data)
        if httpver.startswith('HTTP/'):
            hresp.version = int(httpver.split('/')[1].replace('.', '').ljust(2, '0'))
        resp: Response = adapter.build_response(preq, hresp)
        resp.elapsed = timedelta(milliseconds=data['time'])
        resp.reason = data['response']['statusText']
        if '_cert' in data.keys():
            setattr(resp, 'cert', data['_cert'])
        if '_cert_bin' in data.keys():
            cert_bin = base64.b64decode(data['_cert_bin'])
            setattr(resp, 'cert_bin', cert_bin)
            setattr(resp, 'cert_x509', x509.load_der_x509_certificate(cert_bin))
        if '_ip' in data.keys():
            setattr(resp, 'ip', data['_ip'])
        if '_port' in data.keys():
            setattr(resp, 'port', int(data['_port']))
        return cls(
            page_ref=data.get('pageref', None),
            started_datetime=parse(data['startedDateTime']),
            time=resp.elapsed,
            request=preq,
            response=resp,
            cache=data['cache'],
            timings=Timings.from_dict(data['timings']),
            server_ip_address=data.get('serverIPAddress', None),
            connection=data.get('connection', None),
            comment=data.get('comment', None),
            request_props=cls._extract_custom_properties(data['request']),
            post_data_props=cls._extract_custom_properties(data['request'].get(
                'postData', {})),
            response_props=cls._extract_custom_properties(data['response']),
            content_props=cls._extract_custom_properties(data['response']['content']),
            cache_props=cls._extract_custom_properties(data['cache']),
            timings_props=cls._extract_custom_properties(data['timings'])
        )._setup_custom_properties(data)

    @classmethod
    def _req_from_dict(cls, entry_data: dict) -> Request:
        request_data = entry_data['request']
        data = {}
        if 'postData' in request_data:
            post_data = dict_list_to_tuple_list(request_data['postData']['params'],
                                                case_insensitive=False)
            data = '&'.join(map('='.join, post_data))
            if len(data) == 0:
                data = request_data['postData']['text']
        return Request(
            method=request_data['method'].upper(),
            url=request_data['url'],
            headers=CaseInsensitiveDict(
                dict_list_to_dict(request_data['headers'], case_insensitive=True)),
            data=data,
            cookies=dict_list_to_dict(request_data['cookies'])
        )

    @classmethod
    def _resp_from_dict(cls, entry_data: dict) -> HTTPResponse:
        response_entry = entry_data['response']
        headers = dict_list_to_tuple_list(response_entry['headers'])
        content: dict = response_entry['content']
        encoding = content.get('encoding', None)
        if encoding == 'base64':
            body = base64.b64decode(content.get('text', ''))
        else:
            body = content.get('text', '').encode('utf8')
        resp = HTTPResponse(
            body=BytesIO(body),
            headers=headers,
            status=response_entry['status'],
            preload_content=False,
            original_response=MockHTTPResponse(headers),
            version=response_entry.get('version', 'HTTP/1.1')
        )
        compression = content.get('compression', None)
        if compression is not None:
            setattr(resp, 'compression', compression)
        # Hack to prevent already decoded contents to be decoded again
        resp.CONTENT_DECODERS = []
        return resp

    def to_dict(self) -> dict:
        data = {}
        if self.page_ref is not None:
            data['pageref'] = self.page_ref
        data['startedDateTime'] = self.started_datetime.isoformat()
        data['time'] = self.time.total_seconds() * 1000
        data['request'] = self._req_to_dict()
        data['response'] = self._resp_to_dict(self.response)
        data['cache'] = self.cache
        data['cache'].update(self._cache_props)
        data['timings'] = self.timings.to_dict()
        data['timings'].update(self._timings_props)
        if self.server_ip_address is not None:
            data['serverIPAddress'] = self.server_ip_address
        if self.connection is not None:
            data['connection'] = self.connection
        if self.comment is not None:
            data['comment'] = self.comment
        data.update(self.custom_properties)
        return data

    def _req_to_dict(self) -> dict:
        cookie_jar: RequestsCookieJar = getattr(self.request, '_cookies')
        f_cookies_for_request = getattr(cookie_jar, '_cookies_for_request')
        cookies = self._cookiejar_to_dicts(f_cookies_for_request(request.Request(
            url=self.request.url,
            data=self.request.body,
            method=self.request.method,
        )),
            url=parse_url(self.request.url)
        )
        url = urlparse(self.request.url)
        endpoint = url.path
        if len(url.query) > 0:
            endpoint += f"?{url.query}"
        http_version = self.response.raw.version
        if isinstance(http_version, int):
            http_version = f"HTTP/{http_version / 10.0}".strip('.0')
        header_size = len(f"{self.request.method} {endpoint} {http_version}.\n")
        for key, value in self.request.headers.items():
            header_size += len(f"{key}: {value}\n")
        header_size += 2  # 2 CRLF
        data = {
            'bodySize': len(self.request.body) if self.request.body is not None else 0,
            'method': self.request.method.upper(),
            'url': self.request.url,
            'httpVersion': http_version,
            'headers': dict_to_dict_list(self.request.headers),
            'cookies': cookies,
            'queryString': url_to_query_dict_list(self.request.url),
            'headerSize': header_size
        }
        if self.request.method.upper() == 'POST':
            mimetype = self.request.headers.get('Content-Type', '')
            params = []
            if self.request.body is not None:
                body = self.request.body
                encoding = None
                if isinstance(body, bytes):
                    try:
                        body = body.decode()
                    except UnicodeDecodeError:
                        body = base64.b64encode(body).decode()
                        encoding = 'base64'
                if mimetype == 'application/x-www-form-urlencoded':
                    params = query_to_dict_list(body)
                data['postData'] = {
                    'mimeType': mimetype,
                    'params': params,
                    'text': body
                }
                if encoding is not None:
                    data['postData']['encoding'] = encoding
                data['bodySize'] = len(body)
                data['postData'].update(self._post_data_props)
        data.update(self._request_props)
        return data

    def _resp_to_dict(self, response: Response) -> dict:
        http_version = response.raw.version
        if isinstance(http_version, int):
            http_version = f"HTTP/{response.raw.version / 10}".strip('.0')
        data = {
            'status': response.status_code,
            'statusText': response.reason,
            'httpVersion': http_version,
            'cookies': self._cookiejar_to_dicts(response.cookies,
                                                parse_url(response.url)),
            'headers': dict_to_dict_list(response.headers),
            'content': self._get_content(response),
            'redirectURL': response.headers.get('Location', ''),
            'headerSize': Entry._get_resp_header_size(response),
        }
        if response.content is not None:
            data['bodySize'] = len(response.content) - \
                               data['content'].get('compression', 0)
        else:
            data['bodySize'] = -1
        data.update(self._response_props)
        data['content'].update(self._content_props)
        return data

    def _get_req_header_size(self, request: Request, url: Url, http_version: str) -> \
            int:
        endpoint = url.path
        if len(url.query) > 0:
            endpoint += f"?{url.query}"
        if isinstance(http_version, int):
            http_version = f"HTTP/{http_version / 10.0}".strip('.0')
        header_size = len(f"{request.method} {endpoint} {http_version}.\n")
        for key, value in request.headers.items():
            header_size += len(f"{key}: {value}\n")
        header_size += 2  # 2 CRLF
        return header_size

    @staticmethod
    def _get_resp_header_size(response: Response) -> int:
        url = parse_url(response.url)
        http_version = response.raw.version
        endpoint = url.path
        if url.query is not None and len(url.query) > 0:
            endpoint += f"?{url.query}"
        if isinstance(http_version, int):
            http_version = f"HTTP/{http_version / 10.0}".strip('.0')
        header_size = len(f"{http_version} {response.status_code} {response.reason}\n")
        for key, value in response.headers.items():
            header_size += len(f"{key}: {value}\n")
        header_size += 2  # 2 CRLF
        return header_size

    @staticmethod
    def _get_content(response: Response, comment: str = None) \
            -> dict:
        data = {
            'size': len(response.content) if response.content is not None else -1
        }
        compression = getattr(response.raw, 'compression', None)
        if compression is not None:
            data['compression'] = compression
        data['mimeType'] = response.headers.get('Content-Type', '')
        if response.content is not None:
            try:
                data['text'] = response.content.decode()
            except UnicodeDecodeError:
                data['text'] = base64.b64encode(response.content).decode()
                data['encoding'] = 'base64'
        else:
            data['text'] = ''
        if comment is not None:
            data['comment'] = comment
        return data

    @staticmethod
    def _cookiejar_to_dicts(rcj: RequestsCookieJar, url: Url) -> list[dict]:
        cookies = []
        cookie: Cookie
        for cookie in getattr(rcj, '_cookies', {}).get(url.hostname, {}).get(
                url.path, {}).values():
            cookie_dict = {
                'name': cookie.name,
                'value': cookie.value,
            }
            if cookie.path is not None:
                cookie_dict['path'] = cookie.path
            if cookie.domain is not None:
                cookie_dict['domain'] = cookie.domain
            if cookie.expires is not None:
                cookie_dict['expires'] = datetime.fromtimestamp(
                    cookie.expires).isoformat()
            cookie_dict['httponly'] = 'httponly' in getattr(cookie, '_rest').keys() \
                                      is not None
            if cookie.secure is not None:
                cookie_dict['secure'] = cookie.secure
            if cookie.comment is not None:
                cookie_dict['comment'] = cookie.comment
            cookies.append(cookie_dict)
        return cookies

    def __str__(self) -> str:
        return f"[{self.response.status_code}] {self.request.method} {self.request.url}"


class Log(JsonObject):
    """The root of the exported data"""

    version: str
    creator: Creator
    browser: Browser  # optional
    pages: list[Page]  # optional
    entries: list[Entry]
    comment: str  # optional

    def __init__(
            self,
            version: str,
            creator: Creator,
            entries: list[Entry],
            browser: Browser = None,
            pages: list[Page] = None,
            comment: str = None,
    ):
        super().__init__()
        self.version = version
        self.creator = creator
        self.entries = entries
        self.browser = browser
        self.pages = pages
        self.comment = comment

    @classmethod
    def from_dict(cls, data: dict, adapter: HTTPAdapter = None) -> 'Log':
        return cls(
            version=data['version'],
            creator=Creator.from_dict(data['creator']),
            browser=Browser.from_dict(
                data['browser']) if 'browser' in data.keys() else None,
            pages=list(
                map(Page.from_dict, data['pages'])) if 'pages' in data.keys() else None,
            entries=list(
                map(Entry.from_dict, data.get('entries', []), repeat(adapter))),
            comment=data.get('comment')
        )._setup_custom_properties(data)

    def to_dict(self) -> dict:
        data = {
            'version': self.version,
            'creator': self.creator.to_dict()
        }
        if self.browser is not None:
            data['browser'] = self.browser.to_dict()
        if self.pages is not None:
            data['pages'] = list(map(Page.to_dict, self.pages))
        data['entries'] = list(map(Entry.to_dict, self.entries))
        if self.comment is not None:
            data['comment'] = self.comment
        data.update(self.custom_properties)
        return data

    def __str__(self):
        if self.comment is not None:
            comment = f", {self.comment}"
        else:
            comment = ''
        return f"Log {self.version} ({self.creator}): " \
               f"{len(self.entries)} entries{comment}"


class Har(JsonObject):
    log: Log

    def __init__(
            self,
            log: Log
    ):
        super().__init__()
        self.log = log

    @classmethod
    def from_dict(cls, data: dict, adapter: HTTPAdapter = None) -> 'Har':
        return cls(
            log=Log.from_dict(data['log'], adapter)
        )._setup_custom_properties(data)

    def to_dict(self) -> dict:
        data = {
            'log': self.log.to_dict()
        }
        data.update(self.custom_properties)
        return data

    def __str__(self) -> str:
        return f"HAR: {self.log}"


class HarFile:
    _har: Har
    _fp: TextIO
    _mode: str
    _adapter: HTTPAdapter

    def __init__(self, file: Union[str, os.PathLike], mode: str = 'r', adapter: HTTPAdapter = None):
        if not isinstance(file, Path):
            file = Path(file)
        if not file.exists():
            file.parent.mkdir(parents=True, exist_ok=True)
            file.touch(exist_ok=True)
        self._fp = open(file, mode)
        self._mode = mode
        self._adapter = adapter
        try:
            self.load(json.load(self._fp))
        except JSONDecodeError as e:
            self._har = self._defaults()

    def load(self, data: dict):
        """
        Load HAR from json dict

        :param data: The json dict
        :type data: dict
        :return:
        """
        self._har = Har.from_dict(data, adapter=self._adapter)

    @staticmethod
    def _defaults() -> Har:
        """Construct a default HAR instance"""
        from spoofbot import __version__
        return Har(
            log=Log(
                version='1.2',
                creator=Creator(
                    name='Spoofbot',
                    version=__version__
                ),
                browser=Browser(
                    name='SpoofBot',
                    version=__version__
                ),
                pages=[],
                entries=[]
            )
        )

    def save(self, fp: TextIO = None, **kwargs):
        """
        Saves HAR to file

        :param fp: The file.
        :type fp: TextIO
        :param kwargs: Args to be passed to json.dump
        :return:
        """
        if fp is None:
            fp = self._fp
        fp.seek(0)
        json.dump(self._har.to_dict(), fp, **kwargs)
        fp.truncate()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._fp.close()

    @property
    def har(self) -> Har:
        return self._har

    @har.setter
    def har(self, value: Har):
        self._har = value
