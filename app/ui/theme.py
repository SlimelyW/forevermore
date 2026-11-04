"""Renkler, yazı tipleri, simgeler ve Qt stil sayfası (QSS): tek jeton kaynağı.

Tasarım (Faz 4): sakin, koyu-lacivert zemin (#0f1420) üstünde katmanlı düz yüzeyler (zemin < kart < üzerine gelinen
kart) ve 1 px kenarlık; ana vurgu yeşil #2fd3a1, mor yalnızca odak halkası ve rozette; anlam renkleri
yeşil/sarı/kırmızı/mavi (TONES). Her kategorinin kendi rengi yalnızca simge kutusunda. Gölge, bulanıklık ve cam yok.
Yazı boyutları 24 / 16 / 13 / 12 (TITLE/SECTION/BODY/SMALL), boşluk SPACE, köşe RADIUS; hareket süreleri motion.py'de.

Tek bir genel stil sayfası kullanılır; tek tek widget'lara stil verilmez
(Qt'de bu, yüzlerce kart olduğunda belirgin şekilde hızlıdır). Renk tonları
`tone` özelliğiyle seçilir: `label.setProperty("tone", "sorun")`. Renkli simge
kutuları stil sayfası yerine elle çizilir (widgets.IconTile).

Simgeler Windows'un kendi simge yazı tipinden gelir (Windows 11: Segoe Fluent
Icons, Windows 10: Segoe MDL2 Assets). Uygulamaya dosya gömülmez.
"""

import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QGuiApplication

from app.core import i18n, settings

DARK = {
    "bg": "#0f1420", "side": "#0b101a", "card": "#171e2e", "card_hover": "#1e2739", "border": "#263046",
    "text": "#e9eef8", "muted": "#8d98b0", "accent": "#2fd3a1", "accent_hover": "#52e0b5",
    "accent_soft": "#133a33", "input": "#1c2538", "highlight": "#17423a", "track_off": "#33405a",
    "knob": "#ffffff", "on_accent": "#06281e", "edge": "#35405a", "purple": "#8b7cff", "purple_wash": "#211f45",
}
LIGHT = {
    "bg": "#f4f6f9", "side": "#e9edf3", "card": "#ffffff", "card_hover": "#f3f6fa", "border": "#dde3ec",
    "text": "#141a26", "muted": "#566177", "accent": "#0b7a5a", "accent_hover": "#0e8f6a",
    "accent_soft": "#dcf3ea", "input": "#edf1f6", "highlight": "#cdebdf", "track_off": "#c3cad6",
    "knob": "#ffffff", "on_accent": "#ffffff", "edge": "#ffffff", "purple": "#6a5af0", "purple_wash": "#e8e5fb",
}
# İki temada da okunan anlam renkleri (rozet, şerit, bulgu çizgisi)
TONES = {
    "sorun": "#e5484d", "uyari": "#e09a2b", "bilgi": "#4c8dff", "iyi": "#2fb26d",
    "notr": "#6e7180", "mor": "#8b6cf0", "turkuaz": "#26a69a",
}
IMPACT_TONE = {"yüksek": "iyi", "orta": "turkuaz", "düşük": "notr", "çok düşük": "notr",
               "yok": "notr", "belirsiz": "mor", "durumsal": "mor"}
RISK_TONE = {"güvenli": "iyi", "dikkatli": "uyari", "riskli": "sorun"}
REALITY_TONE = {"gerçek": "iyi", "kısmen gerçek": "turkuaz", "durumsal": "mor", "tartışmalı": "uyari",
                "placebo": "notr", "zararlı": "sorun"}

# Kategori ve menü renkleri (simge kutuları ve kenar menü simgeleri)
CATEGORY_COLORS = {
    "DISP": "#4c8dff", "SYS": "#8e93a8", "PERF": "#ff8a3d", "GPU": "#3ccb7f", "CPU": "#45b7e8",
    "PWR": "#f2c230", "NET": "#26b5a8", "INP": "#b07cff", "AUD": "#ff6fae", "QOL": "#7b6cff",
    "PLC": "#8a8a96", "oyunlar": "#f0565b", "ozet": "#7b6cff", "pc_detay": "#45b7e8",
    "profiller": "#7b6cff", "baslangic": "#8e93a8", "degisiklikler": "#8e93a8", "rapor": "#8e93a8",
    "olcum": "#26b5a8", "boost": "#ff8a3d", "kaldirici": "#e5566d", "ayarlar": "#8e93a8", "bilgi": "#7b6cff", "elle": "#e09a2b", "lisans": "#f2c230",
}

