"""Oyunlar menüsü: oyun kartları ızgarası; bir karta basınca o oyunun kendi alt sayfası açılır (üstte "← Oyunlar").

İlk bakışta "Oyunu başlat" ve "Önerilen ayarları uygula"; diğerleri varsayılan olarak kapalı "Gelişmiş ayarlar"
bölümünde. Her terimin yanında tek cümlelik açıklama veren (i) düğmesi var.

Kalıcı ayarlar (öncelik, GPU tercihi, tam ekran optimizasyonları): kaydedince motordan yazılır ve Değişiklikler'den geri
alınır. "Oyun sırasında" seçenekleri (Rahatsız etme, güç planı, Steam indirme uyarısı…) düz anahtarlardır, varsayılan
KAPALI, oyun başına saklanır; YALNIZCA "Hazırla" / "Oyunu başlat"a basınca uygulanır, oyun kapanınca ya da "Geri al"la
geri alınır. Arka planda izleyici YOK (oyun izleyici 7 Kasım 2026'da kaldırıldı). Anti-cheat'li oyunda yalnızca oyun
sürecine dokunmayanlar görünür (profiles.runtime_options); anti-cheat süreçlerine hiçbir ayar uygulanmaz.
"""

import os
import time

from PySide6.QtCore import QFileInfo, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (QButtonGroup, QComboBox, QFileDialog, QFileIconProvider, QLabel, QMenu, QProgressBar, QPushButton,
                               QVBoxLayout, QWidget)

from app.core import i18n, settings
from app.core.i18n import t, value_label
from app.games import canli_surec, discovery, oyun_ayar, presets, profiles, recorder
from app.ui import dialogs, motion, theme, widgets as w

PRIORITIES = ("Normal", "AboveNormal", "High")
GPU_PREFS = ("varsayilan", "guc_tasarrufu", "yuksek_performans")
MAX_IMAGE_BYTES = 30 * 1024 * 1024  # bundan büyük dosya resim olarak açılmaya çalışılmaz


def _when(iso):
    """"2026-11-07T12:00:05" -> "2026-11-07 12:00"."""
    return (iso or "").replace("T", " ")[:16]


