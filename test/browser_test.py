import unittest

# https://developers.whatismybrowser.com/useragents/explore/
from webbot.browser import Firefox, Windows


class UserAgentTest(unittest.TestCase):
    def test_FF(self):
        browser = Firefox(Windows(native=False))
        self.assertEqual('Mozilla/5.0 (Windows NT 10.0; WOW64; rv:71.0) Gecko/20100101 Firefox/71.0',
                         browser.user_agent)


if __name__ == '__main__':
    unittest.main()
