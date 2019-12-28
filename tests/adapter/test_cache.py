import logging
import unittest

from requests import Session

from tests.config import get_path
from webot.adapter import CacheAdapter

logging.basicConfig(level=logging.DEBUG)


class CacheAdapterTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cache_adapter = CacheAdapter(get_path('../../tests/adapter/.cache'))
        cls.session = Session()
        cls.session.mount('http://', cls.cache_adapter)
        cls.session.mount('https://', cls.cache_adapter)

    def test_request_hit(self):
        self.cache_adapter.use_cache = True
        self.assertIsNotNone(self.session.get("https://www.wuxiaworld.com/novel/heavenly-jewel-change"))
        self.assertTrue(self.cache_adapter._hit)

    def test_request_miss(self):
        self.cache_adapter.use_cache = False
        self.assertIsNotNone(self.session.get("https://www.wuxiaworld.com/novel/heavenly-jewel-change"))
        self.assertFalse(self.cache_adapter._hit)

    def test_delete(self):
        self.cache_adapter.use_cache = True
        self.session.get("https://httpbin.org/anything", headers={'Accept': 'text/json'})
        self.session.get("https://httpbin.org/anything", headers={'Accept': 'text/json'})
        self.assertTrue(self.cache_adapter._hit)
        self.session.get("https://httpbin.org/headers", headers={'Accept': 'text/json'})
        self.session.get("https://httpbin.org/headers", headers={'Accept': 'text/json'})
        self.assertTrue(self.cache_adapter._hit)
        self.cache_adapter.delete("https://httpbin.org/anything", headers={'Accept': 'text/json'})
        self.session.get("https://httpbin.org/anything", headers={'Accept': 'text/json'})
        self.assertFalse(self.cache_adapter._hit)

    def test_delete_last(self):
        self.cache_adapter.use_cache = True
        self.session.get("https://httpbin.org/anything", headers={'Accept': 'text/json'})
        self.session.get("https://httpbin.org/anything", headers={'Accept': 'text/json'})
        self.assertTrue(self.cache_adapter._hit)
        self.session.get("https://httpbin.org/headers", headers={'Accept': 'text/json'})
        self.session.get("https://httpbin.org/headers", headers={'Accept': 'text/json'})
        self.assertTrue(self.cache_adapter._hit)
        self.cache_adapter.delete_last()
        self.session.get("https://httpbin.org/headers", headers={'Accept': 'text/json'})
        self.assertFalse(self.cache_adapter._hit)
