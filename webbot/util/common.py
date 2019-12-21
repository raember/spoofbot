from typing import List, Tuple
from urllib.parse import quote_plus


def encode_form_data(data: List[Tuple[str, str]]) -> str:
    # functional flex
    return '&'.join(map('='.join, map(lambda t: (t[0], quote_plus(t[1])), data)))
