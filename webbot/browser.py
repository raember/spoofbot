import mimetypes
from enum import Enum
from typing import List, Any

import requests
from urllib3.util.url import parse_url, Url


class OS:
    def __init__(self):
        self.comments = []

    def __str__(self):
        return "; ".join(self.comments)


class WindowsVersion(Enum):
    Win10 = '10.0'
    Win8_1 = '6.3'
    Win8 = '6.2'
    Win7 = '6.1'
    Vista = '6.0'
    WinXP = '5.1'
    Win2000 = '5.0'


class Windows(OS):
    def __init__(self, version=WindowsVersion.Win10, x64=True, native=True):
        """A representation of Windows as the underlying operating system.

        :param version: The Windows version (default :py:const:`WindowsVersion.Win10`)
        :param x64: Whether the platform is 64-bit or 32-bit (default: :py:obj:`True`)
        :param native: Whether the browser is 64-bit or 32-bit (default: :py:obj:`True`)
        """
        super(Windows, self).__init__()
        self.comments.append(f"Windows NT {version.value}")
        if x64:
            if native:
                self.comments.append("Win64")
                self.comments.append("x64")
            else:  # 32bit browser on 64bit platform
                self.comments.append("WOW64")


class MacOSXVersion(Enum):
    Cheetah = '10_0'
    Puma = '10_1'
    Jaguar = '10_2'
    Panther = '10_3'
    Tiger = '10_4'
    Leopard = '10_5'
    SnowLeopard = '10_6'
    Lion = '10_7'
    MountainLion = '10_8'
    Mavericks = '10_9'
    Yosemite = '10_10'
    ElCapitan = '10_11'
    Sierra = '10_12'
    HighSierra = '10_13'
    Mojave = '10_14'
    Catalina = '10_15'


class MacOSX(OS):
    def __init__(self, version=MacOSXVersion.Catalina):
        """A representation of Mac OS X as the underlying operating system.

        :param version: The Mac OS X version (default :py:const:`MacOSXVersion.Catalina`)
        """
        super(MacOSX, self).__init__()
        self.comments.append("Macintosh")
        self.comments.append(f"Intel Mac OS X {version.value}")


class LinuxDerivatives(Enum):
    Generic = None
    Ubuntu = 'Ubuntu'


class Linux(OS):
    def __init__(self, derivative=LinuxDerivatives.Generic, x64=True, native=True):
        """A representation of GNU Linux as the underlying operating system.

        :param derivative: The Linux derivative (default :py:const:`LinuxDerivatives.Generic`)
        :param x64: Whether the platform is 64-bit or 32-bit (default: :py:obj:`True`)
        :param native: Whether the browser is 64-bit or 32-bit (default: :py:obj:`True`)
        """
        super(Linux, self).__init__()
        self.comments.append("X11")
        if derivative != LinuxDerivatives.Generic:
            self.comments.append(derivative.value)
        if x64:
            if native:
                self.comments.append("Linux x86_64")
            else:
                self.comments.append("Linux i686 on x86_64")
        else:
            self.comments.append("Linux i686")


def build_chromium_user_agent(
        os=Linux(),
        chromium_version='79.0.3945.92',
        webkit_version='607.1.40') -> str:
    return f"Mozilla/5.0 ({os}) " \
           f"AppleWebKit/{webkit_version} (KHTML, like Gecko) " \
           f"Chromium/{chromium_version} " \
           f"Safari/{webkit_version}"


def build_safari_user_agent(
        os=MacOSX(),
        safari_version='12.1.2',
        webkit_version='607.1.40') -> str:
    return f"Mozilla/5.0 ({os}) " \
           f"AppleWebKit/{webkit_version} (KHTML, like Gecko) " \
           f"Version/{safari_version} " \
           f"Safari/{webkit_version}"


def build_opera_user_agent(
        os=MacOSXVersion.Catalina,
        opera_version='65.0.3467.42',
        chrome_version='78.0.3904.87',
        webkit_version='537.36') -> str:
    return f"Mozilla/5.0 ({os.to_comment()}) " \
           f"AppleWebKit/{webkit_version} (KHTML, like Gecko) " \
           f"Chrome/{chrome_version} " \
           f"Safari/{webkit_version} " \
           f"OPR/{opera_version}"


class MimeType:
    _type: str
    _subtype: str

    def __init__(self, mime_type: str, subtype: str):
        self._type = mime_type
        self._subtype = subtype

    @property
    def type(self) -> str:
        return self._type

    @property
    def subtype(self) -> str:
        return self._subtype

    def __str__(self):
        return f"{self._type}/{self._subtype}"


class QualifiedMimeType(MimeType):
    _q: float

    def __init__(self, mime_type: str, subtype: str, quality: float):
        super(QualifiedMimeType, self).__init__(mime_type, subtype)
        self._q = quality

    @property
    def quality(self) -> float:
        return self._q

    def __str__(self):
        return f"{super().__str__()};q={self._q}"


