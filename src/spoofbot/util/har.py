import base64
import json
import os
from abc import ABC
from datetime import datetime, timedelta
from http.cookiejar import Cookie
from itertools import repeat
from json import JSONDecodeError
from pathlib import Path
from typing import Union, TextIO
from urllib.parse import urlparse
from urllib.request import Request

from dateutil.parser import parse
# https://w3c.github.io/web-performance/specs/HAR/Overview.html
from requests import PreparedRequest, Response
from requests.adapters import HTTPAdapter
from requests.cookies import RequestsCookieJar
from urllib3.util import Url, parse_url

from spoofbot.util import dict_to_dict_list, url_to_query_dict_list, query_to_dict_list
from spoofbot.util.archive import request_from_har_entry, response_from_har_entry


class JsonObject(ABC):
    @classmethod
    def from_dict(cls, *args):
        """Create an instance from a json dict and possible additional args"""
        raise NotImplementedError()

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
        self.name = name
        self.version = version
        self.comment = comment

    @classmethod
    def from_dict(cls, data: dict) -> 'Creator':
        return cls(
            name=data['name'],
            version=data['version'],
            comment=data.get('comment', None)
        )

    def to_dict(self) -> dict:
        data = {
            'name': self.name,
            'version': self.version
        }
        if self.comment is not None:
            data['comment'] = self.comment
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
        self.name = name
        self.version = version
        self.comment = comment

    @classmethod
    def from_dict(cls, data: dict) -> 'Browser':
        return cls(
            name=data['name'],
            version=data['version'],
            comment=data.get('comment', None)
        )

    def to_dict(self) -> dict:
        data = {
            'name': self.name,
            'version': self.version
        }
        if self.comment is not None:
            data['comment'] = self.comment
        return data

    def __str__(self) -> str:
        comment = f" ({self.comment})" if self.comment is not None else ''
        return f"{self.name} {self.version}{comment}"


class PageTimings(JsonObject):
    """This object describes timings for various events (states) fired during the page load."""

    on_content_load: timedelta  # optional
    on_load: timedelta  # optional
    comment: str  # optional

    def __init__(
            self,
            on_content_load: timedelta = None,
            on_load: timedelta = None,
            comment: str = None
    ):
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
        )

    def to_dict(self) -> dict:
        data = {}
        if self.on_content_load is not None:
            data['onContentLoad'] = int(self.on_content_load.total_seconds() * 1000)
        if self.on_load is not None:
            data['onLoad'] = int(self.on_load.total_seconds() * 1000)
        if self.comment is not None:
            data['comment'] = self.comment
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
            title=data['title'],
            page_timings=PageTimings.from_dict(data['pageTimings']),
            comment=data.get('comment', None)
        )

    def to_dict(self) -> dict:
        data = {
            'startedDateTime': self.started_datetime.isoformat(),
            'id': self.id,
            'title': self.title,
            'pageTimings': self.page_timings.to_dict()
        }
        if self.comment is not None:
            data['comment'] = self.comment
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
        )

    def to_dict(self) -> dict:
        data = {}
        if self.expires is not None:
            data['expires'] = self.expires.isoformat()
        data['lastAccess'] = self.last_access.isoformat()
        data['eTag'] = self.e_tag
        data['hitCount'] = self.hit_count
        if self.comment is not None:
            data['comment'] = self.comment
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
        return f"{expires}Last access: {self.last_access}, Hits: {self.hit_count}{comment}"


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
        self.before_request = before_request
        self.after_request = after_request
        self.comment = comment

    @classmethod
    def from_dict(cls, data: dict) -> 'Cache':
        return cls(
            before_request=CacheStats.from_dict(data['beforeRequest']) if 'beforeRequest' in data.keys() else None,
            after_request=CacheStats.from_dict(data['afterRequest']) if 'afterRequest' in data.keys() else None,
            comment=data.get('comment', None)
        )

    def to_dict(self) -> dict:
        data = {}
        if self.before_request is not None:
            data['beforeRequest'] = self.before_request.to_dict()
        if self.after_request is not None:
            data['afterRequest'] = self.after_request.to_dict()
        if self.comment is not None:
            data['comment'] = self.comment
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
        blocked = timedelta(seconds=float(data.get('blocked', 0.0)))
        if blocked.total_seconds() < 0.0:
            blocked = -1
        dns = timedelta(seconds=float(data.get('dns', 0.0)))
        if dns.total_seconds() < 0.0:
            dns = -1
        connect = timedelta(seconds=float(data.get('connect', 0.0)))
        if connect.total_seconds() < 0.0:
            connect = -1
        ssl = timedelta(seconds=float(data.get('ssl', 0.0)))
        if ssl.total_seconds() < 0.0:
            ssl = -1
        return cls(
            blocked=blocked,
            dns=dns,
            connect=connect,
            ssl=ssl,
            send=timedelta(milliseconds=float(data['send'])),
            wait=timedelta(milliseconds=float(data['wait'])),
            receive=timedelta(milliseconds=float(data['receive'])),
            comment=data.get('comment', None)
        )

    def to_dict(self) -> dict:
        data = {}
        if self.blocked is not None:
            if isinstance(self.blocked, int):
                data['blocked'] = self.blocked
            else:
                data['blocked'] = max(int(self.blocked.total_seconds() * 1000), -1)
        if self.dns is not None:
            if isinstance(self.dns, int):
                data['dns'] = self.dns
            else:
                data['dns'] = max(int(self.dns.total_seconds() * 1000), -1)
        if self.connect is not None:
            if isinstance(self.connect, int):
                data['connect'] = self.connect
            else:
                data['connect'] = max(int(self.connect.total_seconds() * 1000), -1)
        if self.ssl is not None:
            if isinstance(self.ssl, int):
                data['ssl'] = self.ssl
            else:
                data['ssl'] = max(int(self.ssl.total_seconds() * 1000), -1)
        if self.send is not None:
            if isinstance(self.send, int):
                data['send'] = self.send
            else:
                data['send'] = max(int(self.send.total_seconds() * 1000), -1)
        if self.wait is not None:
            if isinstance(self.wait, int):
                data['wait'] = self.wait
            else:
                data['wait'] = max(int(self.wait.total_seconds() * 1000), -1)
        if self.receive is not None:
            if isinstance(self.receive, int):
                data['receive'] = self.receive
            else:
                data['receive'] = max(int(self.receive.total_seconds() * 1000), -1)
        if self.comment is not None:
            data['comment'] = self.comment
        return data

    def __str__(self) -> str:
        total = self.total
        return f"total {str(total)} {self.comment if self.comment is not None else ''}".strip()


