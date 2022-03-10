"""Provides functionality to inject HAR files as basis for a session to run on"""
import os
from io import BytesIO
from typing import Union, Optional

from loguru import logger
from mitmproxy.http import HTTPFlow
from mitmproxy.io import read_flows_from_paths
from requests import PreparedRequest, Response, Session, Request
from requests.cookies import extract_cookies_to_jar
from requests.structures import CaseInsensitiveDict
from requests.utils import get_encoding_from_headers
from urllib3 import HTTPResponse
from urllib3.util import parse_url, Url

from spoofbot.adapter.cache import MemoryCacheAdapter
from spoofbot.util import TimelessRequestsCookieJar
from spoofbot.util.file import MockHTTPResponse


class MitmProxyCache(MemoryCacheAdapter):
    """
    MITMProxy flows cache adapter.

    This HTTPAdapter provides an interface to a flows (MITMProxy flows) file. It can
    read flows files and can be used to find stored responses to corresponding requests.
    """

    def __init__(
            self,
            cache_path: Union[str, os.PathLike],
            mode: str = 'r',
            is_active: bool = True,
            is_offline: bool = False,
            is_passive: bool = True,
            delete_after_hit: bool = False,
            match_headers: bool = True,
            match_header_order: bool = False,
            match_data: bool = True
    ):
        """
        Creates a cache HTTP adapter that is based on an flows file.

        :param cache_path: The path to the flows file
        :type cache_path: Union[str, os.PathLike]
        :param mode: In what mode the HAR file should be opened. Default: r
        :type mode: str
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
        """
        super(MitmProxyCache, self).__init__(
            cache_path=cache_path,
            is_active=is_active,
            is_offline=is_offline,
            is_passive=is_passive,
            delete_after_hit=delete_after_hit,
            match_headers=match_headers,
            match_header_order=match_header_order,
            match_data=match_data
        )
        self._mode = mode

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

        cookie_jar = self._session.cookies
        if isinstance(cookie_jar, TimelessRequestsCookieJar) \
                and isinstance(self._session.cookies, TimelessRequestsCookieJar):
            cookie_jar.mock_date = self._session.cookies.mock_date

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


def load_flows(path: Union[str, os.PathLike], session: Session = None) \
        -> dict[Url, list[tuple[PreparedRequest, Response]]]:
    if session is None:
        session = Session()
        session.headers.clear()
    data = {}
    for flow in read_flows_from_paths([path]):
        request: PreparedRequest = session.prepare_request(request_from_flow(flow))
        response: HTTPResponse = response_from_flow(flow)
        url = parse_url(request.url)
        requests = data.get(url, [])
        requests.append((request, response))
        data[url] = requests
    return data


def request_from_flow(flow: HTTPFlow) -> Request:
    req = flow.request
    headers = CaseInsensitiveDict()
    for header, value in req.headers.items():
        headers[header] = value
    cookies = {}
    for cookie, value in req.cookies.items():
        cookies[cookie] = value
    return Request(
        method=req.method.upper(),
        url=req.url,
        headers=headers,
        data=req.content,
        cookies=cookies,
    )


def response_from_flow(flow: HTTPFlow) -> Optional[HTTPResponse]:
    resp = flow.response
    if resp is None:
        return None
    headers = CaseInsensitiveDict()
    for header, value in resp.headers.items():
        headers[header] = value

    resp = HTTPResponse(
        body=BytesIO(resp.content),
        headers=headers,
        status=resp.status_code,
        preload_content=False,
        original_response=MockHTTPResponse(headers.items())
    )
    # Hack to prevent already decoded contents to be decoded again
    resp.CONTENT_DECODERS = []
    return resp
