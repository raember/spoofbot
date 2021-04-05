import logging
import unittest

from requests import Session
from urllib3.util import parse_url

from config import resolve_path
from spoofbot.adapter import FileCache

logging.basicConfig(level=logging.DEBUG)
logging.getLogger('urllib3.connectionpool').setLevel(logging.INFO)

DUCKDUCKGO = parse_url('https://www.duckduckgo.com/')
DUCKDUCKGO_NO_REDIRECT = parse_url('https://duckduckgo.com/')
HTTPBIN = parse_url('https://httpbin.org/')
HTTPBIN_ANYTHING = parse_url('https://httpbin.org/anything')
HTTPBIN_ANYTHING2 = parse_url('https://httpbin.org/anything2')
HTTPBIN_HEADERS = parse_url('https://httpbin.org/headers')


class CacheAdapterTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.cache_adapter = FileCache(resolve_path('../../tests/adapter/.cache'))
        cls.session = Session()
        cls.session.mount('http://', cls.cache_adapter)
        cls.session.mount('https://', cls.cache_adapter)

    def test_url_to_path(self):
        url = 'https://example.com:443/app=/?var=\\some /val&key=ä'
        path = '.cache/example.com:443/app=/?var=%5Csome+%2Fval/key=%C3%A4'
        cache = FileCache('.cache')
        self.assertEqual(path, str(cache.to_filepath(url)))

    def test_path_to_url(self):
        url = 'https://example.com:443/app=?var=\\some /val&key=ä'
        path = '.cache/example.com:443/app=/?var=%5Csome+%2Fval/key=%C3%A4'
        cache = FileCache('.cache')
        self.assertEqual(url, cache.to_url(path).url)

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
        self.cache_adapter.next_request_cache_url = HTTPBIN_ANYTHING2
        self.session.get(HTTPBIN_ANYTHING, headers={'Accept': 'text/json'})
        self.assertFalse(self.cache_adapter.hit)

    # noinspection DuplicatedCode
    def test_delete_last_with_different_path(self):
        self.cache_adapter.use_cache = True
        self.cache_adapter.delete(HTTPBIN_ANYTHING2, headers={'Accept': 'text/json'})
        self.session.get(HTTPBIN_ANYTHING, headers={'Accept': 'text/json'})
        self.assertIsNone(self.cache_adapter.next_request_cache_url)
        self.cache_adapter.next_request_cache_url = HTTPBIN_ANYTHING2
        self.session.get(HTTPBIN_ANYTHING, headers={'Accept': 'text/json'})
        self.assertFalse(self.cache_adapter.hit)
        self.cache_adapter.delete_last()
        self.cache_adapter.next_request_cache_url = HTTPBIN_ANYTHING2
        self.session.get(HTTPBIN_ANYTHING, headers={'Accept': 'text/json'})
        self.assertFalse(self.cache_adapter.hit)

    def test_would_hit(self):
        self.cache_adapter.use_cache = True
        self.session.get(HTTPBIN_ANYTHING, headers={'Accept': 'text/json'})
        self.assertTrue(self.cache_adapter.would_hit(HTTPBIN_ANYTHING, headers={'Accept': 'text/json'}))
        self.cache_adapter.delete_last()
        self.assertFalse(self.cache_adapter.would_hit(HTTPBIN_ANYTHING, headers={'Accept': 'text/json'}))

    def test_list_cached(self):
        self.cache_adapter.use_cache = True
        # self.cache_adapter.next_request_cache_url = HTTPBIN_ANYTHING2
        # self.cache_adapter.next_request_cache_url = None
        self.session.get(HTTPBIN_ANYTHING, headers={'Accept': 'text/json'})
        self.session.get(HTTPBIN_HEADERS, headers={'Accept': 'text/json'})
        print(self.cache_adapter.list_cached(parse_url('https://httpbin.org')))
        self.assertSetEqual(
            {'/anything', '/headers'},
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
