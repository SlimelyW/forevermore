"""PyInstaller giriş dosyası (.exe buradan başlar). Geliştirirken `py -3.12 -m app` kullan."""

import sys

from app.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
