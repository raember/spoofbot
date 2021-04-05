import errno
import logging
import os
from pathlib import Path
from queue import Queue
from typing import Optional, Union

from requests import Response, PreparedRequest
from requests.adapters import HTTPAdapter
from urllib3.util import parse_url, Url

from spoofbot.util import load_response
from spoofbot.util.file import to_filepath, get_symlink_path


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
    _backup: dict[PreparedRequest, bytes] = {}
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
        """
        The root path of the cache.
        """
        return self._cache_path

    @cache_path.setter
    def cache_path(self, path: Path):
        """
        The root path of the cache.

        :param path: The new path
        :type path: Path
        """
        self._cache_path = path

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

    def send(self, request: PreparedRequest, stream=False, timeout=None, verify=True, cert=None, proxies=None
             ) -> Response:
        self._indent = ' ' * len(request.method)
        self._last_request = request
        response = None
        filepath = to_filepath(request.url, self._cache_path)
        if self._is_active:
            if filepath.exists():
                self._log.debug(f"{self._indent}  Cache hit")
                response = self._load_response(request, filepath)
            else:
                self._log.debug(f"{self._indent}  Cache miss")
        if response is None:
            if self._is_offline:
                # In offline mode, we cannot make new HTTP requests for cache misses
                raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), str(filepath))
            self._log.debug(f"{self._indent}  Sending HTTP request.")
            response = super(FileCache, self).send(request, stream, timeout, verify, cert, proxies)
            if self._is_passive and response.status_code in self._cache_on_status:
                if filepath.exists():
                    # TODO: Handle case where response was already cached. Backup mechanism desired
                    pass
                self._save_response(response, filepath)
        # noinspection PyTypeChecker
        self._last_next_request_cache_url, self._next_request_cache_url = self._next_request_cache_url, None
        return response

    def is_hit(self, url: Union[Url, str]) -> bool:
        return to_filepath(url, self._cache_path).exists()

    def _backup_cached_response(self, request: PreparedRequest, filepath: Path):
        assert filepath.exists()
        with open(filepath, 'rb') as fp:
            self._backup[request] = fp.read()

    def _load_response(self, request: PreparedRequest, filepath: Path) -> Optional[Response]:
        # Get file filepath if not already given
        if filepath is None:
            filepath = to_filepath(request.url, self._cache_path)

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
        filepath.parent.mkdir(parents=True, exist_ok=True)
        if response.is_redirect:
            # If the response is a redirection, use a symlink to simulate that
            target = to_filepath(parse_url(response.headers['Location']))
            target = get_symlink_path(filepath, target, self._cache_path)
            filepath.symlink_to(target)
            self._log.debug(f"{self._indent}  Symlinked redirection to target.")
        else:
            if filepath.exists() and self._backup_and_miss_next_request:
                self._log.debug(f"{self._indent}  Backing up old response.")
                self._backup_and_miss_next_request = False
                self._backup_path = filepath
                with open(filepath, 'rb') as fp:
                    self._backup = fp.read()
            if self._save(response.content, filepath):
                self._log.debug(f"{self._indent}  Saved response to cache.")

    def _save(self, content: bytes, path: Path) -> bool:
        try:
            with open(path, 'wb') as fp:
                fp.write(content)
            return True
        except Exception as e:
            self._log.error(f"{self._indent}  Failed to save content to file: {e}")
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
