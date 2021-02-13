import logging
import unittest

from requests import Session
from urllib3.util import parse_url

from spoofbot.adapter import FileCacheAdapter
from tests.config import resolve_path

logging.basicConfig(level=logging.DEBUG)
logging.getLogger('urllib3.connectionpool').setLevel(logging.INFO)

DUCKDUCKGO = 'https://www.duckduckgo.com/'
DUCKDUCKGO_NO_REDIRECT = 'https://duckduckgo.com/'
HTTPBIN = 'https://httpbin.org/'
HTTPBIN_ANYTHING = f'{HTTPBIN}anything'
HTTPBIN_ANYTHING2 = f'{HTTPBIN}anything2'
HTTPBIN_HEADERS = f'{HTTPBIN}headers'


class CacheAdapterTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.cache_adapter = FileCacheAdapter(resolve_path('../../tests/adapter/.cache'))
        cls.session = Session()
        cls.session.mount('http://', cls.cache_adapter)
        cls.session.mount('https://', cls.cache_adapter)

    def test_request_hit(self):
        self.cache_adapter.use_cache = True
        self.assertIsNotNone(self.session.get(DUCKDUCKGO_NO_REDIRECT))
        self.assertIsNotNone(self.session.get(DUCKDUCKGO_NO_REDIRECT))
        self.assertTrue(self.cache_adapter.hit)

    def test_request_miss(self):
        self.cache_adapter.use_cache = True
        self.cache_adapter.delete(DUCKDUCKGO, {'Accept': 'text/html'})
        self.cache_adapter.delete(DUCKDUCKGO_NO_REDIRECT, {'Accept': 'text/html'})
        self.assertIsNotNone(self.session.get(DUCKDUCKGO_NO_REDIRECT))
        self.assertFalse(self.cache_adapter.hit)

    def test_delete(self):
        self.cache_adapter.use_cache = True
        self.session.get(HTTPBIN_ANYTHING, headers={'Accept': 'text/json'})
        self.session.get(HTTPBIN_HEADERS, headers={'Accept': 'text/json'})
        self.cache_adapter.delete(HTTPBIN_ANYTHING, headers={'Accept': 'text/json'})
        self.session.get(HTTPBIN_ANYTHING, headers={'Accept': 'text/json'})
        self.assertFalse(self.cache_adapter.hit)
        self.session.get(HTTPBIN_HEADERS, headers={'Accept': 'text/json'})
        self.assertTrue(self.cache_adapter.hit)

    def test_delete_last(self):
        self.cache_adapter.use_cache = True
        self.session.get(HTTPBIN_HEADERS, headers={'Accept': 'text/json'})
        self.cache_adapter.delete_last()
        self.session.get(HTTPBIN_HEADERS, headers={'Accept': 'text/json'})
        self.assertFalse(self.cache_adapter.hit)

    # noinspection DuplicatedCode
    def test_cache_different_path(self):
        self.cache_adapter.use_cache = True
        self.cache_adapter.delete(HTTPBIN_ANYTHING2, headers={'Accept': 'text/json'})
        self.session.get(HTTPBIN_ANYTHING, headers={'Accept': 'text/json'})
        self.assertIsNone(self.cache_adapter.next_request_cache_url)
        self.cache_adapter.next_request_cache_url = parse_url(HTTPBIN_ANYTHING2)
        self.session.get(HTTPBIN_ANYTHING, headers={'Accept': 'text/json'})
        self.assertFalse(self.cache_adapter.hit)

    # noinspection DuplicatedCode
    def test_delete_last_with_different_path(self):
        self.cache_adapter.use_cache = True
        self.cache_adapter.delete(HTTPBIN_ANYTHING2, headers={'Accept': 'text/json'})
        self.session.get(HTTPBIN_ANYTHING, headers={'Accept': 'text/json'})
        self.assertIsNone(self.cache_adapter.next_request_cache_url)
        self.cache_adapter.next_request_cache_url = parse_url(HTTPBIN_ANYTHING2)
        self.session.get(HTTPBIN_ANYTHING, headers={'Accept': 'text/json'})
        self.assertFalse(self.cache_adapter.hit)
        self.cache_adapter.delete_last()
        self.cache_adapter.next_request_cache_url = parse_url(HTTPBIN_ANYTHING2)
        self.session.get(HTTPBIN_ANYTHING, headers={'Accept': 'text/json'})
        self.assertFalse(self.cache_adapter.hit)

    def test_would_hit(self):
        self.cache_adapter.use_cache = True
        self.session.get(HTTPBIN_ANYTHING, headers={'Accept': 'text/json'})
        self.assertTrue(self.cache_adapter.would_hit(parse_url(HTTPBIN_ANYTHING), headers={'Accept': 'text/json'}))
        self.cache_adapter.delete_last()
        self.assertFalse(self.cache_adapter.would_hit(parse_url(HTTPBIN_ANYTHING), headers={'Accept': 'text/json'}))

    def test_list_cached(self):
        self.cache_adapter.use_cache = True
        self.cache_adapter.next_request_cache_url = parse_url(HTTPBIN_ANYTHING2)
        self.assertTrue(self.cache_adapter.would_hit(parse_url(HTTPBIN_ANYTHING), headers={'Accept': 'text/json'}))
        self.assertTrue(self.cache_adapter.would_hit(parse_url(HTTPBIN_ANYTHING), headers={'Accept': 'text/json'}))
        self.assertTrue(self.cache_adapter.would_hit(parse_url(HTTPBIN_HEADERS), headers={'Accept': 'text/json'}))
        self.assertSetEqual(
            {'/anything2', '/anything', '/headers'},
            set(map(lambda url: url.path, self.cache_adapter.list_cached(HTTPBIN)))
        )

    def test_backup(self):
        self.cache_adapter.use_cache = True
        self.cache_adapter.delete(HTTPBIN_ANYTHING, headers={'Accept': 'text/json'})
        self.session.get(HTTPBIN_ANYTHING, headers={'Accept': 'text/json'})
        self.cache_adapter.backup_and_miss_next_request = True
        response = self.session.get(HTTPBIN_ANYTHING, headers={'Accept': 'text/json', 'Test': 'header'})
        self.assertTrue('Test' in response.json()['headers'])
        self.cache_adapter.restore_backup()
        response = self.session.get(HTTPBIN_ANYTHING, headers={'Accept': 'text/json', 'Test': 'header'})
        self.assertFalse('Test' in response.json()['headers'])
