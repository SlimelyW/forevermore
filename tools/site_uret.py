"""Site klasörünü günceller (geliştirme aracı).

    py -3.12 tools\\site_uret.py

- site/kosullar.html: depo kökündeki LICENSE (MIT) dosyasından üretilir.
- site/img/logo.png: ELLE küçültülmüş kopya (160x84, ≈ 17 KB; data/logo.png 640x336). Bu araç artık üzerine yazmaz.
Ekran görüntüleri (site/img/*_tr.png, *_en.png) ayrıca tests.site_gorselleri ile çizilir.
"""

import html
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"

PAGE = """<!doctype html>
<html lang="tr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Lisans — Forevermore</title>
  <meta name="description" content="Forevermore MIT lisansı (ücretsiz ve açık kaynak). MIT license text in English and Turkish.">
  <link rel="canonical" href="https://forevermore.pages.dev/kosullar.html">
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="Forevermore">
  <meta property="og:title" content="Lisans — Forevermore">
  <meta property="og:description" content="Forevermore MIT lisansı.">
  <meta property="og:url" content="https://forevermore.pages.dev/kosullar.html">
  <meta property="og:locale" content="tr_TR">
  <meta name="twitter:card" content="summary">
  <link rel="icon" href="img/logo.png" type="image/png">
  <link rel="stylesheet" href="style.css">
</head>
<body>
<a class="atla" href="#main">İçeriğe geç / Skip to content</a>
<header class="top">
  <div class="wrap">
    <a class="brand" href="index.html"><img src="img/logo.png" alt="">Forevermore</a>
    <nav class="links"><a href="index.html">Ana sayfa / Home</a></nav>
  </div>
</header>
<main class="doc" id="main">
  <h1>Lisans / License</h1>
  <p class="updated">Forevermore, MIT lisansıyla ücretsiz ve açık kaynaktır; metin depodaki ve programla gelen LICENSE ile aynıdır. / Forevermore is free and open source under the MIT license; this is the same text as the LICENSE file in the repository and in the app.</p>
  <pre>{text}</pre>
</main>
<footer>
  <div class="wrap">
    <span>© 2026 Kubilay Paşa</span>
    <nav><a href="gizlilik.html">Gizlilik / Privacy</a></nav>
  </div>
</footer>
</body>
</html>
"""


def main():
    text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    (SITE / "kosullar.html").write_text(PAGE.format(text=html.escape(text.strip())), encoding="utf-8")
    print("site/kosullar.html güncellendi")


if __name__ == "__main__":
    main()
