import errno
import logging
import os
from pathlib import Path
from typing import Optional, Union

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
    _hit = False
    _last_request: PreparedRequest
    _last_next_request_cache_url: Url
    _next_request_cache_url: Url = None
    _backup: Optional[bytes] = None
    _backup_path: Path = None
    _backup_and_miss_next_request: bool = False
    _indent: str = ''

    def __init__(self, path: str = '.cache', **kwargs):
        super(FileCache, self).__init__(**kwargs)
        self._log = logging.getLogger(self.__class__.__name__)
        self._is_active = True
        self._is_passive = True
        self._is_offline = False
        self._cache_on_status = {200, 201, 300, 301, 302, 303, 307, 308}
        self._cache_path = Path(path)
        self._cache_path.mkdir(parents=True, exist_ok=True)

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

    # TODO: Figure out a good way of keeping track of hits vs misses of the last couple of requests
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
            if self._is_passive and response.status_code in self._cache_on_status:
                if response.is_redirect:
                    self._link_redirection(response, filepath)
                else:
                    self._save_response(response, filepath)
        # noinspection PyTypeChecker
        self._last_next_request_cache_url, self._next_request_cache_url = self._next_request_cache_url, None
        return response

    def _link_redirection(self, response: Response, filepath: Path):
        headers = dict(response.request.headers)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        target = self.to_filepath(parse_url(response.headers['Location']))
        target = Path(
            *['..' for _ in range(len(filepath.parts) - 2)],
            *target.parts[1:]
        )
        filepath.symlink_to(target)
        self._log.debug(f"{self._indent}Symlinked redirection to target.")

    def is_hit(self, url: Union[Url, str], accept_header: str = 'text/html') -> bool:
        return self.to_filepath(url, accept_header).exists()

    def _load_response(self, request: PreparedRequest, filepath: Path) -> Optional[Response]:
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

    def _save_response(self, response: Response, filepath: Path):
        if response.is_redirect:
            self._link_redirection(response, filepath)
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
