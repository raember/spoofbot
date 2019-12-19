import json as jsn
import re
from email import parser, message
from io import BytesIO
from typing import List

from requests import Session, PreparedRequest
from requests.adapters import HTTPAdapter
from requests.structures import CaseInsensitiveDict
from urllib3.response import HTTPResponse


def coerce_content(content, encoding=None):
    if hasattr(content, 'decode'):
        content = content.decode(encoding or 'utf-8', 'replace')
    return content


# Thanks, buddy:
# https://stackoverflow.com/questions/26740791/using-requests-adapters-httpadapter-for-testing
# https://github.com/betamaxpy/betamax/blob/ec077d93cf95b65456819b86174af31d025f0d3c/betamax/cassette/util.py#L118
class MockHTTPResponse():
    def __init__(self, headers):
        h = ["%s: %s" % (k, v) for (k, v) in headers.items()]
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
        return re.split(b', ', self.get(value, b'', *args))


class HarAdapter(HTTPAdapter):
    _data: dict = None

    def __init__(self, har_data: dict):
        super(HarAdapter, self).__init__()
        self._data = har_data

    def send(self, request: PreparedRequest, stream=False, timeout=None, verify=True, cert=None, proxies=None):
        for entry in self._data['log']['entries']:
            req = entry['request']
            if req['method'] == request.method and req['url'] == request.url:
                other_headers = CaseInsensitiveDict(self._to_dict(req['headers']))
                if not self._match_dict(request.headers, other_headers):
                    print(f"Headers mismatch:\n{request.headers}\n !=\n{other_headers}")
                    continue
                resp = entry['response']
                resp_headers = CaseInsensitiveDict(self._to_dict(resp['headers']))
                response = HTTPResponse(
                    body=BytesIO(resp['content']['text'].encode('utf-8')),
                    headers=resp_headers,
                    status=resp['status'],
                    preload_content=False,
                    original_response=MockHTTPResponse(resp_headers)
                )
                return self.build_response(request, response)

    def _to_dict(self, other: List[dict]) -> dict:
        d = {}
        for kv in other:
            d[kv['name']] = kv['value']
        return d

    def _match_dict(self, own: CaseInsensitiveDict, other: CaseInsensitiveDict) -> bool:
        if own is None or len(own) != len(other):
            return False
        for key, value in other.items():
            if own.setdefault(key, None) != value:
                return False
        return True


class HarSession(Session):
    def __init__(self, file: str):
        super(HarSession, self).__init__()
        with open(file, 'r') as fp:
            data = jsn.load(fp)
            self.mount('https://', HarAdapter(data))
            self.mount('http://', HarAdapter(data))