# Simge kod noktaları (Segoe Fluent Icons / MDL2 Assets)
ICONS = {
    "ozet": "", "pc_detay": "", "profiller": "", "DISP": "", "SYS": "",
    "PERF": "", "GPU": "", "CPU": "", "PWR": "", "NET": "", "INP": "",
    "AUD": "", "QOL": "", "PLC": "", "degisiklikler": "", "rapor": "",
    "ayarlar": "", "baslangic": "", "oyunlar": "", "olcum": "", "info": "",
    "bilgi": "", "refresh": "", "warning": "", "check": "", "undo": "",
    "save": "", "chevron": "",
}

ICONS.update(edit="\ue70f", klavye="\ue765", elle="\ue70f", lisans="\ue8d7", boost=ICONS["PERF"], kaldirici="\ue74d")  # düzenle (kalem), klavye

TITLE_SIZE, SECTION_SIZE, BODY_SIZE, SMALL_SIZE = 24, 16, 13, 12
# Tek ölçü sistemi (docs/TASARIM_ESASLARI.md §13): boşluk 4'ün katları, köşe yarıçapı üç basamak.
# Aynı tür öğe her yerde aynı yarıçapı kullanır: kontroller md, kartlar/şeritler lg, rozet sm.
SPACE = (4, 8, 12, 16, 24, 32)
RADIUS = {"sm": 6, "md": 8, "lg": 12}

_icon_family = None


def category_color(key):
    """Kategori/menü simgelerinin rengi (tek renk fazla cansız bulundu: Ekim 2026 geri bildirimi)."""
    return CATEGORY_COLORS.get(key, palette()["accent"])


def soft(color, alpha=40):
    """Rengin saydam hâli (simge kutusu zemini)."""
    result = QColor(color)
    result.setAlpha(alpha)
    return result


def icon_family():
    global _icon_family
    if _icon_family is None:
        families = set(QFontDatabase.families())
        _icon_family = next((f for f in ("Segoe Fluent Icons", "Segoe MDL2 Assets") if f in families), "Segoe UI")
    return _icon_family


def icon_font(size=14):
    font = QFont(icon_family())
    font.setPixelSize(size)
    return font


def ui_font(size=BODY_SIZE, bold=False):
    families = set(QFontDatabase.families())
    # Dil dosyası kendi yazı tipini isteyebilir (ör. Çince/Japonca için); yoksa Segoe UI.
    # Segoe UI'da olmayan karakterler için Windows yazı tipi yedeklemesi zaten devrededir.
    wanted = i18n.meta().get("yazi_tipi")
    readable = bool(settings.get("okunabilir_yazi"))
    if readable and "Verdana" in families:  # disleksi dostu: geniş, ayırt edilebilir harfler
        family = "Verdana"
    elif wanted and wanted in families:
        family = wanted
    else:
        family = "Segoe UI Variable Text" if "Segoe UI Variable Text" in families else "Segoe UI"
    font = QFont(family)
    font.setPixelSize(size + 1 if readable else size)
    if readable:
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.3)
    if bold:
        font.setWeight(QFont.Weight.DemiBold)
    return font


def tabular(widget):
    """Rakamlar sabit genişlikte (tnum): canlı değerler değişirken metin yana kaymaz."""
    font = widget.font()
    font.setFeature(QFont.Tag("tnum"), 1)
    widget.setFont(font)
    return widget


def is_dark():
    forced = os.environ.get("PCOPT_TEMA")  # test için: "koyu" / "acik"
    if forced in ("koyu", "acik"):
        return forced == "koyu"
    hints = QGuiApplication.styleHints()
    try:
        return hints.colorScheme() != Qt.ColorScheme.Light  # bilinmiyorsa koyu (tasarımın tabanı)
    except AttributeError:  # eski Qt sürümü
        return True


# Yüksek karşıtlık: yalnızca metin ve çizgi rengini güçlendirir, yüzeyler aynı kalır.
HIGH_DARK = {"text": "#ffffff", "muted": "#c8d0e2", "border": "#6b7a9c", "edge": "#8794b3"}
HIGH_LIGHT = {"text": "#000000", "muted": "#2b3345", "border": "#5b6678", "edge": "#5b6678"}


