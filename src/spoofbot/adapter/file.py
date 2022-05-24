import errno
import os
from pathlib import Path
from typing import Union, Optional

from loguru import logger
from requests import Response, PreparedRequest
from urllib3.util import parse_url, Url

from spoofbot.util import load_response
from spoofbot.util.file import to_filepath, get_symlink_path, CACHE_DEFAULT_PATH, \
    DEFAULT_CACHEABLE_STATUSES, IGNORE_QUERIES
from .cache import CacheAdapter


class FileCache(CacheAdapter):
    _filepath: Optional[Path]
    _cache_on_status: set[int]
    _ignore_queries: set[str]
    _backup: Optional['Backup']

    def __init__(
            self,
            cache_path: Union[str, os.PathLike] = CACHE_DEFAULT_PATH,
            is_active: bool = True,
            is_offline: bool = False,
            is_passive: bool = True,
            delete_after_hit: bool = False,
            cache_on_status: set[int] = DEFAULT_CACHEABLE_STATUSES,
            ignore_queries: set[str] = IGNORE_QUERIES,
    ):
        """
        Creates a cache HTTP adapter that uses the filesystem to cache responses.

        :param cache_path: The path to the HAR file
        :type cache_path: Union[str, os.PathLike]
        :param is_active: Whether the cache should be checked for hits. Default: True
        :type is_active: bool
        :param is_offline: Whether to block outgoing HTTP requests. Default: False
        :type is_offline: bool
        :param is_passive: Whether to store responses in the cache. Default: True
        :type is_passive: bool
        :param delete_after_hit: Whether to delete responses from the cache. Default:
            False
        :type delete_after_hit: bool
        :param cache_on_status: Only cache responses on these status codes.
        :type cache_on_status: set[int]
        :param ignore_queries: Ignore these queries when determining the file path.
        :type ignore_queries: set[str]
        """
        super(FileCache, self).__init__(
            cache_path=cache_path,
            is_active=is_active,
            is_offline=is_offline,
            is_passive=is_passive,
            delete_after_hit=delete_after_hit,
        )
        self._cache_path.mkdir(parents=True, exist_ok=True)
        self._filepath = None
        self._cache_on_status = cache_on_status
        self._ignore_queries = ignore_queries
        self._backup = None

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
    def backup_data(self) -> Optional['Backup']:
        return self._backup

    @property
    def is_backing_up(self) -> bool:
        return self._backup is not None

    def is_hit(self, url: Union[Url, str]) -> bool:
        """
        Check whether a request to a given URL would hit the cache.

        :param url: The URL
        :type url: Url
        :return: True if it would be a hit. False otherwise.
        :rtype: bool
        """
        return to_filepath(url, self._cache_path, self._ignore_queries).exists()

    def _raise_for_offline(self, request: PreparedRequest):
        raise FileNotFoundError(
            errno.ENOENT,
            os.strerror(errno.ENOENT),
            str(self._filepath)
        )

    def _pre_send(self, request: PreparedRequest):
        self._filepath = to_filepath(
            request.url,
            self._cache_path,
            self._ignore_queries
        )

    def _post_send(self, response: Response):
        self._filepath = None

    def find_response(self, request: PreparedRequest) -> Optional[Response]:
        if not self._filepath.exists():
            return
        if self._filepath.is_file():
            return self.build_response(request, load_response(self._filepath))
        if self._filepath.is_symlink():
            from urllib3 import HTTPResponse
            from io import BytesIO
            return self.build_response(request, HTTPResponse(
                body=BytesIO(b''),
                headers={
                    'Location': f"https://{os.readlink(str(self._filepath)).lstrip('./')}"},
                status=302,
                preload_content=False
            ))
        return

    def _handle_response(self, response: Response):
        if self._is_passive:  # Store received response in cache
            if response.status_code in self._cache_on_status:
                # Store received response in cache
                if self._backup is not None:
                    self._backup.backup_request(response.request, self._filepath)
            self._store_response(response)
            logger.debug(f"{self._indent}  Saved response in cache")
        self._post_send(response)

    def _store_response(self, response: Response):
        self._filepath.parent.mkdir(parents=True, exist_ok=True)
        if response.is_redirect:
            # If the response is a redirection, use a symlink to simulate that
            redirect = response.headers['Location']
            if redirect.startswith('/'):  # Host-less url
                redirect = parse_url(response.url).host + redirect
            redirect_url = parse_url(redirect)
            target = to_filepath(redirect_url, self._cache_path, self._ignore_queries)
            symlink_path = get_symlink_path(self._filepath, target, self._cache_path)
            self._filepath.unlink(missing_ok=True)
            self._filepath.symlink_to(symlink_path)
            logger.debug(f"{self._indent}  Symlinked redirection to target.")
        else:
            if self._save(response.content, self._filepath):
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
        self._filepath = to_filepath(url, self._cache_path, self._ignore_queries)
        # noinspection PyTypeChecker
        self._delete(None)
        self._filepath = None

    def _delete(self, response: Response):
        if self._filepath.exists():
            self._filepath.unlink()
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
            filepath = to_filepath(request.url, self._cache.cache_path,
                                   self._cache.ignore_queries)
        logger.debug(f"{' ' * len(request.method)}  Backup up cached request")
        if not filepath.exists():
            self._requests.append((request, None))
        else:
            with open(filepath, 'rb') as fp:
                self._requests.append((request, fp.read()))

    def restore(self, request: PreparedRequest, data: Optional[bytes]):
        logger.debug("Restoring backup")
        filepath = to_filepath(request.url, self._cache.cache_path,
                               self._cache.ignore_queries)
        assert filepath.exists()
        if data is None:
            filepath.unlink()
        else:
            with open(filepath, 'wb') as fp:
                fp.write(data)

    def restore_all(self):
        for req, data in reversed(
                self._requests):  # Reverse to rollback early backups at the end
            self.restore(req, data)
