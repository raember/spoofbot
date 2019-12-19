import unittest

# https://developers.whatismybrowser.com/useragents/explore/
from webbot.browser import Firefox, Linux
from webbot.util.har import HarSession


class WuxiaWorldTest(unittest.TestCase):
    def test_FF(self):
        browser = Firefox(Linux())
        browser.session = HarSession('../test_data/www.wuxiaworld.com_Archive_fresh_and_extensive.har')
        resp = browser.get('https://www.wuxiaworld.com/')
        print(resp.cookies)
        self.assertIsNotNone(resp)


if __name__ == '__main__':
    unittest.main()
