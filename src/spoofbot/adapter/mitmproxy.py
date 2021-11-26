"""Provides functionality to inject HAR files as basis for a session to run on"""
import os
from typing import Union

from loguru import logger
from requests import PreparedRequest, Session, Response
from requests.cookies import extract_cookies_to_jar
from requests.structures import CaseInsensitiveDict
from requests.utils import get_encoding_from_headers
from urllib3.util import Url, parse_url

from spoofbot.adapter.cache import CacheAdapter
from spoofbot.util import cookie_header_to_dict, TimelessRequestsCookieJar
from spoofbot.util.archive import do_keys_match, are_dicts_same, print_diff


class MitmProxyCache(CacheAdapter):
    """
    MITMProxy flows cache adapter.

    This HTTPAdapter provides an interface to a flows (MITMProxy flows) file. It can
    read flows files and can be used to find stored responses to corresponding requests.
    """
    _entries: dict[Url, list[tuple[PreparedRequest, Response]]]
    _match_header_order: bool
    _match_headers: bool
    _match_data: bool
    _delete_after_matching: bool
    _session: Session

    def __init__(
            self,
            cache_path: Union[str, os.PathLike],
            is_active: bool = True,
            is_offline: bool = False,
            is_passive: bool = True,
            delete_after_hit: bool = False,
            mode: str = 'r',
            match_headers: bool = True,
            match_header_order: bool = False,
            match_data: bool = True
    ):
        """
        Creates a cache HTTP adapter that is based on an flows file.

        :param cache_path: The path to the flows file
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
        :param mode: In what mode the HAR file should be opened. Default: r
        :type mode: str
        :param match_headers: Whether to check for headers to match. Default: True
        :type match_headers: bool
        :param match_header_order: Whether to check for the header order to match:
        Default: False
        :type match_header_order: bool
        :param match_data: Whether to check for the request body to match. Default: True
        """
        super(MitmProxyCache, self).__init__(
            cache_path=cache_path,
            is_active=is_active,
            is_offline=is_offline,
            is_passive=is_passive,
            delete_after_hit=delete_after_hit,
        )
        self._mode = mode
        self._match_header_order = match_header_order
        self._match_headers = match_headers
        self._match_data = match_data

    @property
    def entries(self) -> dict[Url, list[tuple[PreparedRequest, Response]]]:
        return self._entries

    @property
    def match_header_order(self) -> bool:
        return self._match_header_order

    @match_header_order.setter
    def match_header_order(self, value: bool):
        self._match_header_order = value

    @property
    def match_headers(self) -> bool:
        return self._match_headers

    @match_headers.setter
    def match_headers(self, value: bool):
        self._match_headers = value

    @property
    def match_data(self) -> bool:
        return self._match_data

    @match_data.setter
    def match_data(self, value: bool):
        self._match_data = value

    def send(self, request: PreparedRequest, stream=False, timeout=None, verify=True,
             cert=None, proxies=None):
        indent = ' ' * len(request.method)
        possible_requests = self._entries.get(parse_url(request.url), [])
        for i, (cached_request, cached_response) in enumerate(possible_requests):
            if self._match_requests(request, cached_request):
                logger.debug(f"{indent}Request matched")
                if self._delete_after_matching:
                    # Delete entry as we already matched it once.
                    del possible_requests[i]
                    logger.debug(f"{indent}Deleted matched request and response")
                return self.build_response(request, cached_response)
        raise Exception(f"No matching entry found for {request.url}")

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
            if self._match_data and cached_request.body:
                if cached_request.body != request.body:
                    success = False
                    print_diff('data', cached_request.body, request.body, indent_level)
            if not success:
                logger.debug(
                    indent + '=' * 16)  # To easily distinguish multiple tested requests
            return success
        return False

    def build_response(self, req, resp):
        """Builds a :class:`Response <requests.Response>` object from a urllib3
        response. This should not be called from user code, and is only exposed
        for use when subclassing the
        :class:`HTTPAdapter <requests.adapters.HTTPAdapter>`

        :param req: The :class:`PreparedRequest <PreparedRequest>` used to generate the
        response.
        :param resp: The urllib3 response object.
        :rtype: requests.Response
        """
        response = Response()

        cookie_jar = self.session.cookies
        if isinstance(cookie_jar, TimelessRequestsCookieJar) \
                and isinstance(self.session.cookies, TimelessRequestsCookieJar):
            cookie_jar.mock_date = self.session.cookies.mock_date

        response.cookies = cookie_jar

        # Fallback to None if there's no status_code, for whatever reason.
        response.status_code = getattr(resp, 'status', None)

        # Make headers case-insensitive.
        response.headers = CaseInsensitiveDict(getattr(resp, 'headers', {}))

        # Set encoding.
        response.encoding = get_encoding_from_headers(response.headers)
        response.raw = resp
        response.reason = response.raw.reason

        if isinstance(req.url, bytes):
            response.url = req.url.decode('utf-8')
        else:
            response.url = req.url

        # Add new cookies from the server.
        extract_cookies_to_jar(response.cookies, req, resp)

        # Give the Response some context.
        response.request = req
        response.connection = self

        return response
