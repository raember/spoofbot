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

    def test_request_hit(self):
        self.cache_adapter.is_active = True
        self.cache_adapter.is_passive = True
        self.cache_adapter.is_offline = False

        # If we request the same url twice, the second time is bound to be a hit
        self.assertIsNotNone(self.session.get(DUCKDUCKGO_NO_REDIRECT))
        self.assertIsNotNone(self.session.get(DUCKDUCKGO_NO_REDIRECT))
        self.assertTrue(self.cache_adapter.hit)

    def test_request_miss(self):
        self.cache_adapter.is_active = True
        self.cache_adapter.is_passive = True
        self.cache_adapter.is_offline = False
        self.cache_adapter.delete(DUCKDUCKGO_NO_REDIRECT)

        # If we request a url that is not cached, it won't be a hit
        self.assertIsNotNone(self.session.get(DUCKDUCKGO_NO_REDIRECT))
        self.assertFalse(self.cache_adapter.hit)

    def test_request_backup(self):
        self.cache_adapter.is_active = False
        self.cache_adapter.is_passive = True
        self.cache_adapter.is_offline = False
        self.cache_adapter.delete(DUCKDUCKGO_NO_REDIRECT)

        # If we have a response cached already, but bypass the cache to request data from the remote,
        # we expect the cache to create a backup of the original cached response.
        self.assertIsNotNone(self.session.get(DUCKDUCKGO_NO_REDIRECT))
        self.assertFalse(self.cache_adapter.hit)
        backups = self.cache_adapter.backups
        self.assertEqual(0, len(backups))
        self.assertIsNotNone(self.session.get(DUCKDUCKGO_NO_REDIRECT))
        self.assertFalse(self.cache_adapter.hit)
        self.assertEqual(1, len(backups))
        self.assertEqual(DUCKDUCKGO_NO_REDIRECT.url, list(backups.keys())[0].url)
        self.assertTrue(list(backups.values())[0].startswith(b'<!DOCTYPE html>'))

    def test_delete(self):
        self.cache_adapter.is_active = True
        self.cache_adapter.is_passive = True
        self.cache_adapter.is_offline = False
        self.session.get(HTTPBIN_ANYTHING, headers={'Accept': 'text/json'})
        # If we have cached responses, after deleting them and requesting the same url, it will be a miss
        self.cache_adapter.delete(HTTPBIN_ANYTHING)
        self.session.get(HTTPBIN_ANYTHING, headers={'Accept': 'text/json'})
        self.assertFalse(self.cache_adapter.hit)

    def test_delete_last(self):
        self.cache_adapter.is_active = True
        self.cache_adapter.is_passive = True
        self.cache_adapter.is_offline = False
        self.session.get(HTTPBIN_HEADERS, headers={'Accept': 'text/json'})
        # If we delete the last response cached, a new request to that url will be a miss
        self.cache_adapter.delete_last()
        self.session.get(HTTPBIN_HEADERS, headers={'Accept': 'text/json'})
        self.assertFalse(self.cache_adapter.hit)

    def test_would_hit(self):
        self.cache_adapter.is_active = True
        self.cache_adapter.is_passive = True
        self.cache_adapter.is_offline = False
        self.session.get(HTTPBIN_ANYTHING, headers={'Accept': 'text/json'})
        # If we check for a cached response that we requested earlier, it will show as a hit, unless deleted
        self.assertTrue(self.cache_adapter.is_hit(HTTPBIN_ANYTHING))
        self.cache_adapter.delete_last()
        self.assertFalse(self.cache_adapter.is_hit(HTTPBIN_ANYTHING))
