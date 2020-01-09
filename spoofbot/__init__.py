"""Core modules for tht web bot"""

from .browser import Browser, Firefox, Chrome
from .operating_system import OS, Windows, WindowsVersion, MacOSX, MacOSXVersion, Linux, LinuxDerivatives
from .tag import MimeTypeTag, LanguageTag

__version__ = "0.1.1"
