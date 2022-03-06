import unittest

from requests import Session

from spoofbot.adapter import HarCache


class HarProxyTest(unittest.TestCase):
    session: Session = None
    adapter: HarCache = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.adapter = HarCache(
            p / 'test_data/www.wuxiaworld.com_Archive_ALL.har',
            match_headers=False,
            match_header_order=False,
            match_data=False,
        )
        cls.adapter.is_offline = True
        cls.session = Session()
        cls.session.mount('http://', cls.adapter)
        cls.session.mount('https://', cls.adapter)

    def test_hit(self):
        self.adapter.delete_after_hit = False
        self.assertIsNotNone(self.session.get("https://www.wuxiaworld.com/novels"))
        self.assertIsNotNone(self.session.get("https://www.wuxiaworld.com/novels"))

    def test_delete(self):
        self.assertIsNotNone(
            self.session.get("https://www.wuxiaworld.com/profile/karma"))
        self.adapter.delete_after_hit = True
        self.assertIsNotNone(
            self.session.get("https://www.wuxiaworld.com/profile/karma"))
        with self.assertRaises(Exception):
            self.session.get("https://www.wuxiaworld.com/profile/karma")

    def test_strict(self):
        self.adapter.match_headers = True
        self.adapter.match_header_order = False
        self.adapter.match_data = True
        self.adapter.delete_after_hit = True
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
