import os
from abc import ABC
from pathlib import Path
from typing import Union, Optional

from loguru import logger
from requests import PreparedRequest, Response, Session, RequestException
from requests.adapters import HTTPAdapter
from urllib3 import HTTPResponse


class CacheAdapter(HTTPAdapter, ABC):
    _cache_path: Path
    _is_active: bool
    _is_passive: bool
    _is_offline: bool
    _delete_after_hit: bool
    _hit: bool
    _indent: str

    def __init__(
            self,
            cache_path: Union[str, os.PathLike],
            is_active: bool = True,
            is_offline: bool = False,
            is_passive: bool = True,
            delete_after_hit: bool = True
    ):
        super(CacheAdapter, self).__init__()
        if not isinstance(cache_path, Path):
            cache_path = Path(cache_path)
        self._cache_path = cache_path
        self._is_active = is_active
        self._is_offline = is_offline
        self._is_passive = is_passive
        self._delete_after_hit = delete_after_hit

    @property
    def cache_path(self) -> Path:
        """The root path of the cache"""
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

        If true, the CacheAdapter will check new requests against the local cache for hits.
        Otherwise the CacheAdapter will not check for hits.
        """
        return self._is_active

    @is_active.setter
    def is_active(self, value: bool):
        """
        Set whether the cache is in active mode.

        If set to True, the CacheAdapter will check new requests against the local cache for hits.
        Otherwise the CacheAdapter will not check for hits.
        :param value: The new state of the CacheAdapter
        :type value: bool
        """
        self._is_active = value
        if not self._is_active and self._is_offline:
            logger.warning("Active mode requires offline mode to be disabled.")

    @property
    def is_passive(self) -> bool:
        """
        Get whether the cache is in passive mode.

        If true, the CacheAdapter will cache the answer of a successful request in the cache.
        Otherwise the CacheAdapter will not cache the answer.
        """
        return self._is_passive

    @is_passive.setter
    def is_passive(self, value: bool):
        """
        Set whether the cache is in passive mode.

        If true, the CacheAdapter will cache the answer of a successful request in the cache.
        Otherwise the CacheAdapter will not cache the answer.
        :param value: The new state of the CacheAdapter
        :type value: bool
        """
        self._is_passive = value

    @property
    def is_offline(self) -> bool:
        """
        Get whether the cache is in offline mode.

        If true, the CacheAdapter will throw an exception if no cache hit occurs.
        Otherwise the CacheAdapter will allow HTTP requests to remotes.
        Offline mode does not work if active mode is disabled.
        """
        return self._is_offline

    @is_offline.setter
    def is_offline(self, value: bool):
        """
        Set whether the state is in offline mode.

        If set to True, the CacheAdapter will throw an exception if no cache hit occurs.
        Otherwise the CacheAdapter will allow HTTP requests to remotes.
        Offline mode does not work if active mode is disabled.
        :param value: The new state of the FileCache
        :type value: bool
        """
        self._is_offline = value
        if self._is_offline and not self._is_active:
            logger.warning("Offline mode requires active mode to be enabled.")

    @property
    def delete_after_hit(self) -> bool:
        """Whether to delete a cache entry after a hit"""
        return self._delete_after_hit

    @delete_after_hit.setter
    def delete_after_hit(self, value: bool):
        self._delete_after_hit = value

    @property
    def hit(self) -> bool:
        """True if the last processed request was a hit in the cache"""
        return self._hit

    def prepare_session(self, session: Session):
        session.adapters['https://'] = self
        session.adapters['http://'] = self

    def send(self, request: PreparedRequest, stream=False, timeout=None, verify=True, cert=None, proxies=None
             ) -> Response:
        # Set indentation for aligned log messages
        self._indent = ' ' * len(request.method)
        self._pre_send(request)

        # In active mode, check cache for a cached response
        if self._is_active:
            if (response := self.find_response(request)) is not None:
                logger.debug(f"{self._indent}  Cache hit")
                self._hit = True
                if self._delete_after_hit:
                    self._delete(response)
                return response
            logger.debug(f"{self._indent}  Cache miss")
        self._hit = False

        # In offline mode, we cannot make new HTTP requests for cache misses
        if self._is_offline:
            self._raise_for_offline(request)

        # Send HTTP request to remote
        try:
            response = self._send(request, stream, timeout, verify, cert, proxies)
        except RequestException as ex:
            # In case the request fails, we still might want to save it
            logger.error(ex)
            response = self.build_response(request, HTTPResponse(body=''))
            # self._handle_response(response)
            # raise
        self._handle_response(response)
        return response

    def _handle_response(self, response: Response):
        if self._is_passive:  # Store received response in cache
            self._store_response(response)
            logger.debug(f"{self._indent}  Saved response in cache")
        self._post_send(response)

    def _pre_send(self, request: PreparedRequest):
        pass

    def _post_send(self, response: Response):
        pass

    def _send(self, request: PreparedRequest, stream=False, timeout=None, verify=True, cert=None,
              proxies=None) -> Response:
        return super(CacheAdapter, self).send(request, stream, timeout, verify, cert, proxies)

    def find_response(self, request: PreparedRequest) -> Optional[Response]:
        """
        Find a response that matches the request in the cache and return it if found.

        :param request: The request to search by
        :type request: PreparedRequest
        :return: The cached response if hit. Otherwise None.
        :rtype: Optional[Response]
        """
        raise NotImplementedError()

    def _raise_for_offline(self, request: PreparedRequest):
        raise NotImplementedError()

    def _store_response(self, response: Response):
        raise NotImplementedError()

    def _delete(self, response: Response):
        raise NotImplementedError()
