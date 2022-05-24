"""Core modules for tht web bot"""

# noinspection PyUnresolvedReferences
from .browser import Browser, Firefox, Chrome, MimeTypeTag, LanguageTag
# noinspection PyUnresolvedReferences
from .operating_system import OS, Windows, WindowsVersion, MacOSX, MacOSXVersion, \
    Linux, LinuxDerivatives

__version__ = '1.3.4'
