import logging
from pathlib import Path
from typing import Optional, Set

from requests import Response, PreparedRequest
from requests.adapters import HTTPAdapter
from urllib3.util import parse_url, Url

from spoofbot.util import load_response


class FileCache(HTTPAdapter):
    _log: logging.Logger
    _is_active: bool = True
    _is_passive: bool = True
    _is_offline: bool = False
    _cache_on_status: set = {200, 201, 300, 301, 302, 303, 307, 308}
    _cache_path: Path = None
    _add_ext: bool = False
    _hit = False
    _last_request: PreparedRequest
    _last_next_request_cache_url: Url
    _next_request_cache_url: Url = None
    _backup: Optional[bytes] = None
    _backup_path: Path = None
    _backup_and_miss_next_request: bool = False
    _indent: str = ''
    EXTENSIONS = ['.html', '.jpg', '.jpeg', '.png', '.json']

    def __init__(self, path: str = '.cache', **kwargs):
        super(FileCache, self).__init__(**kwargs)
        self._log = logging.getLogger(self.__class__.__name__)
        self._is_active = True
        self._is_passive = True
        self._is_offline = False
        self._cache_on_status = {200, 201, 300, 301, 302, 303, 307, 308}
        self._cache_path = Path(path)
        self._cache_path.mkdir(parents=True, exist_ok=True)
        self._add_ext = False

    @property
    def is_active(self) -> bool:
        """
        Return the cache state to active.

        If true, the FileCache will check new requests against the local cache for hits.
        Otherwise the FileCache will not check for hits.
        """
        return self._is_active

    @is_active.setter
    def is_active(self, value: bool):
        """
        Set whether the cache state is in active mode.

        If set to True, the FileCache will check new requests against the local cache for hits.
        :param value: The new state of the FileCache
        :type value: bool
        """
        self._is_active = value

    @property
    def is_passive(self) -> bool:
        """
        Get whether the cache state is in passive mode.

        If true, the FileCache will cache the answer of a successful request in the cache.
        Otherwise the FileCache will not cache the answer.
        """
        return self._is_passive

    @is_passive.setter
    def is_passive(self, value: bool):
        """
        Set whether the cache state is in passive mode.

        If set to True, the FileCache will cache the answer of a successful request in the cache.
        Otherwise the FileCache will not cache the answer.
        :param value: The new state of the FileCache
        :type value: bool
        """
        self._is_passive = value

    @property
    def is_offline(self) -> bool:
        """
        Get whether the cache state is in offline mode.

        If true, the FileCache will throw an exception if no cache hit occurs.
        Otherwise the FileCache will allow HTTP requests to remotes.
        """
        return self._is_offline

    @is_offline.setter
    def is_offline(self, value: bool):
        """
        Set whether the cache state is in offline mode.

        If set to True, the FileCache will throw an exception if no cache hit occurs.
        Otherwise the FileCache will allow HTTP requests to remotes.
        :param value: The new state of the FileCache
        :type value: bool
        """
        self._is_offline = value

    @property
    def cache_on_status(self) -> set[int]:
        """
        Get which response status leads to local caching of the response.

        :return: A set of status codes of responses to be cached after receiving
        :rtype: set[int]
        """
        return self._cache_on_status

    @cache_on_status.setter
    def cache_on_status(self, status_codes: set[int]):
        """
        Get which response status leads to local caching of the response.

        :param status_codes: The status codes
        :type status_codes: set[int]
        """
        self._cache_on_status = status_codes

    @property
    def cache_path(self) -> Path:
        return self._cache_path

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
        filepath = self.to_filepath(request.url, request.headers.get('Accept', None))
        if self._is_active:
            if filepath.exists():
                self._log.debug(f"{self._indent}  Cache hit")
                response = self._load_response(request, filepath)
            else:
                self._log.debug(f"{self._indent}  Cache miss")
        if response is None:
            if self._is_offline:
                # In offline mode, we cannot make new HTTP requests for cache misses
                raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), filepath)
            self._log.debug(f"{self._indent}  Sending HTTP request")
            response = super(FileCache, self).send(request, stream, timeout, verify, cert, proxies)
            self._last_request_timestamp = datetime.now()
            if self._is_passive and response.status_code in self._cache_on_status:
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
        target = self._get_filename(parse_url(response.headers['Location']), headers)
        target = Path(
            *['..' for _ in range(len(path.parts) - 2)],
            *target.parts[1:]
        )
        path.symlink_to(target)
        self._log.debug(f"{self._indent}Symlinked redirection to target.")

    def is_hit(self, url: Union[Url, str], accept_header: str = 'text/html') -> bool:
        return self.to_filepath(url, accept_header).exists()

    def _load_response(self, request: PreparedRequest, filepath: Path = None) -> Optional[Response]:
        # Get file filepath if not already given
        if filepath is None:
            filepath = self.to_filepath(request.url, request.headers.get('Accept', None))

        if filepath.is_file() and not self._backup_and_miss_next_request:
            self._log.debug(f"{self._indent}Cache hit at '{filepath}'")
            self._hit = True
            return self.build_response(request, load_response(filepath))
        elif filepath.is_symlink() and not self._backup_and_miss_next_request:
            self._log.debug(f"{self._indent}Cache hit redirection at '{filepath}'")
            from urllib3 import HTTPResponse
            import os
            from io import BytesIO
            self._log.debug(f"{self._indent}DIRECTS TO: https://{os.readlink(str(filepath)).lstrip('./')}")
            return self.build_response(request, HTTPResponse(
                body=BytesIO(b''),
                headers={'Location': f"https://{os.readlink(str(filepath)).lstrip('./')}"},
                status=302,
                preload_content=False
            ))
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

    def to_filepath(self, url: Union[Url, str], accept_header: str = 'text/html') -> Path:
        """
        Derives the filesystem filepath of a given url in the cache

        :param url: The url to convert
        :type url: Union[Url, str]
        :param accept_header: The Accept header value (used for deriving the extension if there is not any already)
        Set to None to suppress possibly adding an extension.
        :type accept_header: str
        :return: The filepath the url gets mapped to
        :rtype: Path
        """
        # Make sure we have a proper URL
        if isinstance(url, str):
            url = parse_url(url)

        # Append hostname to filepath
        host = url.host + (f":{url.port}" if url.port else '')
        path = Path(self._cache_path, host)

        # Append url filepath to file filepath
        url_path = url.path if url.path else ''
        for path_seg in url_path.strip('/').split('/'):
            # filepath /= Path(path_seg.encode('unicode_escape').decode('utf-8'))
            path /= Path(path_seg)

        # Append query to filepath
        for i, (key, val) in enumerate(parse_qsl(url.query)):
            key = quote_plus(key)
            val = quote_plus(val)
            if i == 0:  # Preserve the question mark for identifying the query in the filepath
                key = f"?{key}"
            path /= Path(f"{key}={val}")

        # Maybe add an extension
        if path.suffix == '' and accept_header is not None:
            for mimetype in str(accept_header).split(','):
                ext = f".{mimetype.split('/')[1].split(';')[0]}"
                if ext in self.EXTENSIONS:
                    path.with_suffix(ext)
                    break
            path.with_suffix('.html')
        return path

    def to_url(self, filepath: Union[str, os.PathLike]) -> Url:
        """
        Derives the url of a given filesystem path in the cache

        :param filepath: The path the url gets mapped to
        :type filepath: Union[str, os.PathLike]
        :return: The Url that would cause a hit in the cache using the given path.
        :rtype: Url
        """
        # Make sure we have a proper filepath
        if isinstance(filepath, str):
            filepath = Path(filepath)

        host = filepath.parts[1]
        paths = []
        query = None
        for part in reversed(filepath.parts[2:]):
            paths.append(part)
            if part.startswith('?'):  # All parts up until now were part of the query
                queries = []
                for query_part in reversed(paths):
                    queries.append(unquote_plus(query_part))
                query = '&'.join(queries)[1:]
                paths.clear()
        return Url('https', host=host, path='/'.join(paths), query=query)
