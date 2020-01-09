import mimetypes
from typing import List, Any

import requests
from urllib3.util.url import parse_url, Url

from spoofbot.operating_system import Windows
from spoofbot.tag import MimeTypeTag, LanguageTag


class Browser:
    _user_agent: str
    _accept: List[MimeTypeTag]
    _accept_language: List[LanguageTag]
    _accept_encoding: List[str]
    _dnt: bool = False
    _upgrade_insecure_requests: bool = False
    _connection: str = ''
    _session: requests.Session = requests.Session()
    _last_url: str = ''

    @property
    def user_agent(self) -> str:
        return self._user_agent

    @user_agent.setter
    def user_agent(self, value: str):
        self._user_agent = value

    @property
    def accept(self) -> List[MimeTypeTag]:
        return self._accept

    @accept.setter
    def accept(self, value: List[MimeTypeTag]):
        self._accept = value

    @property
    def accept_language(self) -> List[LanguageTag]:
        return self._accept_language

    @accept_language.setter
    def accept_language(self, value: List[LanguageTag]):
        self._accept_language = value

    @property
    def accept_encoding(self) -> List[str]:
        return self._accept_encoding

    @accept_encoding.setter
    def accept_encoding(self, value: List[str]):
        self._accept_encoding = value

    @property
    def do_not_track(self) -> bool:
        return self._dnt

    @do_not_track.setter
    def do_not_track(self, value: bool):
        self._dnt = value

    @property
    def upgrade_insecure_requests(self) -> bool:
        return self._upgrade_insecure_requests

    @upgrade_insecure_requests.setter
    def upgrade_insecure_requests(self, value: bool):
        self._upgrade_insecure_requests = value

    @property
    def connection(self) -> str:
        return self._connection

    @connection.setter
    def connection(self, value: str):
        self._connection = value

    @property
    def session(self) -> requests.Session:
        return self._session

    @session.setter
    def session(self, value: requests.Session):
        self._session = value

    @staticmethod
    def create_user_agent(**kwargs) -> str:
        """Creates a user agent string according to the browsers identity.

        :param kwargs: Specific arguments to take into account.
        :returns: A custom user agent string.
        """
        raise NotImplementedError

    def _assemble_headers(self, url: str, method: str, custom_headers: dict = None) -> dict:
        headers = self._get_default_headers(url)
        mime_type, enc = mimetypes.guess_type(self._strip_query(url))
        if mime_type is not None:
            headers['Accept'] = mime_type
            if enc:
                headers['Accept-Encoding'] = enc
        if 'Referer' not in headers and self._last_url != '':
            headers['Referer'] = self._last_url
        if parse_url(url).scheme == 'https':
            if 'TE' not in headers:
                headers['TE'] = 'Trailers'
        else:
            headers['accept-encoding'] = ', '.join(['gzip', 'deflate'])
        if method in ['POST', 'PATCH', 'PUT']:
            headers.setdefault('Origin', self._get_origin())
        headers.update(custom_headers)
        return headers

    def _get_default_headers(self, url: str) -> dict:
        raise NotImplementedError

    def _get_origin(self) -> str:
        url = parse_url(self._last_url)
        return str(Url(url.scheme, None, url.host, url.port))

    @staticmethod
    def _strip_query(url: str) -> str:
        url = parse_url(url)
        return str(Url(url.scheme, None, url.host, url.port, url.path))

    def navigate(self, url: str, **kwargs) -> requests.Response:
        resp = self.get(url, **kwargs)
        self._last_url = resp.url
        return resp

    def _handle_response(self, response: requests.Response) -> requests.Response:
        if response.history:  # In case of redirect
            self._last_url = response.url
        return response

    def get(self, url: str, **kwargs) -> requests.Response:
        kwargs['headers'] = self._assemble_headers(url, 'GET', kwargs.setdefault('headers', {}))
        return self._handle_response(self._session.get(url, **kwargs))

    def post(self, url: str, data: Any = None, json: Any = None, **kwargs) -> requests.Response:
        kwargs['headers'] = self._assemble_headers(url, 'POST', kwargs.setdefault('headers', {}))
        return self._handle_response(self._session.post(url, data, json, **kwargs))

    def head(self, url: str, **kwargs) -> requests.Response:
        kwargs['headers'] = self._assemble_headers(url, 'HEAD', kwargs.setdefault('headers', {}))
        return self._handle_response(self._session.head(url, **kwargs))

    def delete(self, url: str, **kwargs) -> requests.Response:
        kwargs['headers'] = self._assemble_headers(url, 'DELETE', kwargs.setdefault('headers', {}))
        return self._handle_response(self._session.delete(url, **kwargs))

    def options(self, url: str, **kwargs) -> requests.Response:
        kwargs['headers'] = self._assemble_headers(url, 'OPTIONS', kwargs.setdefault('headers', {}))
        return self._handle_response(self._session.options(url, **kwargs))

    def patch(self, url: str, data: Any = None, **kwargs) -> requests.Response:
        kwargs['headers'] = self._assemble_headers(url, 'PATCH', kwargs.setdefault('headers', {}))
        return self._handle_response(self._session.patch(url, data, **kwargs))

    def put(self, url: str, data: Any = None, **kwargs) -> requests.Response:
        kwargs['headers'] = self._assemble_headers(url, 'PUT', kwargs.setdefault('headers', {}))
        return self._handle_response(self._session.put(url, data, **kwargs))


