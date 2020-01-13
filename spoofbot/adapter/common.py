import re
from email import parser, message

# Thanks, buddy:
# https://stackoverflow.com/questions/26740791/using-requests-adapters-httpadapter-for-testing
# https://github.com/betamaxpy/betamax/blob/ec077d93cf95b65456819b86174af31d025f0d3c/betamax/cassette/util.py#L118


def coerce_content(content, encoding=None):
    if hasattr(content, 'decode'):
        content = content.decode(encoding or 'utf-8', 'replace')
    return content


class EmailMessage(message.Message):
    def getheaders(self, value, *args):
        # noinspection PyArgumentList
        return re.split(b', ', self.get(value, b'', *args))


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
