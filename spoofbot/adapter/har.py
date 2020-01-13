"""Provides functionality to inject HAR files as basis for a session to run on"""

import base64
import json
import logging
from io import BytesIO
from typing import List, Tuple

from requests import PreparedRequest
from requests.adapters import HTTPAdapter
from requests.structures import CaseInsensitiveDict
from urllib3.response import HTTPResponse
from urllib3.util.url import parse_url

from spoofbot.adapter.common import MockHTTPResponse


class HarAdapter(HTTPAdapter):
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
        entries: list = self._data['log']['entries']
        for i, entry in enumerate(entries):
            cached_request = entry['request']
            if cached_request['method'] == request.method and cached_request['url'] == request.url:
                if self._strict_matching:
                    other_headers = CaseInsensitiveDict(self._to_dict(cached_request['headers']))
                    self._log.debug(f"{' ' * len(request.method)}Testing possible match strictly")
                    if not self._match_dict(request.headers, other_headers, len(request.method)):
                        self._log.debug(f"{' ' * len(request.method)}Headers mismatch")
                        continue
                    if 'postData' in cached_request:
                        if not cached_request['postData']['text'] == request.body:
                            self._log.debug(
                                f"{' ' * len(request.method)}Post data mismatch:\n{request.body}\n!=\n{cached_request['postData']['text']}")
                            continue
                self._log.debug(f"{' ' * len(request.method)}Request matched")
                json_response = entry['response'].copy()
                if self._delete_after_match:
                    del entries[i]  # Delete entry as we already matched it once.
                    self._log.debug(f"{' ' * len(request.method)}Deleted matched entry from list")
                if json_response['redirectURL'] != '':
                    if json_response['redirectURL'].startswith('/'):
                        url = parse_url(request.url)
                        url = parse_url(f"{url.scheme}://{url.hostname}{json_response['redirectURL']}")
                    else:
                        url = parse_url(json_response['redirectURL'])
                    self._log.debug(f"{' ' * len(request.method)}Handling redirection to {url}")
                    if url.hostname is not None:
                        request.headers['Host'] = url.hostname
                    if 'Origin' in request.headers:
                        del request.headers['Origin']  # no Origin header for fetch requests, since redirect
                    if url.scheme == 'https':
                        request.headers['accept-encoding'] = ', '.join(['gzip', 'deflate', 'br'])
                        if 'TE' not in request.headers:
                            request.headers['TE'] = 'Trailers'
                return self.build_response(request, self._create_response(json_response))
        raise Exception("No matching entry in HAR found")

    def _to_dict(self, other: List[dict]) -> List[Tuple[str, str]]:
        d = []
        for kv in other:
            if not kv['name'] == 'content-encoding':
                d.append((kv['name'], kv['value']))
        return d

    def _match_dict(self, request_headers: CaseInsensitiveDict, cached_headers: CaseInsensitiveDict,
                    ljustlen: int) -> bool:
        if request_headers is None:
            self._log.warning(f"{' ' * ljustlen}Request headers is None")
            return False
        verdict = True
        missing_keys = []
        mismatching_keys = []
        redundant_keys = []
        for key in cached_headers.keys():
            if key not in request_headers:
                missing_keys.append(key)
            else:
                if request_headers[key] != cached_headers[key]:
                    if key.lower() != 'cookie':
                        mismatching_keys.append(key)
                    else:
                        cached_cookies = dict(map(lambda c: tuple(c.split('=')), cached_headers[key].split('; ')))
                        request_cookies = dict(map(lambda c: tuple(c.split('=')), request_headers[key].split('; ')))
                        missing_cookies = []
                        mismatching_cookies = []
                        redundant_cookies = []
                        for cookey in cached_cookies.keys():
                            if cookey not in request_cookies:
                                missing_cookies.append(cookey)
                            else:
                                if request_cookies[cookey] != cached_cookies[cookey]:
                                    mismatching_cookies.append(cookey)
                        for cookey in request_cookies.keys():
                            if cookey not in cached_cookies:
                                redundant_cookies.append(cookey)
                        if len(missing_cookies) > 0:
                            self._log.debug(f"{' ' * ljustlen}Request cookies are missing the following entries:")
                            for cookey in missing_cookies:
                                self._log.debug(f"{' ' * ljustlen}'{cookey}': '{cached_headers[cookey]}'")
                            verdict = False
                        if len(redundant_cookies) > 0:
                            self._log.debug(f"{' ' * ljustlen}Request cookies have the following redundant entries:")
                            for cookey in redundant_cookies:
                                self._log.debug(f"{' ' * ljustlen}'{cookey}': '{request_headers[cookey]}'")
                            verdict = False
                        if len(mismatching_cookies) > 0:
                            self._log.debug(f"{' ' * ljustlen}Request cookies have the following mismatching entries:")
                            for cookey in mismatching_cookies:
                                self._log.debug(f"{' ' * ljustlen}'{cookey}': '{request_headers[cookey]}'")
                                self._log.debug(f"{' ' * ljustlen}{' ' * (len(cookey) + 2)}  does not equal:")
                                self._log.debug(
                                    f"{' ' * ljustlen}{' ' * (len(cookey) + 2)}  '{cached_headers[cookey]}'")
                            verdict = False
        for key in request_headers.keys():
            if key not in cached_headers:
                redundant_keys.append(key)
        if len(missing_keys) > 0:
            self._log.debug(f"{' ' * ljustlen}Request headers are missing the following entries:")
            for key in missing_keys:
                self._log.debug(f"{' ' * ljustlen}'{key}': '{cached_headers[key]}'")
            verdict = False
        if len(redundant_keys) > 0:
            self._log.debug(f"{' ' * ljustlen}Request headers have the following redundant entries:")
            for key in redundant_keys:
                self._log.debug(f"{' ' * ljustlen}'{key}': '{request_headers[key]}'")
            verdict = False
        if len(mismatching_keys) > 0:
            self._log.debug(f"{' ' * ljustlen}Request headers have the following mismatching entries:")
            for key in mismatching_keys:
                self._log.debug(f"{' ' * ljustlen}'{key}': '{request_headers[key]}'")
                self._log.debug(f"{' ' * ljustlen}{' ' * (len(key) + 2)}  does not equal:")
                self._log.debug(f"{' ' * ljustlen}{' ' * (len(key) + 2)}  '{cached_headers[key]}'")
            verdict = False
        return verdict

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
