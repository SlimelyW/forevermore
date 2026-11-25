"""Ed25519 imza (RFC 8032), saf Python; ek kütüphane gerektirmez.

Yalnızca paket bütünlüğü için kullanılır: derleme sırasında yapımcının özel anahtarıyla imzalanan dosya
listesi, uygulama açılınca gömülü genel anahtarla doğrulanır. Hız önemli değildir (tek imza), sabit
zamanlı değildir; bu yüzden özel anahtarla imzalama yalnızca yapımcının bilgisayarında yapılır.
Algoritma RFC 8032 bölüm 5.1'deki tanıma göre yazılmıştır.
"""

import hashlib

P = 2 ** 255 - 19
L = 2 ** 252 + 27742317777372353535851937790883648493
D = -121665 * pow(121666, P - 2, P) % P
SQRT_M1 = pow(2, (P - 1) // 4, P)


def _sha512(data):
    return hashlib.sha512(data).digest()


def _add(p, q):
    x1, y1, z1, t1 = p
    x2, y2, z2, t2 = q
    a = (y1 - x1) * (y2 - x2) % P
    b = (y1 + x1) * (y2 + x2) % P
    c = 2 * t1 * t2 * D % P
    d = 2 * z1 * z2 % P
    e, f, g, h = b - a, d - c, d + c, b + a
    return e * f % P, g * h % P, f * g % P, e * h % P


def _mul(s, p):
    q = (0, 1, 1, 0)  # nötr öğe
    while s > 0:
        if s & 1:
            q = _add(q, p)
        p = _add(p, p)
        s >>= 1
    return q


def _equal(p, q):
    x1, y1, z1, _ = p
    x2, y2, z2, _ = q
    return (x1 * z2 - x2 * z1) % P == 0 and (y1 * z2 - y2 * z1) % P == 0


def _recover_x(y, sign):
    if y >= P:
        return None
    x2 = (y * y - 1) * pow(D * y * y + 1, P - 2, P)
    if x2 == 0:
        return None if sign else 0
    x = pow(x2, (P + 3) // 8, P)
    if (x * x - x2) % P != 0:
        x = x * SQRT_M1 % P
    if (x * x - x2) % P != 0:
        return None
    if (x & 1) != sign:
        x = P - x
    return x


_GY = 4 * pow(5, P - 2, P) % P
_GX = _recover_x(_GY, 0)
G = (_GX, _GY, 1, _GX * _GY % P)


def _compress(p):
    x, y, z, _ = p
    zinv = pow(z, P - 2, P)
    x, y = x * zinv % P, y * zinv % P
    return int.to_bytes(y | ((x & 1) << 255), 32, "little")


def _decompress(data):
    if len(data) != 32:
        return None
    y = int.from_bytes(data, "little")
    sign = y >> 255
    y &= (1 << 255) - 1
    x = _recover_x(y, sign)
    if x is None:
        return None
    return x, y, 1, x * y % P


def _secret_expand(secret):
    if len(secret) != 32:
        raise ValueError("özel anahtar 32 bayt olmalı")
    h = _sha512(secret)
    a = int.from_bytes(h[:32], "little")
    a &= (1 << 254) - 8
    a |= 1 << 254
    return a, h[32:]


def public_key(secret):
    a, _ = _secret_expand(secret)
    return _compress(_mul(a, G))


def sign(secret, message):
    a, prefix = _secret_expand(secret)
    pub = _compress(_mul(a, G))
    r = int.from_bytes(_sha512(prefix + message), "little") % L
    big_r = _compress(_mul(r, G))
    h = int.from_bytes(_sha512(big_r + pub + message), "little") % L
    s = (r + h * a) % L
    return big_r + int.to_bytes(s, 32, "little")


def verify(public, message, signature):
    if len(public) != 32 or len(signature) != 64:
        return False
    a = _decompress(public)
    big_r = _decompress(signature[:32])
    if a is None or big_r is None:
        return False
    s = int.from_bytes(signature[32:], "little")
    if s >= L:
        return False
    h = int.from_bytes(_sha512(signature[:32] + public + message), "little") % L
    return _equal(_mul(s, G), _add(big_r, _mul(h, a)))
