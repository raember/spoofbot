from abc import ABC
from enum import Enum

from numpy.random import choice


class OS(ABC):
    def __init__(self):
        self.comments = []

    @staticmethod
    def create_random() -> 'OS':
        raise NotImplementedError

    def __str__(self):
        return "; ".join(self.comments)


class WindowsVersion(Enum):
    Win11 = '10.0'  # Yep
    Win10 = '10.0'
    Win8_1 = '6.3'
    Win8 = '6.2'
    Win7 = '6.1'
    Vista = '6.0'
    WinXP = '5.1'
    Win2000 = '5.0'

WindowsVersionALL = [
    WindowsVersion.Win11, WindowsVersion.Win10, WindowsVersion.Win8_1, WindowsVersion.Win8, WindowsVersion.Win7,
    WindowsVersion.Vista, WindowsVersion.WinXP, WindowsVersion.Win2000
]


class Windows(OS):
    def __init__(self, version=WindowsVersion.Win11, x64=True, native=True):
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

    @staticmethod
    def create_random() -> 'Windows':
        return Windows(
            version=choice(WindowsVersionALL, p=[
                0.3, 0.3, 0.2, 0.08, 0.11, 0.01, 0.0, 0.0
            ]),
            x64=choice([True, False], p=[0.9, 0.1]),
            native=choice([True, False], p=[0.8, 0.2])
        )


class MacOSXVersion(Enum):
    Cheetah = '10_0'  # March 24, 2001
    Puma = '10_1'  # September 25, 2001
    Jaguar = '10_2'  # August 23, 2002
    Panther = '10_3'  # October 24, 2003
    Tiger = '10_4'  # April 29, 2005
    Leopard = '10_5'  # October 26, 2007
    SnowLeopard = '10_6'  # June 8, 2009
    Lion = '10_7'  # July 20, 2011
    MountainLion = '10_8'  # July 25, 2012
    Mavericks = '10_9'  # October 22, 2013
    Yosemite = '10_10'  # October 16, 2014
    ElCapitan = '10_11'  # September 30, 2015
    Sierra = '10_12'  # September 20, 2016
    HighSierra = '10_13'  # September 25, 2017
    Mojave = '10_14'  # September 24, 2018
    Catalina = '10_15'  # October 7, 2019
    BigSur = '11'  # November 12, 2020
    Monterey = '12'  # October 25, 2021

MacOSXVersionALL = [
    MacOSXVersion.Monterey, MacOSXVersion.BigSur, MacOSXVersion.Catalina, MacOSXVersion.Mojave,
    MacOSXVersion.HighSierra, MacOSXVersion.Sierra, MacOSXVersion.ElCapitan, MacOSXVersion.Yosemite,
    MacOSXVersion.Mavericks, MacOSXVersion.MountainLion, MacOSXVersion.Lion, MacOSXVersion.SnowLeopard,
    MacOSXVersion.Leopard, MacOSXVersion.Tiger, MacOSXVersion.Panther, MacOSXVersion.Jaguar, MacOSXVersion.Puma,
    MacOSXVersion.Cheetah
]


class MacOSX(OS):
    def __init__(self, version=MacOSXVersion.Monterey):
        """A representation of MacOS X as the underlying operating system.

        :param version: The MacOS X version (default :py:const:`MacOSXVersion.Catalina`)
        """
        super(MacOSX, self).__init__()
        self.comments.append("Macintosh")
        self.comments.append(f"Intel Mac OS X {version.value}")

    @staticmethod
    def create_random() -> 'MacOSX':
        return MacOSX(version=choice(MacOSXVersionALL, p=[
            0.2, 0.2, 0.1, 0.1, 0.1, 0.1, 0.1, 0.05, 0.05, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
        ]))


class LinuxDerivatives(Enum):
    Generic = None
    Ubuntu = 'Ubuntu'


class Linux(OS):
    def __init__(self, derivative=LinuxDerivatives.Generic, x64=True, native=True):
        """A representation of GNU Linux as the underlying operating system.

        :param derivative: The Linux derivative
            (default :py:const:`LinuxDerivatives.Generic`)
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

    @staticmethod
    def create_random() -> 'Linux':
        return Linux(
            derivative=choice([LinuxDerivatives.Ubuntu, LinuxDerivatives.Generic], p=[0.3, 0.7]),
            x64=choice([True, False], p=[0.9, 0.1]),
            native=choice([True, False], p=[0.8, 0.2])
        )


def random_os() -> OS:
    return choice([
            Windows.create_random(),
            MacOSX.create_random(),
            Linux.create_random()
        ], p=[0.8, 0.15, 0.05])
