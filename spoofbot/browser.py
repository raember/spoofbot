import mimetypes
import sys
from datetime import timedelta, datetime
from logging import Logger, getLogger
from time import sleep
from typing import List, Optional

import toposort as toposort
from requests import Response, Session
from requests.adapters import BaseAdapter
from requests.compat import OrderedDict
from urllib3.util.url import parse_url, Url

from spoofbot.adapter import FileCacheAdapter, HarAdapter
from spoofbot.operating_system import Windows
from spoofbot.tag import MimeTypeTag, LanguageTag


# Thanks, buddy
# https://stackoverflow.com/questions/44864896/python-ordered-headers-http-requests#44865372
class OrderedHeaders(dict):
    # The precedence of headers is determined once. In this example,
    # 'Accept-Encoding' must be sorted behind 'User-Agent'
    # (if defined) and 'version' must be sorted behind both
    # 'Accept-Encoding' and 'Connection' (if defined).
    PRECEDENCE = toposort.toposort_flatten({
        'User-Agent': {'Host'},
        'Accept': {'User-Agent'},
        'Accept-Language': {'Accept'},
        'Accept-Encoding': {'Accept-Language'},
        'DNT': {'Accept-Encoding'},
        'Content-Type': {'DNT'},
        'Content-Length': {'Content-Type'},
        'Referer': {'Content-Length'},
        'Origin': {'Referer'},
        'Connection': {'Origin'},
        'Cookie': {'Connection'},
        'Upgrade-Insecure-Request': {'Cookie'},
        'TE': {'Upgrade-Insecure-Request'},
    })

    def items(self):
        s = []
        for k, v in dict.items(self):
            try:
                precedence = self.PRECEDENCE.index(k)
            except ValueError:
                # no defined sort for this header, so we put it behind any other sorted header
                precedence = sys.maxsize
            s.append((precedence, k, v))
        return ((k, v) for _, k, v in sorted(s))


