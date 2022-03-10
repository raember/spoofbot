import base64
import os
from datetime import timedelta
from io import BytesIO
from pathlib import Path
from typing import Union, Optional

from cryptography.hazmat.primitives._serialization import Encoding
from requests import Response, Session, Request
from requests.structures import CaseInsensitiveDict
from urllib3 import HTTPResponse

from spoofbot.adapter.cache import MemoryCacheAdapter
from spoofbot.util import HarFile, Entry, Timings, Har, Browser, \
    dict_list_to_tuple_list, dict_list_to_dict
from spoofbot.util.file import MockHTTPResponse


class HarCache(MemoryCacheAdapter):
    """
    HAR cache adapter.

    This HTTPAdapter provides an interface to a HAR (HTTP archive) file. It can read
    and write HAR files and can be used to find stored responses to corresponding
    requests.
    """
    _har_file: HarFile
    _har: Har
    _expect_new_entry: bool

    def __init__(
            self,
            cache_path: Union[str, os.PathLike],
            mode: str = 'r',
            is_active: bool = True,
            is_offline: bool = False,
            is_passive: bool = True,
            delete_after_hit: bool = False,
            match_headers: bool = True,
            match_header_order: bool = False,
            match_data: bool = True
    ):
        """
        Creates a cache HTTP adapter that is based on an HAR file.

        :param cache_path: The path to the HAR file
        :type cache_path: Union[str, os.PathLike]
        :param mode: In what mode the HAR file should be opened. Default: r
        :type mode: str
        :param is_active: Whether the cache should be checked for hits. Default: True
        :type is_active: bool
        :param is_offline: Whether to block outgoing HTTP requests. Default: False
        :type is_offline: bool
        :param is_passive: Whether to store responses in the cache. Default: True
        :type is_passive: bool
        :param delete_after_hit: Whether to delete responses from the cache. Default:
            False
        :type delete_after_hit: bool
        :param match_headers: Whether to check for headers to match. Default: True
        :type match_headers: bool
        :param match_header_order: Whether to check for the header order to match:
        Default: False
        :type match_header_order: bool
        :param match_data: Whether to check for the request body to match. Default: True
        """
        super(HarCache, self).__init__(
            cache_path=cache_path,
            is_active=is_active,
            is_offline=is_offline,
            is_passive=is_passive,
            delete_after_hit=delete_after_hit,
            match_headers=match_headers,
            match_header_order=match_header_order,
            match_data=match_data
        )
        if not isinstance(cache_path, Path):
            cache_path = Path(cache_path)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._mode = mode
        self._har_file = HarFile(cache_path, mode=self._mode, adapter=self)
        self._har = self._har_file.har
        self._expect_new_entry = False
        for entry in self._har.log.entries:
            self._timestamp = entry.started_datetime
            self._store_response(entry.response)
        self._har.log.entries = []

    @property
    def har_file(self) -> HarFile:
        self._har_file.har = self.har
        return self._har_file

    @property
    def har(self) -> Har:
        har = Har.from_dict(self._har.to_dict(), self)
        for response in self._iter_entries():
            entry = Entry(
                started_datetime=self._timestamp,
                time=response.elapsed,
                request=response.request,
                response=response,
                cache={},
                timings=Timings(
                    send=timedelta(0),
                    wait=response.elapsed,
                    receive=timedelta(0)
                ),
                page_ref=self._har.log.pages[-1].id
                if self._har.log.pages is not None and
                   len(self._har.log.pages) > 0 else None,
                server_ip_address=getattr(response, 'ip', None),
                connection=getattr(response, 'port', None),
                comment=None
            )
            cert = getattr(response, 'cert', None)
            if cert is not None:
                entry.custom_properties['_cert'] = cert
            cert_bin = getattr(response, 'cert_bin', None)
            if cert_bin is not None:
                entry.custom_properties['_cert_bin'] = base64.b64encode(
                    cert_bin).decode()
            x509cert = getattr(response, 'cert_x509', None)
            if x509cert is not None:
                entry.custom_properties['_cert_x509'] = x509cert.public_bytes(
                    Encoding.PEM).decode('utf-8')
            if hasattr(response, 'ip'):
                entry.custom_properties['_ip'] = getattr(response, 'ip')
            if hasattr(response, 'port'):
                entry.custom_properties['_port'] = getattr(response, 'port')
            har.log.entries.append(entry)
        return har

    def __enter__(self):
        self._har_file.__enter__()
        self._har = self._har_file.har
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.har_file.__exit__(exc_type, exc_val, exc_tb)

    def close(self):
        self.__exit__(None, None, None)

    def prepare_session(self, session: Session):
        super(HarCache, self).prepare_session(session)
        from spoofbot import Browser as SBBrowser
        if isinstance(session, SBBrowser):
            self._har.log.browser = Browser(
                name=session.name,
                version=session.version,
                comment="Created with Spoofbot"
            )

    def _store_response(self, response: Response):
        super(HarCache, self)._store_response(response)
        self._expect_new_entry = True


def request_from_har_entry(entry: dict) -> tuple[Request, str]:
    request_entry = entry['request']
    data = {}
    if 'postData' in request_entry:
        post_data = dict_list_to_tuple_list(request_entry['postData']['params'],
                                            case_insensitive=False)
        data = '&'.join(map('='.join, post_data))
        if len(data) == 0:
            data = request_entry['postData']['text']
    return Request(
        method=request_entry['method'].upper(),
        url=request_entry['url'],
        headers=CaseInsensitiveDict(
            dict_list_to_dict(request_entry['headers'], case_insensitive=True)),
        data=data,
        cookies=dict_list_to_dict(request_entry['cookies'])
    ), request_entry['httpVersion'].upper()


def response_from_har_entry(entry: dict) -> Optional[HTTPResponse]:
    response_entry = entry['response']
    if response_entry is None:
        return None

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
    # Hack to prevent already decoded contents to be decoded again
    resp.CONTENT_DECODERS = []
    return resp
