import logging
from pathlib import Path
from typing import Optional, Set

from requests import Response, PreparedRequest
from requests.adapters import HTTPAdapter
from urllib3.util import parse_url, Url

from spoofbot.util import load_response


class FileCacheAdapter(HTTPAdapter):
    _log: logging.Logger
    _path: Path = None
    _use_cache = True
    _hit = False
    _last_request: PreparedRequest
    _last_next_request_cache_url: Url
    _next_request_cache_url: Url = None
    _backup: Optional[bytes] = None
    _backup_path: Path = None
    _backup_and_miss_next_request: bool = False
    _indent: str = ''
    EXTENSIONS = ['.html', '.jpg', '.jpeg', '.png', '.json']

    def __init__(self, path: str = '.cache'):
        super(FileCacheAdapter, self).__init__()
        self._log = logging.getLogger(self.__class__.__name__)
        self._path = Path(path)
        if not self._path.exists():
            self._path.mkdir(parents=True)  # Don't use exists_ok=True; Might have path traversal

    @property
    def path(self) -> Path:
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
        path = self._get_filename(parse_url(response.request.url), headers)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.symlink_to(self._get_filename(parse_url(response.headers['Location']), headers))
        self._log.debug(f"{self._indent}Symlinked redirection to target.")

    def would_hit(self, url: Url, headers: dict) -> bool:
        return self._get_filename(url, headers).exists()

    def list_cached(self, url: Url) -> Set[Url]:
        urls = set()
        dir = self._get_filename(url, {}, add_ext=False)  # with no header, ".html" is assumed. strip the ".html"
        base_path = Path(self._path, url.host)
        for child in dir.glob('*'):
            if child.is_file():
                path = str(child.relative_to(base_path).with_suffix(''))
                if path.endswith('.html'):
                    path = path[:-5]
                if len(path) == 0:
                    path = '/'
                urls.add(Url(
                    scheme=url.scheme,
                    host=url.hostname,
                    path=path,
                    query=url.query,
                    fragment=url.fragment
                ))
        return urls

    def _get_response_if_hit(self, request: PreparedRequest) -> Optional[Response]:
        url = parse_url(request.url)
        filepath = self._get_filename(url, dict(request.headers))
        if filepath.exists() and not self._backup_and_miss_next_request:
            self._log.debug(f"{self._indent}Cache hit at '{filepath}'")
            self._hit = True
            return self.build_response(request, load_response(filepath))
        else:
            self._log.debug(f"{self._indent}Cache miss for '{filepath}'")
        self._hit = False
        return None

    def _get_filename(self, url: Url, headers: dict, add_ext: bool = True) -> Path:
        """
        Derive the file path of a URL in the cache.

        :param url: The URL to look up in the cache.
        :param headers: The headers for the potential request. Only the accept header is used to derive the file extension, which defaults to ".html"
        :return: The potential file path in cache of the given URL.
        :raises ValueError: The URL contained too many '..', leading to path traversal outside the designated path.
        """
        if self._next_request_cache_url is not None:
            url = self._next_request_cache_url
            del self._next_request_cache_url
        base_path = Path(self._path, url.host)
        url_path = url.path if url.path else ''
        if add_ext:
            url_path += self._extract_extension(url, headers)
        abs_filepath = Path(base_path, url_path.lstrip('/')).resolve()
        try:
            rel_filepath = abs_filepath.relative_to(base_path.resolve())
        except ValueError as e:
            self._log.error("Url contained path traversal.")
            raise e
        return Path(base_path, rel_filepath)

    def _extract_extension(self, url: Url, headers: dict) -> str:
        # if url.query is not None:
        #     self.log.warning(f"Url has query ({url.query}), which gets ignored when looking in cache.")
        url_ext = Path(url.path if url.path else '/').suffix
        if url_ext == '':
            # self.log.debug(f"No extension found in url path ({url.path}).")
            if headers and 'Accept' in headers:
                for mime_type in str(headers['Accept']).split(','):
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
        if filepath.exists() and self._backup_and_miss_next_request:
            self._log.debug(f"{self._indent}Backing up old response.")
            self._backup_and_miss_next_request = False
            self._backup_path = filepath
            with open(filepath, 'rb') as fp:
                self._backup = fp.read()
        if self._save(response.content, filepath):
            self._log.debug(f"{self._indent}Cached answer in '{filepath}'")

    def _save(self, content: bytes, path: Path) -> bool:
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(path, 'wb') as fp:
                fp.write(content)
            return True
        except Exception as e:
            self._log.error(f"{self._indent}Failed to save content to file: {e}")
            return False

    def delete(self, url: Url, headers: dict):
        filepath = self._get_filename(url, headers)
        self._log.debug(f"Deleting cached response at '{filepath}'")
        if filepath.exists():
            filepath.unlink()
            self._log.debug("Cache hit. Deleted response.")
        else:
            self._log.debug("Cache miss. No response to delete.")

    def delete_last(self):
        if self._last_request:
            temp_url, self.next_request_cache_url = self._next_request_cache_url, self._last_next_request_cache_url
            self.next_request_cache_url = self._last_next_request_cache_url
            self.delete(parse_url(self._last_request.url), headers=dict(self._last_request.headers))
            self.next_request_cache_url = temp_url

    def restore_backup(self) -> bool:
        if self._backup is None:
            self._log.error(f"{self._indent}No backup available.")
            return False
        self._log.debug(f"{self._indent}Restoring backup.")
        assert self._backup_path.exists()
        try:
            with open(self._backup_path, 'wb') as fp:
                fp.write(self._backup)
        except Exception as e:
            self._log.error(f"{self._indent}Failed to save content to file: {e}")
            return False
        self._backup = None
        self._backup_path = Path()
        return True