class Browser:
    """Basic model of a browser

    Specific browsers must inherit from this class and overwrite the abstract methods
    """

    _log: Logger
    _user_agent: str
    _accept: List[MimeTypeTag]
    _accept_language: List[LanguageTag]
    _accept_encoding: List[str]
    _dnt: bool
    _upgrade_insecure_requests: bool
    _te: str
    _connection: str
    _session: Session
    _adapter: BaseAdapter
    _last_url: Url
    _last_request_timestamp: datetime
    _request_timeout: timedelta
    _honor_timeout: bool
    _waiting_period: timedelta
    _did_wait: bool

    def __init__(self):
        self._log = getLogger(self.__class__.__name__)
        self._user_agent = ''
        self._accept = []
        self._accept_language = []
        self._accept_encoding = []
        self._dnt = False
        self._upgrade_insecure_requests = False
        self._te = 'Trailers'
        self._connection = 'keep-alive'
        self._session = Session()
        self._adapter = self._session.get_adapter('https://')
        # noinspection PyTypeChecker
        self._last_url = None
        self._last_request_timestamp = datetime(1, 1, 1)
        self._request_timeout = timedelta(seconds=1.0)
        self._honor_timeout = True
        self._waiting_period = timedelta(seconds=0.0)
        self._did_wait = False

    @property
    def user_agent(self) -> str:
        return self._user_agent

    @user_agent.setter
    def user_agent(self, value: str):
        self._user_agent = value

    @property
    def accept(self) -> List[MimeTypeTag]:
        return self._accept

    @accept.setter
    def accept(self, value: List[MimeTypeTag]):
        self._accept = value

    @property
    def accept_language(self) -> List[LanguageTag]:
        return self._accept_language

    @accept_language.setter
    def accept_language(self, value: List[LanguageTag]):
        self._accept_language = value

    @property
    def accept_encoding(self) -> List[str]:
        return self._accept_encoding

    @accept_encoding.setter
    def accept_encoding(self, value: List[str]):
        self._accept_encoding = value

    @property
    def do_not_track(self) -> bool:
        return self._dnt

    @do_not_track.setter
    def do_not_track(self, value: bool):
        self._dnt = value

    @property
    def upgrade_insecure_requests(self) -> bool:
        return self._upgrade_insecure_requests

    @upgrade_insecure_requests.setter
    def upgrade_insecure_requests(self, value: bool):
        self._upgrade_insecure_requests = value

    @property
    def transfer_encoding(self) -> str:
        return self._te

    @transfer_encoding.setter
    def transfer_encoding(self, value: str):
        self._te = value

    @property
    def connection(self) -> str:
        return self._connection

    @connection.setter
    def connection(self, value: str):
        self._connection = value

    @property
    def session(self) -> Session:
        return self._session

    @session.setter
    def session(self, value: Session):
        self._session = value
        self._adapter = self._session.get_adapter('https://')

    @property
    def adapter(self) -> BaseAdapter:
        return self._adapter

    @adapter.setter
    def adapter(self, value: BaseAdapter):
        self._adapter = value
        if self._session is not None:
            self._session.mount('https://', self._adapter)
            self._session.mount('http://', self._adapter)

    @property
    def origin(self) -> Optional[Url]:
        if self._last_url is None:
            return None
        return Url(self._last_url.scheme, host=self._last_url.host)

    @property
    def referer(self) -> Optional[Url]:
        return self._last_url

    @property
    def last_request_timestamp(self) -> datetime:
        return self._last_request_timestamp

    @last_request_timestamp.setter
    def last_request_timestamp(self, value: datetime):
        self._last_request_timestamp = value

    @property
    def request_timeout(self) -> timedelta:
        return self._request_timeout

    @request_timeout.setter
    def request_timeout(self, value: timedelta):
        self._request_timeout = value

    @property
    def honor_timeout(self) -> bool:
        return self._honor_timeout

    @honor_timeout.setter
    def honor_timeout(self, value: bool):
        self._honor_timeout = value

    @property
    def waiting_period(self) -> timedelta:
        return self._waiting_period

    @property
    def did_wait(self) -> bool:
        return self._did_wait

    @staticmethod
    def create_user_agent(**kwargs) -> str:
        """Creates a user agent string according to the browsers identity.

        :param kwargs: Specific arguments to take into account.
        :returns: A custom user agent string.
        :rtype: str
        """
        raise NotImplementedError

    def navigate(self, url: Url, **kwargs) -> Response:
        """Sends a GET request to the url and sets will set it into the Referer header in subsequent requests

        :param url: The url the browser is supposed to connect to
        :param kwargs: Additional arguments to forward to the requests module
        :returns: The response to the sent request
        :rtype: Response
        """
        response = self.get(url, **kwargs)
        self._last_url = parse_url(response.url)
        return response

    def get(self, url: Url, **kwargs) -> Response:
        """Sends a GET request to the url

        :param url: The url the browser is supposed to connect to
        :param kwargs: Additional arguments to forward to the requests module
        :returns: The response to the sent request
        :rtype: Response
        """
        self._session.headers = self._assemble_headers('GET', url)
        self._session.headers.update(kwargs.setdefault('headers', {}))
        del kwargs['headers']
        self.await_timeout()
        self._report_request('GET', url)
        return self._handle_response(self._session.get(url, **kwargs))

    def post(self, url: Url, data: str = None, json: dict = None, **kwargs) -> Response:
        """Sends a POST request to the url

        :param url: The url the browser is supposed to connect to
        :param data: Optional data string as payload to the request
        :param json: Optional json data structure as payload to the request
        :param kwargs: Additional arguments to forward to the requests module
        :returns: The response to the sent request
        :rtype: Response
        """
        self._session.headers = self._assemble_headers('POST', url)
        self._session.headers.update(kwargs.setdefault('headers', {}))
        del kwargs['headers']
        self.await_timeout()
        self._report_request('POST', url)
        return self._handle_response(self._session.post(url, data, json, **kwargs))

    def head(self, url: Url, **kwargs) -> Response:
        """Sends a HEAD request to the url

        :param url: The url the browser is supposed to connect to
        :param kwargs: Additional arguments to forward to the requests module
        :returns: The response to the sent request
        :rtype: Response
        """
        self._session.headers = self._assemble_headers('HEAD', url)
        self._session.headers.update(kwargs.setdefault('headers', {}))
        del kwargs['headers']
        self.await_timeout()
        self._report_request('HEAD', url)
        return self._handle_response(self._session.head(url, **kwargs))

    def delete(self, url: Url, **kwargs) -> Response:
        """Sends a DELETE request to the url

        :param url: The url the browser is supposed to connect to
        :param kwargs: Additional arguments to forward to the requests module
        :returns: The response to the sent request
        :rtype: Response
        """
        self._session.headers = self._assemble_headers('DELETE', url)
        self._session.headers.update(kwargs.setdefault('headers', {}))
        del kwargs['headers']
        self.await_timeout()
        self._report_request('DELETE', url)
        return self._handle_response(self._session.delete(url, **kwargs))

    def options(self, url: Url, **kwargs) -> Response:
        """Sends a OPTIONS request to the url

        :param url: The url the browser is supposed to connect to
        :param kwargs: Additional arguments to forward to the requests module
        :returns: The response to the sent request
        :rtype: Response
        """
        self._session.headers = self._assemble_headers('OPTIONS', url)
        self._session.headers.update(kwargs.setdefault('headers', {}))
        del kwargs['headers']
        self.await_timeout()
        self._report_request('OPTIONS', url)
        return self._handle_response(self._session.options(url, **kwargs))

    def patch(self, url: Url, data: str = None, **kwargs) -> Response:
        """Sends a PATCH request to the url

        :param url: The url the browser is supposed to connect to
        :param data: Optional data string as payload to the request
        :param kwargs: Additional arguments to forward to the requests module
        :returns: The response to the sent request
        :rtype: Response
        """
        self._session.headers = self._assemble_headers('PATCH', url)
        self._session.headers.update(kwargs.setdefault('headers', {}))
        del kwargs['headers']
        self.await_timeout()
        self._report_request('PATCH', url)
        return self._handle_response(self._session.patch(url, data, **kwargs))

    def put(self, url: Url, data: str = None, **kwargs) -> Response:
        """Sends a PUT request to the url

        :param url: The url the browser is supposed to connect to
        :param data: Optional data string as payload to the request
        :param kwargs: Additional arguments to forward to the requests module
        :returns: The response to the sent request
        :rtype: Response
        """
        self._session.headers = self._assemble_headers('PUT', url)
        self._session.headers.update(kwargs.setdefault('headers', {}))
        del kwargs['headers']
        self.await_timeout()
        self._report_request('PUT', url)
        return self._handle_response(self._session.put(url, data, **kwargs))

    def _report_request(self, method: str, url: Url):
        self._log.debug(f"\033[36m{method}\033[0m {url}")  # 36 = cyan fg

    def _report_response(self, response: Response):
        fg_red = 31
        fg_mag = 35
        rev_vd = 7
        fg_grn = 32
        fg_wht = 97
        color, msg = {
            500: (fg_red, 'Internal Server Error'),
            501: (fg_red, 'Not Implemented'),
            502: (fg_red, 'Bad Gateway'),
            503: (fg_red, 'Service Unavailable'),
            504: (fg_red, 'Gateway Timeout'),
            505: (fg_red, 'HTTP Version Not Supported'),
            506: (fg_mag, 'Variant Also Negotiates'),
            507: (fg_mag, 'Insufficient Storage'),  # WebDAV
            508: (fg_mag, 'Loop Detected'),  # WebDAV
            510: (fg_mag, 'Not Extended'),
            511: (fg_mag, 'Network Authentication Required'),
            400: (fg_mag, 'Bad Request'),
            401: (fg_mag, 'Unauthorized'),
            402: (fg_mag, 'Payment Required'),
            403: (fg_mag, 'Forbidden'),
            404: (fg_mag, 'Not Found'),
            405: (fg_mag, 'Method Not Allowed'),
            406: (fg_mag, 'Not Acceptable'),
            407: (fg_mag, 'Proxy Authentication Required'),
            408: (fg_mag, 'Request Timeout'),
            409: (fg_mag, 'Conflict'),
            410: (fg_mag, 'Gone'),
            411: (fg_mag, 'Length Required'),
            412: (fg_mag, 'Precondition Failed'),
            413: (fg_mag, 'Payload Too Large'),
            414: (fg_mag, 'URI Too Long'),
            415: (fg_mag, 'Unsupported Media Type'),
            416: (fg_mag, 'Range Not Satisfiable'),
            417: (fg_mag, 'Expectation Failed'),
            418: (fg_mag, "I'm a teapot"),
            421: (fg_mag, 'Misdirected Request'),
            422: (fg_mag, 'Unprocessable Entity'),  # WebDAV
            423: (fg_mag, 'Locked'),  # WebDAV
            424: (fg_mag, 'Failed Dependency'),  # WebDAV
            425: (fg_mag, 'Too Early'),
            426: (fg_mag, 'Upgrade Required'),
            428: (fg_mag, 'Precondition Required'),
            429: (fg_mag, 'Too Many Requests'),
            431: (fg_mag, 'Request Header Fields Too Large'),
            451: (fg_mag, 'Unavailable For Legal Reasons'),
            300: (rev_vd, 'Multiple Choices'),
            301: (rev_vd, 'Moved Permanently'),
            302: (rev_vd, 'Found'),
            303: (rev_vd, 'See Other'),
            304: (rev_vd, 'Not Modified'),
            305: (rev_vd, 'Use Proxy'),
            307: (rev_vd, 'Temporary Redirect'),
            308: (rev_vd, 'Permanent Redirect'),
            200: (fg_grn, 'OK'),
            201: (fg_grn, 'Created'),
            202: (fg_grn, 'Accepted'),
            203: (fg_grn, 'Non-Authoritative Information'),
            204: (fg_grn, 'No Content'),
            205: (fg_grn, 'Reset Content'),
            206: (fg_grn, 'Partial Content'),
            207: (fg_grn, 'Multi-Status'),  # WebDAV
            208: (fg_grn, 'Already Reported'),  # WebDAV
            226: (fg_grn, 'IM Used'),
            100: (fg_wht, 'Continue'),
            101: (fg_wht, 'Switching Protocols'),
            102: (fg_wht, 'Processing'),  # WebDAV
            103: (fg_wht, 'Early Hints'),
        }.get(response.status_code, (91, 'UNKNOWN'))
        self._log.debug(f"{' ' * len(response.request.method)} \033[{color}m← {response.status_code} {msg}\033[0m "
                        f"{response.headers.get('Content-Type', '-')}")

    def _assemble_headers(self, method: str, url: Url) -> dict:
        """Assembles the headers for the next request

        The method tries to guess the mimetype and encoding to fill the Accept and Accept-Encoding headers
        :param method: The method of the HTTP request
        :param url: The url the browser is supposed to connect to
        :returns: The assembled and merged headers
        :rtype: OrderedDict
        """
        headers = self._get_default_headers(url)
        mime_type, enc = mimetypes.guess_type(url.path if url.path is not None else '')
        if mime_type is not None:
            headers['Accept'] = mime_type
            if enc:
                headers['Accept-Encoding'] = enc
        if self._last_url is not None:
            headers.setdefault('Referer', self._last_url.url)
        headers.setdefault('TE', self._te)
        # else:
        #     headers['Accept-Encoding'] = ', '.join(['gzip', 'deflate'])
        if self.origin is not None and self.origin.hostname == url.hostname and method != 'GET':
            headers.setdefault('Origin', self.origin.url)
        return headers

    def _get_default_headers(self, url: Url) -> OrderedHeaders:
        """Provides the default headers the browser should send when connecting to an unknown url

        :param url: The url the browser is supposed to connect to
        :returns: A dictionary form of the default headers.
        :rtype: OrderedHeaders
        """
        raise NotImplementedError

    def _handle_response(self, response: Response) -> Response:
        self._last_request_timestamp = datetime.now()
        if response.history:  # In case of redirect
            self._last_url = parse_url(response.url)
        self._report_response(response)
        return response

    def await_timeout(self):
        """Waits until the request timeout expires.

        The delay will be omitted if the last request was a hit in the cache.
        Gets called automatically on every request.
        """
        if not self._honor_timeout:
            return
        self._waiting_period = timedelta(seconds=0.0)
        self._did_wait = False
        if isinstance(self._adapter, HarAdapter) or isinstance(self._adapter, FileCacheAdapter) and self._adapter.hit:
            self._log.debug("Last request was a hit in cache. No need to wait.")
            return
        now = datetime.now()
        wait_until = self._last_request_timestamp + self._request_timeout
        if now < wait_until:
            self._waiting_period = wait_until - now
            self._did_wait = True
            self._log.debug(f"Waiting for {self._waiting_period.total_seconds()} seconds.")
            sleep(self._waiting_period.total_seconds())


