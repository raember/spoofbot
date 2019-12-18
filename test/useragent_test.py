import unittest

# https://developers.whatismybrowser.com/useragents/explore/
from webbot.browser import Firefox, Linux, Chrome, Windows, MacOSX


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
