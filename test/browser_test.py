import json
import logging
import unittest
# https://developers.whatismybrowser.com/useragents/explore/
from io import BytesIO

import PIL
from PIL.Image import Image
from bs4 import BeautifulSoup, Tag

from webbot import Firefox
from webbot.util import encode_form_data, load_har, HarAdapter

logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(name)18s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    level=logging.DEBUG
)


class WuxiaWorldTest(unittest.TestCase):
    def test_FF(self):
        browser = Firefox()
        har_adapter = HarAdapter(load_har('../test_data/www.wuxiaworld.com_Archive_ALL.har'))
        browser.session.mount('http://', har_adapter)
        browser.session.mount('https://', har_adapter)

        resp = browser.navigate('http://wuxiaworld.com/')
        self.assertEqual(200, resp.status_code)
        print(f"### {resp.url}")

        resp = browser.navigate('https://www.wuxiaworld.com/account/login')
        self.assertEqual(200, resp.status_code)
        print(f"### {resp.url}")

        with open('../test_data/ww_auth.json', 'r') as fp:
            auth = json.load(fp)
        doc = BeautifulSoup(resp.text, features="html.parser")
        rvt_input: Tag = doc.select_one('input[name="__RequestVerificationToken"]')
        data = [
            ('Email', auth['Email']),
            ('Password', auth['Password']),
            ('RememberMe', 'true'),
            ('__RequestVerificationToken', rvt_input.get('value')),
            ('RememberMe', 'false')
        ]
        resp = browser.post('https://www.wuxiaworld.com/account/login', headers={
            'Content-Type': 'application/x-www-form-urlencoded'
        }, data=encode_form_data(data))
        self.assertEqual(200, resp.status_code)
        print(f"### {resp.url}")

        resp = browser.navigate('https://www.wuxiaworld.com/profile/karma')
        self.assertEqual(200, resp.status_code)
        print(f"### {resp.url}")

        resp = browser.navigate('https://www.wuxiaworld.com/profile/missions')
        self.assertEqual(200, resp.status_code)
        print(f"### {resp.url}")

        doc = BeautifulSoup(resp.text, features="html.parser")
        rvt_input: Tag = doc.select_one('input[name="__RequestVerificationToken"]')
        data = [
            ('Type', 'Login'),
            ('__RequestVerificationToken', rvt_input.get('value')),
        ]
        resp = browser.post('https://www.wuxiaworld.com/profile/missions', headers={
            'Content-Type': 'application/x-www-form-urlencoded'
        }, data=encode_form_data(data))
        self.assertEqual(200, resp.status_code)
        print(f"### {resp.url}")

        resp = browser.post('https://www.wuxiaworld.com/account/logout', headers={
            'Accept': 'application/json, text/plain, */*',
            'Upgrade-Insecure-Requests': None,
        }, data='')
        self.assertEqual(200, resp.status_code)
        print(f"### {resp.url}")

        resp = browser.navigate('https://www.wuxiaworld.com/novels')
        self.assertEqual(200, resp.status_code)
        print(f"### {resp.url}")

        resp = browser.post('https://www.wuxiaworld.com/api/novels/search', headers={
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
        print(f"### {resp.url}")

        resp = browser.navigate('https://www.wuxiaworld.com/novel/battle-through-the-heavens')
        self.assertEqual(200, resp.status_code)
        print(f"### {resp.url}")

        resp = browser.get(
            'https://cdn.wuxiaworld.com/images/covers/btth.jpg?ver=b49ecfeb59e7f8a1e94379b5bfa58828e70883a4', headers={
                'Accept': 'image/webp,*/*',
                'Upgrade-Insecure-Requests': None,
                'TE': None,
            })
        self.assertEqual(200, resp.status_code)
        print(f"### {resp.url}")
        img: Image = PIL.Image.open(BytesIO(resp.content))
        self.assertEqual(208, img.width)
        self.assertEqual(277, img.height)

        resp = browser.navigate('https://www.wuxiaworld.com/novel/battle-through-the-heavens/btth-chapter-1')
        self.assertEqual(200, resp.status_code)
        print(f"### {resp.url}")

        resp = browser.navigate('https://www.wuxiaworld.com/novel/battle-through-the-heavens/btth-chapter-2')
        self.assertEqual(200, resp.status_code)
        print(f"### {resp.url}")


if __name__ == '__main__':
    unittest.main()