class Firefox(Browser):
    def __init__(self,
                 os=Windows(),
                 ff_version=(71, 0),
                 build_id=20100101,
                 lang=(
                         LanguageTag("en", "US"),
                         LanguageTag("en", '', 0.5)
                 ),
                 do_not_track=False,
                 upgrade_insecure_requests=True):
        super(Firefox, self).__init__()
        self._user_agent = self.create_user_agent(os, ff_version, build_id)
        self._accept = [
            MimeTypeTag("text", "html"),
            MimeTypeTag("application", "xhtml+xml"),
            MimeTypeTag("application", "xml", 0.9),
            # MimeTypeTag("image", "webp"),
            MimeTypeTag("*", "*", 0.8)
        ]
        self._accept_language = list(lang)
        self._accept_encoding = ['gzip', 'deflate', 'br']
        self._dnt = do_not_track
        self._upgrade_insecure_requests = upgrade_insecure_requests
        self._connection = 'keep-alive'

    @staticmethod
    def create_user_agent(os=Windows(), version=(71, 0), build_id=20100101) -> str:
        """Creates a user agent string for Firefox

        :param os: The underlying operating system (default :py:class:`Windows`).
        :param version: The version of Firefox (default (71, 0)).
        :param build_id: The build id of Gecko (default 20100101).
        :returns: A custom user agent string.
        """
        ff_version = '.'.join(map(str, version))
        return f"Mozilla/5.0 ({os}; rv:{ff_version}) " \
               f"Gecko/{build_id} " \
               f"Firefox/{ff_version}"

    def _get_default_headers(self, url: str) -> dict:
        headers = {
            'Host': parse_url(url).hostname,
            'User-Agent': self._user_agent,
            'Accept': ','.join(map(str, self._accept)),
            'Accept-Language': ','.join(map(str, self._accept_language)),
            'Accept-Encoding': ', '.join(map(str, self._accept_encoding))
        }
        if self._connection != '':
            headers['Connection'] = self._connection
        if self._dnt:
            headers['DNT'] = '1'
        if self._upgrade_insecure_requests:
            headers['Upgrade-Insecure-Requests'] = '1'
        return headers


class Chrome(Browser):
    def __init__(self,
                 os=Windows(),
                 chrome_version=(79, 0, 3945, 88),
                 webkit_version=(537, 36),
                 lang=(
                         LanguageTag("en", "US"),
                         LanguageTag("en", '', 0.5)
                 ),
                 do_not_track=False,
                 upgrade_insecure_requests=False):
        super(Chrome, self).__init__()
        self._user_agent = self.create_user_agent(os=os, version=chrome_version, webkit_version=webkit_version)
        self._accept = [
            MimeTypeTag("text", "html"),
            MimeTypeTag("application", "xhtml+xml"),
            MimeTypeTag("application", "xml", 0.9),
            MimeTypeTag("image", "webp"),
            MimeTypeTag(quality=0.8)
        ]
        self._accept_language = list(lang)
        self._accept_encoding = ['gzip', 'deflate', 'br']
        self._dnt = do_not_track
        self._upgrade_insecure_requests = upgrade_insecure_requests
        self._connection = 'keep-alive'

    @staticmethod
    def create_user_agent(os=Windows(), version=(79, 0, 3945, 88), webkit_version=(537, 36)) -> str:
        """Creates a user agent string for Firefox

        :param os: The underlying operating system (default :py:class:`Windows`).
        :param version: The version of the underlying webkit (default `(79, 0, 3945, 88)).
        :param webkit_version: The version of Chrome (default: (537, 36)).
        :returns: A custom user agent string.
        """
        webkit_ver = '.'.join(map(str, webkit_version))
        return f"Mozilla/5.0 ({os}) " \
               f"AppleWebKit/{webkit_ver} (KHTML, like Gecko) " \
               f"Chrome/{'.'.join(map(str, version))} " \
               f"Safari/{webkit_ver}"

    def _get_default_headers(self, **kwargs) -> dict:
        headers = {
            'User-Agent': self._user_agent,
            'Accept': ','.join(map(str, self._accept)),
            'Accept-Language': ','.join(map(str, self._accept_language)),
            'Accept-Encoding': ', '.join(map(str, self._accept_encoding))
        }
        if self._dnt:
            headers['DNT'] = 1
        if self._upgrade_insecure_requests:
            headers['Upgrade-Insecure-Requests'] = 1
        if self._connection != '':
            headers['Connection'] = self._connection
        return headers

# def build_chromium_user_agent(
#         os=Linux(),
#         chromium_version='79.0.3945.92',
#         webkit_version='607.1.40') -> str:
#     return f"Mozilla/5.0 ({os}) " \
#            f"AppleWebKit/{webkit_version} (KHTML, like Gecko) " \
#            f"Chromium/{chromium_version} " \
#            f"Safari/{webkit_version}"
#
#
# def build_safari_user_agent(
#         os=MacOSX(),
#         safari_version='12.1.2',
#         webkit_version='607.1.40') -> str:
#     return f"Mozilla/5.0 ({os}) " \
#            f"AppleWebKit/{webkit_version} (KHTML, like Gecko) " \
#            f"Version/{safari_version} " \
#            f"Safari/{webkit_version}"
#
#
# def build_opera_user_agent(
#         os=MacOSXVersion.Catalina,
#         opera_version='65.0.3467.42',
#         chrome_version='78.0.3904.87',
#         webkit_version='537.36') -> str:
#     return f"Mozilla/5.0 ({os.to_comment()}) " \
#            f"AppleWebKit/{webkit_version} (KHTML, like Gecko) " \
#            f"Chrome/{chrome_version} " \
#            f"Safari/{webkit_version} " \
#            f"OPR/{opera_version}"