class Firefox(Browser):
    def __init__(self,
                 os=Windows(),
                 ff_version=(72, 0),
                 build_id=20100101,
                 lang=(
                         LanguageTag("en", "US"),
                         LanguageTag("en", q=0.5)
                 ),
                 do_not_track=False,
                 upgrade_insecure_requests=True):
        super(Firefox, self).__init__()
        self._user_agent = self.create_user_agent(os, ff_version, build_id)
        self._accept = [
            MimeTypeTag("text", "html"),
            MimeTypeTag("application", "xhtml+xml"),
            MimeTypeTag("application", "xml", q=0.9),
            MimeTypeTag("image", "webp"),
            MimeTypeTag("*", "*", q=0.8)
        ]
        self._accept_language = list(lang)
        self._accept_encoding = ['gzip', 'deflate', 'br']
        self._dnt = do_not_track
        self._upgrade_insecure_requests = upgrade_insecure_requests
        self._connection = 'keep-alive'

    @staticmethod
    def create_user_agent(os=Windows(), version=(71, 0), build_id=20100101) -> str:
        """Creates a user agent string for Firefox

        :param os: The underlying operating system (default :py:class:`Windows`).
        :param version: The version of Firefox (default (71, 0)).
        :param build_id: The build id of Gecko (default 20100101).
        :returns: A custom user agent string.
        """
        ff_version = '.'.join(map(str, version))
        return f"Mozilla/5.0 ({os}; rv:{ff_version}) " \
               f"Gecko/{build_id} " \
               f"Firefox/{ff_version}"

    def _get_default_headers(self, url: Url) -> OrderedHeaders:
        headers = OrderedHeaders({
            'Host': url.hostname,
            'User-Agent': self._user_agent,
            'Accept': ','.join(map(str, self._accept)),
            'Accept-Language': ','.join(map(str, self._accept_language)),
            'Accept-Encoding': ', '.join(map(str, self._accept_encoding))
        })
        if self._connection != '':
            headers['Connection'] = self._connection
        if self._dnt:
            headers['DNT'] = '1'
        if self._upgrade_insecure_requests:
            headers['Upgrade-Insecure-Requests'] = '1'
        return headers


