"""Common and random utilities that can be useful"""

from typing import List, Tuple, Dict
from urllib.parse import quote_plus


def encode_form_data(data: List[Tuple[str, str]]) -> str:
    """Encodes data from html forms into an escaped, url-query-like string for post messages"""
    # functional flex
    return '&'.join(map('='.join, map(lambda t: (t[0], quote_plus(t[1])), data)))


def dict_to_tuple_list(other: dict) -> List[Tuple[str, str]]:
    d = []
    for key, val in other.items():
        d.append((key, val))
    return d


def dict_list_to_dict(other: List[dict]) -> dict:
    d = {}
    for kv in other:
        d[kv['name']] = kv['value']
    return d


def cookie_header_to_dict(cookie: str) -> Dict[str, str]:
    if cookie == '':
        return {}
    return dict(map(lambda c: tuple(c.split('=')), cookie.split('; ')))
