import logging
import os
from io import BytesIO
from typing import Optional

from requests import Response, PreparedRequest
from urllib3 import HTTPResponse
from urllib3.util import parse_url, Url

from webot.adapter.common import MockHTTPResponse, ReportingAdapter


class CacheAdapter(ReportingAdapter):
    _log: logging.Logger
    _path = ''
    _use_cache = True
    _hit = False
    _last_request: PreparedRequest
    EXTENSIONS = ['.html', '.jpg', '.jpeg', '.png', '.json']

    def __init__(self, path: str = '.cache'):
        super(CacheAdapter, self).__init__()
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

    def send(self,
             request: PreparedRequest,
             stream=False,
             timeout=None,
             verify=True,
             cert=None,
             proxies=None) -> Response:
        self._last_request = request
        self._report_request(request)
        response = self._check_cache_for(request)
        if not response:
            response = super(CacheAdapter, self).send(request, stream, timeout, verify, cert, proxies)
            self._store(response)
        self._report_response(response)
        return response

    def _check_cache_for(self, request: PreparedRequest) -> Optional[Response]:
        url = parse_url(request.url)
        filepath = self._get_filename(url, request.headers)
        if self._use_cache:
            # self.log.debug(f"Looking for cached response at '{filepath}'")
            if os.path.exists(filepath):
                self._log.debug(f"Cache hit at '{filepath}'")
                self._hit = True
                response = self._load_response(filepath)
                return self.build_response(request, response)
            else:
                self._log.debug(f"Cache miss for '{filepath}'")
        self._hit = False
        return None

    def _get_filename(self, url: Url, headers: dict):
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
        self._log.error(f"None of the supported extensions matched '{url_ext}'.")
        return url_ext

    def _store(self, response: Response) -> Response:
        url = parse_url(response.request.url)
        filepath = self._get_filename(url, response.request.headers)
        directories = os.path.split(filepath)[0]
        if not os.path.exists(directories):
            os.makedirs(directories)  # Don't use exists_ok=True; Might have '..' in path
        with open(filepath, 'wb') as fp:
            fp.write(response.content)
        self._log.debug(f"Cached answer in '{filepath}'")
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
            self.delete(self._last_request.url, headers=self._last_request.headers)
