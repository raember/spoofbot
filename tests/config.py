"""Used for storing tests related data like paths for reuse"""
from os.path import dirname, abspath, join
from typing import Tuple

ROOT = dirname(dirname(abspath(__file__)))


def resolve_path(path) -> str:
    if isinstance(path, str):
        return join(ROOT, path.replace('../', ''))
    elif isinstance(path, Tuple):
        return join(ROOT, *[frag for frag in path if frag != '..'])