class Entry(JsonObject):
    """Represents an array with all exported HTTP requests."""

    page_ref: str  # optional
    started_datetime: datetime
    time: timedelta
    request: PreparedRequest
    response: Response
    cache: dict
    timings: Timings
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
            comment: str = None
    ):
        self.started_datetime = started_datetime
        self.time = time
        self.request = request
        self.response = response
        if cache is None:
            cache = {}
        self.cache = cache
        self.timings = timings
        self.page_ref = page_ref
        self.server_ip_address = server_ip_address
        self.connection = connection
        self.comment = comment

    @classmethod
    def from_dict(cls, data: dict, adapter: HTTPAdapter = None) -> 'Entry':
        if adapter is None:
            adapter = HTTPAdapter()
        req, httpver = request_from_har_entry(data)
        preq = req.prepare()
        hresp = response_from_har_entry(data)
        if httpver.upper().startswith('HTTP/'):
            hresp.version = int(httpver.split('/')[1].replace('.', '').ljust(2, '0'))
        resp: Response = adapter.build_response(preq, hresp)
        resp.elapsed = timedelta(milliseconds=int(data['time']))
        resp.reason = data['response']['statusText']
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
            comment=data.get('comment', None)
        )

    def to_dict(self) -> dict:
        data = {}
        if self.page_ref is not None:
            data['pageref'] = self.page_ref
        data['startedDateTime'] = self.started_datetime.isoformat()
        data['time'] = int(self.time.total_seconds() * 1000)
        data['request'] = self._req_to_dict(self.request, self.response.raw.version)
        data['response'] = self._resp_to_dict(self.response)
        data['cache'] = self.cache
        data['timings'] = self.timings.to_dict()
        if self.server_ip_address is not None:
            data['serverIPAddress'] = self.server_ip_address
        if self.connection is not None:
            data['connection'] = self.connection
        if self.comment is not None:
            data['comment'] = self.comment
        return data

    @staticmethod
    def _req_to_dict(request: PreparedRequest, http_version: int) -> dict:
        cookie_jar: RequestsCookieJar = getattr(request, '_cookies')
        f_cookies_for_request = getattr(cookie_jar, '_cookies_for_request')
        cookies = Entry._cookiejar_to_dicts(f_cookies_for_request(Request(
            url=request.url,
            data=request.body,
            method=request.method,
        )),
            url=parse_url(request.url)
        )
        url = urlparse(request.url)
        endpoint = url.path
        if len(url.query) > 0:
            endpoint += f"?{url.query}"
        http_ver_str = f"HTTP/{http_version / 10.0}".strip('.0')
        header_size = len(f"{request.method} {endpoint} {http_ver_str}.\n")
        for key, value in request.headers.items():
            header_size += len(f"{key}: {value}\n")
        header_size += 2  # 2 CRLF
        data = {
            'bodySize': len(request.body) if request.body is not None else 0,
            'method': request.method.upper(),
            'url': request.url,
            'httpVersion': http_ver_str,
            'headers': dict_to_dict_list(request.headers),
            'cookies': cookies,
            'queryString': url_to_query_dict_list(request.url),
            'headersSize': header_size
        }
        if request.method.upper() == 'POST':
            mimetype = request.headers.get('Content-Type', '')
            if mimetype == 'application/x-www-form-urlencoded':
                params = query_to_dict_list(request.body)
            else:
                params = []
            data['postData'] = {
                'mimeType': mimetype,
                'params': params,
                'text': request.body
            }
        return data

    @staticmethod
    def _resp_to_dict(response: Response) -> dict:
        return {
            'status': response.status_code,
            'statusText': response.reason,
            'httpVersion': f"HTTP/{response.raw.version / 10}".strip('.0'),
            'cookies': Entry._cookiejar_to_dicts(response.cookies, parse_url(response.url)),
            'headers': dict_to_dict_list(response.headers),
            'content': Entry._get_content(response),
            'redirectURL': response.headers.get('Location', ''),
            'headerSize': 0,
            'bodySize': len(response.content) if response.content is not None else -1,
        }

    @staticmethod
    def _get_content(response) -> dict:
        data = {
            'size': len(response.content) if response.content is not None else -1,
            'mimeType': response.headers.get('Content-Type', '')
        }
        if response.content is not None:
            try:
                data['text'] = response.content.decode()
            except UnicodeDecodeError:
                data['text'] = base64.b64encode(response.content).decode()
                data['encoding'] = 'base64'
        else:
            data['text'] = ''
        return data

    @staticmethod
    def _cookiejar_to_dicts(rcj: RequestsCookieJar, url: Url) -> list[dict]:
        cookies = []
        cookie: Cookie
        for cookie in getattr(rcj, '_cookies', {}).get(url.hostname, {}).get(url.path, {}).values():
            cookie_dict = {
                'name': cookie.name,
                'value': cookie.value,
            }
            if cookie.path is not None:
                cookie_dict['path'] = cookie.path
            if cookie.domain is not None:
                cookie_dict['domain'] = cookie.domain
            if cookie.expires is not None:
                cookie_dict['expires'] = datetime.fromtimestamp(cookie.expires).isoformat()
            cookie_dict['httponly'] = 'httponly' in getattr(cookie, '_rest').keys() is not None
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
            browser=Browser.from_dict(data['browser']) if 'browser' in data.keys() else None,
            pages=list(map(Page.from_dict, data['pages'])) if 'pages' in data.keys() else None,
            entries=list(map(Entry.from_dict, data.get('entries', []), repeat(adapter))),
            comment=data.get('comment')
        )

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
        return data

    def __str__(self):
        if self.comment is not None:
            comment = f", {self.comment}"
        else:
            comment = ''
        return f"Log {self.version} ({self.creator}): {len(self.entries)} entries{comment}"


class Har(JsonObject):
    log: Log

    def __init__(
            self,
            log: Log
    ):
        self.log = log

    @classmethod
    def from_dict(cls, data: dict, adapter: HTTPAdapter = None) -> 'Har':
        return cls(
            log=Log.from_dict(data['log'], adapter)
        )

    def to_dict(self) -> dict:
        return {
            'log': self.log.to_dict()
        }

    def __str__(self) -> str:
        return f"HAR: {self.log}"


class HarFile:
    _har: Har
    _fp: TextIO
    _mode: str
    _adapter: HTTPAdapter

    def __init__(self, file: Union[str, os.PathLike], adapter: HTTPAdapter, mode: str = 'r'):
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
        except JSONDecodeError:
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

    def save(self, fp: TextIO = None):
        """
        Saves HAR to file

        :param fp: The file.
        :type fp: TextIO
        :return:
        """
        if fp is None:
            fp = self._fp
        fp.seek(0)
        json.dump(self._har.to_dict(), fp, indent='\t')
        fp.truncate()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._fp.close()

    @property
    def har(self) -> Har:
        return self._har
