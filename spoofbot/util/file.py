import re
from email import message, parser
from io import BytesIO

from urllib3 import HTTPResponse

from .common import coerce_content


class EmailMessage(message.Message):
    def getheaders(self, value, *args):
        # noinspection PyArgumentList
        return re.split(b', ', self.get(value, b'', *args))


class MockHTTPResponse:
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

    # noinspection PyMethodMayBeStatic
    def isclosed(self):
        return False


def load_response(filepath: str) -> HTTPResponse:
    with open(filepath, 'rb') as fp:
        text = fp.read()
    # body = text.encode('utf-8')
    return HTTPResponse(
        body=BytesIO(text),
        headers={},
        status=200,
        preload_content=False,
        original_response=MockHTTPResponse({})
    )
