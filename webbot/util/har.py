import base64
import json
import logging
import re
from email import parser, message
from io import BytesIO
from typing import List, Tuple

from requests import PreparedRequest
from requests.adapters import HTTPAdapter
from requests.structures import CaseInsensitiveDict
from urllib3.response import HTTPResponse
from urllib3.util.url import parse_url


def coerce_content(content, encoding=None):
    if hasattr(content, 'decode'):
        content = content.decode(encoding or 'utf-8', 'replace')
    return content


# Thanks, buddy:
# https://stackoverflow.com/questions/26740791/using-requests-adapters-httpadapter-for-testing
# https://github.com/betamaxpy/betamax/blob/ec077d93cf95b65456819b86174af31d025f0d3c/betamax/cassette/util.py#L118
class MockHTTPResponse():
    def __init__(self, headers):
        h = ["%s: %s" % (k, v) for (k, v) in headers]
        h = map(coerce_content, h)
        h = '\r\n'.join(h)
        p = parser.Parser(EmailMessage)
        # Thanks to Python 3, we have to use the slightly more awful API below
        # mimetools was deprecated so we have to use email.message.Message
        # which takes no arguments in its initializer.
        self.msg = p.parsestr(h)
        self.msg.set_payload(h)

    def isclosed(self):
        return False


class EmailMessage(message.Message):
    def getheaders(self, value, *args):
        # noinspection PyArgumentList
        return re.split(b', ', self.get(value, b'', *args))


class HarAdapter(HTTPAdapter):
    _data: dict = None
    _log = logging.getLogger('HarAdapter')

    def __init__(self, har_data: dict):
        super(HarAdapter, self).__init__()
        self._data = har_data
        self._log.setLevel(logging.DEBUG)

    def send(self, request: PreparedRequest, stream=False, timeout=None, verify=True, cert=None, proxies=None):
        self._log.info(f"Matching {request.method} {request.url}")
        entries: list = self._data['log']['entries']
        for i, entry in enumerate(entries):
            req = entry['request']
            if req['method'] == request.method and req['url'] == request.url:
                other_headers = CaseInsensitiveDict(self._to_dict(req['headers']))
                if not self._match_dict(request.headers, other_headers):
                    self._log.warning(f"Headers mismatch:\n{request.headers}\n !=\n{other_headers}")
                    continue
                if 'postData' in req:
                    if not req['postData']['text'] == request.body:
                        self._log.error(f"Post data mismatch:\n{request.headers}\n !=\n{other_headers}")
                        continue
                self._log.info("Request matched")
                resp = entry['response']
                response = self._create_response(resp)
                if resp['redirectURL'] != '':
                    url = parse_url(resp['redirectURL'])
                    if url.hostname is not None:
                        request.headers['Host'] = url.hostname
                    if 'Origin' in request.headers:
                        del request.headers['Origin']  # no Origin header for fetch requests, since redirect
                    if url.scheme == 'https':
                        request.headers['accept-encoding'] = ', '.join(['gzip', 'deflate', 'br'])
                        if 'TE' not in request.headers:
                            request.headers['TE'] = 'Trailers'
                del entries[i]  # Delete entry as we already matched it once.
                self._log.debug("Deleted matched entry from list")
                return self.build_response(request, response)
        raise Exception("No matching entry in HAR found")

    def _to_dict(self, other: List[dict]) -> List[Tuple[str, str]]:
        d = []
        for kv in other:
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

    def _create_response(self, resp: dict) -> HTTPResponse:
        resp_headers = self._to_dict(resp['headers'])
        content = resp['content']
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
            headers=resp_headers,
            status=resp['status'],
            preload_content=False,
            original_response=MockHTTPResponse(resp_headers)
        )


def load_har(file: str) -> dict:
    with open(file, 'r') as fp:
        return json.load(fp)
