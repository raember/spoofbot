import errno
import os
from pathlib import Path
from typing import Union, Optional

from loguru import logger
from requests import Response, PreparedRequest
from requests.adapters import HTTPAdapter
from urllib3.util import parse_url, Url

from spoofbot.util import load_response
from spoofbot.util.file import to_filepath, get_symlink_path, CACHE_DEFAULT_PATH, \
    DEFAULT_CACHEABLE_STATUSES, IGNORE_QUERIES


class FileCache(HTTPAdapter):
    _cache_path: Path
    _is_active: bool
    _is_passive: bool
    _is_offline: bool
    _cache_on_status: set[int]
    _ignore_queries: set[str]
    _hit: bool
    _backup: Optional['Backup']
    _indent: str

    def __init__(
            self,
            path: Union[str, os.PathLike] = CACHE_DEFAULT_PATH,
            active: bool = True,
            passive: bool = True,
            offline: bool = False,
            cache_on_status: set[int] = None,
            ignore_queries: set[str] = None,
            **kwargs
    ):
        """Initializes the file cache.

        :param path: The path for the root of the file cache
        :type path: Union[str, os.PathLike]
        :param active: Set the cache in active mode.
        :type active: bool
        :param passive: Set the cache in passive mode.
        :type passive: bool
        :param offline: Set the cache in strict offline mode.
        :type offline: bool
        :param cache_on_status: Only cache responses on these status codes.
        :type cache_on_status: set[int]
        :param ignore_queries: Ignore these queries when determining the file path.
        :type ignore_queries: set[str]
        :param kwargs: Additional args to be passed to the HTTPAdapter constructor
        :type kwargs: dict
        """
        super(FileCache, self).__init__(**kwargs)
        self._cache_path = Path(path) if isinstance(path, str) else path
        self._cache_path.mkdir(parents=True, exist_ok=True)
        self._is_active = active
        self._is_passive = passive
        self._is_offline = offline
        if cache_on_status is None:
            cache_on_status = DEFAULT_CACHEABLE_STATUSES
        self._cache_on_status = cache_on_status
        if ignore_queries is None:
            ignore_queries = IGNORE_QUERIES
        self._ignore_queries = ignore_queries
        self._hit = False
        self._backup = None
        self._indent = ''

    @property
    def cache_path(self) -> Path:
        """
        The root path of the cache.
        """
        return self._cache_path

    @cache_path.setter
    def cache_path(self, path: Union[str, os.PathLike]):
        """
        The root path of the cache.

        :param path: The new path
        :type path: Union[str, os.PathLike]
        """
        self._cache_path = Path(path) if isinstance(path, str) else path

    @property
    def is_active(self) -> bool:
        """
        Get whether the cache is in active mode.

        If true, the FileCache will check new requests against the local cache for hits.
        Otherwise the FileCache will not check for hits.
        """
        return self._is_active

    @is_active.setter
    def is_active(self, value: bool):
        """
        Set whether the cache is in active mode.

        If set to True, the FileCache will check new requests against the local cache for hits.
        Otherwise the FileCache will not check for hits.
        :param value: The new state of the FileCache
        :type value: bool
        """
        self._is_active = value
        if not self._is_active and self._is_offline:
            logger.warning("Active mode requires offline mode to be disabled.")

    @property
    def is_passive(self) -> bool:
        """
        Get whether the cache is in passive mode.

        If true, the FileCache will cache the answer of a successful request in the cache.
        Otherwise the FileCache will not cache the answer.
        """
        return self._is_passive

    @is_passive.setter
    def is_passive(self, value: bool):
        """
        Set whether the cache is in passive mode.

        If true, the FileCache will cache the answer of a successful request in the cache.
        Otherwise the FileCache will not cache the answer.
        :param value: The new state of the FileCache
        :type value: bool
        """
        self._is_passive = value

    @property
    def is_offline(self) -> bool:
        """
        Get whether the cache is in offline mode.

        If true, the FileCache will throw an exception if no cache hit occurs.
        Otherwise the FileCache will allow HTTP requests to remotes.
        Offline mode does not work if active mode is not enabled.
        """
        return self._is_offline

    @is_offline.setter
    def is_offline(self, value: bool):
        """
        Set whether the state is in offline mode.

        If set to True, the FileCache will throw an exception if no cache hit occurs.
        Otherwise the FileCache will allow HTTP requests to remotes.
        Offline mode does not work if active mode is disabled.
        :param value: The new state of the FileCache
        :type value: bool
        """
        self._is_offline = value
        if self._is_offline and not self._is_active:
            logger.warning("Offline mode requires active mode to be enabled.")

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
    def ignore_queries(self) -> set[str]:
        """
        Set of query parameters to ignore when mapping a URL to a path.

        Defaults to {'_'}
        """
        return self._ignore_queries

    @ignore_queries.setter
    def ignore_queries(self, params: set[str]):
        """
        Set of query parameters to ignore when mapping a URL to a path.

        :param params: The new set or params to ignore
        :type params: set[str]
        """
        self._ignore_queries = params

    @property
    def hit(self) -> bool:
        """
        True if the last processed request was a hit in the cache
        """
        return self._hit

    @property
    def backup_data(self) -> Optional['Backup']:
        return self._backup

    @property
    def is_backing_up(self) -> bool:
        return self._backup is not None

    def send(self, request: PreparedRequest, stream=False, timeout=None, verify=True, cert=None, proxies=None
             ) -> Response:
        # Set indentation for aligned log messages
        self._indent = ' ' * len(request.method)
        filepath = to_filepath(request.url, self._cache_path, self._ignore_queries)
        if self._is_active:  # Check for a cached answer
            if filepath.exists():
                logger.debug(f"{self._indent}  Cache hit")
                self._hit = True
                return self._load_response(request, filepath)
        logger.debug(f"{self._indent}  Cache miss")
        self._hit = False

        # In offline mode, we cannot make new HTTP requests for cache misses
        if self._is_offline:
            raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), str(filepath))

        # Send HTTP request to remote
        response = super(FileCache, self).send(request, stream, timeout, verify, cert, proxies)
        if self._is_passive and response.status_code in self._cache_on_status:  # Store received response in cache
            if self._backup is not None:
                self._backup.backup_request(request, filepath)
            self._save_response(response, filepath)
        return response

    def is_hit(self, url: Union[Url, str]) -> bool:
        """
        Check whether a request to a given URL would hit the cache.

        :param url: The URL
        :type url: Url
        :return: True if it would be a hit. False otherwise.
        :rtype: bool
        """
        return to_filepath(url, self._cache_path, self._ignore_queries).exists()

    def _load_response(self, request: PreparedRequest, filepath: Path) -> Response:
        """
        Load response from cache.

        :param request: The request
        :type request: PreparedRequest
        :param filepath: The path of the cached response
        :type filepath: Path
        :return: The cached response
        :rtype: Response
        """
        # Get file filepath if not already given
        if filepath is None:
            filepath = to_filepath(request.url, self._cache_path, self._ignore_queries)

        assert filepath.exists()

        if filepath.is_file():
            return self.build_response(request, load_response(filepath))
        elif filepath.is_symlink():
            from urllib3 import HTTPResponse
            from io import BytesIO
            return self.build_response(request, HTTPResponse(
                body=BytesIO(b''),
                headers={'Location': f"https://{os.readlink(str(filepath)).lstrip('./')}"},
                status=302,
                preload_content=False
            ))
        else:
            raise NotImplementedError("File path exists but is neither a file nor a symlink?")

    def _save_response(self, response: Response, filepath: Path):
        """
        Save response into the cache.

        :param response: The response to cache
        :type response: Response
        :param filepath: The path of the cached response
        :type filepath: Path
        """
        filepath.parent.mkdir(parents=True, exist_ok=True)
        if response.is_redirect:  # If the response is a redirection, use a symlink to simulate that
            redirect = response.headers['Location']
            if redirect.startswith('/'):  # Host-less url
                redirect = parse_url(response.url).host + redirect
            redirect_url = parse_url(redirect)
            target = to_filepath(redirect_url, self._cache_path, self._ignore_queries)
            symlink_path = get_symlink_path(filepath, target, self._cache_path)
            filepath.symlink_to(symlink_path)
            logger.debug(f"{self._indent}  Symlinked redirection to target.")
        else:
            if self._save(response.content, filepath):
                logger.debug(f"{self._indent}  Saved response in cache.")

    def _save(self, content: bytes, path: Path) -> bool:
        try:
            with open(path, 'wb') as fp:
                fp.write(content)
            return True
        except Exception as e:
            logger.error(f"{self._indent}  Failed to save content to file: {e}")
            return False

    def delete(self, url: Union[str, os.PathLike]):
        """
        Delete a cached response from the cache.

        :param url: The url from which the response was received
        :type url: Union[str, PathLike]
        """
        filepath = to_filepath(url, self._cache_path, self._ignore_queries)
        if filepath.exists():
            filepath.unlink()
            logger.debug("Deleted response.")
        else:
            logger.debug("No response to delete.")

    def backup(self) -> 'Backup':
        self._backup = Backup(self)
        return self._backup

    def stop_backup(self):
        del self._backup
        self._backup = None


