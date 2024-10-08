import logging
import shutil
import unittest
from pathlib import Path
from typing import Tuple

from requests import Session
from urllib3.util import parse_url

from spoofbot import Browser, Firefox
from spoofbot.adapter.file import FileCache
from spoofbot.util import to_filepath

logging.basicConfig(level=logging.DEBUG)
logging.getLogger('urllib3.connectionpool').setLevel(logging.INFO)

DUCKDUCKGO = parse_url('https://www.duckduckgo.com/')
DUCKDUCKGO_NO_REDIRECT = parse_url('https://duckduckgo.com/')
HTTPBIN = parse_url('https://httpbin.org/')
HTTPBIN_ANYTHING = parse_url('https://httpbin.org/anything')
HTTPBIN_ANYTHING2 = parse_url('https://httpbin.org/anything2')
HTTPBIN_HEADERS = parse_url('https://httpbin.org/headers')


def prepare_cache(use: str) -> Tuple[Session, FileCache]:
    d = Path(__file__).parent / f".cache_{use}"
    if d.is_dir():
        shutil.rmtree(d)
    fc = FileCache(d)
    s = Firefox()
    s.adapter = fc
    return s, fc


class FileCacheTest(unittest.TestCase):
    cache_adapter: FileCache = None
    session: Browser = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.session, cls.cache_adapter = prepare_cache('file_cache_test')

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.cache_adapter.cache_path)

    def test_request_hit(self):
        # Preparation
        self.cache_adapter.is_active = True
        self.cache_adapter.is_passive = True
        self.cache_adapter.is_offline = False
        self.cache_adapter.delete(DUCKDUCKGO_NO_REDIRECT)

        self.assertIsNotNone(self.session.get(DUCKDUCKGO_NO_REDIRECT))
        self.assertFalse(self.cache_adapter.hit)

        # If we request the same url twice, the second time is bound to be a hit
        self.assertIsNotNone(self.session.get(DUCKDUCKGO_NO_REDIRECT))
        self.assertTrue(self.cache_adapter.hit)

    def test_request_miss(self):
        # Preparation
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
        ctx = self.cache_adapter.backup()
        backup = ctx.__enter__()
        self.assertEqual(backup, self.cache_adapter.backup_data[-1])
        self.assertEqual(0, len(backup.requests))
        self.assertIsNotNone(self.session.get(DUCKDUCKGO_NO_REDIRECT))
        self.assertFalse(self.cache_adapter.hit)
        self.assertEqual(1, len(backup.requests))
        self.assertIsNotNone(self.session.get(DUCKDUCKGO_NO_REDIRECT))
        self.assertFalse(self.cache_adapter.hit)
        self.assertEqual(2, len(backup.requests))
        self.assertEqual(DUCKDUCKGO_NO_REDIRECT.url, backup.requests[0][0].url)
        self.assertTrue(backup.requests[1][1].startswith(b'<!DOCTYPE html>'))
        ctx.__exit__(None, None, None)
        self.assertEqual(0, len(self.cache_adapter.backup_data))

    def test_request_backup_with(self):
        self.cache_adapter.is_active = False
        self.cache_adapter.is_passive = True
        self.cache_adapter.is_offline = False
        self.cache_adapter.delete(DUCKDUCKGO_NO_REDIRECT)
        self.assertEqual(0, len(self.cache_adapter.backup_data))

        # If we have a response cached already, but bypass the cache to request data from the remote,
        # we expect the cache to create a backup of the original cached response.
        with self.cache_adapter.backup() as backup:
            self.assertEqual(backup, self.cache_adapter.backup_data[-1])
            self.assertEqual(0, len(backup.requests))
            self.assertIsNotNone(self.session.get(DUCKDUCKGO_NO_REDIRECT))
            self.assertFalse(self.cache_adapter.hit)
            self.assertEqual(1, len(backup.requests))
            self.assertIsNotNone(self.session.get(DUCKDUCKGO_NO_REDIRECT))
            self.assertFalse(self.cache_adapter.hit)
            self.assertEqual(2, len(backup.requests))
            self.assertEqual(DUCKDUCKGO_NO_REDIRECT.url, backup.requests[0][0].url)
            self.assertTrue(backup.requests[1][1].startswith(b'<!DOCTYPE html>'))
        self.assertEqual(0, len(self.cache_adapter.backup_data))

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
        resp = self.session.get(HTTPBIN_HEADERS, headers={'Accept': 'text/json'})
        # If we delete the last response cached, a new request to that url will be a miss
        to_filepath(HTTPBIN_HEADERS, self.cache_adapter.cache_path, self.cache_adapter.ignore_queries).unlink()
        self.session.get(HTTPBIN_HEADERS, headers={'Accept': 'text/json'})
        self.assertFalse(self.cache_adapter.hit)

    def test_would_hit(self):
        self.cache_adapter.is_active = True
        self.cache_adapter.is_passive = True
        self.cache_adapter.is_offline = False
        resp = self.session.get(HTTPBIN_ANYTHING, headers={'Accept': 'text/json'})
        # If we check for a cached response that we requested earlier, it will show as a hit, unless deleted
        self.assertTrue(self.cache_adapter.is_hit(HTTPBIN_ANYTHING))
        to_filepath(HTTPBIN_ANYTHING, self.cache_adapter.cache_path, self.cache_adapter.ignore_queries).unlink()
        self.assertFalse(self.cache_adapter.is_hit(HTTPBIN_ANYTHING))

    def test_with_mode(self):
        self.cache_adapter.is_active = True
        self.cache_adapter.is_passive = True
        self.cache_adapter.is_offline = False
        with self.cache_adapter.use_mode(True, False, False):
            self.assertTrue(self.cache_adapter.is_active)
            self.assertFalse(self.cache_adapter.is_passive)
            self.assertFalse(self.cache_adapter.is_offline)
            with self.cache_adapter.use_mode(True, False, True):
                self.assertTrue(self.cache_adapter.is_active)
                self.assertFalse(self.cache_adapter.is_passive)
                self.assertTrue(self.cache_adapter.is_offline)
            self.assertTrue(self.cache_adapter.is_active)
            self.assertFalse(self.cache_adapter.is_passive)
            self.assertFalse(self.cache_adapter.is_offline)
        self.assertTrue(self.cache_adapter.is_active)
        self.assertTrue(self.cache_adapter.is_passive)
        self.assertFalse(self.cache_adapter.is_offline)

    def test_with_mode2(self):
        self.cache_adapter.is_active = True
        self.cache_adapter.is_passive = True
        self.cache_adapter.is_offline = False
        with self.session.use_mode(True, False, False):
            self.assertTrue(self.cache_adapter.is_active)
            self.assertFalse(self.cache_adapter.is_passive)
            self.assertFalse(self.cache_adapter.is_offline)
            with self.session.use_mode(True, False, True):
                self.assertTrue(self.cache_adapter.is_active)
                self.assertFalse(self.cache_adapter.is_passive)
                self.assertTrue(self.cache_adapter.is_offline)
            self.assertTrue(self.cache_adapter.is_active)
            self.assertFalse(self.cache_adapter.is_passive)
            self.assertFalse(self.cache_adapter.is_offline)
        self.assertTrue(self.cache_adapter.is_active)
        self.assertTrue(self.cache_adapter.is_passive)
        self.assertFalse(self.cache_adapter.is_offline)
