import json
import logging
import unittest
from datetime import datetime
from io import BytesIO

import PIL
from PIL.Image import Image
from bs4 import BeautifulSoup
from bs4.element import Tag
from requests import Response

from spoofbot import Firefox, Chrome, MimeTypeTag
from spoofbot import Windows, MacOSX, Linux
from spoofbot.adapter import load_har, HarAdapter
from spoofbot.util import encode_form_data, TimelessRequestsCookieJar
from tests.config import resolve_path

logging.basicConfig(level=logging.DEBUG)
# noinspection SpellCheckingInspection
logging.getLogger('urllib3.connectionpool').setLevel(logging.INFO)
# noinspection SpellCheckingInspection
logging.getLogger('chardet.charsetprober').setLevel(logging.INFO)


class WuxiaWorldTest(unittest.TestCase):
    def test_FF(self):
        browser = Firefox(ff_version=(71, 0))
        browser.cookies = TimelessRequestsCookieJar(datetime(2019, 12, 21, 12, 0, 0))
        browser._accept = [
            MimeTypeTag("text", "html"),
            MimeTypeTag("application", "xhtml+xml"),
            MimeTypeTag("application", "xml", q=0.9),
            MimeTypeTag("*", "*", q=0.8)
        ]
        # browser.accept_encoding = ['gzip', 'deflate']
        adapter = HarAdapter(load_har(resolve_path('../test_data/www.wuxiaworld.com_Archive_ALL.har')))
        adapter.session = browser
        browser.mount('https://', adapter)
        browser.mount('http://', adapter)

        browser.transfer_encoding = 'Trailers'
        # browser.accept_encoding = ['gzip', 'deflate', 'br']
        resp = browser.navigate('https://www.wuxiaworld.com/')
        self.assertEqual(200, resp.status_code)

        resp = browser.navigate('https://www.wuxiaworld.com/account/login')
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
        resp = browser.post('https://www.wuxiaworld.com/account/login', headers={
            'Content-Type': 'application/x-www-form-urlencoded'
        }, data=encode_form_data(data))
        self.assertEqual(200, resp.status_code)

        resp = browser.navigate('https://www.wuxiaworld.com/profile/karma')
        self.assertEqual(200, resp.status_code)

        resp = browser.navigate('https://www.wuxiaworld.com/profile/missions')
        self.assertEqual(200, resp.status_code)

        doc = BeautifulSoup(resp.text, features="html.parser")
        # noinspection PyTypeChecker
        rvt_input: Tag = doc.select_one('input[name="__RequestVerificationToken"]')
        data = [
            ('Type', 'Login'),
            ('__RequestVerificationToken', rvt_input.get('value')),
        ]
        resp = browser.post('https://www.wuxiaworld.com/profile/missions', headers={
            'Content-Type': 'application/x-www-form-urlencoded'
        }, data=encode_form_data(data))
        self.assertEqual(200, resp.status_code)

        browser.upgrade_insecure_requests = False
        resp = browser.post('https://www.wuxiaworld.com/account/logout', headers={
            'Accept': 'application/json, text/plain, */*',
        }, data='')
        self.assertEqual(200, resp.status_code)

        browser.upgrade_insecure_requests = True
        resp = browser.navigate('https://www.wuxiaworld.com/novels')
        self.assertEqual(200, resp.status_code)

        browser.upgrade_insecure_requests = False
        resp = browser.post('https://www.wuxiaworld.com/api/novels/search', headers={
            'Accept': 'application/json, text/plain, */*',
            'Content-Type': 'application/json;charset=utf-8',
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

        browser.upgrade_insecure_requests = True
        resp = browser.navigate('https://www.wuxiaworld.com/novel/battle-through-the-heavens')
        self.assertEqual(200, resp.status_code)

        browser.upgrade_insecure_requests = False
        resp = browser.get(
            'https://cdn.wuxiaworld.com/images/covers/btth.jpg?ver=b49ecfeb59e7f8a1e94379b5bfa58828e70883a4',
            headers={
                'Accept': 'image/webp,*/*',
                'TE': None,
            })
        self.assertEqual(200, resp.status_code)
        img: Image = PIL.Image.open(BytesIO(resp.content))
        self.assertEqual(208, img.width)
        self.assertEqual(277, img.height)

        browser.upgrade_insecure_requests = True
        resp = browser.navigate('https://www.wuxiaworld.com/novel/battle-through-the-heavens/btth-chapter-1')
        self.assertEqual(200, resp.status_code)

        resp = browser.navigate('https://www.wuxiaworld.com/novel/battle-through-the-heavens/btth-chapter-2')
        self.assertEqual(200, resp.status_code)


class ChromeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.browser = Chrome()
        adapter = HarAdapter(load_har(resolve_path('test_data/chrome_full.har')))
        cls.browser.mount('https://', adapter)
        cls.browser.mount('http://', adapter)
        cls.duckduckgo_navigate = Response()
        cls.duckduckgo_navigate.url = 'https://duckduckgo.com/'
        cls.httpbin_navigate = Response()
        cls.httpbin_navigate.url = 'https://httpbin.org/'

    def test_01_duckduckgo(self):
        self.browser.transfer_encoding = None
        self.assertIsNotNone(self.browser.navigate('http://www.duckduckgo.com/'))

    def test_02_duckduckgo_search(self):
        self.browser.transfer_encoding = ''
        self.browser.connection = ''
        self.browser.upgrade_insecure_requests = False
        self.browser._last_navigate = self.duckduckgo_navigate
        headers = {
            'Accept': '*/*',
            'Host': None,
            'Sec-Fetch-Mode': 'no-cors'
        }
        self.assertIsNotNone(self.browser.get(
            'https://duckduckgo.com/ac/?callback=autocompleteCallback&q=h&kl=wt-wt&_=1579391036112',
            headers=headers
        ))
        self.assertIsNotNone(self.browser.get(
            'https://duckduckgo.com/ac/?callback=autocompleteCallback&q=ht&kl=wt-wt&_=1579391036113',
            headers=headers
        ))
        self.assertIsNotNone(self.browser.get(
            'https://duckduckgo.com/ac/?callback=autocompleteCallback&q=htt&kl=wt-wt&_=1579391036114',
            headers=headers
        ))
        self.assertIsNotNone(self.browser.get(
            'https://duckduckgo.com/ac/?callback=autocompleteCallback&q=http&kl=wt-wt&_=1579391036115',
            headers=headers
        ))
        self.assertIsNotNone(self.browser.get(
            'https://duckduckgo.com/ac/?callback=autocompleteCallback&q=httpb&kl=wt-wt&_=1579391036116',
            headers=headers
        ))
        self.assertIsNotNone(self.browser.get(
            'https://duckduckgo.com/ac/?callback=autocompleteCallback&q=httpbin&kl=wt-wt&_=1579391036117',
            headers=headers
        ))

    def test_03_duckduckgo_httpbin(self):
        self.browser.upgrade_insecure_requests = True
        self.browser.connection = ''
        self.browser._last_navigate = self.duckduckgo_navigate
        self.assertIsNotNone(self.browser.get('https://duckduckgo.com/?q=httpbin&t=h_', headers={
            'Host': None,
            'Sec-Fetch-User': '?1',
            'Sec-Fetch-Mode': 'navigate',
        }))

    def test_04_httpbin(self):
        self.browser.transfer_encoding = None
        self.browser.connection = 'keep-alive'
        self.browser.upgrade_insecure_requests = True
        self.browser._last_navigate = self.duckduckgo_navigate
        self.assertIsNotNone(self.browser.navigate('https://httpbin.org/', headers={
            'Origin': None,
            'Sec-Fetch-Site': 'cross-site',
        }))

    def test_05_httpbin_delete(self):  # Had to add Content-Length header to HAR
        self.browser.transfer_encoding = None
        self.browser.upgrade_insecure_requests = False
        self.browser._last_navigate = self.httpbin_navigate
        self.assertIsNotNone(
            self.browser.delete('https://httpbin.org/delete', headers={
                'Accept': 'application/json',
                'Sec-Fetch-Mode': 'cors',
            }))

    def test_06_httpbin_get(self):
        self.browser.transfer_encoding = None
        self.browser.upgrade_insecure_requests = False
        self.browser._last_navigate = self.httpbin_navigate
        self.assertIsNotNone(
            self.browser.get('https://httpbin.org/get', headers={
                'Accept': 'application/json',
                'Sec-Fetch-Mode': 'cors',
            }))

    def test_07_httpbin_patch(self):  # Had to add Content-Length header to HAR
        self.browser.transfer_encoding = None
        self.browser.upgrade_insecure_requests = False
        self.browser._last_navigate = self.httpbin_navigate
        self.assertIsNotNone(
            self.browser.patch('https://httpbin.org/patch', headers={'Accept': 'application/json'}))

    def test_08_httpbin_post(self):  # Had to add Content-Length header to HAR
        self.browser.transfer_encoding = None
        self.browser.upgrade_insecure_requests = False
        self.browser._last_navigate = self.httpbin_navigate
        self.assertIsNotNone(
            self.browser.post('https://httpbin.org/post', headers={'Accept': 'application/json'}))

    def test_09_httpbin_put(self):  # Had to add Content-Length header to HAR
        self.browser.transfer_encoding = None
        self.browser.upgrade_insecure_requests = False
        self.browser._last_navigate = self.httpbin_navigate
        self.assertIsNotNone(
            self.browser.put('https://httpbin.org/put', headers={'Accept': 'application/json'}))

    def test_10_httpbin_basic_auth(self):
        self.browser.transfer_encoding = None
        self.browser.upgrade_insecure_requests = False
        self.browser._last_navigate = self.httpbin_navigate
        self.assertIsNotNone(self.browser.get('https://httpbin.org/basic-auth/admin/password', headers={
            'Accept': 'application/json',
            'Sec-Fetch-Mode': 'cors',
            # 'Authorization': 'Basic YWRtaW46cGFzc3dvcmQ=',
        }))

    def test_11_httpbin_status_200(self):
        self.browser.transfer_encoding = None
        self.browser.upgrade_insecure_requests = False
        self.browser._last_navigate = self.httpbin_navigate
        response = self.browser.get('https://httpbin.org/status/200', headers={
            'Accept': 'text/plain',
            'Sec-Fetch-Mode': 'cors',
        })
        self.assertIsNotNone(response)
        self.assertEqual(200, response.status_code)

    def test_12_httpbin_status_300(self):
        self.browser.transfer_encoding = None
        self.browser.upgrade_insecure_requests = False
        self.browser._last_navigate = self.httpbin_navigate
        response = self.browser.get('https://httpbin.org/status/300', headers={
            'Accept': 'text/plain',
            'Sec-Fetch-Mode': 'cors',
        })
        self.assertIsNotNone(response)
        self.assertEqual(300, response.status_code)

    def test_13_httpbin_status_400(self):
        self.browser.transfer_encoding = None
        self.browser.upgrade_insecure_requests = False
        self.browser._last_navigate = self.httpbin_navigate
        response = self.browser.get('https://httpbin.org/status/400', headers={
            'Accept': 'text/plain',
            'Sec-Fetch-Mode': 'cors',
        })
        self.assertIsNotNone(response)
        self.assertEqual(400, response.status_code)

    def test_14_httpbin_status_500(self):
        self.browser.transfer_encoding = None
        self.browser.upgrade_insecure_requests = False
        self.browser._last_navigate = self.httpbin_navigate
        response = self.browser.get('https://httpbin.org/status/500', headers={
            'Accept': 'text/plain',
            'Sec-Fetch-Mode': 'cors',
        })
        self.assertIsNotNone(response)
        self.assertEqual(500, response.status_code)

    def test_15_httpbin_brotli(self):
        self.browser.transfer_encoding = None
        self.browser.upgrade_insecure_requests = False
        self.browser._last_navigate = self.httpbin_navigate
        response = self.browser.get('https://httpbin.org/brotli', headers={
            'Accept': 'application/json',
            'Sec-Fetch-Mode': 'cors',
        })
        self.assertIsNotNone(response)
        self.assertTrue(response.json()['brotli'])


class FirefoxTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.browser = Firefox()
        adapter = HarAdapter(load_har(resolve_path('../test_data/ff_full.har')))
        cls.browser.mount('https://', adapter)
        cls.browser.mount('http://', adapter)
        cls.duckduckgo_navigate = Response()
        cls.duckduckgo_navigate.url = 'https://duckduckgo.com/'
        cls.httpbin_navigate = Response()
        cls.httpbin_navigate.url = 'https://httpbin.org/'

    def test_01_duckduckgo(self):
        self.browser.transfer_encoding = None
        self.assertIsNotNone(self.browser.navigate('https://duckduckgo.com/'))

    def test_02_duckduckgo_search(self):
        self.browser.transfer_encoding = 'Trailers'
        self.browser.upgrade_insecure_requests = False
        self.browser._last_navigate = self.duckduckgo_navigate
        headers = {'Accept': '*/*'}
        self.assertIsNotNone(self.browser.get(
            'https://duckduckgo.com/ac/?callback=autocompleteCallback&q=h&kl=wt-wt&_=1579378231414',
            headers=headers
        ))
        self.assertIsNotNone(self.browser.get(
            'https://duckduckgo.com/ac/?callback=autocompleteCallback&q=ht&kl=wt-wt&_=1579378231415',
            headers=headers
        ))
        self.assertIsNotNone(self.browser.get(
            'https://duckduckgo.com/ac/?callback=autocompleteCallback&q=htt&kl=wt-wt&_=1579378231416',
            headers=headers
        ))
        self.assertIsNotNone(self.browser.get(
            'https://duckduckgo.com/ac/?callback=autocompleteCallback&q=http&kl=wt-wt&_=1579378231417',
            headers=headers
        ))
        self.assertIsNotNone(self.browser.get(
            'https://duckduckgo.com/ac/?callback=autocompleteCallback&q=httpb&kl=wt-wt&_=1579378231418',
            headers=headers
        ))
        self.assertIsNotNone(self.browser.get(
            'https://duckduckgo.com/ac/?callback=autocompleteCallback&q=httpbin&kl=wt-wt&_=1579378231419',
            headers=headers
        ))

    def test_03_duckduckgo_httpbin(self):
        self.browser.upgrade_insecure_requests = True
        self.browser._last_navigate = self.duckduckgo_navigate
        self.assertIsNotNone(self.browser.get('https://duckduckgo.com/?q=httpbin&t=h_'))

    def test_04_httpbin(self):
        self.browser.transfer_encoding = None
        self.browser.upgrade_insecure_requests = True
        self.browser._last_navigate = self.duckduckgo_navigate
        self.assertIsNotNone(self.browser.navigate('https://httpbin.org/', headers={'Origin': None}))

    def test_05_httpbin_delete(self):  # Had to add Content-Length header to HAR
        self.browser.transfer_encoding = None
        self.browser.upgrade_insecure_requests = False
        self.browser._last_navigate = self.httpbin_navigate
        self.assertIsNotNone(
            self.browser.delete('https://httpbin.org/delete', headers={'Accept': 'application/json'}))

    def test_06_httpbin_get(self):
        self.browser.transfer_encoding = None
        self.browser.upgrade_insecure_requests = False
        self.browser._last_navigate = self.httpbin_navigate
        self.assertIsNotNone(
            self.browser.get('https://httpbin.org/get', headers={'Accept': 'application/json'}))

    def test_07_httpbin_patch(self):  # Had to add Content-Length header to HAR
        self.browser.transfer_encoding = None
        self.browser.upgrade_insecure_requests = False
        self.browser._last_navigate = self.httpbin_navigate
        self.assertIsNotNone(
            self.browser.patch('https://httpbin.org/patch', headers={'Accept': 'application/json'}))

    def test_08_httpbin_post(self):  # Had to add Content-Length header to HAR
        self.browser.transfer_encoding = None
        self.browser.upgrade_insecure_requests = False
        self.browser._last_navigate = self.httpbin_navigate
        self.assertIsNotNone(
            self.browser.post('https://httpbin.org/post', headers={'Accept': 'application/json'}))

    def test_09_httpbin_put(self):  # Had to add Content-Length header to HAR
        self.browser.transfer_encoding = None
        self.browser.upgrade_insecure_requests = False
        self.browser._last_navigate = self.httpbin_navigate
        self.assertIsNotNone(
            self.browser.put('https://httpbin.org/put', headers={'Accept': 'application/json'}))

    def test_10_httpbin_basic_auth(self):
        self.browser.transfer_encoding = None
        self.browser.upgrade_insecure_requests = False
        self.browser._last_navigate = self.httpbin_navigate
        self.assertIsNotNone(self.browser.get('https://httpbin.org/basic-auth/admin/password', headers={
            'Accept': 'application/json',
            'Authorization': 'Basic YWRtaW46cGFzc3dvcmQ=',
        }))

    def test_11_httpbin_status_200(self):
        self.browser.transfer_encoding = None
        self.browser.upgrade_insecure_requests = False
        self.browser._last_navigate = self.httpbin_navigate
        response = self.browser.get('https://httpbin.org/status/200', headers={'Accept': 'text/plain'})
        self.assertIsNotNone(response)
        self.assertEqual(200, response.status_code)

    def test_12_httpbin_status_300(self):
        self.browser.transfer_encoding = None
        self.browser.upgrade_insecure_requests = False
        self.browser._last_navigate = self.httpbin_navigate
        response = self.browser.get('https://httpbin.org/status/300', headers={'Accept': 'text/plain'})
        self.assertIsNotNone(response)
        self.assertEqual(300, response.status_code)

    def test_13_httpbin_status_400(self):
        self.browser.transfer_encoding = None
        self.browser.upgrade_insecure_requests = False
        self.browser._last_navigate = self.httpbin_navigate
        response = self.browser.get('https://httpbin.org/status/400', headers={'Accept': 'text/plain'})
        self.assertIsNotNone(response)
        self.assertEqual(400, response.status_code)

    def test_14_httpbin_status_500(self):
        self.browser.transfer_encoding = None
        self.browser.upgrade_insecure_requests = False
        self.browser._last_navigate = self.httpbin_navigate
        response = self.browser.get('https://httpbin.org/status/500', headers={'Accept': 'text/plain'})
        self.assertIsNotNone(response)
        self.assertEqual(500, response.status_code)

    def test_15_httpbin_brotli(self):
        self.browser.transfer_encoding = None
        self.browser.upgrade_insecure_requests = False
        self.browser._last_navigate = self.httpbin_navigate
        response = self.browser.get('https://httpbin.org/brotli', headers={'Accept': 'application/json'})
        self.assertIsNotNone(response)
        self.assertTrue(response.json()['brotli'])


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
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.130 Safari/537.36',
            Chrome.create_user_agent()
        )

    def test_win(self):
        self.assertEqual(
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.130 Safari/537.36',
            Chrome.create_user_agent(Windows())
        )

    def test_mac(self):
        self.assertEqual(
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.130 Safari/537.36',
            Chrome.create_user_agent(MacOSX())
        )

    def test_linux(self):
        self.assertEqual(
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.130 Safari/537.36',
            Chrome.create_user_agent(Linux())
        )

    def test_69_42(self):
        self.assertEqual(
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/59.0.3071.115 Safari/537.36',
            Chrome.create_user_agent(version=(59, 0, 3071, 115))
        )

    def test_20181001000000(self):
        self.assertEqual(
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/536.5 (KHTML, like Gecko) Chrome/79.0.3945.130 Safari/536.5',
            Chrome.create_user_agent(webkit_version=(536, 5))
        )


if __name__ == '__main__':
    unittest.main()
