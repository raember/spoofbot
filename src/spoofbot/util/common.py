"""Common and random utilities that can be useful"""
import time
from datetime import datetime
# noinspection PyUnresolvedReferences,PyProtectedMember
from http.cookiejar import split_header_words, _warn_unhandled_exception, \
    parse_ns_headers, _debug, CookieJar, \
    CookiePolicy
from typing import List, Tuple, Dict, Union
from urllib.parse import quote_plus, urlparse

from requests.cookies import RequestsCookieJar
from requests.structures import CaseInsensitiveDict
from urllib3.util import Url


def coerce_content(content, encoding=None):
    if hasattr(content, 'decode'):
        content = content.decode(encoding or 'utf-8', 'replace')
    return content


def encode_form_data(data: List[Tuple[str, str]]) -> str:
    """
    Encodes data from html forms into an escaped, url-query-like string for post
    messages
    """
    # functional flex
    return '&'.join(map('='.join, map(lambda t: (t[0], quote_plus(t[1])), data)))


def dict_to_tuple_list(other: dict) -> List[Tuple[str, str]]:
    d = []
    for key, val in other.items():
        d.append((key, val))
    return d


def dict_list_to_dict(other: List[dict], case_insensitive: bool = False) -> dict:
    d = {}
    for kv in other:
        key = kv['name']
        if case_insensitive:
            key = header_to_snake_case(key)
        d[key] = kv['value']
    return d


def dict_to_dict_list(headers: CaseInsensitiveDict) -> list[dict[str, str]]:
    data = []
    for key, value in headers.items():
        data.append({
            'name': key,
            'value': value
        })
    return data


def dict_list_to_tuple_list(other: List[dict], case_insensitive: bool = False) -> \
        List[Tuple[str, str]]:
    tuples = []
    for kv in other:
        key = kv['name']
        if case_insensitive:
            key = header_to_snake_case(key)
        tuples.append((key, kv['value']))
    return tuples


def dict_to_str(d: dict, sep: str = '; ', eq: str = '=') -> str:
    strings = []
    for k, v in d.items():
        if v:
            strings.append(f"{k}{eq}{v}")
        else:
            strings.append(k)
    return sep.join(strings)


def header_to_snake_case(string: str) -> str:
    return '-'.join(
        map(lambda w: w.capitalize() if not w.isupper() else w, string.split('-')))


def cookie_header_to_dict(cookie: str, sep: str = '; ', eq: str = '=') -> \
        Dict[str, str]:
    d = {}
    for tag in cookie.split(sep):
        if eq in tag:
            k, v = tag.split(eq, 1)
            d[k] = v
        else:
            d[tag] = None
    return d


def query_to_dict_list(query: str) -> list[dict[str, str]]:
    queries = []
    for kvp in query.split('&'):
        if '=' in kvp:
            k, v = kvp.split('=', 1)
        else:
            k, v = kvp, ''
        queries.append({
            'name': k,
            'value': v
        })
    return queries


def url_to_query_dict_list(url: Union[Url, str]) -> list[dict[str, str]]:
    if isinstance(url, str):
        url = urlparse(url)
    if url.query == '':
        return []
    return query_to_dict_list(url.query)


