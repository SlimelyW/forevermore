"""Registry okuma yardımcıları (salt okunur).

Yazma işlemleri ayar motorunda (app/engine/system.py), yedekleme ile birlikte
yapılır. 32 bit Python ile çalıştırılsa bile her zaman 64 bit registry görünümü
kullanılır (KEY_WOW64_64KEY), böylece HKLM\\SOFTWARE yönlendirilmez.
"""

import winreg

ROOTS = {"HKCU": winreg.HKEY_CURRENT_USER, "HKLM": winreg.HKEY_LOCAL_MACHINE}
READ = winreg.KEY_READ | winreg.KEY_WOW64_64KEY

TYPE_NAMES = {
    winreg.REG_DWORD: "REG_DWORD",
    winreg.REG_SZ: "REG_SZ",
    winreg.REG_EXPAND_SZ: "REG_EXPAND_SZ",
    winreg.REG_BINARY: "REG_BINARY",
    winreg.REG_MULTI_SZ: "REG_MULTI_SZ",
    winreg.REG_QWORD: "REG_QWORD",
}
TYPE_CODES = {name: code for code, name in TYPE_NAMES.items()}


def _root(root):
    return ROOTS[root] if isinstance(root, str) else root


def read(root, path, name, default=None):
    """Değeri döndürür; anahtar/değer yoksa veya okunamazsa `default`."""
    try:
        with winreg.OpenKey(_root(root), path, 0, READ) as key:
            return winreg.QueryValueEx(key, name)[0]
    except OSError:
        return default


def read_typed(root, path, name):
    """(değer, tür_adı) veya değer yoksa None."""
    try:
        with winreg.OpenKey(_root(root), path, 0, READ) as key:
            value, kind = winreg.QueryValueEx(key, name)
            return value, TYPE_NAMES.get(kind, str(kind))
    except FileNotFoundError:
        return None


def key_exists(root, path):
    try:
        with winreg.OpenKey(_root(root), path, 0, READ):
            return True
    except OSError:
        return False


def subkeys(root, path):
    try:
        with winreg.OpenKey(_root(root), path, 0, READ) as key:
            count = winreg.QueryInfoKey(key)[0]
            return [winreg.EnumKey(key, i) for i in range(count)]
    except OSError:
        return []


def values(root, path):
    """Anahtardaki tüm değerler: {ad: değer}."""
    result = {}
    try:
        with winreg.OpenKey(_root(root), path, 0, READ) as key:
            count = winreg.QueryInfoKey(key)[1]
            for i in range(count):
                name, value, _kind = winreg.EnumValue(key, i)
                result[name] = value
    except OSError:
        pass
    return result
