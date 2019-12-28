from enum import Enum


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
