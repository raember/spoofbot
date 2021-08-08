import re
from email import message, parser
from io import BytesIO
from itertools import zip_longest
from os import PathLike
from pathlib import Path
from typing import Union
from urllib.parse import quote_plus, unquote_plus, parse_qsl

from loguru import logger
from requests import PreparedRequest
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

    # noinspection PyMethodMayBeStatic
    def isclosed(self):
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


CACHE_FILE_SUFFIX = '.cache'
IGNORE_QUERIES = {'_'}


def to_filepath(
        url: Union[Url, str],
        root_path: Union[str, PathLike] = Path('.'),
        ignore_queries: set[str] = None) -> Path:
    """
    Derives the filesystem filepath of a given url in the cache

    :param url: The url to convert
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
        root_path = Path(root_path)

    if ignore_queries is None:
        ignore_queries = IGNORE_QUERIES

    # Append hostname to filepath
    host = url.host + (f":{url.port}" if url.port else '')
    path = Path(root_path, host)

    # Append url filepath to file filepath
    url_path = url.path if url.path else ''
    for path_seg in url_path.strip('/').split('/'):
        # filepath /= Path(path_seg.encode('unicode_escape').decode('utf-8'))
        path /= Path(path_seg)

    # Append query to filepath
    for i, (key, val) in enumerate(parse_qsl(url.query)):
        if key in ignore_queries:
            continue
        key = quote_plus(key)
        val = quote_plus(val)
        if i == 0:  # Preserve the question mark for identifying the query in the filepath
            key = f"?{key}"
        path /= Path(f"{key}={val}")
    return path.parent / (path.name + CACHE_FILE_SUFFIX)  # Suffix minimizes clash between files and directories


def to_url(filepath: Union[str, PathLike], root_path: Union[str, PathLike] = Path('.')) -> Url:
    """
    Derives the url of a given filesystem path in the cache

    :param filepath: The path the url gets mapped to
    :type filepath: Union[str, os.PathLike]
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
    for from_part, to_part in zip_longest(from_path.parts[offset:], to_path.parts[offset:]):
        if from_part != to_part:
            divide_found = True
        if divide_found:
            if from_part is not None:
                ups.append('..')
            if to_part is not None:
                downs.append(to_part)
    return Path(*ups, *downs)


def update_cache_to_1_0_3(path: str = CACHE_FILE_SUFFIX):
    cache = Path(path)
    for host in cache.glob('*'):
        logger.info(f"Updating all cached responses of {host}")
        for cached_resp in host.glob('**/*.*'):
            if not cached_resp.is_file():
                continue
            if cached_resp.suffix == '':
                new_cached_resp = cached_resp.with_name(CACHE_FILE_SUFFIX)
            else:
                new_cached_resp = cached_resp.with_suffix(CACHE_FILE_SUFFIX)
            cached_resp.rename(new_cached_resp)


def update_cached_response_to_1_0_3(req: PreparedRequest):
    pass
