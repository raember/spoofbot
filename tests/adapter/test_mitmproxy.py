import unittest

from requests import Session

from adapter import p
from spoofbot.adapter import MitmProxyCache
from spoofbot.util import load_flows


class MITMProxyTest(unittest.TestCase):
    session: Session = None
    adapter: MitmProxyCache = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.adapter = MitmProxyCache(
            load_flows(p / 'test_data/www.wuxiaworld.com_mitmproxy.flows'),
            match_headers=False,
            match_header_order=False,
            match_data=False,
        )
        cls.session = cls.adapter.session
        cls.session.mount('http://', cls.adapter)
        cls.session.mount('https://', cls.adapter)

    def test_hit(self):
        self.adapter.delete_after_hit = False
        self.assertIsNotNone(self.session.get("https://www.wuxiaworld.com"))
        self.assertIsNotNone(self.session.get("https://www.wuxiaworld.com"))

    def test_delete(self):
        self.adapter.delete_after_hit = True
        self.assertIsNotNone(self.session.get("https://www.wuxiaworld.com/novels"))
        with self.assertRaises(Exception):
            self.session.get("https://www.wuxiaworld.com/novels")

    def test_strict(self):
        self.adapter.match_headers = True
        self.adapter.match_header_order = True
        self.adapter.match_data = True
        self.adapter.delete_after_hit = False
        self.assertIsNotNone(self.session.get("https://www.wuxiaworld.com/", headers={
            # 'Host': 'www.wuxiaworld.com',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            # 'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'none',
            'sec-fetch-user': '?1',
            'TE': 'trailers',
        }))
        with self.assertRaises(Exception):
            self.assertIsNotNone(
                self.session.get("https://www.wuxiaworld.com/", headers={
                    'Host': 'www.wuxiaworld.com',
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:71.0) Gecko/20100101 Firefox/71.0',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1'
                }))