class Cover(QWidget):
    """Oyun kapağı (3:4 kutu). Sıra: kullanıcının seçtiği resim -> Steam'in yerel önbelleğindeki en uygun görsel (HER görsel
    kutuyu kırparak doldurur; yatay olan ortadan kırpılır) -> oyunun exe simgesi (koyu zeminde ortada) -> adın ilk harfi
    (renk oyun adından sabit). Ağdan hiçbir şey indirilmez. Resim ve exe simgesi kart ilk çizilirken okunur (ekrana gelmeyen kartlar
    için hiç okunmaz) ve yola göre saklanır."""

    W, H = 156, 208
    ICON = 88  # exe simgesinin kart içindeki kenarı (mantıksal px)
    _cache = {}  # (dosya yolu, değişme zamanı) -> QPixmap (sayfa her yenilendiğinde yeniden çözülmesin)
    _icons = {}  # exe yolu -> QPixmap ya da None

    def __init__(self, game, path):
        super().__init__()
        self.setFixedSize(self.W, self.H)
        self.name = game["ad"]
        self.letter = (game["ad"].strip()[:1] or "?").upper()
        self.exe = game.get("exe")
        self.path = path
        self._pixmap, self._loaded = None, False

    @property
    def pixmap(self):
        """Kapak resmi (QPixmap ya da None). Dosya kart İLK ÇİZİLİRKEN çözülür/ölçeklenir: ekrana gelmeyen kartlar için hiç
        okunmaz (Oyunlar sayfası açılışı kapak sayısıyla uzamasın); çözülmüş resim sınıf önbelleğinde durur."""
        if not self._loaded:
            self._loaded = True
            self._pixmap = self._load(self.path) if self.path else None
        return self._pixmap

    @classmethod
    def _load(cls, path):
        """QPixmap ya da None: görsel kutuyu doldurur, taşan kısım ortadan kırpılır (yatay görselde yanlar gider)."""
        try:
            key = (path, os.stat(path).st_mtime_ns)  # kullanıcı aynı yola yeni resim koyunca eskisi kalmasın
        except OSError:
            return None
        if key not in cls._cache:
            source = QPixmap(path)
            result = None
            if not source.isNull():
                scaled = source.scaled(cls.W * 2, cls.H * 2, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                       Qt.TransformationMode.SmoothTransformation)
                x, y = (scaled.width() - cls.W * 2) // 2, (scaled.height() - cls.H * 2) // 2
                result = scaled.copy(x, y, cls.W * 2, cls.H * 2)
            cls._cache[key] = result
        return cls._cache[key]

    @classmethod
    def import_image(cls, game_id, source):
        """Kullanıcının dosyasını uygulama veri klasörüne kopyalar: kutuya göre ortadan kırpılıp 2x boyuta ölçeklenir ve
        JPEG olarak yazılır (özgün dosyaya dokunulmaz, yola bağlı kalınmaz). Başarılıysa True."""
        image = QImage(source)
        if image.isNull() or not discovery.USER_COVER_ID.fullmatch(game_id):
            return False
        scaled = image.scaled(cls.W * 2, cls.H * 2, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                              Qt.TransformationMode.SmoothTransformation)
        crop = scaled.copy((scaled.width() - cls.W * 2) // 2, (scaled.height() - cls.H * 2) // 2, cls.W * 2, cls.H * 2)
        folder = discovery.user_cover_dir()
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / f"{game_id}.jpg"
        temp = folder / f"{game_id}.tmp.jpg"
        if not crop.convertToFormat(QImage.Format.Format_RGB32).save(str(temp), "JPEG", 90):
            return False
        os.replace(temp, target)
        return True

    @classmethod
    def exe_icon(cls, exe):
        """Windows'un exe için verdiği büyük simge (yoksa/okunamazsa None)."""
        if exe not in cls._icons:
            pixmap = None
            if exe and os.path.isfile(exe):
                pixmap = QFileIconProvider().icon(QFileInfo(exe)).pixmap(QSize(128, 128))
                pixmap = None if pixmap.isNull() else pixmap
            cls._icons[exe] = pixmap
        return cls._icons[exe]

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        rect = QRectF(self.rect())
        clip = QPainterPath()
        clip.addRoundedRect(rect, 8, 8)
        painter.setClipPath(clip)
        if self.pixmap is not None:
            painter.drawPixmap(rect, self.pixmap, QRectF(self.pixmap.rect()))
            return
        icon = self.exe_icon(self.exe)
        if icon is not None:
            painter.fillRect(rect, QColor(theme.ICON_GROUND))
            side = self.ICON
            target = QRectF((self.W - side) / 2, (self.H - side) / 2, side, side)
            painter.drawPixmap(target, icon, QRectF(icon.rect()))
            return
        color, ground = theme.letter_style(self.name)
        painter.fillRect(rect, QColor(ground))
        painter.setPen(QColor(color))
        painter.setFont(theme.ui_font(56, bold=True))
        painter.drawText(self.rect(), int(Qt.AlignmentFlag.AlignCenter), self.letter)


class AddCard(QPushButton):
    """Izgaranın sonundaki kesikli çerçeveli "+ Oyun ekle": kapakla aynı boyda. (Stil sayfasının min-height'ı sabit
    boyu ezdiğinden boyut sizeHint ile verilir.)"""

    def sizeHint(self):
        return QSize(Cover.W + 20, Cover.H + 20)


class GameCard(w.Card):
    """Tıklanınca (kartın herhangi bir yeri; düğmeler kendi işini yapar) `opened` yayan oyun kartı."""

    opened = Signal()

    def __init__(self):
        super().__init__(spacing=8, margins=(10, 10, 10, 12), hover=True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.opened.emit()
        super().mouseReleaseEvent(event)


class GamesPage(w.Page):
    def __init__(self, app):
        super().__init__(app)
        self.store = app.game_store
        cache = discovery.load_cache()  # son tarama: açılışta hemen gösterilir, arka planda yenilenir
        self.found = cache["oyunlar"] if cache else None   # bulunan oyunlar (None: hiç taranmadı)
        self.found_time = cache["zaman"] if cache else None
        self.source_errors = (cache or {}).get("hatalar") or {}
        self.scan_error = None     # tarama tamamen başarısızsa sebebi
        self.scanning = False
        self.scanned = False       # bu oturumda tarandı mı (her açılışta bir kez arka planda taranır)
        self.scan_finished = 0.0
        self.editing = None        # seçili oyunun kimliği
        self.opened = False        # seçili oyunun alt sayfası açık mı (liste ve "Bulunan" bölümü o sırada gizli)
        self.draft = None          # seçili oyunun düzenlenen profili
        self.candidates = {}       # oyun kimliği -> .exe adayları
        self.advanced_open = False
        self.found_all = False     # bulunan oyunlar listesi tamamen açık mı
        self._live = None          # "Şu an" satırı (canlı FPS); yalnızca bu oyun sürerken ve canlı FPS çalışırken
        self._live_timer = QTimer(self)
        self._live_timer.setInterval(1000)
        self._live_timer.timeout.connect(self._refresh_live)
        self._procs = None         # canlı süreç listesi (C8): yalnızca oyun sürerken, sayfa görünürken ve kayıt ayarı açıkken
        self._procs_game = None
        self._proc_labels = {}
        self._proc_timer = QTimer(self)
        self._proc_timer.setInterval(1000)  # yalnızca koşulları denetler/ekranı tazeler; ölçüm iş parçacığı ayrı
        self._proc_timer.timeout.connect(self._procs_tick)

    def on_show(self, highlight=None):
        if self.opened:  # menüden (yeniden) gelince liste görünür; alt sayfada açık kalmaz
            self.opened = False
            self.draft = None
            if self.built:
                self.data_reloaded()
        self.ensure_built()
        # Oturum açılışında tepside başlayınca ilk tarama sürücüler hazır olmadan yapılmış olabilir: boş sonuç kalıcı olmasın.
        empty_and_old = self.scanned and not self.found and time.monotonic() - self.scan_finished > 60
        if (not self.scanned or empty_and_old) and not self.scanning:
            self._rescan()

    # ------------------------------------------------------------------ kurulum
    def build(self):
        super().build()
        if not self.scanned and not self.scanning:
            self._discover()  # uygulama açılınca (sayfa önceden kurulurken) arka planda
        self.store.ensure_anti_cheat()
        game = self.store.get(self.editing) if self.editing else None
        if game is None:
            self.editing, self.draft, self.opened = None, None, False
        if self.opened:  # oyunun alt sayfası: liste ve "Bulunan" bölümü gizli, geri düğmesi + Esc
            back = w.button(t("ui.oyun_geri"), self._back)
            back.setAccessibleName(t("ui.oyun_geri_ad"))
            self.header.addWidget(w.hbox(back, None))
            if not self.c.can_modify:
                self.body.addWidget(w.banner(t("ui.oyun_izleyici_mod"), "uyari"))
            self.body.addWidget(self._game_page(game))
            return
        self.header.addWidget(w.hbox(w.title(t("ui.menu.oyunlar")), None, self._scan_button()))
        self.header.addWidget(w.label(t("ui.oyunlar_aciklama"), muted=True))
        if not self.c.can_modify:
            self.body.addWidget(w.banner(t("ui.oyun_izleyici_mod"), "uyari"))
        if self.store.load_error:  # oyun listesi dosyası bozuktu (ör. zorla kapatma): sessizce boş liste gösterilmez
            self.body.addWidget(w.banner(t(f"ui.oyun_liste_{self.store.load_error}"), "uyari"))
        self.body.addWidget(self._picker())

    def _back(self):
        """Alt sayfadan oyun listesine dönüş (düğme ve Esc)."""
        self.opened, self.draft = False, None
        self.data_reloaded()
        QTimer.singleShot(10, self.scroll_top)

    def handle_escape(self):
        """Pencerenin Esc'i önce sayfaya sorar: alt sayfa açıksa listeye döner (önceki sayfaya değil)."""
        if self.opened:
            self._back()
            return True
        return False

    def _open(self, game_id):
        self.editing, self.draft, self.opened = game_id, None, True
        QTimer.singleShot(0, self.data_reloaded)
        QTimer.singleShot(20, self.scroll_top)

    FOUND_LIMIT = 6  # bulunan oyunlar listesi bunu aşarsa "Tümünü göster"

    def _empty(self):
        """Hiç oyun yok ve bulunan da yok (tarama bitmiş): boş durum cümlesi + 'Elle ekle'."""
        return not self.store.games and not self._remaining() and not self.scanning

    def _picker(self):
        """Oyun kapak kartları ızgarası (kapak, ad, "Hazırla"): önce listemdeki oyunlar (favoriler üstte), sonra bilgisayarda
        bulunup henüz eklenmemişler; ızgaranın sonunda kesikli çerçeveli "+ Oyun ekle". İkincil işlemler '…' menüsünde.
        Karta basınca oyunun alt sayfası açılır. Kapaklar yalnızca Steam'in yerel önbelleğinden okunur (ağ yok)."""
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        root = discovery.steam_root()
        favorites = set(settings.get("favori_oyunlar") or [])
        mine = sorted(self.store.games, key=lambda g: g["id"] not in favorites)  # kararlı sıralama: favoriler üstte
        remaining = self._remaining()
        add = self._add_card()  # ilk uygun ızgaranın sonuna konur
        if mine:
            lay.addWidget(w.section_title(t("ui.oyun_liste_benim")))
            lay.addWidget(w.flow(*(self._card(g, g["id"] in favorites, root, True) for g in mine), add, spacing=12))
            add = None
        if remaining:
            lay.addWidget(w.section_title(t("ui.oyun_liste_bulunan")))
            shown = remaining if self.found_all else remaining[:self.FOUND_LIMIT]
            lay.addWidget(w.flow(*(self._card(g, False, root, False) for g in shown), *([add] if add else []), spacing=12))
            add = None
            if len(remaining) > self.FOUND_LIMIT:
                more = w.button(t("ui.oyun_az_goster") if self.found_all else t("ui.oyun_hepsi_goster", n=len(remaining)),
                                self._toggle_found_all)
                lay.addWidget(w.hbox(more, None))
        if not self.store.games:  # liste varken tarama durumu Gelişmiş'te
            lay.addWidget(self._scan_status(len(remaining)))
        if self._empty():
            lay.addWidget(w.label(t("ui.oyun_yok"), muted=True))
        if add is not None:
            lay.addWidget(w.flow(add))
        return box

    def _add_card(self):
        card = AddCard(t("ui.oyun_ekle_kart"))
        card.setObjectName("AddCard")
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        card.clicked.connect(lambda _=False: self._add_manual())
        return card

    def _toggle_found_all(self):
        self.found_all = not self.found_all
        QTimer.singleShot(0, self.data_reloaded)

    def _card(self, game, favorite, root, own):
        card = GameCard()
        card.setFixedWidth(Cover.W + 20)
        card.opened.connect(lambda g=game, o=own: self._picked(("oyun", g["id"]) if o else ("bulunan", g)))
        card.lay.addWidget(Cover(game, discovery.cover_path(game, root)))
        name = QLabel(("★ " if favorite else "") + game["ad"])
        name.setObjectName("CardTitle")
        name.setWordWrap(True)
        name.setMinimumHeight(40)  # iki satıra kadar: kartların düğmeleri hizalı kalır
        name.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        name.setToolTip(game["ad"])
        card.lay.addWidget(name)
        card.lay.addWidget(w.label(value_label("ui.oyun_kaynak", game["kaynak"]), muted=True, size=12, wrap=False))
        if not own:
            # ikincil görünüm: birincil yeşil yalnızca listemdeki oyunlarda (yoksa sayfa yeşil bloklarla dolar)
            setup = w.button(t("ui.oyun_hazirla"), lambda _=False, g=game: self._picked(("bulunan", g)))
        else:
            setup = w.button(t("ui.oyun_hazirla"), lambda _=False, gid=game["id"]: self._picked(("oyun", gid)), primary=True)
        if isinstance(setup, QPushButton):
            setup.setAccessibleName(f"{t('ui.oyun_hazirla')}: {game['ad']}")
        if not own:
            card.lay.addWidget(setup)
            return card
        more = w.button("…", None, width=44)
        more.setToolTip(t("ui.oyun_menu"))
        more.setAccessibleName(f"{t('ui.oyun_menu')}: {game['ad']}")
        more.clicked.connect(lambda _=False, b=more, g=game, f=favorite: self._row_menu(b, g, f))
        card.lay.addWidget(w.hbox((setup, 1), more, spacing=6))
        return card

    def _row_menu(self, button, game, favorite):
        """İkincil işlemler: favori ve oyunu başlat (satırın birincil düğmesi yalnızca 'Hazırla')."""
        menu = QMenu(button)
        menu.addAction(t("ui.oyun_favori_kaldir" if favorite else "ui.oyun_favori_ekle"),
                       lambda: self._toggle_favorite(game["id"]))
        target = profiles.launch_target(game)
        if target:
            menu.addAction(t("ui.oyun_baslat"),
                           lambda: os.startfile(profiles.launch_target(game, rediscover=True) or target))
        menu.addSeparator()
        menu.addAction(t("ui.oyun_resim_sec"), lambda: self._pick_image(game))
        if discovery.user_cover(game["id"]):
            menu.addAction(t("ui.oyun_resim_kaldir"), lambda: self._remove_image(game))
        menu.exec(button.mapToGlobal(button.rect().bottomLeft()))

    def _pick_image(self, game):
        """Kullanıcının kendi resim dosyası: yerel olarak kopyalanır ve ölçeklenir (ağ yok)."""
        path, _ = QFileDialog.getOpenFileName(self, t("ui.oyun_resim_baslik"), "", t("ui.oyun_resim_filtre"))
        if not path:
            return
        try:
            ok = os.path.getsize(path) <= MAX_IMAGE_BYTES and Cover.import_image(game["id"], path)
        except OSError:
            ok = False
        if not ok:
            self.app.set_status(t("ui.oyun_resim_hata"), "uyari")
            return
        self.app.set_status(t("ui.oyun_resim_tamam", ad=game["ad"]), "iyi")
        QTimer.singleShot(0, self.data_reloaded)

    def _remove_image(self, game):
        discovery.remove_user_cover(game["id"])
        self.app.set_status(t("ui.oyun_resim_kaldirildi", ad=game["ad"]), "iyi")
        QTimer.singleShot(0, self.data_reloaded)

    def _remaining(self):
        """Bilgisayarda bulunup henüz listeye eklenmemiş oyunlar."""
        added = {g["klasor"].lower() for g in self.store.games}
        return [g for g in self.found or [] if g["klasor"].lower() not in added]

    def _toggle_favorite(self, game_id):
        favorites = list(settings.get("favori_oyunlar") or [])
        favorites.remove(game_id) if game_id in favorites else favorites.append(game_id)
        settings.set("favori_oyunlar", favorites)
        QTimer.singleShot(0, self.data_reloaded)

    def _picked(self, data):
        if not data:
            return
        kind, value = data
        if kind == "bulunan":
            self._add_found(value)
        else:
            self._open(value)

    # ------------------------------------------------------------------ oyun bulma ve ekleme
    def _scan_button(self):
        button = w.button(t("ui.oyun_taraniyor") if self.scanning else t("ui.oyun_tara"), self._rescan)
        button.setEnabled(not self.scanning)
        return button

    def _scan_status(self, remaining):
        """Tarama durumu: sürüyor (ilerleme), başarısız (sebep + Yeniden tara), kaynak hataları, son tarama zamanı."""
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        if self.scanning:
            bar = QProgressBar()
            bar.setRange(0, 0)
            bar.setObjectName("Thin")
            bar.setTextVisible(False)
            lay.addWidget(bar)
            lay.addWidget(w.label(t("ui.oyun_taraniyor"), muted=True, size=12))
        if self.scan_error:
            lay.addWidget(w.colored(t("ui.oyun_tarama_hata", hata=self.scan_error), "sorun"))
            lay.addWidget(w.hbox(w.button(t("ui.oyun_yeniden_tara"), self._rescan), None))
        elif self.source_errors and not self.scanning:
            lay.addWidget(w.colored(t("ui.oyun_kaynak_hata", liste=", ".join(
                f"{k} ({v})" for k, v in self.source_errors.items())), "uyari"))
        if self.found is not None:
            text = t("ui.oyun_bulundu", adet=len(self.found), kalan=remaining)
            if self.found_time:
                text += " " + t("ui.oyun_son_tarama", zaman=i18n.fmt_date(self.found_time))
            lay.addWidget(w.label(text, muted=True, size=12))
        elif not self.scanning and not self.scan_error:
            lay.addWidget(w.label(t("ui.okunuyor_bekle"), muted=True, size=12))
        return box

    def _rescan(self):
        self._discover()
        self.data_reloaded()

    def _discover(self):
        """Oyunları arka planda tarar; sonuç kalıcı saklanır. Hata sessizce boş listeye dönüşmez."""
        if self.scanning:
            return
        self.scanning, self.scan_error = True, None
        errors = {}

        def done(found):
            cache = discovery.save_cache(found, errors)
            self.found, self.found_time, self.source_errors = found, cache["zaman"], errors
            self.scanning, self.scanned, self.scan_finished = False, True, time.monotonic()
            self.data_reloaded()

        def failed(exc):
            self.scanning, self.scanned, self.scan_finished = False, True, time.monotonic()
            self.scan_error = str(exc) or type(exc).__name__
            self.data_reloaded()
        self.app.worker.run(lambda: discovery.discover(errors), done, failed, serial=False)

    def _add_found(self, game):
        if not game:
            return
        try:
            added = self.store.add(game["ad"], game["klasor"], game["kaynak"], game.get("exe"), game.get("baslat"))
        except ValueError:
            dialogs.show_message(self.app, t("ui.dikkat"), t("ui.oyun_korumali"), "uyari")
            return
        self._open(added["id"])

    def _add_manual(self):
        path, _ = QFileDialog.getOpenFileName(self.app, t("ui.oyun_elle_ekle"), "", "Oyun (*.exe)")
        if not path:
            return
        path = os.path.normpath(path)
        try:
            added = self.store.add(os.path.splitext(os.path.basename(path))[0], os.path.dirname(path),
                                   t("ui.oyun_elle"), path)
        except ValueError:
            dialogs.show_message(self.app, t("ui.dikkat"), t("ui.oyun_korumali"), "uyari")
            return
        self._open(added["id"])

    def _remove(self, game):
        if dialogs.ask_yes_no(self.app, t("ui.oyun_kaldir"), t("ui.oyun_kaldir_soru", ad=game["ad"])):
            self.store.remove(game["id"])
            if self.editing == game["id"]:
                self.editing, self.draft, self.opened = None, None, False
            self.app.update_game_detector()
            self.data_reloaded()

    # ------------------------------------------------------------------ seçili oyunun sayfası
    def _game_page(self, game):
        if self.draft is None:
            self.draft = dict(game["profil"])
            if game.get("exe") and self.draft.get("otomatik", True):
                # kalıcı ayarlarda sisteme güvenilir, profil dosyasına değil
                self.draft.update(profiles.read_persistent(game, self._read_reg))
        card = w.Card(spacing=12)
        card.lay.addWidget(self._game_header(game))
        if not game.get("exe"):
            card.lay.addWidget(self._exe_row(game))  # exe seçilmeden başka bir şey yapılamaz
            return card
        card.lay.addWidget(self._main_row(game))
        card.lay.addWidget(self._runtime_section(game))
        if game.get("anti_cheat"):
            card.lay.addWidget(w.colored(t("ui.oyun_anticheat_var", liste=", ".join(game["anti_cheat"])), "uyari"))
        # sayfa yeniden kurulmaz: bölüm yerinde açılır, kaydırma konumu korunur
        advanced = self._advanced(game)
        advanced.setVisible(False) if not self.advanced_open else None  # açıkken görünürlüğe dokunulmaz (ebeveynsiz setVisible(True) üst pencere olur)
        toggle = w.button(t("ui.oyun_gelismis_gizle") if self.advanced_open else t("ui.oyun_gelismis_goster"),
                          lambda: self._toggle_advanced(toggle, advanced))
        card.lay.addWidget(w.hbox(toggle, None))
        card.lay.addWidget(advanced)
        return card

    def _main_row(self, game):
        """Ana düğmeler: Oyunu başlat + Önerilen ayarları uygula (N/M). Başka bir şey ilk bakışta yok."""
        parts = []
        target = profiles.launch_target(game)
        prepared = self.app.prepared_game is not None and self.app.prepared_game["id"] == game["id"]
        wanted = bool(profiles.runtime_selected(game))
        if target:
            # tıklayınca: eski kayıtta Steam/Epic kısayolu yoksa yeniden bulunur (TEST_FAZI A7: oyun Steam'siz açılıyordu)
            def launch():
                try:
                    os.startfile(profiles.launch_target(game, rediscover=True) or target)
                except OSError:  # Steam kaldırılmış / exe silinmiş: sessiz kalmasın
                    self.app.set_status(t("ui.oyun_baslatilamadi"), "sorun")
            start = w.button(t("ui.oyun_baslat"),
                             lambda: self.app.prepare_game(game, launch=launch), primary=True)
            start.setMinimumHeight(44)
            if wanted:
                start.setToolTip(t("ui.hazirla.baslat_ipucu"))
            parts.append(start)
        if prepared:
            self._prepare_button = None  # sayfa yeniden kurulurken eski (silinmiş) düğmeye dokunulmasın
            undo = w.button(t("ui.hazirla.geri_al"), lambda: self.app.unprepare_game())
            undo.setMinimumHeight(44)
            parts.append(undo)
        else:
            prepare = w.button(t("ui.hazirla.dugme"), lambda: self.app.prepare_game(game))
            prepare.setMinimumHeight(44)
            prepare.setToolTip(t("ui.hazirla.dugme_ipucu"))
            prepare.setEnabled(self.c.can_modify)
            self._prepare_button = prepare
            parts.append(prepare)
        done, total = presets.recommended_count(game["profil"], self._two_gpus())
        if total and done == total:
            parts.append(w.badge(t("ui.oyun_oner_tamam", n=done, m=total), "iyi"))
        elif total:
            apply = w.button(t("ui.oyun_onerilen", n=done, m=total), lambda: self._apply_recommended(game))
            apply.setMinimumHeight(44)
            apply.setToolTip(t("ui.oyun_onerilen_ipucu"))
            apply.setEnabled(self.c.can_modify)
            parts.append(apply)
        row = w.hbox(*parts, None, spacing=12)
        if not prepared:
            self._prepare_button.setVisible(wanted)  # çocuk olduktan sonra: ebeveynsiz setVisible(True) üst pencere olur
        return row

    def _runtime_section(self, game):
        """"Oyun sırasında": düz anahtarlar (varsayılan KAPALI, oyun başına saklanır; sisteme hiçbir şey yazılmaz). Seçenekler
        yalnızca "Hazırla" / "Oyunu başlat"ta uygulanır. Anti-cheat'li oyunda yalnızca oyun sürecine dokunmayanlar görünür."""
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 4, 0, 0)
        lay.setSpacing(8)
        lay.addWidget(w.section_title(t("ui.hazirla.baslik")))
        lay.addWidget(w.label(t("ui.hazirla.aciklama"), muted=True, size=12))
        profile = game["profil"]
        for key in profiles.runtime_options(game):
            switch = w.ToggleSwitch()
            switch.setChecked(bool(profile.get(key)))
            switch.setEnabled(self.c.can_modify)
            switch.setAccessibleName(t(f"ui.hazirla.ad.{key}"))
            switch.toggled.connect(lambda on, k=key: self._set_runtime(game, k, on))
            text = QVBoxLayout()
            text.setSpacing(0)
            text.addWidget(w.label(t(f"ui.hazirla.ad.{key}"), bold=True))
            text.addWidget(w.label(t(f"ui.hazirla.acik.{key}"), muted=True, size=12))
            holder = QWidget()
            holder.setLayout(text)
            text.setContentsMargins(0, 0, 0, 0)
            lay.addWidget(w.hbox((holder, 1), switch, spacing=12))
        if game.get("anti_cheat"):
            lay.addWidget(w.label(t("ui.hazirla.anticheat"), muted=True, size=12))
        if self.app.steam_note and self.app.prepared_game and self.app.prepared_game["id"] == game["id"]:
            lay.addWidget(w.hbox(w.colored(t("ui.hazirla.steam_indiriyor"), "uyari"),
                                 w.button(t("ui.hazirla.steam_ac"), lambda: os.startfile("steam://open/downloads")), None))
        return box

    def _set_runtime(self, game, key, on):
        self.store.set_runtime(game["id"], key, on)
        if self.draft is not None:
            self.draft[key] = bool(on)  # taslakta eski değer kalıp "Kaydet"te ezmesin
        button = getattr(self, "_prepare_button", None)
        if button is not None:
            button.setVisible(bool(profiles.runtime_selected(game)))

    def _apply_recommended(self, game):
        """'Dengeli' hazır ayarı taslağa yazar ve kaydeder (mevcut Kaydet yolu: onay, yedek, geri alma)."""
        self.draft.update(presets.build("dengeli", self._two_gpus()))
        self._save(game)

    def _anti_cheat_fps_note(self, game):
        """Anti-cheat'li oyunda canlı FPS ve FPS kutusu hiç çalışmaz (izin yok): ayar açıksa tek satır neden."""
        if not ((settings.get("canli_fps") or settings.get("fps_widget")) and game.get("anti_cheat")):
            return None
        return w.label(t("ui.canli_fps.oyunda_kapali"), muted=True, size=12)

    def _live_line(self, game):
        if not (self.app.live_fps is not None and self._running(game)):
            self._live = None
            return None
        self._live = w.label("", size=12)
        self._live_timer.start()
        self._refresh_live()
        return self._live

    def _running(self, game):
        """Bu oyun şu an açık mı ("oyun açık mı" algılayıcısı; yalnızca canlı FPS / oyun kaydı açıkken çalışır)."""
        detector = self.app.game_detector
        return bool(detector is not None and detector.active and detector.active[0]["id"] == game["id"])

    def _refresh_live(self):
        live, label = self.app.live_fps, self._live
        if live is None or label is None:
            self._live_timer.stop()
            return
        try:
            if not label.isVisible():
                return
            snap = live.snapshot()
            key = snap["durum"]
            if key == "olculuyor" and snap["dusus"]:
                text = t("ui.canli_fps.dusus", fps=snap["fps"], onceki=snap["dusus"]["onceki_fps"])
            elif key == "olculuyor":
                text = t("ui.canli_fps.olculuyor", fps=snap["fps"])
            else:
                text = t(f"ui.canli_fps.{key}")
            full = self.app.vram_dolu()
            if full:
                text += chr(10) + t("ui.canli_fps.vram_dolu", yuzde=full)
            label.setText(text)
        except RuntimeError:  # sayfa yeniden kurulurken satır silinmiş olabilir
            self._live = None
            self._live_timer.stop()

    # ------------------------------------------------------------------ canlı süreç listesi (C8)
    def _procs_wanted(self):
        game = self._procs_game
        return bool(game is not None and settings.get("oyun_kaydi") and self._running(game))

    def _procs_card(self, game):
        """İki grup (Uygulamalar / Arka plan): toplam CPU% + en çok kullanan 5 program. "Oyun oturumu kaydı" kapalıysa yok."""
        self._procs_game = game
        if not self._procs_wanted():
            self._procs_stop()
            return None
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(w.label(t("ui.canli_surec.baslik"), bold=True, size=12))
        columns, grid = w.grid(2, spacing=16)
        self._proc_labels = {}
        for i, group in enumerate(("uygulamalar", "arka_plan")):
            head = w.label(t(f"ui.canli_surec.{group}"), bold=True, size=12)
            body = w.label(t("ui.canli_surec.olculuyor"), muted=True, size=12, plain=True)
            grid.addWidget(head, 0, i)
            grid.addWidget(body, 1, i)
            grid.setRowStretch(1, 1)
            self._proc_labels[group] = (head, body)
        lay.addWidget(columns)
        lay.addWidget(w.label(t("ui.canli_surec.not"), muted=True, size=11))
        self._procs_fill()  # sayfa yeniden kurulunca "Ölçülüyor…" yanıp sönmesin
        self._proc_timer.start()
        return box

    def _procs_stop(self):
        self._proc_timer.stop()
        procs, self._procs = self._procs, None
        if procs is not None:
            procs.stop()

    def _procs_tick(self):
        if not self._procs_wanted():  # oyun bitti ya da ayar kapandı: iş parçacığı da sayaç da kapanır
            self._procs_stop()
            return
        if not (self.isVisible() and not self.window().isMinimized()):  # sayfa görünmüyor: ölçüm HİÇ çalışmaz
            if self._procs is not None:
                self._procs.stop()
                self._procs = None
            return
        if self._procs is None:
            self._procs = canli_surec.LiveProcesses(os.path.basename(self._procs_game.get("exe") or ""))
            self._procs.start()
        self._procs_fill()

    def _procs_fill(self):
        snap = self._procs.snapshot() if self._procs is not None else None
        if snap is None:
            return
        try:
            for group, (head, body) in self._proc_labels.items():
                data = snap[group]
                head.setText(t("ui.canli_surec.grup", ad=t(f"ui.canli_surec.{group}"),
                               yuzde=i18n.fmt_percent(data["toplam"], 1)))
                lines = [f"{p['ad']}  {i18n.fmt_percent(p['cpu'], 1)}" for p in data["liste"]]
                body.setText(chr(10).join(lines) or t("ui.canli_surec.bos"))
        except RuntimeError:  # sayfa yeniden kurulurken etiketler silinmiş olabilir
            self._proc_labels = {}

    def _game_header(self, game):
        name = QLabel(game["ad"])
        name.setObjectName("Title")
        parts = [w.IconTile(theme.ICONS["oyunlar"], theme.category_color("oyunlar"), 40),
                 (name, 1), w.badge(value_label("ui.oyun_kaynak", game["kaynak"]), "notr")]
        if game.get("anti_cheat"):
            badge = w.badge(t("ui.anti_cheat_rozet", liste=", ".join(game["anti_cheat"])), "uyari")
            badge.setToolTip(t("ui.anti_cheat_oyun", liste=", ".join(game["anti_cheat"])))
            parts.append(badge)
        if self._running(game):
            parts.append(w.badge(t("ui.oyun_calisiyor"), "iyi"))
        favorites = settings.get("favori_oyunlar") or []
        star = w.button("★" if game["id"] in favorites else "☆", lambda: self._toggle_favorite(game["id"]))
        star.setToolTip(t("ui.oyun_favori_kaldir" if game["id"] in favorites else "ui.oyun_favori_ekle"))
        parts.append(star)
        return w.hbox(*parts, spacing=10)

    @staticmethod
    def _duration(seconds):
        return t("ui.oyun_kayit.dk", n=round(seconds / 60)) if seconds >= 90 else t("ui.oyun_kayit.sn", n=seconds)

    def _usage_lines(self, card, usage):
        """Kaynak kullanımı (yalnızca kayıt açıkken alınmış oturumlarda). Uyarı penceresi yok: sakin satırlar."""
        self._fps_lines(card, usage)
        if usage.get("ornek", 0) < 2:
            if not usage.get("fps"):  # yalnızca FPS alınan oturumda "kayıt yetersiz" denmez
                card.lay.addWidget(w.label(t("ui.oyun_kayit.yetersiz"), muted=True, size=12))
            return
        card.lay.addWidget(w.label(t("ui.oyun_kayit.baslik", sure=self._duration(usage["sure"])), bold=True, size=12))
        for key in ("cpu", "gpu", "ram", "disk"):
            if usage.get(key):
                card.lay.addWidget(w.label(t("ui.oyun_kayit.satir", ad=t(f"ui.oyun_kayit.{key}"), ort=usage[key]["ort"],
                                             maks=usage[key]["maks"]), size=12))
        for key in ("cpu", "ram"):
            if usage.get(f"{key}_yuksek_sn", 0) >= 10:
                card.lay.addWidget(w.label(t(f"ui.oyun_kayit.esik_{key}", sure=self._duration(usage[f"{key}_yuksek_sn"])),
                                           muted=True, size=12))
        if usage.get("arka_plan"):
            card.lay.addWidget(w.label(t("ui.oyun_kayit.arka", liste=", ".join(f"{p['ad']} {i18n.fmt_percent(p['cpu'])}" for p in usage["arka_plan"])),
                                       muted=True, size=12, plain=True))

    def _fps_lines(self, card, usage):
        """Canlı FPS özeti ve düşüşler (yalnızca canlı FPS çalışmış oturumda). Sakin satırlar, uyarı penceresi yok."""
        fps = usage.get("fps")
        if not fps:
            return
        card.lay.addWidget(w.label(t("ui.canli_fps.ozet", min=round(fps["min"]), ort=round(fps["ort"]), maks=round(fps["maks"])),
                                   bold=True, size=12))
        drops = usage.get("fps_dususleri") or []
        if not drops:
            card.lay.addWidget(w.label(t("ui.canli_fps.dusus_yok"), muted=True, size=12))
        for drop in drops[:5]:
            card.lay.addWidget(w.label(t("ui.canli_fps.dusus_satir", dk=drop["sn"] // 60 + 1, sure=drop["sure_sn"],
                                         onceki=drop["onceki_fps"], dusuk=drop["en_dusuk_fps"]), muted=True, size=12))
        if len(drops) > 5:
            card.lay.addWidget(w.label(t("ui.canli_fps.dusus_daha", n=len(drops) - 5), muted=True, size=12))

    def _session_card(self, name, usage):
        """Son oyun oturumu: kaynak kullanımı ve canlı FPS özeti (kayıt veya canlı FPS açıkken alınmış oturumlarda)."""
        card = w.Card(spacing=4)
        head = QLabel(t("ui.oyun_oturum.baslik", ad=name))
        head.setObjectName("CardTitle")
        card.lay.addWidget(head)
        self._usage_lines(card, usage)
        return card

    def _preset_row(self):
        """Görsel öncelik / Dengeli / Performans: profil taslağını doldurur, "Kaydet"e kadar uygulanmaz."""
        now = presets.current(self.draft, self._two_gpus())
        group = QButtonGroup(self)
        buttons = []
        for key in presets.PRESETS:
            button = w.button(t(f"ui.oyun_hazir.{key}"), lambda _=False, k=key: self._apply_preset(k))
            button.setCheckable(True)
            button.setProperty("segment", True)
            button.setMinimumHeight(34)
            button.setChecked(now == key)
            button.setEnabled(self.c.can_modify)
            group.addButton(button)
            buttons.append(button)
        row = w.hbox(self._caption(t("ui.oyun_hazir_ayar"), "hazir_ayar"), (w.flow(*buttons), 1), spacing=12)
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        lay.addWidget(row)
        lay.addWidget(w.label(t("ui.oyun_hazir.not"), muted=True, size=12))
        return box

    def _file_section(self, game_id):
        """Oyunun kendi ayar dosyası: sakla / geri yükle / sıfırla / geri al (app/games/oyun_ayar.py). Durum arka planda okunur."""
        holder = QWidget()
        lay = QVBoxLayout(holder)
        lay.setContentsMargins(0, 4, 0, 4)
        lay.setSpacing(4)
        lay.addWidget(w.label(t("ui.oyun_ayar.baslik"), bold=True))
        lay.addWidget(w.label(t("ui.oyun_ayar.aciklama"), muted=True, size=12))
        lay.addWidget(w.label(t(f"ui.oyun_ayar.risk.{game_id}"), muted=True, size=12))
        state = w.label(t("ui.oyun_ayar.okunuyor"), muted=True, size=12)
        lay.addWidget(state)

        def loaded(info):
            try:
                self._file_buttons(lay, state, game_id, info)
            except RuntimeError:  # sayfa bu arada yeniden kuruldu, eski kart silindi
                pass

        self.app.worker.run(lambda: oyun_ayar.status(game_id), loaded, lambda _exc: None, serial=False)
        return holder

    def _file_buttons(self, lay, state, game_id, info):
        copies = info["kopyalar"]
        if info["calisiyor"]:
            state.setText(t("ui.oyun_ayar.acik"))
        elif not (info["var"] or copies or info["geri_al"]):
            state.setText(t("ui.oyun_ayar.yok"))
        else:
            state.setText(t("ui.oyun_ayar.son_kopya", tarih=_when(copies[0]["tarih"])) if copies else t("ui.oyun_ayar.kopya_yok"))
        actions = [("sakla", info["var"], None, None),
                   ("geri_yukle", copies, copies and copies[0]["ad"], copies and _when(copies[0]["tarih"])),
                   ("sifirla", info["sifirla"] and info["var"], None, None),
                   ("geri_al", info["geri_al"], info["geri_al"], None)]
        buttons = []
        for kind, shown, arg, when in actions:
            if shown:
                button = w.button(t(f"ui.oyun_ayar.{kind}"), lambda _=False, k=kind, a=arg, d=when: self._file_action(game_id, k, a, d))
                button.setEnabled(self.c.can_modify and not info["calisiyor"])
                buttons.append(button)
        if buttons:
            lay.addWidget(w.flow(*buttons))

    def _file_action(self, game_id, kind, arg, when):
        if kind != "sakla" and not dialogs.ask_yes_no(self.app, t("ui.dikkat"), t(f"ui.oyun_ayar.soru.{kind}", tarih=when)):
            return
        func = {"sakla": lambda: oyun_ayar.save(game_id), "geri_yukle": lambda: oyun_ayar.restore(game_id, arg),
                "sifirla": lambda: oyun_ayar.reset(game_id), "geri_al": lambda: oyun_ayar.undo(game_id, arg)}[kind]

        def done(_result):
            self.app.set_status(t(f"ui.oyun_ayar.tamam.{kind}"), "iyi")
            QTimer.singleShot(0, self.data_reloaded)

        def failed(exc):
            open_ = isinstance(exc, RuntimeError) and str(exc) == "calisiyor"
            self.app.set_status(t("ui.oyun_ayar.hata_acik" if open_ else "ui.oyun_ayar.hata"), "sorun")
            QTimer.singleShot(0, self.data_reloaded)

        self.app.worker.run(func, done, failed, serial=False)

    def _apply_preset(self, preset):
        self.draft.update(presets.build(preset, self._two_gpus()))
        QTimer.singleShot(0, self.data_reloaded)

    def _two_gpus(self):
        hw = ((self.c.scan or {}).get("bolumler") or {}).get("donanim") or {}
        return len(hw.get("gpu") or []) >= 2

    def _dual_gpu(self):
        hw = ((self.c.scan or {}).get("bolumler") or {}).get("donanim") or {}
        return len(hw.get("gpu") or []) >= 2 or self.draft.get("gpu_tercihi") != "varsayilan"

    # ------------------------------------------------------------------ kontroller
    def _info(self, info_key, title):
        return w.info_button(lambda: dialogs.show_message(self.app, title, t(f"ui.oyun_bilgi.{info_key}"), "bilgi"))

    def _caption(self, text, info_key, bold=True):
        label = w.label(text, bold=bold, wrap=False)
        label.setMinimumWidth(230)
        return w.hbox(label, self._info(info_key, text), spacing=6)

    def _switch_row(self, key, text, info_key, bold=True):
        switch = w.ToggleSwitch()
        switch.setChecked(bool(self.draft.get(key, key == "otomatik")))
        switch.setEnabled(self.c.can_modify)
        switch.toggled.connect(lambda on: self._set(key, on, rebuild=key == "otomatik"))
        return w.hbox(self._caption(text, info_key, bold), None, switch)

    def _segment_row(self, text, key, info_key, values, label_of):
        group = QButtonGroup(self)
        buttons = []
        for value in values:
            button = w.button(label_of(value), lambda _=False, v=value: self._set(key, v))
            button.setCheckable(True)
            button.setProperty("segment", True)
            button.setMinimumHeight(34)
            button.setChecked(self.draft.get(key) == value)
            button.setEnabled(self.c.can_modify)
            group.addButton(button)
            buttons.append(button)
        return w.hbox(self._caption(text, info_key), (w.flow(*buttons), 1), spacing=12)

    def _set(self, key, value, rebuild=False):
        self.draft[key] = value
        if rebuild:
            QTimer.singleShot(0, self.data_reloaded)

    def _toggle_advanced(self, toggle, box):
        self.advanced_open = not self.advanced_open
        toggle.setText(t("ui.oyun_gelismis_gizle") if self.advanced_open else t("ui.oyun_gelismis_goster"))
        motion.expand(box, self.advanced_open)

    def _advanced(self, game):
        """Katlanır bölüm: ayarlar, Kaydet, ölçüm/kayıt, oyun dosyası ve liste, rehberler. İlk bakışta kapalı."""
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        lay.addWidget(w.label(t("ui.oyun_gelismis_aciklama"), muted=True, size=12))
        lay.addWidget(w.section_title(t("ui.oyun_grp.ayar")))
        lay.addWidget(self._preset_row())
        lay.addWidget(self._switch_row("otomatik", t("ui.oyun_otomatik"), "otomatik", bold=True))
        if not self.draft.get("otomatik", True):
            lay.addWidget(w.label(t("ui.oyun_otomatik_kapali"), muted=True, size=12))
        lay.addWidget(self._segment_row(t("ui.oyun_oncelik"), "oncelik", "oncelik", PRIORITIES,
                                        lambda v: t(f"ui.oncelik.{v}")))
        if self._dual_gpu():
            lay.addWidget(self._segment_row(t("ui.oyun_gpu"), "gpu_tercihi", "gpu", GPU_PREFS,
                                            lambda v: t(f"ui.gpu_tercihi.{v}")))
        lay.addWidget(self._switch_row("fso_kapali", t("ui.oyun_fso"), "fso", bold=False))
        save = w.button(t("ui.oyun_kaydet"), lambda: self._save(game), primary=True)
        save.setEnabled(self.c.can_modify)
        save.setMinimumHeight(36)
        lay.addWidget(w.hbox((w.label(t("ui.oyun_kaydet_aciklama"), muted=True, size=12), 1), save))

        measured = [x for x in (self._anti_cheat_fps_note(game), self._live_line(game),
                                self._procs_card(game)) if x is not None]
        summary = self.app.last_sessions.get(game["id"])
        usage = (summary or {}).get("kaynak") or recorder.latest_for(game["id"])  # yeniden açıldıysa son kayıtlı oturum
        if usage:
            measured.append(self._session_card(game["ad"], usage))
        if measured:
            lay.addWidget(w.section_title(t("ui.oyun_grp.olcum")))
            for widget in measured:
                lay.addWidget(widget)

        lay.addWidget(w.section_title(t("ui.oyun_grp.dosya")))
        lay.addWidget(self._exe_row(game))
        file_id = oyun_ayar.find(game["ad"])  # oyunun KENDİ ayar dosyası: sakla / geri yükle (oyun içi ayar rehberi Rehber sayfasında)
        if file_id:
            lay.addWidget(self._file_section(file_id))
        lay.addWidget(w.colored(t("ui.anti_cheat_oyun", liste=", ".join(game["anti_cheat"])), "uyari") if game.get("anti_cheat")
                      else w.label(t("ui.anti_cheat_bulunamadi"), muted=True, size=12))
        lay.addWidget(w.colored(t("ui.anti_cheat_genel"), "uyari"))
        lay.addWidget(self._scan_status(len(self._remaining())))
        lay.addWidget(w.hbox(w.button(t("ui.oyun_kaldir"), lambda: self._remove(game)), None))

        return box

    def _exe_row(self, game):
        combo = QComboBox()
        options = self.candidates.get(game["id"])
        if options is None:
            self.candidates[game["id"]] = []
            self.app.worker.run(lambda: discovery.exe_candidates(game["klasor"]),
                                lambda found: self._candidates_found(game["id"], found), serial=False)
            options = []
        for path in ([game["exe"]] if game.get("exe") else []) + [p for p in options if p != game.get("exe")]:
            combo.addItem(os.path.relpath(path, game["klasor"]) if path.lower().startswith(game["klasor"].lower())
                          else path, path)
        combo.setMinimumWidth(360)
        combo.activated.connect(lambda _i: self._set_exe(game, combo.currentData()))
        browse = w.button(t("ui.gozat"), lambda: self._browse_exe(game))
        return w.hbox(w.label(t("ui.oyun_exe"), muted=True, wrap=False), combo, browse, None)

    def _candidates_found(self, game_id, found):
        self.candidates[game_id] = found
        game = self.store.get(game_id)
        if game and not game.get("exe") and found:
            try:
                self.store.set_exe(game_id, found[0])
            except ValueError:
                pass
        if self.editing == game_id:
            self.data_reloaded()

    def _set_exe(self, game, path):
        if not path or path == game.get("exe"):
            return
        try:
            self.store.set_exe(game["id"], path)
        except ValueError:
            dialogs.show_message(self.app, t("ui.dikkat"), t("ui.oyun_korumali"), "uyari")
            return
        self.draft = None
        QTimer.singleShot(0, self.data_reloaded)

    def _browse_exe(self, game):
        path, _ = QFileDialog.getOpenFileName(self.app, t("ui.oyun_exe"), game["klasor"], "Oyun (*.exe)")
        if path:
            self._set_exe(game, os.path.normpath(path))

    def _read_reg(self, root, path, name):
        try:
            value = self.c.engine.system.read_reg(root, path, name)
        except Exception:
            return None
        return value[0] if value else None

    # ------------------------------------------------------------------ kaydet
    def _save(self, game):
        draft = dict(self.draft)
        if draft.get("otomatik", True) and draft["oncelik"] == "High" and \
                not dialogs.ask_yes_no(self.app, t("ui.dikkat"), t("ui.oncelik_yuksek_onay")):
            return
        self.store.update_profile(game["id"], draft)
        # Otomatik uygulama kapalıysa seçimler saklanır ama sisteme Windows varsayılanı yazılır.
        effective = draft if draft.get("otomatik", True) else dict(draft, **profiles.PERSISTENT_DEFAULTS)
        changes = profiles.persistent_changes(game, effective, self._read_reg)

        def next_change():
            if not changes:
                self.app.update_game_detector()
                self.app.set_status(t("ui.oyun_kaydedildi", ad=game["ad"]), "iyi")
                self.draft = None
                self.data_reloaded()
                return
            change_id, name_key, step, value = changes.pop(0)
            self.app.apply_custom(change_id, t(name_key, ad=game["ad"]), [step], [value], next_change,
                                  restart="uygulama")
        next_change()
