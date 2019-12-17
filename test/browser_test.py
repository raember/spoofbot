import unittest
# https://developers.whatismybrowser.com/useragents/explore/


class UserAgentTest(unittest.TestCase):
    def test_FF(self):
        browser = Firefox()
        self.assertEqual('', browser.userAgent)


if __name__ == '__main__':
    unittest.main()