def palette():
    base = DARK if is_dark() else LIGHT
    if settings.get("yuksek_karsitlik"):
        return {**base, **(HIGH_DARK if is_dark() else HIGH_LIGHT)}
    return base


def stylesheet(p=None):
    p = p or palette()
    r = RADIUS
    tones = "\n".join(
        f'QLabel[tone="{name}"] {{ background: {color}; color: white; border-radius: {r['sm']}px; padding: 1px 7px; }}\n'
        f'QFrame[stripe="{name}"] {{ background: {color}; border-radius: 2px; }}\n'
        f'QLabel[fg="{name}"] {{ color: {color}; }}\n'
        f'QFrame[banner="{name}"] {{ background: {color}; border-radius: {r['lg']}px; }}'
        for name, color in TONES.items()
    )
    return f"""
    QWidget {{ color: {p['text']}; }}
    QMainWindow, QDialog, #Root {{ background: {p['bg']}; }}
    QScrollArea, #PageBody {{ background: transparent; border: none; }}
    #Sidebar {{ background: {p['side']}; }}
    #Brand {{ font-size: 23px; font-weight: 700; }}
    #BrandSub {{ color: {p['muted']}; font-size: 11px; }}
    #NavItem {{ border-radius: {r['md']}px; }}
    #NavItem[selected="true"] {{ background: {p['accent_soft']}; }}
    #NavMarker {{ background: transparent; border-radius: 2px; }}
    #NavItem[selected="true"] #NavMarker {{ background: {p['accent']}; }}
    #NavCount {{ background: {p['input']}; color: {p['muted']}; border-radius: 8px; padding: 0 6px; font-size: 11px; }}
    #NavGroup {{ color: {p['muted']}; font-size: 10px; font-weight: 700; padding: 0 0 2px 6px; }}
    #NavMore {{ color: {p['muted']}; font-size: 12px; padding: 4px 0 0 36px; }}
    #NavMore:hover {{ color: {p['accent']}; }}
    #DonateBtn {{ margin: 6px 10px 12px 10px; padding: 9px 12px; background: {p['accent_soft']}; color: {p['accent']}; border: 1px solid {p['accent']}; border-radius: {r['md']}px; font-weight: 600; }}
    #DonateBtn:hover {{ background: {p['accent']}; color: {p['bg']}; }}
    #Card {{ background: {p['card']}; border: 1px solid {p['border']}; border-top-color: {p['edge']}; border-radius: {r['lg']}px; }}
    #List {{ background: {p['card']}; border: 1px solid {p['border']}; border-top-color: {p['edge']}; border-radius: {r['lg']}px; }}
    #Card[inlist="true"] {{ background: transparent; border: none; border-radius: {r['md']}px; }}
    #Divider {{ background: {p['border']}; margin: 0 16px; }}
    #Skeleton {{ background: {p['input']}; border-radius: {r['md']}px; }}
    #Card[highlight="true"] {{ background: {p['highlight']}; }}
    #StatNum {{ font-size: 20px; font-weight: 600; }}
    #LiveNum {{ font-size: 22px; font-weight: 600; }}
    #Muted, QLabel[muted="true"] {{ color: {p['muted']}; }}
    #Title {{ font-size: {TITLE_SIZE}px; font-weight: 600; }}
    #Section {{ font-size: {SECTION_SIZE}px; font-weight: 600; padding-top: 12px; color: {p['accent']}; }}
    #CardTitle {{ font-size: 14px; font-weight: 600; }}
    #Summary {{ color: {p['muted']}; font-size: {SMALL_SIZE}px; }}
    #Big {{ font-size: 34px; font-weight: 600; }}
    #Card[hero="true"] {{ border: 1px solid {p['accent']}; border-radius: {r['lg']}px; }}
    #HeroTitle {{ font-size: 26px; font-weight: 600; }}
    #Toast {{ background: {p['accent']}; border-radius: {r['lg']}px; }}
    #Toast QLabel {{ background: transparent; color: {p['on_accent']}; font-weight: 600; padding: 4px 0; }}
    #ToastAction {{ background: transparent; color: {p['on_accent']}; border: 1px solid {p['on_accent']}; font-weight: 600;
                    min-height: 24px; padding: 8px 14px; }}
    #ToastAction:hover {{ background: {p['accent_hover']}; }}
    #ToastAction:pressed {{ background: {p['accent_soft']}; }}
    QProgressBar#Thin {{ background: {p['border']}; border: none; border-radius: 3px; min-height: 6px; max-height: 6px; }}
    QProgressBar#Thin::chunk {{ background: {p['accent']}; border-radius: 3px; }}
    #HeroDone {{ color: {p['accent']}; font-weight: 600; }}
    #Hero {{ font-size: 30px; font-weight: 700; }}
    QPushButton {{ background: {p['input']}; border: 1px solid {p['border']}; border-radius: {r['md']}px;
                   padding: 9px 14px; min-height: 20px; }}
    QPushButton:focus {{ border-color: {p['purple']}; background: {p['purple_wash']}; }}
    QPushButton:hover {{ background: {p['card_hover']}; border-color: {p['edge']}; }}
    QPushButton:pressed {{ background: {p['border']}; }}
    QPushButton:disabled {{ color: {p['muted']}; border-color: {p['border']}; }}
    QPushButton[primary="true"] {{ background: {p['accent']}; color: {p['on_accent']}; border: none; font-weight: 600; }}
    QPushButton[primary="true"]:hover {{ background: {p['accent_hover']}; }}
    QPushButton[primary="true"]:pressed {{ background: {p['accent']}; }}
    QPushButton[primary="true"]:disabled {{ background: {p['track_off']}; color: {p['muted']}; }}
    QPushButton[warn="true"] {{ background: {TONES['uyari']}; color: white; border: none; }}
    QPushButton[warn="true"]:disabled {{ background: {p['track_off']}; color: {p['muted']}; }}
    QPushButton[segment="true"]:checked {{ background: {p['accent']}; color: white; border: none; }}
    QPushButton#InfoButton, QPushButton#IconButton {{ border-radius: 14px; padding: 0; margin: 6px; font-weight: 600;
                              background: transparent; border: 1px solid {p['border']}; }}
    QPushButton#InfoButton:hover, QPushButton#IconButton:hover {{ background: {p['card_hover']}; }}
    QComboBox, QLineEdit {{ background: {p['input']}; border: 1px solid {p['border']}; border-radius: {r['md']}px; padding: 5px 9px; }}
    QComboBox:hover, QLineEdit:hover {{ border-color: {p['edge']}; }}
    QComboBox:focus, QLineEdit:focus {{ border-color: {p['purple']}; }}
    QComboBox:disabled, QLineEdit:disabled {{ color: {p['muted']}; }}
    QComboBox QAbstractItemView {{ background: {p['card']}; selection-background-color: {p['accent']}; }}
    QCheckBox {{ spacing: 8px; }}
    QPlainTextEdit {{ background: {p['card']}; border: 1px solid {p['border']}; border-radius: {r['lg']}px;
                      font-family: Consolas; font-size: 12px; }}
    QProgressBar {{ background: {p['input']}; border: none; border-radius: 4px; max-height: 8px; }}
    QProgressBar::chunk {{ background: {p['accent']}; border-radius: 4px; }}
    #Sidebar QLineEdit {{ background: {p['card']}; border: 1px solid {p['border']}; border-radius: {r['md']}px; padding: 6px 8px; }}
    #Sidebar QLineEdit:focus {{ border-color: {p['purple']}; }}
    #Sidebar QListWidget {{ background: {p['card']}; border: 1px solid {p['border']}; border-radius: {r['md']}px; outline: 0; }}
    #Sidebar QListWidget::item {{ padding: 4px 6px; }}
    #Sidebar QListWidget::item:selected, #Sidebar QListWidget::item:hover {{ background: {p['card_hover']}; }}
    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
    QScrollBar::handle:vertical {{ background: {p['border']}; border-radius: 4px; min-height: 30px; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
    QSlider::groove:horizontal {{ height: 4px; background: {p['input']}; border-radius: 2px; }}
    QSlider::handle:horizontal {{ background: {p['accent']}; width: 14px; margin: -6px 0; border-radius: 7px; }}
    #StatusBar {{ color: {p['muted']}; padding: 4px 16px; }}
    #StatusBar[fg="iyi"] {{ color: {TONES['iyi']}; }}
    #StatusBar[fg="sorun"] {{ color: {TONES['sorun']}; }}
    {tones}
    QFrame[banner] QLabel {{ color: white; background: transparent; }}
    """
