class Tag:
    _major: str
    _minor: str
    _separator: str
    _quality: float

    def __init__(self, major: str, minor="", separator="", quality=1.0):
        self._major = major
        self._minor = minor
        self._separator = separator
        self._quality = quality

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
    def quality(self) -> float:
        return self._quality

    @quality.setter
    def quality(self, value: float):
        self._quality = min(1.0, max(0.0, value))

    def __str__(self):
        tag = self._major
        if self._minor != '':
            tag += self._separator + self._minor
        if self._quality != 1.0:
            tag += f";q={self._quality}"
        return tag


class MimeTypeTag(Tag):
    def __init__(self, mime_type: str = "*", sub_type: str = "*", quality=1.0):
        super(MimeTypeTag, self).__init__(mime_type, sub_type, '/', quality)


class LanguageTag(Tag):
    def __init__(self, lang: str, country_code: str, quality=1.0):
        super(LanguageTag, self).__init__(lang, country_code, '-', quality)
