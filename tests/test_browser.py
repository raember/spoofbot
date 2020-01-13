import json
import logging
import unittest
from io import BytesIO

import PIL
from PIL.Image import Image
from bs4 import BeautifulSoup
from bs4.element import Tag
from urllib3.util import parse_url

from spoofbot import Firefox, Chrome
from spoofbot import Windows, MacOSX, Linux
from spoofbot.adapter import load_har, HarAdapter
from spoofbot.util import encode_form_data
from tests.config import resolve_path

logging.basicConfig(level=logging.DEBUG)


class WuxiaWorldTest(unittest.TestCase):
    def test_FF(self):
        browser = Firefox()
        browser.adapter = HarAdapter(load_har(resolve_path('../test_data/www.wuxiaworld.com_Archive_ALL.har')))

        resp = browser.navigate(parse_url('http://wuxiaworld.com/'))
        self.assertEqual(200, resp.status_code)

        resp = browser.navigate(parse_url('https://www.wuxiaworld.com/account/login'))
        self.assertEqual(200, resp.status_code)

        with open(resolve_path('../test_data/ww_auth.json'), 'r') as fp:
            auth = json.load(fp)
        doc = BeautifulSoup(resp.text, features="html.parser")
        # noinspection PyTypeChecker
        rvt_input: Tag = doc.select_one('input[name="__RequestVerificationToken"]')
        data = [
            ('Email', auth['Email']),
            ('Password', auth['Password']),
            ('RememberMe', 'true'),
            ('__RequestVerificationToken', rvt_input.get('value')),
            ('RememberMe', 'false')
        ]
        resp = browser.post(parse_url('https://www.wuxiaworld.com/account/login'), headers={
            'Content-Type': 'application/x-www-form-urlencoded'
        }, data=encode_form_data(data))
        self.assertEqual(200, resp.status_code)

        resp = browser.navigate(parse_url('https://www.wuxiaworld.com/profile/karma'))
        self.assertEqual(200, resp.status_code)

        resp = browser.navigate(parse_url('https://www.wuxiaworld.com/profile/missions'))
        self.assertEqual(200, resp.status_code)

        doc = BeautifulSoup(resp.text, features="html.parser")
        # noinspection PyTypeChecker
        rvt_input: Tag = doc.select_one('input[name="__RequestVerificationToken"]')
        data = [
            ('Type', 'Login'),
            ('__RequestVerificationToken', rvt_input.get('value')),
        ]
        resp = browser.post(parse_url('https://www.wuxiaworld.com/profile/missions'), headers={
            'Content-Type': 'application/x-www-form-urlencoded'
        }, data=encode_form_data(data))
        self.assertEqual(200, resp.status_code)

        resp = browser.post(parse_url('https://www.wuxiaworld.com/account/logout'), headers={
            'Accept': 'application/json, text/plain, */*',
            'Upgrade-Insecure-Requests': None,
        }, data='')
        self.assertEqual(200, resp.status_code)

        resp = browser.navigate(parse_url('https://www.wuxiaworld.com/novels'))
        self.assertEqual(200, resp.status_code)

        resp = browser.post(parse_url('https://www.wuxiaworld.com/api/novels/search'), headers={
            'Accept': 'application/json, text/plain, */*',
            'Content-Type': 'application/json;charset=utf-8',
            'Upgrade-Insecure-Requests': None,
        }, data=json.dumps({
            "title": "",
            "tags": [],
            "genres": [],
            "active": None,
            "sortType": "Name",
            "sortAsc": True,
            "searchAfter": None,
            "count": 15
        }, separators=(',', ':')))
        self.assertEqual(200, resp.status_code)

        resp = browser.navigate(parse_url('https://www.wuxiaworld.com/novel/battle-through-the-heavens'))
        self.assertEqual(200, resp.status_code)

        resp = browser.get(
            parse_url('https://cdn.wuxiaworld.com/images/covers/btth.jpg?ver=b49ecfeb59e7f8a1e94379b5bfa58828e70883a4'),
            headers={
                'Accept': 'image/webp,*/*',
                'Upgrade-Insecure-Requests': None,
                'TE': None,
            })
        self.assertEqual(200, resp.status_code)
        img: Image = PIL.Image.open(BytesIO(resp.content))
        self.assertEqual(208, img.width)
        self.assertEqual(277, img.height)

        resp = browser.navigate(parse_url('https://www.wuxiaworld.com/novel/battle-through-the-heavens/btth-chapter-1'))
        self.assertEqual(200, resp.status_code)

        resp = browser.navigate(parse_url('https://www.wuxiaworld.com/novel/battle-through-the-heavens/btth-chapter-2'))
        self.assertEqual(200, resp.status_code)


class FirefoxUserAgentTest(unittest.TestCase):
    def test_default(self):
        self.assertEqual(
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:71.0) Gecko/20100101 Firefox/71.0',
            Firefox.create_user_agent()
        )

    def test_win(self):
        self.assertEqual(
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:71.0) Gecko/20100101 Firefox/71.0',
            Firefox.create_user_agent(Windows())
        )

    def test_mac(self):
        self.assertEqual(
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15; rv:71.0) Gecko/20100101 Firefox/71.0',
            Firefox.create_user_agent(MacOSX())
        )

    def test_linux(self):
        self.assertEqual(
            'Mozilla/5.0 (X11; Linux x86_64; rv:71.0) Gecko/20100101 Firefox/71.0',
            Firefox.create_user_agent(Linux())
        )

    def test_69_42(self):
        self.assertEqual(
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:69.42) Gecko/20100101 Firefox/69.42',
            Firefox.create_user_agent(version=(69, 42))
        )

    def test_20181001000000(self):
        self.assertEqual(
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:71.0) Gecko/20181001000000 Firefox/71.0',
            Firefox.create_user_agent(build_id=20181001000000)
        )


class ChromeUserAgentTest(unittest.TestCase):
    def test_default(self):
        self.assertEqual(
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.88 Safari/537.36',
            Chrome.create_user_agent()
        )

    def test_win(self):
        self.assertEqual(
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.88 Safari/537.36',
            Chrome.create_user_agent(Windows())
        )

    def test_mac(self):
        self.assertEqual(
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.88 Safari/537.36',
            Chrome.create_user_agent(MacOSX())
        )

    def test_linux(self):
        self.assertEqual(
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.88 Safari/537.36',
            Chrome.create_user_agent(Linux())
        )

    def test_69_42(self):
        self.assertEqual(
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/59.0.3071.115 Safari/537.36',
            Chrome.create_user_agent(version=(59, 0, 3071, 115))
        )

    def test_20181001000000(self):
        self.assertEqual(
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/536.5 (KHTML, like Gecko) Chrome/79.0.3945.88 Safari/536.5',
            Chrome.create_user_agent(webkit_version=(536, 5))
        )


if __name__ == '__main__':
    unittest.main()
