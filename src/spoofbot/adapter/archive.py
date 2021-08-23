"""Provides functionality to inject HAR files as basis for a session to run on"""

from typing import MutableMapping

from loguru import logger
from requests import PreparedRequest, Session, Response
from requests.adapters import HTTPAdapter
from requests.cookies import extract_cookies_to_jar
from requests.structures import CaseInsensitiveDict
from requests.utils import get_encoding_from_headers
from urllib3.util import Url, parse_url

from spoofbot.util import cookie_header_to_dict, TimelessRequestsCookieJar


class ArchiveCache(HTTPAdapter):
    """An adapter to be registered in a Session."""
    _entries: dict[Url, list[tuple[PreparedRequest, Response]]]
    _match_header_order: bool
    _match_headers: bool
    _match_data: bool
    _delete_after_matching: bool
    _session: Session

    def __init__(
            self,
            entries: dict[Url, list[tuple[PreparedRequest, Response]]],
            match_header_order: bool = True,
            match_headers: bool = True,
            match_data: bool = True,
            delete_after_matching: bool = True,
            session: Session = None,
            **kwargs
    ):
        """Creates a new recording-file-based cache

        :param entries: The prepared recordings
        :type entries: dict[Url, list[tuple[PreparedRequest, Response]]]
        :param match_header_order: Whether to require the order of the headers to match when looking for hits
        :type match_header_order: bool
        :param match_headers: Whether to require the headers to match when looking for hits
        :type match_headers: bool
        :param match_data: Whether to require the request data to match when looking for hits
        :type match_data: bool
        :param delete_after_matching: Whether to delete hits from the cache once hit
        :type delete_after_matching: bool
        :param session: The session to use when building responses
        :type session: Session
        :param kwargs:
        :type kwargs:
        """
        super(ArchiveCache, self).__init__(**kwargs)
        self._entries = entries
        self._match_header_order = match_header_order
        self._match_headers = match_headers
        self._match_data = match_data
        self._delete_after_matching = delete_after_matching
        if session is None:
            session = Session()
            session.headers.clear()
        self._session = session

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

    @property
    def delete_after_matching(self) -> bool:
        return self._delete_after_matching

    @delete_after_matching.setter
    def delete_after_matching(self, value: bool):
        self._delete_after_matching = value

    @property
    def session(self) -> Session:
        return self._session

    @session.setter
    def session(self, value: Session):
        self._session = value

    def send(self, request: PreparedRequest, stream=False, timeout=None, verify=True, cert=None, proxies=None):
        indent = ' ' * len(request.method)
        possible_requests = self._entries.get(parse_url(request.url), [])
        for i, (cached_request, cached_response) in enumerate(possible_requests):
            if self._match_requests(request, cached_request):
                logger.debug(f"{indent}Request matched")
                if self._delete_after_matching:
                    del possible_requests[i]  # Delete entry as we already matched it once.
                    logger.debug(f"{indent}Deleted matched request and response")
                return self.build_response(request, cached_response)
        raise Exception(f"No matching entry found for {request.url}")

    def _print_diff(self, name: str, expected: str, actual: str, indent_level: int):
        indent = ' ' * indent_level
        logger.debug(f"{indent}Request {name} does not match:")
        logger.debug(f"{indent}  {actual}")
        logger.debug(f"{indent}  does not equal expected:")
        logger.debug(f"{indent}  {expected}")

    def _match_requests(self, request: PreparedRequest, cached_request: PreparedRequest) -> bool:
        indent_level = len(request.method)
        indent = ' ' * indent_level
        if cached_request.method == request.method and cached_request.url == request.url:
            success = True
            if self._match_header_order:
                success &= self._do_keys_match(request.headers, cached_request.headers, indent_level)
            if self._match_headers:
                success &= self._are_dicts_same(request.headers, cached_request.headers, indent_level, 'headers')
                if 'Cookie' in cached_request.headers or 'Cookie' in request.headers:
                    request_cookies = cookie_header_to_dict(request.headers.get('Cookie', ''))
                    cached_cookies = cookie_header_to_dict(cached_request.headers.get('Cookie', ''))
                    success &= self._are_dicts_same(request_cookies, cached_cookies, indent_level + 2, 'cookies')
            if self._match_data and cached_request.body:
                if cached_request.body != request.body:
                    success = False
                    self._print_diff('data', cached_request.body, request.body, indent_level)
            if not success:
                logger.debug(indent + '=' * 16)  # To easily distinguish multiple tested requests
            return success
        return False

    def _do_keys_match(
            self,
            request_headers: CaseInsensitiveDict,
            cached_headers: CaseInsensitiveDict,
            indent_level: int
    ) -> bool:
        if list(map(str.lower, dict(request_headers).keys())) != list(map(str.lower, dict(cached_headers).keys())):
            self._print_diff(
                'data',
                f"({len(cached_headers)}) {', '.join(list(dict(cached_headers).keys()))}",
                f"({len(request_headers)}) {', '.join(list(dict(request_headers).keys()))}",
                indent_level
            )
            return False
        return True

    def _are_dicts_same(
            self,
            request_dict: MutableMapping,
            cached_dict: MutableMapping,
            indent_level: int,
            name: str
    ) -> bool:
        indent = ' ' * indent_level
        missing_keys = []
        mismatching_keys = []
        redundant_keys = []
        verdict = True
        for key in cached_dict.keys():
            if key not in request_dict:
                missing_keys.append(key)
            else:
                if request_dict[key] != cached_dict[key] and key.lower() != 'cookie':
                    mismatching_keys.append(key)
        for key in request_dict.keys():
            if key not in cached_dict:
                redundant_keys.append(key)
        if len(missing_keys) > 0:
            logger.debug(f"{indent}Request {name} are missing the following entries:")
            for key in missing_keys:
                logger.debug(f"{indent}  - '{key}': '{cached_dict[key]}'")
            verdict = False
        if len(redundant_keys) > 0:
            logger.debug(f"{indent}Request {name} have the following redundant entries:")
            for key in redundant_keys:
                logger.debug(f"{indent}  + '{key}': '{request_dict[key]}'")
            verdict = False
        if len(mismatching_keys) > 0:
            logger.debug(f"{indent}Request {name} have the following mismatching entries:")
            for key in mismatching_keys:
                logger.debug(f"{indent}  · '{key}': '{request_dict[key]}'")
                logger.debug(f"{indent}    {' ' * (len(key) + 2)}  does not equal expected {name[:-1]}:")
                logger.debug(f"{indent}    {' ' * (len(key) + 2)}  '{cached_dict[key]}'")
            verdict = False
        return verdict

    def build_response(self, req, resp):
        """Builds a :class:`Response <requests.Response>` object from a urllib3
        response. This should not be called from user code, and is only exposed
        for use when subclassing the
        :class:`HTTPAdapter <requests.adapters.HTTPAdapter>`

        :param req: The :class:`PreparedRequest <PreparedRequest>` used to generate the response.
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