class Language:
    _tag: str
    _subtag: str

    def __init__(self, tag: str, subtag: str = ''):
        self._tag = tag
        self._subtag = subtag

    @property
    def tag(self) -> str:
        return self._tag

    @property
    def subtag(self) -> str:
        return self._subtag

    def __str__(self):
        if self._subtag != '':
            return f"{self._tag}-{self._subtag}"
        return self._tag


class QualifiedLanguage(Language):
    _q: float

    def __init__(self, tag: str, subtag: str, quality: float):
        super(QualifiedLanguage, self).__init__(tag, subtag)
        self._q = quality

    @property
    def quality(self) -> float:
        return self._q

    def __str__(self):
        return f"{super().__str__()};q={self._q}"


class Browser:
    _user_agent: str
    _accept: List[MimeType]
    _accept_language: List[Language]
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
    def accept(self) -> List[MimeType]:
        return self._accept

    @accept.setter
    def accept(self, value: List[MimeType]):
        self._accept = value

    @property
    def accept_language(self) -> List[Language]:
        return self._accept_language

    @accept_language.setter
    def accept_language(self, value: List[Language]):
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
        mimetype, enc = mimetypes.guess_type(self._strip_query(url))
        if mimetype is not None:
            headers['Accept'] = mimetype
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

    def _strip_query(self, url: str) -> str:
        url = parse_url(url)
        return str(Url(url.scheme, None, url.host, url.port, url.path))

    def navigate(self, url: str, **kwargs) -> requests.Response:
        resp = self.get(url, **kwargs)
        self._last_url = resp.url
        return resp

    def get(self, url: str, **kwargs) -> requests.Response:
        kwargs['headers'] = self._assemble_headers(url, 'GET', kwargs.setdefault('headers', {}))
        resp = self._session.get(url, **kwargs)
        return resp

    def post(self, url: str, data: Any = None, json: Any = None, **kwargs) -> requests.Response:
        kwargs['headers'] = self._assemble_headers(url, 'POST', kwargs.setdefault('headers', {}))
        resp = self._session.post(url, data, json, **kwargs)
        if resp.request.method == 'GET':  # In case of redirect
            self._last_url = resp.url
        return resp

    def head(self, url: str, **kwargs) -> requests.Response:
        kwargs['headers'] = self._assemble_headers(url, 'HEAD', kwargs.setdefault('headers', {}))
        resp = self._session.head(url, **kwargs)
        return resp

    def delete(self, url: str, **kwargs) -> requests.Response:
        kwargs['headers'] = self._assemble_headers(url, 'DELETE', kwargs.setdefault('headers', {}))
        resp = self._session.delete(url, **kwargs)
        return resp

    def options(self, url: str, **kwargs) -> requests.Response:
        kwargs['headers'] = self._assemble_headers(url, 'OPTIONS', kwargs.setdefault('headers', {}))
        resp = self._session.options(url, **kwargs)
        return resp

    def patch(self, url: str, data: Any = None, **kwargs) -> requests.Response:
        kwargs['headers'] = self._assemble_headers(url, 'PATCH', kwargs.setdefault('headers', {}))
        resp = self._session.patch(url, data, **kwargs)
        if resp.request.method == 'GET':  # In case of redirect
            self._last_url = resp.url
        return resp

    def put(self, url: str, data: Any = None, **kwargs) -> requests.Response:
        kwargs['headers'] = self._assemble_headers(url, 'PUT', kwargs.setdefault('headers', {}))
        resp = self._session.put(url, data, **kwargs)
        if resp.request.method == 'GET':  # In case of redirect
            self._last_url = resp.url
        return resp


class Firefox(Browser):
    def __init__(self,
                 os=Windows(),
                 ff_version=(71, 0),
                 build_id=20100101,
                 lang=(
                         Language("en", "US"),
                         QualifiedLanguage("en", '', 0.5)
                 ),
                 do_not_track=False,
                 upgrade_insecure_requests=True):
        super(Firefox, self).__init__()
        self._user_agent = self.create_user_agent(os, ff_version, build_id)
        self._accept = [
            MimeType("text", "html"),
            MimeType("application", "xhtml+xml"),
            QualifiedMimeType("application", "xml", 0.9),
            # MimeType("image", "webp"),
            QualifiedMimeType("*", "*", 0.8)
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
                         Language("en", "US"),
                         QualifiedLanguage("en", '', 0.5)
                 ),
                 do_not_track=False,
                 upgrade_insecure_requests=False):
        super(Chrome, self).__init__()
        self._user_agent = self.create_user_agent(os=os, version=chrome_version, webkit_version=webkit_version)
        self._accept = [
            MimeType("text", "html"),
            MimeType("application", "xhtml+xml"),
            QualifiedMimeType("application", "xml", 0.9),
            MimeType("image", "webp"),
            QualifiedMimeType("*", "*", 0.8)
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
