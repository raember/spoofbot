import logging
import os
from typing import Optional, Set

from requests import Response, PreparedRequest
from requests.adapters import HTTPAdapter
from urllib3.util import parse_url, Url

from spoofbot.util import load_response


class FileCacheAdapter(HTTPAdapter):
    _log: logging.Logger
    _path = ''
    _use_cache = True
    _hit = False
    _last_request: PreparedRequest
    _last_next_request_cache_url: Url
    _next_request_cache_url: Url = None
    _backup: Optional[bytes] = None
    _backup_path: str = None
    _backup_and_miss_next_request: bool = False
    _indent: str = ''
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

    @property
    def backup_and_miss_next_request(self) -> bool:
        return self._backup_and_miss_next_request

    @backup_and_miss_next_request.setter
    def backup_and_miss_next_request(self, value: bool):
        self._backup_and_miss_next_request = value

    def send(self, request: PreparedRequest, stream=False, timeout=None, verify=True, cert=None, proxies=None
             ) -> Response:
        self._indent = ' ' * len(request.method)
        self._last_request = request
        response = None
        if self._use_cache:
            response = self._get_response_if_hit(request)
        if response is None:
            response = super(FileCacheAdapter, self).send(request, stream, timeout, verify, cert, proxies)
            if response.is_redirect:
                self._link_redirection(response)
            else:
                self._save_response(response)
        # noinspection PyTypeChecker
        self._last_next_request_cache_url, self._next_request_cache_url = self._next_request_cache_url, None
        return response

    def _link_redirection(self, response: Response):
        headers = dict(response.request.headers)
        path_from = self._get_filename(parse_url(response.request.url), headers)
        path_to = self._get_filename(parse_url(response.headers['Location']), headers)
        self._make_sure_dir_exists(path_from)
        os.symlink(path_to, path_from)
        self._log.debug(f"{self._indent}Symlinked redirection to target.")

    def would_hit(self, url: Url, headers: dict) -> bool:
        return os.path.exists(self._get_filename(url, headers))

    def list_cached(self, url: str) -> Set[Url]:
        urls = set()
        parsed_url = parse_url(url)
        path = parsed_url.path.rstrip('/')
        for file in os.listdir(os.path.normpath(os.path.join(self._path, parsed_url.host + parsed_url.path))):
            if os.path.isfile(os.path.normpath(os.path.join(self._path, parsed_url.host + parsed_url.path, file))):
                urls.add(Url(
                    parsed_url.scheme,
                    host=parsed_url.hostname,
                    path='/'.join((path, os.path.splitext(file)[0])),
                    query=parsed_url.query,
                    fragment=parsed_url.fragment
                ))
        return urls

    def _get_response_if_hit(self, request: PreparedRequest) -> Optional[Response]:
        url = parse_url(request.url)
        filepath = self._get_filename(url, dict(request.headers))
        if os.path.exists(filepath) and not self._backup_and_miss_next_request:
            self._log.debug(f"{self._indent}Cache hit at '{filepath}'")
            self._hit = True
            return self.build_response(request, load_response(filepath))
        else:
            self._log.debug(f"{self._indent}Cache miss for '{filepath}'")
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

    def _save_response(self, response: Response):
        filepath = self._get_filename(parse_url(response.request.url), dict(response.request.headers))
        if os.path.exists(filepath) and self._backup_and_miss_next_request:
            self._log.debug(f"{self._indent}Backing up old response.")
            self._backup_and_miss_next_request = False
            self._backup_path = filepath
            with open(filepath, 'rb') as fp:
                self._backup = fp.read()
        if self._save(response.content, filepath):
            self._log.debug(f"{self._indent}Cached answer in '{filepath}'")

    @staticmethod
    def _make_sure_dir_exists(path):
        directories = os.path.split(path)[0]
        if not os.path.exists(directories):
            os.makedirs(directories)  # Don't use exists_ok=True; Might have '..' in path

    def _save(self, content: bytes, path: str) -> bool:
        self._make_sure_dir_exists(path)
        try:
            with open(path, 'wb') as fp:
                fp.write(content)
            return True
        except Exception as e:
            self._log.error(f"{self._indent}Failed to save content to file: {e}")
            return False

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
            self.delete(self._last_request.url, headers=dict(self._last_request.headers))
            self.next_request_cache_url = temp_url

    def restore_backup(self) -> bool:
        if self._backup is None:
            self._log.error(f"{self._indent}No backup available.")
            return False
        self._log.debug(f"{self._indent}Restoring backup.")
        assert os.path.exists(self._backup_path)
        try:
            with open(self._backup_path, 'wb') as fp:
                fp.write(self._backup)
        except Exception as e:
            self._log.error(f"{self._indent}Failed to save content to file: {e}")
            return False
        self._backup = None
        self._backup_path = ''
        return True
