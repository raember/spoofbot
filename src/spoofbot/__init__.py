"""Core modules for the web bot"""

# noinspection PyUnresolvedReferences
from .browser import Browser, Firefox, Chrome, MimeTypeTag, LanguageTag
# noinspection PyUnresolvedReferences
from .operating_system import OS, Windows, WindowsVersion, MacOSX, MacOSXVersion, \
    Linux, LinuxDerivatives

__version__ = '1.4.0'
