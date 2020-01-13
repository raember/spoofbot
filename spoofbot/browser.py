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
        'Origin': {'Content-Length'},
        'Connection': {'Origin'},
        'Referer': {'Connection'},
        'Cookie': {'Referer'},
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
        self._log.debug(f"\033[36m{method}\033[0m {url}")

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

    def _assemble_headers(self, method: str, url: Url) -> dict:
        """Assembles the headers for the next request

        The method tries to guess the mimetype and encoding to fill the Accept and Accept-Encoding headers
        :param method: The method of the HTTP request
        :param url: The url the browser is supposed to connect to
        :returns: The assembled and merged headers
        :rtype: OrderedDict
        """
        headers = self._get_default_headers(url)
        mime_type, enc = mimetypes.guess_type(url.path)
        if mime_type is not None:
            headers['Accept'] = mime_type
            if enc:
                headers['Accept-Encoding'] = enc
        if 'Referer' not in headers and self._last_url is not None:
            headers['Referer'] = self._last_url.url
        if url.scheme == 'https':
            if 'TE' not in headers:
                headers['TE'] = 'Trailers'
        else:
            headers['Accept-Encoding'] = ', '.join(['gzip', 'deflate'])
        if method in ['POST', 'PATCH', 'PUT'] and self.origin is not None:
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
        else:
            self._log.debug("Delay already expired. No need to wait")


class Firefox(Browser):
    def __init__(self,
                 os=Windows(),
                 ff_version=(71, 0),
                 build_id=20100101,
                 lang=(
                         LanguageTag("en", "US"),
                         LanguageTag("en", '', 0.5)
                 ),
                 do_not_track=False,
                 upgrade_insecure_requests=True):
        super(Firefox, self).__init__()
        self._user_agent = self.create_user_agent(os, ff_version, build_id)
        self._accept = [
            MimeTypeTag("text", "html"),
            MimeTypeTag("application", "xhtml+xml"),
            MimeTypeTag("application", "xml", 0.9),
            # MimeTypeTag("image", "webp"),
            MimeTypeTag("*", "*", 0.8)
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
                 chrome_version=(79, 0, 3945, 88),
                 webkit_version=(537, 36),
                 lang=(
                         LanguageTag("en", "US"),
                         LanguageTag("en", '', 0.5)
                 ),
                 do_not_track=False,
                 upgrade_insecure_requests=False):
        super(Chrome, self).__init__()
        self._user_agent = self.create_user_agent(os=os, version=chrome_version, webkit_version=webkit_version)
        self._accept = [
            MimeTypeTag("text", "html"),
            MimeTypeTag("application", "xhtml+xml"),
            MimeTypeTag("application", "xml", 0.9),
            MimeTypeTag("image", "webp"),
            MimeTypeTag(quality=0.8)
        ]
        self._accept_language = list(lang)
        self._accept_encoding = ['gzip', 'deflate', 'br']
        self._dnt = do_not_track
        self._upgrade_insecure_requests = upgrade_insecure_requests
        self._connection = 'keep-alive'

    @staticmethod
    def create_user_agent(os=Windows(), version=(79, 0, 3945, 88), webkit_version=(537, 36)) -> str:
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

    def _get_default_headers(self, **kwargs) -> OrderedHeaders:
        headers = OrderedHeaders({
            'User-Agent': self._user_agent,
            'Accept': ','.join(map(str, self._accept)),
            'Accept-Language': ','.join(map(str, self._accept_language)),
            'Accept-Encoding': ', '.join(map(str, self._accept_encoding))
        })
        if self._dnt:
            headers['DNT'] = 1
        if self._upgrade_insecure_requests:
            headers['Upgrade-Insecure-Requests'] = 1
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
