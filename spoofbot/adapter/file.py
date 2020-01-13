import logging
import os
from io import BytesIO
from typing import Optional, List

from requests import Response, PreparedRequest
from requests.adapters import HTTPAdapter
from urllib3 import HTTPResponse
from urllib3.util import parse_url, Url

from spoofbot.adapter.common import MockHTTPResponse


class FileCacheAdapter(HTTPAdapter):
    _log: logging.Logger
    _path = ''
    _use_cache = True
    _hit = False
    _last_request: PreparedRequest
    _last_next_request_cache_url: Url
    _next_request_cache_url: Url = None
    EXTENSIONS = ['.html', '.jpg', '.jpeg', '.png', '.json']

    def __init__(self, path: str = '.cache'):
        super(FileCacheAdapter, self).__init__()
        self._log = logging.getLogger(self.__class__.__name__)
        self._path = path
        if not os.path.exists(self._path):
            os.makedirs(self._path)  # Don't use exists_ok=True; Might have path traversal

    @property
    def path(self) -> str:
        return self._path

    @property
    def use_cache(self) -> bool:
        return self._use_cache

    @use_cache.setter
    def use_cache(self, value: bool):
        self._use_cache = value

    @property
    def hit(self) -> bool:
        return self._hit

    @property
    def next_request_cache_url(self) -> Url:
        return self._next_request_cache_url

    @next_request_cache_url.setter
    def next_request_cache_url(self, value: Url):
        self._next_request_cache_url = value

    def send(self,
             request: PreparedRequest,
             stream=False,
             timeout=None,
             verify=True,
             cert=None,
             proxies=None) -> Response:
        self._last_request = request
        response = self._check_cache_for(request)
        if not response:
            response = super(FileCacheAdapter, self).send(request, stream, timeout, verify, cert, proxies)
            if not response.is_redirect:
                self._store(response)
        # noinspection PyTypeChecker
        self._last_next_request_cache_url, self._next_request_cache_url = self._next_request_cache_url, None
        return response

    def would_hit(self, url: str, headers: dict) -> bool:
        return os.path.exists(self._get_filename(parse_url(url), headers))

    def list_cached(self, url: str) -> List[Url]:
        urls = []
        parsed_url = parse_url(url)
        path = parsed_url.path.rstrip('/')
        for file in os.listdir(os.path.normpath(os.path.join(self._path, parsed_url.host + parsed_url.path))):
            urls.append(Url(
                parsed_url.scheme,
                host=parsed_url.hostname,
                path='/'.join((path, os.path.splitext(file)[0])),
                query=parsed_url.query,
                fragment=parsed_url.fragment
            ))
        return urls

    def _check_cache_for(self, request: PreparedRequest) -> Optional[Response]:
        url = parse_url(request.url)
        filepath = self._get_filename(url, request.headers)
        if self._use_cache:
            # self.log.debug(f"Looking for cached response at '{filepath}'")
            if os.path.exists(filepath):
                self._log.debug(f"{' ' * len(request.method)}Cache hit at '{filepath}'")
                self._hit = True
                response = self._load_response(filepath)
                return self.build_response(request, response)
            else:
                self._log.debug(f"{' ' * len(request.method)}Cache miss for '{filepath}'")
        self._hit = False
        return None

    def _get_filename(self, url: Url, headers: dict):
        if self._next_request_cache_url is not None:
            url = self._next_request_cache_url
        path = os.path.splitext(url.path)[0] + self._extract_extension(url, headers)
        return os.path.normpath(os.path.join(self._path, url.host + path))

    def _extract_extension(self, url: Url, headers: dict) -> str:
        # if url.query is not None:
        #     self.log.warning(f"Url has query ({url.query}), which gets ignored when looking in cache.")
        url_ext = os.path.splitext(url.path)[-1]
        if url_ext == '':
            # self.log.debug(f"No extension found in url path ({url.path}).")
            if headers and 'Accept' in headers:
                for mime_type in headers['Accept'].split(','):
                    for ext in self.EXTENSIONS:
                        if ext[1:] in mime_type:
                            # self.log.debug(f"Found extension '{ext[1:]}' in Accept header ({accept}).")
                            return ext
            else:
                pass
                # self.log.debug("No accept headers present")
            url_ext = '.html'
            # self.log.warning(f"No extension found using the Accept header. Assuming {url_ext[1:]}.")
            return url_ext
        if url_ext in self.EXTENSIONS:
            return url_ext
        return url_ext

    def _store(self, response: Response) -> Response:
        url = parse_url(response.request.url)
        filepath = self._get_filename(url, response.request.headers)
        directories = os.path.split(filepath)[0]
        if not os.path.exists(directories):
            os.makedirs(directories)  # Don't use exists_ok=True; Might have '..' in path
        with open(filepath, 'wb') as fp:
            fp.write(response.content)
        self._log.debug(f"{' ' * len(response.request.method)}Cached answer in '{filepath}'")
        return response

    def _load_response(self, filepath: str) -> HTTPResponse:
        with open(filepath, 'rb') as fp:
            text = fp.read()
        # body = text.encode('utf-8')
        return HTTPResponse(
            body=BytesIO(text),
            headers={},
            status=200,
            preload_content=False,
            original_response=MockHTTPResponse({})
        )

    def delete(self, url: str, headers: dict):
        url_parsed = parse_url(url)
        filepath = self._get_filename(url_parsed, headers)
        self._log.debug(f"Deleting cached response at '{filepath}'")
        if os.path.exists(filepath):
            os.remove(filepath)
            self._log.debug("Cache hit. Deleted response.")
        else:
            self._log.debug("Cache miss. No response to delete.")

    def delete_last(self):
        if self._last_request:
            temp_url, self.next_request_cache_url = self._next_request_cache_url, self._last_next_request_cache_url
            self.next_request_cache_url = self._last_next_request_cache_url
            self.delete(self._last_request.url, headers=self._last_request.headers)
            self.next_request_cache_url = temp_url
