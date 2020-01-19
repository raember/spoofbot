class Tag:
    _major: str
    _minor: str
    _separator: str
    _factors: dict

    def __init__(self, major: str, minor="", separator="", **kwargs):
        self._major = major
        self._minor = minor
        self._separator = separator
        self._factors = kwargs

    @property
    def major(self) -> str:
        return self._major

    @major.setter
    def major(self, value: str):
        self._major = value

    @property
    def minor(self) -> str:
        return self._minor

    @minor.setter
    def minor(self, value: str):
        self._minor = value

    @property
    def separator(self) -> str:
        return self._separator

    @separator.setter
    def separator(self, value: str):
        self._separator = value

    @property
    def factors(self) -> dict:
        return self._factors

    @factors.setter
    def factors(self, value: dict):
        self._factors = value

    def __str__(self):
        tags = []
        if self._minor != '':
            tags.append(self._major + self._separator + self._minor)
        else:
            tags.append(self._major)
        for key, val in self._factors.items():
            tags.append(f"{key}={val}")
        return ';'.join(tags)


class MimeTypeTag(Tag):
    def __init__(self, mime_type: str = "*", sub_type: str = "*", **kwargs):
        super(MimeTypeTag, self).__init__(mime_type, sub_type, '/', **kwargs)


class LanguageTag(Tag):
    def __init__(self, lang: str, country_code: str = '', **kwargs):
        super(LanguageTag, self).__init__(lang, country_code, '-', **kwargs)
