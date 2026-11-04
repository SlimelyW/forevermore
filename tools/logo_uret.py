"""Logo görselinden uygulama simgelerini üretir (geliştirme aracı).

    py -3.12 tools\\logo_uret.py <logo.jpg>

Açık arka planlı logodan yalnızca yaprak motifli sonsuzluk işaretini keser (yazının üstündeki
renkli bölge), arka planı saydam yapar ve şunları yazar:
  data/logo.png          uygulama içinde (kenar menü, Bilgi sayfası, pencere simgesi)
  build/forevermore.ico  .exe simgesi (PyInstaller)
Saydamlık renk doygunluğundan hesaplanır: arka plan neredeyse gri, işaret yeşil-turkuaz.
"""

import sys
from pathlib import Path

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter

ROOT = Path(__file__).resolve().parent.parent
BACKGROUND = (242, 246, 246)
SAT_LOW, SAT_HIGH = 14, 60  # bu doygunluğun altı tamamen saydam, üstü tamamen opak


def mark_bounds(image):
    """Yazının üstündeki (görselin üst %60'ı) doygun piksellerin sınırı."""
    xs, ys = [], []
    for y in range(0, int(image.height() * 0.6), 2):
        for x in range(0, image.width(), 2):
            c = image.pixelColor(x, y)
            if max(c.red(), c.green(), c.blue()) - min(c.red(), c.green(), c.blue()) > 40:
                xs.append(x)
                ys.append(y)
    pad = 12
    return QRect(min(xs) - pad, min(ys) - pad, max(xs) - min(xs) + 2 * pad, max(ys) - min(ys) + 2 * pad)


def cut_out(image):
    out = QImage(image.size(), QImage.Format.Format_ARGB32)
    for y in range(image.height()):
        for x in range(image.width()):
            c = image.pixelColor(x, y)
            rgb = (c.red(), c.green(), c.blue())
            alpha = (max(rgb) - min(rgb) - SAT_LOW) / (SAT_HIGH - SAT_LOW)
            alpha = min(1.0, max(0.0, alpha))
            if alpha == 0:
                out.setPixelColor(x, y, QColor(0, 0, 0, 0))
                continue
            # arka planın karıştığı kenar piksellerinden beyazı çıkar (açık zeminde beyaz hale kalmasın)
            pure = [min(255, max(0, round((v - (1 - alpha) * b) / alpha))) for v, b in zip(rgb, BACKGROUND)]
            out.setPixelColor(x, y, QColor(*pure, round(alpha * 255)))
    return out


def square(image, size):
    canvas = QImage(size, size, QImage.Format.Format_ARGB32)
    canvas.fill(Qt.GlobalColor.transparent)
    scaled = image.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    painter = QPainter(canvas)
    painter.drawImage((size - scaled.width()) // 2, (size - scaled.height()) // 2, scaled)
    painter.end()
    return canvas


def main():
    QGuiApplication(sys.argv[:1])
    source = QImage(sys.argv[1]).convertToFormat(QImage.Format.Format_RGB32)
    if source.isNull():
        raise SystemExit("görsel okunamadı")
    mark = cut_out(source.copy(mark_bounds(source)))
    logo = mark.scaledToWidth(640, Qt.TransformationMode.SmoothTransformation)
    logo.save(str(ROOT / "data" / "logo.png"))
    if not square(logo, 256).save(str(ROOT / "build" / "forevermore.ico")):
        raise SystemExit("ico yazılamadı (Qt ico eklentisi yok mu?)")
    print(f"data/logo.png {logo.width()}x{logo.height()}, build/forevermore.ico 256x256")


if __name__ == "__main__":
    main()
