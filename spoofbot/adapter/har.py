"""Provides functionality to inject HAR files as basis for a session to run on"""

import json
import logging
import os
from typing import List

from requests import PreparedRequest
from requests.adapters import HTTPAdapter
from requests.structures import CaseInsensitiveDict
from urllib3.util.url import parse_url

from spoofbot.util import request_from_entry, response_from_entry
from spoofbot.util.har import prepare_request


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
        self._log.info(f"Using HAR file from {str(self)}")

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

    def send(self, request: PreparedRequest, stream=False, timeout=None, verify=True, cert=None, proxies=None):
        indent = ' ' * len(request.method)
        for i, entry in enumerate(self.entries):
            cached_request = prepare_request(request_from_entry(entry))
            if self._match_requests(request, cached_request):
                self._log.debug(f"{indent}Request matched")
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
                if not self._match_dict(request.headers, cached_request.headers, len(request.method)):
                    self._log.debug(f"{indent}Headers mismatch")
                    return False
                if cached_request.body:
                    if cached_request.body != request.body:
                        self._log.debug(
                            f"{indent}Post data mismatch:\n{request.body}\n!=\n{cached_request.body}")
                        return False
            return True
        return False

    def _match_dict(self, request_headers: CaseInsensitiveDict, cached_headers: CaseInsensitiveDict,
                    ljustlen: int) -> bool:
        indent = ' ' * ljustlen
        if request_headers is None:
            self._log.warning(f"{indent}Request headers is None")
            return False
        verdict = True
        if dict(request_headers).keys() != dict(cached_headers).keys():
            self._log.debug(f"{indent}Request header order does not match:")
            self._log.debug(f"{indent}  {list(dict(request_headers).keys())}")
            self._log.debug(f"{indent}  does not equal cached:")
            self._log.debug(f"{indent}  {list(dict(cached_headers).keys())}")
            verdict = False
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
                            self._log.debug(f"{indent}Request cookies are missing the following entries:")
                            for cookey in missing_cookies:
                                self._log.debug(f"{indent}  '{cookey}': '{cached_headers[cookey]}'")
                            verdict = False
                        if len(redundant_cookies) > 0:
                            self._log.debug(f"{indent}Request cookies have the following redundant entries:")
                            for cookey in redundant_cookies:
                                self._log.debug(f"{indent}  '{cookey}': '{request_headers[cookey]}'")
                            verdict = False
                        if len(mismatching_cookies) > 0:
                            self._log.debug(f"{indent}Request cookies have the following mismatching entries:")
                            for cookey in mismatching_cookies:
                                self._log.debug(f"{indent}  '{cookey}': '{request_headers[cookey]}'")
                                self._log.debug(f"{indent}  {' ' * (len(cookey) + 2)}  does not equal:")
                                self._log.debug(
                                    f"{indent}  {' ' * (len(cookey) + 2)}  '{cached_headers[cookey]}'")
                            verdict = False
        for key in request_headers.keys():
            if key not in cached_headers:
                redundant_keys.append(key)
        if len(missing_keys) > 0:
            self._log.debug(f"{indent}Request headers are missing the following entries:")
            for key in missing_keys:
                self._log.debug(f"{indent}  '{key}': '{cached_headers[key]}'")
            verdict = False
        if len(redundant_keys) > 0:
            self._log.debug(f"{indent}Request headers have the following redundant entries:")
            for key in redundant_keys:
                self._log.debug(f"{indent}  '{key}': '{request_headers[key]}'")
            verdict = False
        if len(mismatching_keys) > 0:
            self._log.debug(f"{indent}Request headers have the following mismatching entries:")
            for key in mismatching_keys:
                self._log.debug(f"{indent}  '{key}': '{request_headers[key]}'")
                self._log.debug(f"{indent}  {' ' * (len(key) + 2)}  does not equal:")
                self._log.debug(f"{indent}  {' ' * (len(key) + 2)}  '{cached_headers[key]}'")
            verdict = False
        return verdict

    def __str__(self):
        version = self.creator_version
        if version != '':
            return f"{self.creator} {version}, {len(self.entries)} Requests"
        return f"{self.creator}, {len(self.entries)} Requests"


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


def load_har(file: str) -> dict:
    with open(file, 'r') as fp:
        return json.load(fp)
