"""Provides functionality to inject HAR files as basis for a session to run on"""

import base64
import json
import logging
from io import BytesIO
from typing import List, Tuple

from requests import PreparedRequest
from requests.structures import CaseInsensitiveDict
from urllib3.response import HTTPResponse
from urllib3.util.url import parse_url

from spoofbot.adapter.common import MockHTTPResponse, ReportingAdapter


class HarAdapter(ReportingAdapter):
    """An adapter to be registered in a Session.."""
    _data: dict = None
    _log: logging.Logger
    _strict_matching: bool = True
    _delete_after_match: bool = True

    def __init__(self, har_data: dict):
        super(HarAdapter, self).__init__()
        self._log = logging.getLogger(self.__class__.__name__)
        self._data = har_data

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

    def send(self, request: PreparedRequest, stream=False, timeout=None, verify=True, cert=None, proxies=None):
        self._report_request(request)
        entries: list = self._data['log']['entries']
        for i, entry in enumerate(entries):
            req = entry['request']
            if req['method'] == request.method and req['url'] == request.url:
                if self._strict_matching:
                    other_headers = CaseInsensitiveDict(self._to_dict(req['headers']))
                    if not self._match_dict(request.headers, other_headers):
                        self._log.warning(f"Headers mismatch:\n{request.headers}\n!=\n{other_headers}")
                        continue
                if 'postData' in req:
                    if not req['postData']['text'] == request.body:
                        self._log.error(f"Post data mismatch:\n{request.body}\n!=\n{req['postData']['text']}")
                        continue
                self._log.debug("Request matched")
                json_response = entry['response']
                if json_response['redirectURL'] != '':
                    url = parse_url(json_response['redirectURL'])
                    if url.hostname is not None:
                        request.headers['Host'] = url.hostname
                    if 'Origin' in request.headers:
                        del request.headers['Origin']  # no Origin header for fetch requests, since redirect
                    if url.scheme == 'https':
                        request.headers['accept-encoding'] = ', '.join(['gzip', 'deflate', 'br'])
                        if 'TE' not in request.headers:
                            request.headers['TE'] = 'Trailers'
                if self._delete_after_match:
                    del entries[i]  # Delete entry as we already matched it once.
                    self._log.debug("Deleted matched entry from list")
                response = self.build_response(request, self._create_response(json_response))
                self._report_response(response)
                return response
        raise Exception("No matching entry in HAR found")

    def _to_dict(self, other: List[dict]) -> List[Tuple[str, str]]:
        d = []
        for kv in other:
            if not kv['name'] == 'content-encoding':
                d.append((kv['name'], kv['value']))
        return d

    def _match_dict(self, own: CaseInsensitiveDict, other: CaseInsensitiveDict) -> bool:
        if own is None:
            self._log.error("Own headers are None")
            return False
        if len(own) != len(other):
            self._log.warning(f"Own header length: {len(own)} != {len(other)}")
            return False
        for key, value in other.items():
            if own.setdefault(key, None) != value:
                if key == 'Cookie' and own[key] is not None:
                    own_cookies = own[key].split('; ')
                    other_cookies = value.split('; ')
                    if len(own_cookies) != len(other_cookies):
                        self._log.warning(f"Number of own cookies {len(own_cookies)} != {len(other_cookies)}")
                        return False
                    for other_cookie in other_cookies:
                        if other_cookie not in own_cookies:
                            self._log.warning(f"Own cookies missing: {other_cookie}")
                            return False
                else:
                    self._log.warning(f"{key}: {own[key]}")
                    self._log.warning(f"{' ' * len(key)}!={value}")
                    return False
        return True

    def _create_response(self, json_response: dict) -> HTTPResponse:
        headers = self._to_dict(json_response['headers'])
        content = json_response['content']
        if 'text' in content:
            text = content['text']
            if 'encoding' in content:
                encoding = content['encoding']
                if encoding == 'base64':
                    body = base64.b64decode(text)
                else:
                    body = text.decode(encoding)
            else:
                body = text.encode('utf-8')
        else:
            body = b""
        return HTTPResponse(
            body=BytesIO(body),
            headers=headers,
            status=json_response['status'],
            preload_content=False,
            original_response=MockHTTPResponse(headers)
        )


def load_har(file: str) -> dict:
    with open(file, 'r') as fp:
        return json.load(fp)
