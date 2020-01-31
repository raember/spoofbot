import logging
import unittest

from requests import Session
from urllib3.util import parse_url

from spoofbot.adapter import FileCacheAdapter
from tests.config import resolve_path

logging.basicConfig(level=logging.DEBUG)


class CacheAdapterTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cache_adapter = FileCacheAdapter(resolve_path('../../tests/adapter/.cache'))
        cls.session = Session()
        cls.session.mount('http://', cls.cache_adapter)
        cls.session.mount('https://', cls.cache_adapter)

    def test_request_hit(self):
        self.cache_adapter.use_cache = True
        self.assertIsNotNone(self.session.get("https://www.duckduckgo.com/"))
        self.assertTrue(self.cache_adapter.hit)

    def test_request_miss(self):
        self.cache_adapter.use_cache = False
        self.assertIsNotNone(self.session.get("https://www.duckduckgo.com/"))
        self.assertFalse(self.cache_adapter.hit)

    def test_delete(self):
        self.cache_adapter.use_cache = True
        self.session.get("https://httpbin.org/anything", headers={'Accept': 'text/json'})
        self.session.get("https://httpbin.org/headers", headers={'Accept': 'text/json'})
        self.cache_adapter.delete("https://httpbin.org/anything", headers={'Accept': 'text/json'})
        self.session.get("https://httpbin.org/anything", headers={'Accept': 'text/json'})
        self.assertFalse(self.cache_adapter.hit)
        self.session.get("https://httpbin.org/headers", headers={'Accept': 'text/json'})
        self.assertTrue(self.cache_adapter.hit)

    def test_delete_last(self):
        self.cache_adapter.use_cache = True
        self.session.get("https://httpbin.org/headers", headers={'Accept': 'text/json'})
        self.cache_adapter.delete_last()
        self.session.get("https://httpbin.org/headers", headers={'Accept': 'text/json'})
        self.assertFalse(self.cache_adapter.hit)

    def test_cache_different_path(self):
        self.cache_adapter.use_cache = True
        self.cache_adapter.delete("https://httpbin.org/anything2", headers={'Accept': 'text/json'})
        self.session.get("https://httpbin.org/anything", headers={'Accept': 'text/json'})
        self.assertIsNone(self.cache_adapter.next_request_cache_url)
        self.cache_adapter.next_request_cache_url = parse_url("https://httpbin.org/anything2")
        self.session.get("https://httpbin.org/anything", headers={'Accept': 'text/json'})
        self.assertFalse(self.cache_adapter.hit)

    def test_delete_last_with_different_path(self):
        self.cache_adapter.use_cache = True
        self.cache_adapter.delete("https://httpbin.org/anything2", headers={'Accept': 'text/json'})
        self.session.get("https://httpbin.org/anything", headers={'Accept': 'text/json'})
        self.assertIsNone(self.cache_adapter.next_request_cache_url)
        self.cache_adapter.next_request_cache_url = parse_url("https://httpbin.org/anything2")
        self.session.get("https://httpbin.org/anything", headers={'Accept': 'text/json'})
        self.assertFalse(self.cache_adapter.hit)
        self.cache_adapter.delete_last()
        self.cache_adapter.next_request_cache_url = parse_url("https://httpbin.org/anything2")
        self.session.get("https://httpbin.org/anything", headers={'Accept': 'text/json'})
        self.assertFalse(self.cache_adapter.hit)

    def test_would_hit(self):
        self.cache_adapter.use_cache = True
        self.session.get("https://httpbin.org/anything", headers={'Accept': 'text/json'})
        self.assertTrue(self.cache_adapter.would_hit("https://httpbin.org/anything", headers={'Accept': 'text/json'}))
        self.cache_adapter.delete_last()
        self.assertFalse(self.cache_adapter.would_hit("https://httpbin.org/anything", headers={'Accept': 'text/json'}))

    def test_list_cached(self):
        self.cache_adapter.use_cache = True
        self.cache_adapter.next_request_cache_url = parse_url("https://httpbin.org/anything2")
        self.assertTrue(self.cache_adapter.would_hit("https://httpbin.org/anything", headers={'Accept': 'text/json'}))
        self.assertTrue(self.cache_adapter.would_hit("https://httpbin.org/anything", headers={'Accept': 'text/json'}))
        self.assertTrue(self.cache_adapter.would_hit("https://httpbin.org/headers", headers={'Accept': 'text/json'}))
        self.assertSetEqual(
            {'/anything2', '/anything', '/headers'},
            set(map(lambda url: url.path, self.cache_adapter.list_cached("https://httpbin.org/")))
        )
