import unittest
# https://developers.whatismybrowser.com/useragents/explore/
from webbot.browser import parse_user_agent


class UserAgentTest(unittest.TestCase):
    def test_parse(self):
        USERAGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:54.0) Gecko/20100101 Firefox/54.0'
        userAgent = parse_user_agent(USERAGENT)
        self.assertEqual('Mozilla', userAgent.product)
        self.assertEqual((5, 0), userAgent.product_version)
        self.assertEqual(USERAGENT, str(userAgent))


if __name__ == '__main__':
    unittest.main()
