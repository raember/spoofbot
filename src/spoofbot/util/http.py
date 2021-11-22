import re
import sys
from enum import Enum
from typing import Optional, Tuple, Any, Generator, NamedTuple

from publicsuffix2 import get_sld
from urllib3.util import Url


def is_ip(string: str) -> bool:
    return re.match(
        r'^(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)$',
        string) is not None


def is_domain(string: str) -> bool:
    return not is_ip(string)


def opaque_origin(url: Url) -> str:
    """
    https://html.spec.whatwg.org/multipage/origin.html#concept-origin-opaque
    https://html.spec.whatwg.org/multipage/origin.html#ascii-serialisation-of-an-origin
    """
    if url.port is None:
        return f"{url.scheme}://{url.hostname}"
    return f"{url.scheme}://{url.hostname}:{url.port}"


class OriginTuple(NamedTuple):
    scheme: str
    host: str
    port: Optional[int]
    domain: Optional[str]


def origin_tuple(url: Url) -> OriginTuple:
    """https://html.spec.whatwg.org/multipage/origin.html#concept-origin-tuple"""
    # noinspection PyTypeChecker
    return OriginTuple(url.scheme, url.hostname, url.port, None)


def are_same_origin(a: Url, b: Url) -> bool:
    """https://html.spec.whatwg.org/multipage/origin.html#same-origin"""
    # if opaque_origin(a) == opaque_origin(b):
    #     return True
    a_tpl = origin_tuple(a)
    b_tpl = origin_tuple(b)
    return \
        a_tpl.scheme == b_tpl.scheme and \
        a_tpl.host == b_tpl.host and \
        a_tpl.port == b_tpl.port


def are_same_origin_domain(a: Url, b: Url) -> bool:
    """https://html.spec.whatwg.org/multipage/origin.html#same-origin-domain"""
    # if opaque_origin(a) == opaque_origin(b):
    #     return True
    a_tuple, b_tuple = origin_tuple(a), origin_tuple(b)
    if a_tuple[0] == b_tuple[0] and \
            a_tuple[1] is not None and \
            b_tuple[1] is not None and \
            a_tuple[1] == b_tuple[1]:
        return True
    return False


# noinspection SpellCheckingInspection
def are_schemelessly_same_site(a: Url, b: Url) -> bool:
    """https://html.spec.whatwg.org/multipage/origin.html#schemelessly-same-site"""
    # if opaque_origin(a) == opaque_origin(b):
    #     return True
    host_a, host_b = a.hostname, b.hostname
    reg_dom_a = get_sld(a.url)
    if host_a == host_b and reg_dom_a is not None:
        return True
    if reg_dom_a is not None and reg_dom_a == get_sld(b.url):
        return True
    return False


def are_same_site(a: Url, b: Url) -> bool:
    """https://html.spec.whatwg.org/multipage/origin.html#same-site"""
    return are_schemelessly_same_site(a, b) and a.scheme == b.scheme


def strip_url_for_referrer(url: Url, origin_only: bool = False) -> str:
    if url is None or url.scheme in ['about', 'blob', 'data']:
        return 'no referer'
    if origin_only:
        return Url(url.scheme, host=url.hostname, port=url.port).url
    return Url(url.scheme, host=url.hostname, port=url.port, path=url.path,
               query=url.query).url


def is_downgrade(origin: Url, target: Url) -> bool:
    return origin.scheme == 'https' and target.scheme != 'https'


class ReferrerPolicy(Enum):
    NO_REFERRER = 0
    NO_REFERRER_WHEN_DOWNGRADE = 1
    SAME_ORIGIN = 2
    ORIGIN = 3
    STRICT_ORIGIN = 4
    ORIGIN_WHEN_CROSS_ORIGIN = 5
    STRICT_ORIGIN_WHEN_CROSS_ORIGIN = 6
    UNSAFE_URL = 7

    def get_referrer(self, origin: Url, target: Url, origin_only: bool = False) -> \
            Optional[str]:
        if self == ReferrerPolicy.NO_REFERRER or origin is None:
            return None
        if self == ReferrerPolicy.NO_REFERRER_WHEN_DOWNGRADE:
            if is_downgrade(origin, target):
                return None
            return strip_url_for_referrer(origin, origin_only)
        if self == ReferrerPolicy.SAME_ORIGIN:
            if are_same_origin(origin, target):
                return strip_url_for_referrer(origin, origin_only)
            return None
        if self == ReferrerPolicy.ORIGIN:
            return strip_url_for_referrer(origin, True)
        if self == ReferrerPolicy.STRICT_ORIGIN:
            if is_downgrade(origin, target):
                return strip_url_for_referrer(origin, True)
            return None
        if self == ReferrerPolicy.ORIGIN_WHEN_CROSS_ORIGIN:
            if are_same_origin(origin, target):
                return strip_url_for_referrer(origin, origin_only)
            return strip_url_for_referrer(origin, True)
        if self == ReferrerPolicy.STRICT_ORIGIN_WHEN_CROSS_ORIGIN:
            if are_same_origin(origin, target):
                return strip_url_for_referrer(origin, origin_only)
            if is_downgrade(origin, target):
                return strip_url_for_referrer(origin, True)
            return None
        if self == ReferrerPolicy.UNSAFE_URL:
            return strip_url_for_referrer(origin, origin_only)
        raise LookupError(f"Could not look determine referrer url with {self} policy.")

    def get_origin(self, origin: Url, target: Url) -> Optional[str]:
        if self == ReferrerPolicy.NO_REFERRER or origin is None:
            return None
        if self in [
            ReferrerPolicy.NO_REFERRER_WHEN_DOWNGRADE,
            ReferrerPolicy.STRICT_ORIGIN,
            ReferrerPolicy.STRICT_ORIGIN_WHEN_CROSS_ORIGIN
        ]:
            if is_downgrade(origin, target):
                return None
        if self == ReferrerPolicy.SAME_ORIGIN:
            if not are_same_origin(origin, target):
                return None
        return strip_url_for_referrer(origin, True)


def sort_dict(d: dict, precedence: list) -> Generator[Tuple[Any, Any], Any, None]:
    items = []
    for k, v in d.items():
        try:
            item_precedence = precedence.index(k)
        except ValueError:
            # no defined sort for this header,
            # so we put it behind any other sorted header
            item_precedence = sys.maxsize
        items.append((item_precedence, k, v))
    return ((k, v) for _, k, v in sorted(items))
