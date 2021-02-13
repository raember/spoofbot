import mimetypes
from datetime import timedelta, datetime
from enum import Enum
from http.cookiejar import CookieJar
from logging import Logger, getLogger
from time import sleep
from typing import List, Optional, AnyStr, TypeVar, TextIO, Tuple, Callable, Dict
from urllib.parse import urlparse, urljoin

from requests import Response, Session, Request, PreparedRequest, codes
# noinspection PyProtectedMember
from requests._internal_utils import to_native_string
from requests.adapters import BaseAdapter
from requests.cookies import extract_cookies_to_jar, merge_cookies, cookiejar_from_dict
from requests.exceptions import ChunkedEncodingError, ContentDecodingError, TooManyRedirects
from requests.sessions import merge_setting, merge_hooks
from requests.structures import CaseInsensitiveDict
from requests.utils import requote_uri, rewind_body, get_netrc_auth
from urllib3.util.url import parse_url, Url

from spoofbot.adapter import FileCacheAdapter, HarAdapter
from spoofbot.operating_system import Windows
from spoofbot.tag import MimeTypeTag, LanguageTag
from spoofbot.util import ReferrerPolicy, are_same_origin, are_same_site, sort_dict, TimelessRequestsCookieJar


class Destination(Enum):
    AUDIO = "audio"
    AUDIO_WORKLET = "audioworklet"
    DOCUMENT = "document"
    EMBED = "embed"
    EMPTY = "empty"
    FONT = "font"
    IMAGE = "image"
    MANIFEST = "manifest"
    OBJECT = "object"
    PAINT_WORKLET = "paintworklet"
    REPORT = "report"
    SCRIPT = "script"
    SERVICE_WORKER = "serviceworker"
    SHARED_WORKER = "sharedworker"
    STYLE = "style"
    TRACK = "track"
    VIDEO = "video"
    WORKER = "worker"
    XSLT = "xslt"
    NESTED_DOCUMENT = "nested-document"


class Mode(Enum):
    CORS = "cors"
    NAVIGATE = "navigate"
    NESTED_NAVIGATE = "nested-navigate"
    NO_CORS = "no-cors"
    SAME_ORIGIN = "same-origin"
    WEBSOCKET = "websocket"


class Site(Enum):
    CROSS_SITE = "cross-site"
    SAME_ORIGIN = "same-origin"
    SAME_SITE = "same-site"
    NONE = "none"


class User(Enum):
    USER_ACTIVATED = "?1"
    AUTOMATIC = None


DictOrBytes = TypeVar('DictOrBytes', dict, bytes)
DictOrTupleListOrBytesOrFileLike = TypeVar('DictOrTupleListOrBytesOrFileLike', dict, List[tuple], bytes, TextIO)
DictOrCookieJar = TypeVar('DictOrCookieJar', dict, CookieJar)
StrOrFileLike = TypeVar('StrOrFileLike', str, TextIO)
AuthTupleOrCallable = TypeVar('AuthTupleOrCallable', Tuple[str, str], Callable)
FloatOrTuple = TypeVar('FloatOrTuple', float, Tuple[float, float])
StrOrBool = TypeVar('StrOrBool', str, bool)
StrOrStrTuple = TypeVar('StrOrStrTuple', str, Tuple[str, str])


