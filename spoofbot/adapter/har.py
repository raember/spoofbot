"""Provides functionality to inject HAR files as basis for a session to run on"""

import json
import logging
import os
from typing import List, MutableMapping

from requests import PreparedRequest, Session, Response
from requests.adapters import HTTPAdapter
from requests.cookies import extract_cookies_to_jar
from requests.structures import CaseInsensitiveDict
from requests.utils import get_encoding_from_headers
from urllib3.util.url import parse_url

from spoofbot.util import request_from_entry, response_from_entry, cookie_header_to_dict, TimelessRequestsCookieJar


class HarAdapter(HTTPAdapter):
    """An adapter to be registered in a Session.."""
    _data: dict = None
    _log: logging.Logger
    _strict_matching: bool = True
    _delete_after_match: bool = True
    _session: Session

    def __init__(self, har_data: dict, session: Session = None):
        super(HarAdapter, self).__init__()
        self._log = logging.getLogger(self.__class__.__name__)
        self._data = har_data
        self._log.info(f"Using HAR file from {str(self)}")
        if session is None:
            session = Session()
            session.headers = {}
        self._session = session

    @property
    def creator(self) -> str:
        return self._data['log'].get('creator', {}).get('name', '')

    @property
    def creator_version(self) -> str:
        return self._data['log'].get('creator', {}).get('version', '')

    @property
    def entries(self) -> List[dict]:
        return self._data['log']['entries']

    @property
    def strict_matching(self) -> bool:
        return self._strict_matching

    @strict_matching.setter
    def strict_matching(self, value: bool):
        self._strict_matching = value

    @property
    def delete_after_match(self) -> bool:
        return self._delete_after_match

    @delete_after_match.setter
    def delete_after_match(self, value: bool):
        self._delete_after_match = value

    @property
    def session(self) -> Session:
        return self._session

    @session.setter
    def session(self, value: Session):
        self._session = value

    def send(self, request: PreparedRequest, stream=False, timeout=None, verify=True, cert=None, proxies=None):
        indent = ' ' * len(request.method)
        for i, entry in enumerate(self.entries):
            cached_request = self._session.prepare_request(request_from_entry(entry))
            if self._match_requests(request, cached_request):
                self._log.debug(f"{indent}Request matched")
                for key, val in request.headers.items():
                    self._log.debug(f"{indent}  - {key}: {val}")
                if self._delete_after_match:
                    del self._data['log']['entries'][i]  # Delete entry as we already matched it once.
                    self._log.debug(f"{indent}Deleted matched entry from list")
                json_response = entry['response']
                if json_response['redirectURL'] != '':
                    if json_response['redirectURL'].startswith('/'):
                        url = parse_url(request.url)
                        url = parse_url(f"{url.scheme}://{url.hostname}{json_response['redirectURL']}")
                    else:
                        url = parse_url(json_response['redirectURL'])
                    self._log.debug(f"{indent}Handling redirection to {url}")
                    # if url.hostname is not None:
                    #     request.headers['Host'] = url.hostname
                    # if 'Origin' in request.headers:
                    #     del request.headers['Origin']  # no Origin header for fetch requests, since redirect
                    # if url.scheme == 'https':
                    #     request.headers['accept-encoding'] = ', '.join(['gzip', 'deflate', 'br'])
                    #     if 'TE' not in request.headers:
                    #         request.headers['TE'] = 'Trailers'
                response = self.build_response(request, response_from_entry(entry))
                return response
        raise Exception("No matching entry in HAR found")

    def _match_requests(self, request: PreparedRequest, cached_request: PreparedRequest) -> bool:
        indent = ' ' * len(request.method)
        if cached_request.method == request.method and cached_request.url == request.url:
            if self._strict_matching:
                self._log.debug(f"{indent}Testing possible match strictly")
                if not self._do_headers_match(request.headers, cached_request.headers, len(request.method)):
                    self._log.debug(f"{indent}Headers mismatch")
                    return False
                if cached_request.body:
                    if cached_request.body != request.body:
                        self._log.debug(
                            f"{indent}Post data mismatch:\n{request.body}\n!=\n{cached_request.body}")
                        return False
            return True
        return False

    def _do_headers_match(self, request_headers: CaseInsensitiveDict, cached_headers: CaseInsensitiveDict,
                          indent_level: int) -> bool:
        self._log.debug(' ' * indent_level + '=' * 16)
        success = True
        success &= self._do_keys_match(request_headers, cached_headers, indent_level)
        success &= self._are_dicts_same(request_headers, cached_headers, indent_level, 'headers')
        if 'Cookie' in cached_headers or 'Cookie' in request_headers:
            self._log.debug(f"{' ' * indent_level}Cookies mismatch:")
            request_cookies = cookie_header_to_dict(request_headers.get('Cookie', ''))
            cached_cookies = cookie_header_to_dict(cached_headers.get('Cookie', ''))
            success &= self._are_dicts_same(request_cookies, cached_cookies, indent_level + 2, 'cookies')
        return success

    def _do_keys_match(self, request_headers: CaseInsensitiveDict, cached_headers: CaseInsensitiveDict,
                       indent_level: int) -> bool:
        indent = ' ' * indent_level
        if list(map(str.lower, dict(request_headers).keys())) != list(map(str.lower, dict(cached_headers).keys())):
            self._log.debug(f"{indent}Request header order does not match:")
            self._log.debug(f"{indent}  ({len(request_headers)}) {list(dict(request_headers).keys())}")
            self._log.debug(f"{indent}  does not equal cached:")
            self._log.debug(f"{indent}  ({len(cached_headers)}) {list(dict(cached_headers).keys())}")
            return False
        return True

    def _are_dicts_same(self, request_dict: MutableMapping, cached_dict: MutableMapping, indent_level: int,
                        name: str) -> bool:
        indent = ' ' * indent_level
        missing_keys = []
        mismatching_keys = []
        redundant_keys = []
        verdict = True
        for key in cached_dict.keys():
            if key not in request_dict:
                missing_keys.append(key)
            else:
                if request_dict[key] != cached_dict[key] and key not in ['Cookie',
                                                                         'expires']:  # For cookies with altered expiration date
                    mismatching_keys.append(key)
        for key in request_dict.keys():
            if key not in cached_dict:
                redundant_keys.append(key)
        if len(missing_keys) > 0:
            self._log.debug(f"{indent}Request {name} are missing the following entries:")
            for key in missing_keys:
                self._log.debug(f"{indent}  '{key}': '{cached_dict[key]}'")
            verdict = False
        if len(redundant_keys) > 0:
            self._log.debug(f"{indent}Request {name} have the following redundant entries:")
            for key in redundant_keys:
                self._log.debug(f"{indent}  '{key}': '{request_dict[key]}'")
            verdict = False
        if len(mismatching_keys) > 0:
            self._log.debug(f"{indent}Request {name} have the following mismatching entries:")
            for key in mismatching_keys:
                self._log.debug(f"{indent}  '{key}': '{request_dict[key]}'")
                self._log.debug(f"{indent}  {' ' * (len(key) + 2)}  does not equal cached {name[:-1]}:")
                self._log.debug(f"{indent}  {' ' * (len(key) + 2)}  '{cached_dict[key]}'")
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

        cookie_jar = self.session.cookies.__new__(self.session.cookies.__class__)
        cookie_jar.__init__()
        if isinstance(cookie_jar, TimelessRequestsCookieJar):
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

    def __str__(self):
        version = self.creator_version
        if version != '':
            return f"HAR file, {self.creator} {version}, {len(self.entries)} Requests"
        return f"HAR file, {self.creator}, {len(self.entries)} Requests"


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


def load_har(file: str) -> dict:
    with open(file, 'r') as fp:
        return json.load(fp)
