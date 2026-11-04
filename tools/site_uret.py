"""Site klasörünü günceller (geliştirme aracı).

    py -3.12 tools\\site_uret.py

- site/kosullar.html: depo kökündeki LICENSE (MIT) dosyasından üretilir.
- site/img/logo.png: data/logo.png kopyası.
Ekran görüntüleri (site/img/*_tr.png, *_en.png) ayrıca tests.site_gorselleri ile çizilir.
"""

import html
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"

PAGE = """<!doctype html>
<html lang="tr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Lisans — Forevermore</title>
  <link rel="icon" href="img/logo.png">
  <link rel="stylesheet" href="style.css">
</head>
<body>
<header class="top">
  <div class="wrap">
    <a class="brand" href="index.html"><img src="img/logo.png" alt="">Forevermore</a>
    <nav class="links"><a href="index.html">Ana sayfa</a><a class="lang" href="#en">EN</a></nav>
  </div>
</header>
<main class="doc">
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
    (SITE / "img").mkdir(exist_ok=True)
    shutil.copyfile(ROOT / "data" / "logo.png", SITE / "img" / "logo.png")
    print("site/kosullar.html ve site/img/logo.png güncellendi")


if __name__ == "__main__":
    main()