class Backup:
    _cache: FileCache
    _requests: list[tuple[PreparedRequest, Optional[bytes]]]

    def __init__(self, cache: FileCache):
        self._cache = cache
        self._requests = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._cache.stop_backup()

    def __del__(self):
        del self._requests

    def stop_backup(self):
        self._cache.stop_backup()

    @property
    def requests(self):
        return self._requests

    def backup_request(self, request: PreparedRequest, filepath: Path = None):
        if filepath is None:
            filepath = to_filepath(request.url, self._cache.cache_path, self._cache.ignore_queries)
        logger.debug(f"{' ' * len(request.method)}  Backup up cached request")
        if not filepath.exists():
            self._requests.append((request, None))
        else:
            with open(filepath, 'rb') as fp:
                self._requests.append((request, fp.read()))

    def restore(self, request: PreparedRequest, data: Optional[bytes]):
        logger.debug("Restoring backup")
        filepath = to_filepath(request.url, self._cache.cache_path, self._cache.ignore_queries)
        assert filepath.exists()
        if data is None:
            filepath.unlink()
        else:
            with open(filepath, 'wb') as fp:
                fp.write(data)

    def restore_all(self):
        for req, data in reversed(self._requests):  # Reverse to rollback early backups at the end
            self.restore(req, data)
