"""Adapters to mount on sessions"""

from .cache import CacheAdapter, MemoryCacheAdapter
from .file import FileCache, Backup
from .har import HarCache
from .mitmproxy import MitmProxyCache
