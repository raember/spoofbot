"""Common and random utilities that can be useful"""

from typing import List, Tuple
from urllib.parse import quote_plus


def encode_form_data(data: List[Tuple[str, str]]) -> str:
    """Encodes data from html forms into an escaped, url-query-like string for post messages"""
    # functional flex
    return '&'.join(map('='.join, map(lambda t: (t[0], quote_plus(t[1])), data)))
