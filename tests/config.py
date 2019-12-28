"""Used for storing tests related data like paths for reuse"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_path(path: str) -> str:
    return os.path.join(ROOT, path.replace('../', ''))
