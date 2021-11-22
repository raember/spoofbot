import re
from email import message, parser
from io import BytesIO
from itertools import zip_longest
from os import PathLike
from pathlib import Path
from typing import Union
from urllib.parse import quote_plus, unquote_plus, parse_qsl

from urllib3 import HTTPResponse
from urllib3.util import Url, parse_url

from spoofbot.util.common import coerce_content


class EmailMessage(message.Message):
    def getheaders(self, value, *args):
        # noinspection PyArgumentList
        return re.split(b', ', self.get(value, b'', *args))


class MockHTTPResponse:
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

    @staticmethod
    def isclosed():
        return False


def load_response(filepath: Path) -> HTTPResponse:
    with open(filepath, 'rb') as fp:
        text = fp.read()
    # body = text.encode('utf-8')
    return HTTPResponse(
        body=BytesIO(text),
        headers={},
        status=200,
        preload_content=False,
        original_response=MockHTTPResponse({})
    )


CACHE_DEFAULT_PATH = '.cache'
CACHE_FILE_SUFFIX = '.cache'
DEFAULT_CACHEABLE_STATUSES = {200, 201, 300, 301, 302, 303, 307, 308}
IGNORE_QUERIES = {'_'}


def to_filepath(
        url: Union[Url, str],
        root_path: Union[str, PathLike] = CACHE_DEFAULT_PATH,
        ignore_queries: set[str] = None) -> Path:
    """
    Maps the given url to a file path in the cache.

    :param url: The url to map
    :type url: Union[Url, str]
    :param root_path: The base path
    :type root_path: Union[str, PathLike]
    :param ignore_queries: The queries to ignore. Defaults to IGNORE_QUERIES={'_'}
    :type ignore_queries: set[str]
    :return: The filepath the url gets mapped to
    :rtype: Path
    """
    # Make sure we have a proper URL
    if isinstance(url, str):
        url = parse_url(url)

    # Make sure we have a proper root path
    if isinstance(root_path, str):
        path = Path(root_path)
    else:
        path = root_path

    if ignore_queries is None:
        ignore_queries = IGNORE_QUERIES

    # Append hostname to filepath
    host = url.host + (f":{url.port}" if url.port else '')
    path /= host

    # Append url filepath to file filepath
    if url.path:
        path /= url.path.strip('/')

    # Append query to filepath
    for i, (key, val) in enumerate(parse_qsl(url.query)):
        ignore = False
        for pattern in ignore_queries:
            if re.match(pattern, key) is not None:
                ignore = True
        if ignore:
            continue
        key = quote_plus(key)
        val = quote_plus(val)
        if i == 0:
            # Preserve the question mark for identifying the query in the filepath
            key = f"?{key}"
        path /= f"{key}={val}"
    # Suffix minimizes clash between files and directories
    return path.parent / (path.name + CACHE_FILE_SUFFIX)


def to_url(filepath: Union[str, PathLike],
           root_path: Union[str, PathLike] = CACHE_DEFAULT_PATH) -> Url:
    """
    Derives the url of a given filesystem path in the cache

    :param filepath: The path the url gets mapped to
    :type filepath: Union[str, PathLike]
    :param root_path: The base path
    :type root_path: Union[str, PathLike]
    :return: The Url that would cause a hit in the cache using the given path.
    :rtype: Url
    """
    # Make sure we have a proper filepath
    if isinstance(filepath, str):
        filepath = Path(filepath)

    # Make sure we have a proper root path
    if isinstance(root_path, str):
        root_path = Path(root_path)

    # All cache files need the CACHE_FILE_SUFFIX
    assert filepath.suffix == CACHE_FILE_SUFFIX

    host = filepath.parts[len(root_path.parts)]
    paths = []
    query = None
    removed_suffix = False
    for part in reversed(filepath.parts[(len(root_path.parts) + 1):]):
        if not removed_suffix:
            assert part.endswith(CACHE_FILE_SUFFIX)
            part = part[:-(len(CACHE_FILE_SUFFIX))]
            removed_suffix = True
        paths.append(part)
        if part.startswith('?'):  # All parts up until now were part of the query
            queries = []
            for query_part in reversed(paths):
                queries.append(unquote_plus(query_part))
            query = '&'.join(queries)[1:]
            paths.clear()
    return Url('https', host=host, path='/'.join(paths), query=query)


def get_symlink_path(from_path: Path, to_path: Path, root: Path) -> Path:
    """
    Get the relative path from one path to another using path traversal for symlinking.

    :param from_path: The path of the symlink
    :type from_path: Path
    :param to_path: The path of the target of the symlink
    :type to_path: Path
    :param root: The shared root path
    :type root: Path
    :return: The relative path possibly using path traversal
    """
    if not from_path.is_relative_to(root):
        raise ValueError(f"{from_path} is not a subdir of {root}")
    if not to_path.is_relative_to(root):
        raise ValueError(f"{to_path} is not a subdir of {root}")
    from_path = from_path.parent
    offset = max(0, len(root.parts) - 1)
    ups = []
    downs = []
    divide_found = False
    for from_part, to_part in zip_longest(from_path.parts[offset:],
                                          to_path.parts[offset:]):
        if from_part != to_part:
            divide_found = True
        if divide_found:
            if from_part is not None:
                ups.append('..')
            if to_part is not None:
                downs.append(to_part)
    return Path(*ups, *downs)
