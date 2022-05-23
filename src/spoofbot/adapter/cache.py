import os
import socket
from abc import ABC
from datetime import datetime
from pathlib import Path
from ssl import SSLSocket
from typing import Union, Optional, Dict, List, Generator, Tuple

from cryptography import x509
from loguru import logger
from requests import PreparedRequest, Response, Session, RequestException
from requests.adapters import HTTPAdapter
from urllib3 import HTTPResponse
from urllib3.util import Url, parse_url

from spoofbot.util import cookie_header_to_dict
from spoofbot.util.archive import do_keys_match, are_dicts_same, print_diff


class CacheAdapter(HTTPAdapter, ABC):
    _session: Session
    _cache_path: Path
    _is_active: bool
    _is_passive: bool
    _is_offline: bool
    _delete_after_hit: bool
    _hit: bool
    _indent: str
    _timestamp: datetime
    _del_idx: int

    def __init__(
            self,
            cache_path: Union[str, os.PathLike],
            is_active: bool = True,
            is_offline: bool = False,
            is_passive: bool = True,
            delete_after_hit: bool = False
    ):
        """
        Creates an HTTPAdapter that supports cache-functionality.

        :param cache_path: The path to the cache
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
        """
        super(CacheAdapter, self).__init__()
        if not isinstance(cache_path, Path):
            cache_path = Path(cache_path)
        self._session = Session()
        self._cache_path = cache_path
        self._is_active = is_active
        self._is_offline = is_offline
        self._is_passive = is_passive
        self._delete_after_hit = delete_after_hit
        self._hit = False
        self._indent = ''
        self._timestamp = datetime.now().astimezone()
        self._del_idx = -1

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

        If true, the CacheAdapter will check new requests against the local cache for
        hits.
        Otherwise the CacheAdapter will not check for hits.
        """
        return self._is_active

    @is_active.setter
    def is_active(self, value: bool):
        """
        Set whether the cache is in active mode.

        If set to True, the CacheAdapter will check new requests against the local cache
        for hits.
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

        If true, the CacheAdapter will cache the answer of a successful request in the
        cache.
        Otherwise the CacheAdapter will not cache the answer.
        """
        return self._is_passive

    @is_passive.setter
    def is_passive(self, value: bool):
        """
        Set whether the cache is in passive mode.

        If true, the CacheAdapter will cache the answer of a successful request in the
        cache.
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
        self._session = session

    def send(self, request: PreparedRequest, stream=False, timeout=None, verify=True,
             cert=None, proxies=None
             ) -> Response:
        # Set indentation for aligned log messages
        self._indent = ' ' * len(request.method)
        self._pre_send(request)

        # In active mode, check cache for a cached response
        if self._is_active:
            if (response := self._get_cached_response(request)) is not None:
                return response
        self._hit = False

        # In offline mode, we cannot make new HTTP requests for cache misses
        if self._is_offline:
            self._raise_for_offline(request)

        # Send HTTP request to remote
        # noinspection PyTypeChecker
        response: Response = None
        try:
            stream = True  # to keep the socket as to be able to get peer ip and port
            response = self._send(request, stream, timeout, verify, cert, proxies)
        except RequestException as ex:
            # In case the request fails, we still might want to save it
            logger.error(ex)
            response = self.build_response(request, HTTPResponse(body=''))
            self._handle_response(response)
            raise
        else:
            self._handle_response(response)
        return response

    def _get_cached_response(self, request: PreparedRequest) -> Optional[Response]:
        if (response := self.find_response(request)) is not None:
            logger.debug(f"{self._indent}  Cache hit")
            self._hit = True
            if self._delete_after_hit:
                self._delete(response)
            return response
        logger.debug(f"{self._indent}  Cache miss")
        return None

    def _handle_response(self, response: Response):
        if self._is_passive:  # Store received response in cache
            self._prepare_response(response)
            self._store_response(response)
            logger.debug(f"{self._indent}  Saved response in cache")
        self._post_send(response)

    def _pre_send(self, request: PreparedRequest):
        self._timestamp = datetime.now().astimezone()

    def _post_send(self, response: Response):
        pass

    def _send(self, request: PreparedRequest, stream=False, timeout=None, verify=True,
              cert=None, proxies=None) -> Response:
        return super(CacheAdapter, self).send(request, stream, timeout, verify, cert,
                                              proxies)

    def find_response(self, request: PreparedRequest) -> Optional[Response]:
        """
        Find a response that matches the request in the cache and return it if found.

        :param request: The request to search by
        :type request: PreparedRequest
        :return: The cached response if hit. Otherwise None.
        :rtype: Optional[Response]
        """
        raise NotImplementedError()

    def use_mode(self, active: bool = None, passive: bool = None,
                 offline: bool = None) -> 'Mode':
        return Mode(self, active=active, passive=passive, offline=offline)

    def _raise_for_offline(self, request: PreparedRequest):
        logger.error(
            f"{self._indent}Failed to find request in cache while in offline mode")
        raise ValueError(
            f"Could not find cached request for [{request.method}] {request.url}")

    def _store_response(self, response: Response):
        raise NotImplementedError()

    def _prepare_response(self, response: Response):
        setattr(response, 'timestamp', self._timestamp)
        sock: socket
        try:
            sock = socket.fromfd(response.raw.fileno(), socket.AF_INET, socket.SOCK_STREAM)
        except IOError as e:
            logger.debug(f"No response socket: {e}")
            return
        setattr(response.raw, 'sock', sock)
        if sock is not None and not getattr(sock, '_closed'):
            if isinstance(sock, SSLSocket):
                # Save ssl certificate info
                cert: dict = sock.getpeercert()
                setattr(response, 'cert', cert)
                cert_bin: bytes = sock.getpeercert(binary_form=True)
                setattr(response, 'cert_bin', cert_bin)
                x509cert = x509.load_der_x509_certificate(cert_bin)
                setattr(response, 'cert_x509', x509cert)
            ip, port = sock.getpeername()
            # Save connection info
            setattr(response, 'ip', ip)
            setattr(response, 'port', port)
            sock.close()

    def _delete(self, response: Response, **kwargs):
        raise NotImplementedError()