class Browser(Session):
    """Basic browser session

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
    _last_response: Response
    _last_navigate: Response
    _last_request_timestamp: datetime
    _request_timeout: timedelta
    _honor_timeout: bool
    _waiting_period: timedelta
    _did_wait: bool
    _header_precedence: list
    _referrer_policy: ReferrerPolicy
    _adapter: BaseAdapter

    def __init__(self):
        super(Browser, self).__init__()
        self._log = getLogger(self.__class__.__name__)
        self._user_agent = ''
        self._accept = []
        self._accept_language = []
        self._accept_encoding = []
        self._dnt = False
        self._upgrade_insecure_requests = False
        self._te = 'Trailers'
        self._connection = 'keep-alive'
        # noinspection PyTypeChecker
        self._last_response = None
        # noinspection PyTypeChecker
        self._last_navigate = None
        self._last_request_timestamp = datetime(1, 1, 1)
        self._request_timeout = timedelta(seconds=1.0)
        self._honor_timeout = True
        self._waiting_period = timedelta(seconds=0.0)
        self._did_wait = False
        self._header_precedence = []
        self._referrer_policy = ReferrerPolicy.NO_REFERRER_WHEN_DOWNGRADE
        # noinspection PyTypeChecker
        self._adapter = None

    @property
    def adapter(self) -> BaseAdapter:
        return self._adapter

    @adapter.setter
    def adapter(self, value: BaseAdapter):
        self._adapter = value
        self.mount('https://', value)
        self.mount('http://', value)

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
    def origin(self) -> Optional[Url]:
        if self._last_response is None:
            return None
        last_url = parse_url(self._last_response.url)
        return Url(last_url.scheme, host=last_url.host)

    @property
    def last_response(self) -> Optional[Response]:
        return self._last_response

    @property
    def last_navigate(self) -> Optional[Response]:
        return self._last_navigate

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

    @property
    def header_precedence(self) -> list:
        return self._header_precedence

    @header_precedence.setter
    def header_precedence(self, value: list):
        self._header_precedence = value

    @staticmethod
    def create_user_agent(**kwargs) -> str:
        """Creates a user agent string according to the browsers identity.

        :param kwargs: Specific arguments to take into account.
        :returns: A custom user agent string.
        :rtype: str
        """
        raise NotImplementedError

    # noinspection DuplicatedCode
    def _get_referer(self, url: Url) -> Optional[str]:
        if self._last_navigate is None:
            return None
        nav_url = parse_url(self._last_navigate.url)
        return self._referrer_policy.get_referrer(nav_url, url)

    def _get_origin(self, method: str, url: Url) -> Optional[str]:
        if self._last_navigate is None:
            return None
        nav_url = parse_url(self._last_navigate.url)
        if not are_same_origin(nav_url, url) or method not in ['GET', 'HEAD']:
            return self._referrer_policy.get_origin(nav_url, url)

    # noinspection PyMethodMayBeStatic
    def _get_host(self, url: Url) -> str:
        if url.port:
            return f"{url.hostname}:{url.port}"
        return url.hostname

    def _get_user_agent(self) -> str:
        return self._user_agent

    def _get_accept(self, url: Url) -> str:
        mime_type, _ = mimetypes.guess_type(url.path if url.path is not None else '')
        if mime_type is not None:
            return mime_type
        return ','.join(map(str, self._accept))

    def _get_accept_language(self) -> str:
        return ','.join(map(str, self._accept_language))

    def _get_accept_encoding(self, url: Url) -> str:
        _, enc = mimetypes.guess_type(url.path if url.path is not None else '')
        if enc is not None:
            return enc
        encodings = self._accept_encoding.copy()
        if url.scheme != 'https' and 'br' in encodings:
            encodings.remove('br')
        return ', '.join(encodings)

    def _get_connection(self) -> Optional[str]:
        if self._connection != '':
            return self._connection

    def _get_dnt(self) -> Optional[str]:
        if self._dnt:
            return '1'

    def _get_upgrade_insecure_requests(self) -> Optional[str]:
        if self._upgrade_insecure_requests:
            return '1'

    def _get_te(self, url: Url) -> Optional[str]:
        if url.scheme == 'https' and self._te != '':
            return self._te

    # noinspection PyMethodMayBeStatic
    def _get_sec_fetch_dest(self, dest: Destination) -> str:
        # https://www.w3.org/TR/fetch-metadata/#sec-fetch-dest-header
        # noinspection SpellCheckingInspection
        if dest is None:
            dest = Destination.EMPTY
        # noinspection PyTypeChecker
        return dest.value

    def _get_sec_fetch_mode(self, method: str, url: Url) -> str:
        # https://www.w3.org/TR/fetch-metadata/#sec-fetch-mode-header
        mode = Mode.NO_CORS
        if self._last_navigate is None:
            mode = Mode.NAVIGATE
            # noinspection PyTypeChecker
            return mode.value
        nav_url = parse_url(self._last_navigate.url)
        if are_same_origin(url, nav_url):
            mode = Mode.SAME_ORIGIN
        if self._get_origin(method, url) is not None:
            mode = Mode.CORS
        # noinspection PyTypeChecker
        return mode.value

    def _get_sec_fetch_site(self, url: Url) -> str:
        # https://www.w3.org/TR/fetch-metadata/#sec-fetch-site-header
        site = Site.SAME_ORIGIN
        if self._last_navigate is None:
            site = Site.NONE
            # noinspection PyTypeChecker
            return site.value
        nav_url = parse_url(self._last_navigate.url)
        if not are_same_origin(url, nav_url):
            site = Site.CROSS_SITE
            if not are_same_site(url, nav_url):
                site = Site.SAME_SITE
        # noinspection PyTypeChecker
        return site.value

    def navigate(self, url: str, **kwargs) -> Response:
        """Sends a GET request to the url and sets will set it into the Referer header in subsequent requests

        :param url: The url the browser is supposed to connect to
        :param kwargs: Additional arguments to forward to the requests module
        :returns: The response to the sent request
        :rtype: Response
        """
        kwargs.setdefault('user_activation', True)
        response = self.get(url, **kwargs)
        self._last_navigate = response
        return response

    def request(self, method: AnyStr, url: AnyStr, params: DictOrBytes = None,
                data: DictOrTupleListOrBytesOrFileLike = None, headers: dict = None, cookies: DictOrCookieJar = None,
                files: StrOrFileLike = None, auth: AuthTupleOrCallable = None, timeout: FloatOrTuple = None,
                allow_redirects=True, proxies: Dict[str, str] = None, hooks: Dict[str, Callable] = None,
                stream: bool = None, verify: StrOrBool = None, cert: StrOrStrTuple = None,
                json: str = None, user_activation: bool = False) -> Response:
        """Constructs a :class:`Request <Request>`, prepares it and sends it.
        Returns :class:`Response <Response>` object.

        :param user_activation: (optional) Indicates that the request was user
            initiated.
        :param hooks: (optional) Dictionary mapping a hook (only 'request' is
            possible) to a Callable.
        :param method: method for the new :class:`Request` object.
        :param url: URL for the new :class:`Request` object.
        :param params: (optional) Dictionary or bytes to be sent in the query
            string for the :class:`Request`.
        :param data: (optional) Dictionary, list of tuples, bytes, or file-like
            object to send in the body of the :class:`Request`.
        :param json: (optional) json to send in the body of the
            :class:`Request`.
        :param headers: (optional) Dictionary of HTTP Headers to send with the
            :class:`Request`.
        :param cookies: (optional) Dict or CookieJar object to send with the
            :class:`Request`.
        :param files: (optional) Dictionary of ``'filename': file-like-objects``
            for multipart encoding upload.
        :param auth: (optional) Auth tuple or callable to enable
            Basic/Digest/Custom HTTP Auth.
        :param timeout: (optional) How long to wait for the server to send
            data before giving up, as a float, or a :ref:`(connect timeout,
            read timeout) <timeouts>` tuple.
        :type timeout: float or tuple
        :param allow_redirects: (optional) Set to True by default.
        :type allow_redirects: bool
        :param proxies: (optional) Dictionary mapping protocol or protocol and
            hostname to the URL of the proxy.
        :param stream: (optional) whether to immediately download the response
            content. Defaults to ``False``.
        :param verify: (optional) Either a boolean, in which case it controls whether we verify
            the server's TLS certificate, or a string, in which case it must be a path
            to a CA bundle to use. Defaults to ``True``.
        :param cert: (optional) if String, path to ssl client cert file (.pem).
            If Tuple, ('cert', 'key') pair.
        :rtype: requests.Response
        """
        self._report_request(method, url)

        self.headers = self._get_default_headers(method, parse_url(url), user_activation)
        self.headers.update(headers if headers else {})

        # Create the Request.
        req = Request(
            method=method.upper(),
            url=url,
            headers=self.headers,
            files=files,
            data=data or {},
            json=json,
            params=params or {},
            auth=auth,
            cookies=cookies,
            hooks=hooks,
        )
        prep = self.prepare_request(req)

        prep.headers = CaseInsensitiveDict(sort_dict(dict(prep.headers), self._header_precedence))

        proxies = proxies or {}

        settings = self.merge_environment_settings(
            prep.url, proxies, stream, verify, cert
        )

        # Await the request timeout
        self.await_timeout(parse_url(prep.url), prep.headers)

        # Send the request.
        send_kwargs = {
            'timeout': timeout,
            'allow_redirects': allow_redirects,
        }
        send_kwargs.update(settings)
        response = self.send(prep, **send_kwargs)

        self._last_request_timestamp = datetime.now()
        self._last_response = response
        self._report_response(response)
        return response

    def prepare_request(self, request):
        """Constructs a :class:`PreparedRequest <PreparedRequest>` for
        transmission and returns it. The :class:`PreparedRequest` has settings
        merged from the :class:`Request <Request>` instance and those of the
        :class:`Session`.

        :param request: :class:`Request` instance to prepare with this
            session's settings.
        :rtype: requests.PreparedRequest
        """
        cookies = request.cookies or {}

        # Bootstrap CookieJar.
        if not isinstance(cookies, CookieJar):
            cookies = cookiejar_from_dict(cookies)

        # Merge with session cookies
        cookie_jar = self.cookies.__new__(self.cookies.__class__)
        cookie_jar.__init__()
        if isinstance(cookie_jar, TimelessRequestsCookieJar):
            cookie_jar.mock_date = self.cookies.mock_date
        merged_cookies = merge_cookies(
            merge_cookies(cookie_jar, self.cookies), cookies)

        # Set environment's basic authentication if not explicitly set.
        auth = request.auth
        if self.trust_env and not auth and not self.auth:
            auth = get_netrc_auth(request.url)

        p = PreparedRequest()
        p.prepare(
            method=request.method.upper(),
            url=request.url,
            files=request.files,
            data=request.data,
            json=request.json,
            headers=merge_setting(request.headers, self.headers, dict_class=CaseInsensitiveDict),
            params=merge_setting(request.params, self.params),
            auth=merge_setting(auth, self.auth),
            cookies=merged_cookies,
            hooks=merge_hooks(request.hooks, self.hooks),
        )
        p.headers = CaseInsensitiveDict(sort_dict(dict(p.headers), self._header_precedence))
        return p

    def resolve_redirects(self, resp, req, stream=False, timeout=None,
                          verify=True, cert=None, proxies=None, yield_requests=False, **adapter_kwargs):
        """Receives a Response. Returns a generator of Responses or Requests."""

        hist = []  # keep track of history

        url = self.get_redirect_target(resp)
        previous_fragment = urlparse(req.url).fragment
        while url:
            self._report_response(resp)
            prepared_request = req.copy()

            # Update history and keep track of redirects.
            # resp.history must ignore the original request in this loop
            hist.append(resp)
            resp.history = hist[1:]

            try:
                # noinspection PyStatementEffect
                resp.content  # Consume socket so it can be released
            except (ChunkedEncodingError, ContentDecodingError, RuntimeError):
                resp.raw.read(decode_content=False)

            if len(resp.history) >= self.max_redirects:
                raise TooManyRedirects('Exceeded %s redirects.' % self.max_redirects, response=resp)

            # Release the connection back into the pool.
            resp.close()

            # Handle redirection without scheme (see: RFC 1808 Section 4)
            if url.startswith('//'):
                # noinspection SpellCheckingInspection
                parsed_rurl = urlparse(resp.url)
                url = '%s:%s' % (to_native_string(parsed_rurl.scheme), url)

            # Normalize url case and attach previous fragment if needed (RFC 7231 7.1.2)
            parsed = urlparse(url)
            if parsed.fragment == '' and previous_fragment:
                # noinspection PyProtectedMember
                parsed = parsed._replace(fragment=previous_fragment)
            elif parsed.fragment:
                previous_fragment = parsed.fragment
            url = parsed.geturl()

            # Facilitate relative 'location' headers, as allowed by RFC 7231.
            # (e.g. '/path/to/resource' instead of 'http://domain.tld/path/to/resource')
            # Compliant with RFC3986, we percent encode the url.
            if not parsed.netloc:
                url = urljoin(resp.url, requote_uri(url))
            else:
                url = requote_uri(url)

            prepared_request.url = to_native_string(url)

            self.rebuild_method(prepared_request, resp)

            # https://github.com/requests/requests/issues/1084
            if resp.status_code not in (codes.temporary_redirect, codes.permanent_redirect):
                # https://github.com/requests/requests/issues/3490
                purged_headers = ('Content-Length', 'Content-Type', 'Transfer-Encoding')
                for header in purged_headers:
                    prepared_request.headers.pop(header, None)
                prepared_request.body = None

            parsed_url = parse_url(url)
            headers = dict(prepared_request.headers)
            if 'Accept-Encoding' in headers:
                headers['Accept-Encoding'] = self._get_accept_encoding(parsed_url)

            te = self._get_te(parsed_url)
            if 'TE' in headers and te is None:
                del headers['TE']
            elif te is not None:
                headers['TE'] = te

            uir = self._get_upgrade_insecure_requests()
            if 'Upgrade-Insecure-Requests' in headers and uir is None:
                del headers['Upgrade-Insecure-Requests']
            elif uir is not None:
                headers['Upgrade-Insecure-Requests'] = uir

            if 'Host' in headers:
                headers['Host'] = parsed_url.hostname

            origin = self._get_origin(prepared_request.method, parsed_url)
            if 'Origin' in headers and origin is None:
                del headers['Origin']
            elif origin is not None:
                headers['Origin'] = origin
            try:
                del headers['Cookie']
            except KeyError:
                pass

            prepared_request.headers = headers

            self._adapt_redirection(prepared_request)

            # Extract any cookies sent on the response to the cookiejar
            # in the new request. Because we've mutated our copied prepared
            # request, use the old one that we haven't yet touched.
            # noinspection PyProtectedMember
            extract_cookies_to_jar(prepared_request._cookies, req, resp.raw)
            # noinspection PyProtectedMember
            merge_cookies(prepared_request._cookies, self.cookies)
            # noinspection PyProtectedMember
            prepared_request.prepare_cookies(prepared_request._cookies)

            # Rebuild auth and proxy information.
            proxies = self.rebuild_proxies(prepared_request, proxies)
            self.rebuild_auth(prepared_request, resp)

            # A failed tell() sets `_body_position` to `object()`. This non-None
            # value ensures `rewindable` will be True, allowing us to raise an
            # UnrewindableBodyError, instead of hanging the connection.
            # noinspection PyProtectedMember
            rewindable = (
                    prepared_request._body_position is not None and
                    ('Content-Length' in headers or 'Transfer-Encoding' in headers)
            )

            # Attempt to rewind consumed file-like object.
            if rewindable:
                rewind_body(prepared_request)

            # Override the original request.
            prepared_request.headers = dict(sort_dict(prepared_request.headers, self._header_precedence))
            req = prepared_request
            self._report_request(req.method, req.url)

            if yield_requests:
                yield req
            else:

                resp = self.send(
                    req,
                    stream=stream,
                    timeout=timeout,
                    verify=verify,
                    cert=cert,
                    proxies=proxies,
                    allow_redirects=False,
                    **adapter_kwargs
                )

                extract_cookies_to_jar(self.cookies, prepared_request, resp.raw)

                # extract redirect url, if any, for the next loop
                url = self.get_redirect_target(resp)
                self._last_navigate = resp
                yield resp

    def _report_request(self, method: str, url: str):
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

    def _get_default_headers(self, method: str, url: Url, user_activation: bool) -> CaseInsensitiveDict:
        """Provides the default headers the browser should send when connecting to an endpoint

        The method tries to guess the mimetype and encoding to fill the Accept and Accept-Encoding headers
        :param method: The method of the HTTP request
        :param url: The url the browser is supposed to connect to
        :returns: A dictionary form of the default headers.
        :rtype: OrderedHeaders
        """
        return CaseInsensitiveDict({
            'Host': self._get_host(url),
            'User-Agent': self._get_user_agent(),
            'Accept': self._get_accept(url),
            'Accept-Language': self._get_accept_language(),
            'Accept-Encoding': self._get_accept_encoding(url),
            'Connection': self._get_connection(),
            'Origin': self._get_origin(method, url),
            'Referer': self._get_referer(url),
            'DNT': self._get_dnt(),
            'Upgrade-Insecure-Requests': self._get_upgrade_insecure_requests(),
            'TE': self._get_te(url),
        })

    def await_timeout(self, url: Url = None, headers: CaseInsensitiveDict = None):
        """Waits until the request timeout expires.

        The delay will be omitted if the last request was a hit in the cache.
        Gets called automatically on every request.
        """
        if not self._honor_timeout:
            return
        self._waiting_period = timedelta(seconds=0.0)
        self._did_wait = False
        adapter = self.get_adapter('https://')
        if isinstance(adapter, HarAdapter) or isinstance(adapter, FileCacheAdapter) and adapter.hit:
            self._log.debug("Last request was a hit in cache. No need to wait.")
            return
        if headers is None:
            headers = {}
        headers.setdefault('Accept', 'text/html')
        if url is not None and isinstance(adapter, FileCacheAdapter) and adapter.would_hit(url, headers):
            self._log.debug("Request will be a hit in cache. No need to wait.")
            return
        now = datetime.now()
        wait_until = self._last_request_timestamp + self._request_timeout
        if now < wait_until:
            self._waiting_period = wait_until - now
            self._did_wait = True
            self._log.debug(f"Waiting for {self._waiting_period.total_seconds()} seconds.")
            sleep(self._waiting_period.total_seconds())

    def _adapt_redirection(self, request: PreparedRequest):
        pass


class Firefox(Browser):
    def __init__(self,
                 os=Windows(),
                 ff_version=(85, 0),
                 build_id=20100101,
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
        self._accept_language = [
            LanguageTag("en", "US"),
            LanguageTag("en", q=0.5)
        ]
        self._accept_encoding = ['gzip', 'deflate', 'br']
        self._dnt = do_not_track
        self._upgrade_insecure_requests = upgrade_insecure_requests
        self._connection = 'keep-alive'
        self._header_precedence = [
            'Host',
            'User-Agent',
            'Accept',
            'Accept-Language',
            'Accept-Encoding',
            'DNT',
            'Content-Type',
            'Content-Length',
            'Origin',
            'Connection',
            'Referer',
            'Cookie',
            'Upgrade-Insecure-Requests',
            'TE',
        ]

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


class Chrome(Browser):
    def __init__(self,
                 os=Windows(),
                 chrome_version=(79, 0, 3945, 130),
                 webkit_version=(537, 36),
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
        self._accept_language = [
            LanguageTag("en", "US"),
            LanguageTag("en", q=0.9)
        ]
        self._accept_encoding = ['gzip', 'deflate', 'br']
        self._dnt = do_not_track
        self._upgrade_insecure_requests = upgrade_insecure_requests
        self._connection = 'keep-alive'
        self._header_precedence = [
            'Host',
            'Connection',
            'Content-Type',
            # 'Content-Length',
            'Upgrade-Insecure-Requests',
            'User-Agent',
            'Sec-Fetch-User',
            'Accept',
            'Origin',
            'Sec-Fetch-Site',
            'Sec-Fetch-Mode',
            'Referer',
            'Accept-Encoding',
            'Accept-Language',
            # 'DNT',
            # 'Cookie',
            # 'TE',
        ]

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

    def navigate(self, url: str, **kwargs) -> Response:
        if parse_url(url).scheme == 'https':
            kwargs.setdefault('headers', {}).setdefault('Sec-Fetch-User', '?1')
            kwargs.setdefault('headers', {}).setdefault('Sec-Fetch-Mode', 'navigate')
        response = self.get(url, **kwargs)
        self._last_navigate = response
        return response

    def _get_default_headers(self, method: str, url: Url, user_activation: bool) -> CaseInsensitiveDict:
        adjust_accept_encoding = self._last_navigate is None
        if adjust_accept_encoding:
            self._accept_encoding = ['gzip', 'deflate']
        headers = super(Chrome, self)._get_default_headers(method, url, user_activation)
        if adjust_accept_encoding:
            self._accept_encoding = ['gzip', 'deflate', 'br']
        if url.scheme == 'https':
            headers['Sec-Fetch-Site'] = self._get_sec_fetch_site(url)
            headers['Sec-Fetch-Mode'] = self._get_sec_fetch_mode(method, url)
        return headers

    def _adapt_redirection(self, request: PreparedRequest):
        url = parse_url(request.url)
        if 'Host' in request.headers:
            del request.headers['Host']
        if 'Connection' in request.headers:
            del request.headers['Connection']
        if 'Accept-Encoding' in request.headers:
            request.headers['Accept-Encoding'] = self._get_accept_encoding(url)
        if url.scheme == 'https':
            request.headers['Sec-Fetch-Site'] = self._get_sec_fetch_site(url)
            if self._last_navigate is None:
                request.headers['Sec-Fetch-Mode'] = 'navigate'
            else:
                request.headers['Sec-Fetch-Mode'] = self._get_sec_fetch_mode(request.method, url)
        request.headers = CaseInsensitiveDict(sort_dict(dict(request.headers), self._header_precedence))

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
