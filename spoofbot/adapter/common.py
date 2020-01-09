import logging
import re
from email import parser, message

# Thanks, buddy:
# https://stackoverflow.com/questions/26740791/using-requests-adapters-httpadapter-for-testing
# https://github.com/betamaxpy/betamax/blob/ec077d93cf95b65456819b86174af31d025f0d3c/betamax/cassette/util.py#L118
from requests import PreparedRequest, Response
from requests.adapters import HTTPAdapter


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


class ReportingAdapter(HTTPAdapter):
    _log: logging.Logger

    def _report_request(self, request: PreparedRequest):
        self._log.debug(f"\033[36m{request.method}\033[0m {request.url}")

    def _report_response(self, response: Response):
        if response.status_code >= 500:
            color = 31  # Red
        elif response.status_code >= 400:
            color = 35  # Magenta
        elif response.status_code >= 300:
            color = 27  # Reverse video
        elif response.status_code >= 200:
            color = 32  # Green
        else:
            color = 39  # Default
        self._log.debug(f"{' ' * len(response.request.method)} \033[{color}m← {response.status_code}\033[0m "
                        f"{response.headers.get('Content-Type', '-')}")