class Chrome(Browser):
    def __init__(self,
                 os=Windows(),
                 chrome_version=(79, 0, 3945, 130),
                 webkit_version=(537, 36),
                 lang=(
                         LanguageTag("en", "US"),
                         LanguageTag("en", q=0.9)
                 ),
                 do_not_track=False,
                 upgrade_insecure_requests=True):
        super(Chrome, self).__init__()
        self._user_agent = self.create_user_agent(os=os, version=chrome_version, webkit_version=webkit_version)
        self._accept = [
            MimeTypeTag("text", "html"),
            MimeTypeTag("application", "xhtml+xml"),
            MimeTypeTag("application", "xml", q=0.9),
            MimeTypeTag("image", "webp"),
            MimeTypeTag("image", "apng"),
            MimeTypeTag(q=0.8),
            MimeTypeTag("application", "signed-exchange", v='b3', q=0.9),
        ]
        self._accept_language = list(lang)
        self._accept_encoding = ['gzip', 'deflate', 'br']
        self._dnt = do_not_track
        self._upgrade_insecure_requests = upgrade_insecure_requests
        self._connection = 'keep-alive'

    @staticmethod
    def create_user_agent(os=Windows(), version=(79, 0, 3945, 130), webkit_version=(537, 36)) -> str:
        """Creates a user agent string for Firefox

        :param os: The underlying operating system (default :py:class:`Windows`).
        :param version: The version of the underlying webkit (default `(79, 0, 3945, 88)).
        :param webkit_version: The version of Chrome (default: (537, 36)).
        :returns: A custom user agent string.
        """
        webkit_ver = '.'.join(map(str, webkit_version))
        return f"Mozilla/5.0 ({os}) " \
               f"AppleWebKit/{webkit_ver} (KHTML, like Gecko) " \
               f"Chrome/{'.'.join(map(str, version))} " \
               f"Safari/{webkit_ver}"

    def _get_default_headers(self, url: Url) -> OrderedHeaders:
        headers = OrderedHeaders({
            'Host': url.hostname,
            'User-Agent': self._user_agent,
            'Accept': ','.join(map(str, self._accept)),
            'Accept-Language': ','.join(map(str, self._accept_language)),
            'Accept-Encoding': ', '.join(map(str, self._accept_encoding))
        })
        if self._dnt:
            headers['DNT'] = '1'
        if self._upgrade_insecure_requests:
            headers['Upgrade-Insecure-Requests'] = '1'
        if self._connection != '':
            headers['Connection'] = self._connection
        return headers

# def build_chromium_user_agent(
#         os=Linux(),
#         chromium_version='79.0.3945.92',
#         webkit_version='607.1.40') -> str:
#     return f"Mozilla/5.0 ({os}) " \
#            f"AppleWebKit/{webkit_version} (KHTML, like Gecko) " \
#            f"Chromium/{chromium_version} " \
#            f"Safari/{webkit_version}"
#
#
# def build_safari_user_agent(
#         os=MacOSX(),
#         safari_version='12.1.2',
#         webkit_version='607.1.40') -> str:
#     return f"Mozilla/5.0 ({os}) " \
#            f"AppleWebKit/{webkit_version} (KHTML, like Gecko) " \
#            f"Version/{safari_version} " \
#            f"Safari/{webkit_version}"
#
#
# def build_opera_user_agent(
#         os=MacOSXVersion.Catalina,
#         opera_version='65.0.3467.42',
#         chrome_version='78.0.3904.87',
#         webkit_version='537.36') -> str:
#     return f"Mozilla/5.0 ({os.to_comment()}) " \
#            f"AppleWebKit/{webkit_version} (KHTML, like Gecko) " \
#            f"Chrome/{chrome_version} " \
#            f"Safari/{webkit_version} " \
#            f"OPR/{opera_version}"