class Mode:
    """Sets a mode context for a given cache adapter"""
    _cache: CacheAdapter
    _old_active: bool
    _old_passive: bool
    _old_offline: bool

    def __init__(self, cache: CacheAdapter, active: bool = None, passive: bool = None,
                 offline: bool = None):
        self._cache = cache
        self._old_active = self._cache.is_active
        if active is not None:
            self._cache.is_active = active
        self._old_passive = self._cache.is_passive
        if passive is not None:
            self._cache.is_passive = passive
        self._old_offline = self._cache.is_offline
        if offline is not None:
            self._cache.is_offline = offline

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._cache.is_active = self._old_active
        self._cache.is_passive = self._old_passive
        self._cache.is_offline = self._old_offline


class MemoryCacheAdapter(CacheAdapter, ABC):
    """
    Memory based cache adapter.

    This HTTPAdapter provides any memory based cache adapter. It stores requests and
    responses in memory for easy and fast access.
    """
    _match_headers: bool
    _match_header_order: bool
    _match_data: bool
    _entries: Dict[str, Dict[str, List[Response]]]
    _expect_new_entry: bool
    _url: Url

    def __init__(
            self,
            cache_path: Union[str, os.PathLike],
            is_active: bool = True,
            is_offline: bool = False,
            is_passive: bool = True,
            delete_after_hit: bool = False,
            match_headers: bool = True,
            match_header_order: bool = False,
            match_data: bool = True
    ):
        """
        Creates a cache HTTP adapter that is storing the requests and responses in
        memory.

        :param is_active: Whether the cache should be checked for hits. Default: True
        :type is_active: bool
        :param is_offline: Whether to block outgoing HTTP requests. Default: False
        :type is_offline: bool
        :param is_passive: Whether to store responses in the cache. Default: True
        :type is_passive: bool
        :param delete_after_hit: Whether to delete responses from the cache. Default:
            False
        :type delete_after_hit: bool
        :param match_headers: Whether to check for headers to match. Default: True
        :type match_headers: bool
        :param match_header_order: Whether to check for the header order to match:
        Default: False
        :type match_header_order: bool
        :param match_data: Whether to check for the request body to match. Default: True
        :type match_data: bool
        """
        super(MemoryCacheAdapter, self).__init__(
            cache_path=cache_path,
            is_active=is_active,
            is_offline=is_offline,
            is_passive=is_passive,
            delete_after_hit=delete_after_hit,
        )
        self._match_headers = match_headers
        self._match_header_order = match_header_order
        self._match_data = match_data
        self._entries = {}
        self._expect_new_entry = False
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def match_headers(self) -> bool:
        return self._match_headers

    @match_headers.setter
    def match_headers(self, value: bool):
        self._match_headers = value

    @property
    def match_header_order(self) -> bool:
        return self._match_header_order

    @match_header_order.setter
    def match_header_order(self, value: bool):
        self._match_header_order = value

    @property
    def match_data(self) -> bool:
        return self._match_data

    @match_data.setter
    def match_data(self, value: bool):
        self._match_data = value

    def _iter_entries(self) -> Generator[Response, None, None]:
        for origin, d in self._entries.items():
            for path, reqs in d.items():
                for req in reqs:
                    yield req

    def _get_cached_response(self, request: PreparedRequest) -> Optional[Response]:
        idx, response = self.find_response(request)
        if response is not None:
            logger.debug(f"{self._indent}  Cache hit")
            self._hit = True
            if self._delete_after_hit:
                self._delete(response, idx=idx)
            return response
        logger.debug(f"{self._indent}  Cache miss")
        return None

    def find_response(self, request: PreparedRequest) -> Optional[Tuple[int, Response]]:
        # TODO: Find a consistent way to reintroduce the fast lookup-index
        url = parse_url(request.url)
        cached = self._entries.get(url.hostname, {}).get(url.path, [])
        for idx, response in enumerate(cached):
            if self._match_requests(request, response.request):
                self._del_idx = idx
                return idx, response
        return None, None

    def _match_requests(self, request: PreparedRequest,
                        cached_request: PreparedRequest) -> bool:
        indent_level = len(request.method)
        indent = ' ' * indent_level
        if cached_request.method == request.method and \
                cached_request.url == request.url:
            success = True
            if self._match_header_order:
                success &= do_keys_match(request.headers, cached_request.headers,
                                         indent_level)
            if self._match_headers:
                success &= are_dicts_same(request.headers, cached_request.headers,
                                          indent_level, 'headers')
                if 'Cookie' in cached_request.headers or 'Cookie' in request.headers:
                    request_cookies = cookie_header_to_dict(
                        request.headers.get('Cookie', ''))
                    cached_cookies = cookie_header_to_dict(
                        cached_request.headers.get('Cookie', ''))
                    success &= are_dicts_same(request_cookies, cached_cookies,
                                              indent_level + 2, 'cookies')
            if self._match_data and cached_request.body and \
                    cached_request.body != request.body:
                success = False
                print_diff('data', cached_request.body, request.body, indent_level)
            if not success:
                logger.debug(
                    indent + '=' * 16)  # To easily distinguish multiple tested requests
            return success
        return False

    def _store_response(self, response: Response):
        url = parse_url(response.request.url)
        origin = self._entries.get(url.hostname, {})
        responses = origin.get(url.path, [])
        responses.append(response)
        origin[url.path] = responses
        self._entries[url.hostname] = origin

    def _delete(self, response: Response, **kwargs):
        url = parse_url(response.request.url)
        cached = self._entries.get(url.hostname, {}).get(url.path, [])
        idx = kwargs.get('idx', -1)
        if 0 <= idx < len(cached):
            del cached[idx]
            logger.debug("Removed response from cache")
        else:
            logger.warning(
                f"{self._indent}  Failed to delete response {response} from cache: "
                f"No valid index set.")
