import logging
import unittest

from requests import Session

from tests.config import resolve_path
from webot.adapter import HarAdapter, load_har

logging.basicConfig(level=logging.DEBUG)


class HarProxyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.har_adapter = HarAdapter(load_har(resolve_path('../../test_data/www.wuxiaworld.com_Archive_ALL.har')))
        cls.session = Session()
        cls.session.mount('http://', cls.har_adapter)
        cls.session.mount('https://', cls.har_adapter)

    def test_hit(self):
        self.har_adapter.strict_matching = False
        self.har_adapter.delete_after_match = False
        self.assertIsNotNone(self.session.get("https://www.wuxiaworld.com/novels"))
        self.assertIsNotNone(self.session.get("https://www.wuxiaworld.com/novels"))

    def test_delete(self):
        self.har_adapter.strict_matching = False
        self.har_adapter.delete_after_match = True
        self.assertIsNotNone(self.session.get("https://www.wuxiaworld.com/profile/karma"))
        with self.assertRaises(Exception):
            self.session.get("https://www.wuxiaworld.com/profile/karma")

    def test_strict(self):
        self.har_adapter.strict_matching = True
        self.har_adapter.delete_after_match = True
        self.assertIsNotNone(self.session.get("https://www.wuxiaworld.com/", headers={
            'Host': 'www.wuxiaworld.com',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:71.0) Gecko/20100101 Firefox/71.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'TE': 'Trailers'
        }))
        with self.assertRaises(Exception):
            self.assertIsNotNone(self.session.get("https://www.wuxiaworld.com/", headers={
                'Host': 'www.wuxiaworld.com',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:71.0) Gecko/20100101 Firefox/71.0',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }))
