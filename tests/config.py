"""Used for storing tests related data like paths for reuse"""
from os.path import dirname, abspath, join
from pathlib import Path
from typing import Tuple

print(str(Path(__file__).parent.parent))
ROOT = dirname(dirname(abspath(__file__)))


def resolve_path(path) -> str:
    if isinstance(path, str):
        return join(ROOT, path.replace('../', ''))
    elif isinstance(path, Tuple):
        return join(ROOT, *[frag for frag in path if frag != '..'])
