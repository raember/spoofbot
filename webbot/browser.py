from typing import Tuple, NamedTuple

from user_agents import parsers as ua, parse
import re


class UserAgent:
    _product: str
    _product_version: Tuple[int, int]

    @property
    def product(self) -> str:
        return self._product

    @product.setter
    def product(self, value):
        self._product = value

    @property
    def product_version(self) -> Tuple[int, int]:
        return self._product_version

    @product_version.setter
    def product_version(self, value):
        self._product_version = value


def parse_user_agent(user_agent_str: str) -> UserAgent:
    match = re.match(r'^(?P<product>[^/]+?)/(?P<product_version>\d+(\.\d+)*?) (?P<comment>.*?)$', user_agent_str)
    if not match:
        raise Exception("Malformed user agent string")
    user_agent = UserAgent()
    user_agent.product, product_version_str, _, comment = match.groups()
    user_agent.product_version = tuple(map(int, product_version_str.split('.')))
    # TODO: Parse comment
    return user_agent


class Browser:
    userAgent: ua.UserAgent


# Host: web.de
# User-Agent: Mozilla/5.0 (Windows NT 10.0; rv:68.0) Gecko/20100101 Firefox/68.0
# Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8
# Accept-Language: en-US,en;q=0.5
# Accept-Encoding: gzip, deflate, br
# DNT: 1
# Upgrade-Insecure-Requests: 1
# Connection: keep-alive


class Firefox(Browser):
    def __init__(self, version=(71,), buildid=20100101):
        super(Firefox, self).__init__()
        self.userAgent = ua.UserAgent(
            f"Mozilla/5.0 (Windows NT 6.1; WOW64; rv:{'.'.join(version)}) Gecko/{buildid} Firefox/{'.'.join(version)}")