# noinspection SpellCheckingInspection,PyUnresolvedReferences
class TimelessRequestsCookieJar(RequestsCookieJar, CookieJar):
    _mock_date: datetime = None
    _now: float = 0.0
    _timedelta: float = 0.0
    _policy: CookiePolicy

    def __init__(self, mock_date: datetime = datetime.now()):
        super(TimelessRequestsCookieJar, self).__init__()
        self.mock_date = mock_date

    @property
    def mock_date(self) -> datetime:
        return self._mock_date

    @mock_date.setter
    def mock_date(self, value: datetime):
        self._mock_date = value
        self._now = value.timestamp()
        self._policy._now = value.timestamp()
        self._timedelta = (datetime.now() - value).total_seconds()

    def copy(self):
        """Return a copy of this RequestsCookieJar."""
        new_cj = TimelessRequestsCookieJar(self.mock_date)
        new_cj.set_policy(self.get_policy())
        new_cj.update(self)
        return new_cj

    def make_cookies(self, response, request):
        """Return sequence of Cookie objects extracted from response object."""
        # get cookie-attributes for RFC 2965 and Netscape protocols
        headers = response.info()
        rfc2965_hdrs = headers.get_all("Set-Cookie2", [])
        ns_hdrs = headers.get_all("Set-Cookie", [])
        self._policy._now = self._now = int(time.time() - self._timedelta)

        rfc2965 = self._policy.rfc2965
        netscape = self._policy.netscape

        if ((not rfc2965_hdrs and not ns_hdrs) or
                (not ns_hdrs and not rfc2965) or
                (not rfc2965_hdrs and not netscape) or
                (not netscape and not rfc2965)):
            return []  # no relevant cookie headers: quick exit

        # noinspection PyBroadException
        try:
            cookies = self._cookies_from_attrs_set(
                split_header_words(rfc2965_hdrs), request)
        except Exception:
            _warn_unhandled_exception()
            cookies = []

        if ns_hdrs and netscape:
            # noinspection PyBroadException
            try:
                # RFC 2109 and Netscape cookies
                ns_cookies = self._cookies_from_attrs_set(
                    parse_ns_headers(ns_hdrs), request)
            except Exception:
                _warn_unhandled_exception()
                ns_cookies = []
            self._process_rfc2109_cookies(ns_cookies)

            # Look for Netscape cookies (from Set-Cookie headers) that match
            # corresponding RFC 2965 cookies (from Set-Cookie2 headers).
            # For each match, keep the RFC 2965 cookie and ignore the Netscape
            # cookie (RFC 2965 section 9.1).  Actually, RFC 2109 cookies are
            # bundled in with the Netscape cookies for this purpose, which is
            # reasonable behaviour.
            if rfc2965:
                lookup = {}
                for cookie in cookies:
                    lookup[(cookie.domain, cookie.path, cookie.name)] = None

                # noinspection PyShadowingNames
                def no_matching_rfc2965(ns_cookie, lookup=None):
                    if lookup is None:
                        lookup = lookup
                    key = ns_cookie.domain, ns_cookie.path, ns_cookie.name
                    return key not in lookup

                ns_cookies = filter(no_matching_rfc2965, ns_cookies)

            if ns_cookies:
                cookies.extend(ns_cookies)

        return cookies

    def set_cookie_if_ok(self, cookie, request):
        """Set a cookie if policy says it's OK to do so."""
        self._cookies_lock.acquire()
        try:
            self._policy._now = self._now = int(time.time() - self._timedelta)
            if self._policy.set_ok(cookie, request):
                self.set_cookie(cookie)
        finally:
            self._cookies_lock.release()

    def add_cookie_header(self, request):
        """Add correct Cookie: header to request (urllib.request.Request object).

        The Cookie2 header is also added unless policy.hide_cookie2 is true.

        """
        _debug("add_cookie_header")
        self._cookies_lock.acquire()
        try:

            self._policy._now = self._now = int(time.time() - self._timedelta)

            cookies = self._cookies_for_request(request)

            attrs = self._cookie_attrs(cookies)
            if attrs:
                if not request.has_header("Cookie"):
                    request.add_unredirected_header(
                        "Cookie", "; ".join(attrs))

            # if necessary, advertise that we know RFC 2965
            if (self._policy.rfc2965 and not self._policy.hide_cookie2 and
                    not request.has_header("Cookie2")):
                for cookie in cookies:
                    if cookie.version != 1:
                        request.add_unredirected_header("Cookie2", '$Version="1"')
                        break

        finally:
            self._cookies_lock.release()

        self.clear_expired_cookies()
