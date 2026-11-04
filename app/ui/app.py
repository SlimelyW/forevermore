"""Ana pencere: kenar menü, sayfalar, uyarı şeritleri ve durum satırı.

Hız düzeni:
- Pencere, önceki oturumun önbelleğiyle HEMEN açılır.
- Ayar durumları ve tarama arka planda, paralel okunur; her ayarın satırı
  kendi durumu gelince tek başına güncellenir (sayfa yeniden çizilmez).
- Sayfalar ilk kez açılınca veya boşta sırayla önceden kurulur.

Ayar değiştirme akışı:
  1. Salt okunur/önizleme modunda değişiklik yapılmaz.
  2. Onay: "dikkatli" (veya uyarılı) ayarı açarken tek onay penceresi;
     "riskli" ayarı açarken VE kapatırken/eski haline getirirken iki ayrı ekran.
  3. Oturumdaki ilk değişiklikte geri yükleme noktası (bekleme penceresiyle).
  4. İşlem arka planda; sonuç durum satırında ve gerekirse pencerede.
"""

import datetime
import os
import sys
from ctypes import wintypes

from PySide6.QtCore import QEvent, QProcess, QRectF, Qt, QTimer
from PySide6.QtGui import QAction, QColor, QFont, QGuiApplication, QIcon, QKeySequence, QPainter, QPen, QPixmap, QShortcut
from PySide6.QtWidgets import (QAbstractSpinBox, QApplication, QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit,
                               QListWidget, QMainWindow, QMenu, QPlainTextEdit, QPushButton, QScrollArea, QStackedWidget,
                               QSystemTrayIcon, QVBoxLayout, QWidget)

from app.core import admin, consent, guncelleme, i18n, log, paths, settings, tek_ornek
from app.core.i18n import fmt_date, t
from app.engine import profiles as profile_module, system_protection
from app.ui import dialogs, motion, theme, widgets as w
from app.ui.controller import MODE_NORMAL, MODE_PREVIEW, OWN_PAGE, Controller, is_manual
from app.ui.live_monitor import LiveMonitor
from app.ui.page_boost import BoostPage
from app.ui.page_kaldirici import UninstallerPage
from app.ui.page_category import CategoryPage, ManualPage
from app.ui.page_other import ChangesPage, ProfilesPage, ReportPage
from app.ui.page_details import PcDetailsPage
from app.ui.page_settings import AboutPage, SettingsPage, about_data, donate_url_ok
from app.games.profiles import GameStore
from app.games.runtime import GameSession, GameWatcher, ProcessOps
from app.ui.page_games import GamesPage
from app.ui.page_measure import MeasurePage
from app.ui.page_startup import StartupPage
from app.ui.page_summary import SummaryPage
from app.ui.search import SearchBox
from app.ui.worker import StallWatch, Worker

_log = log.get("ui")




class NavItem(motion.HoverFade, QFrame):
    hover = True
    hover_radius = 8

    def __init__(self, key, glyph, text, on_click, on_hover=None):
        super().__init__()
        self._on_hover = on_hover
        self.setObjectName("NavItem")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)  # klavyeyle gezilir; Enter/Boşluk açar
        self.setAccessibleName(text)
        self.key = key
        self._on_click = on_click
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 8, 10, 8)
        lay.setSpacing(10)
        marker = QFrame()
        marker.setObjectName("NavMarker")
        marker.setFixedSize(3, 18)
        lay.addWidget(marker)
        icon = QLabel(glyph)
        icon.setFont(theme.icon_font(16))
        icon.setFixedWidth(20)
        icon.setStyleSheet(f"color: {theme.category_color(key)}; background: transparent;")  # kategori rengi
        lay.addWidget(icon)
        lay.addWidget(QLabel(text), 1)
        self.count = QLabel("")
        self.count.setObjectName("NavCount")
        self.count.setVisible(False)
        theme.tabular(self.count)
        lay.addWidget(self.count)

    def set_selected(self, on):
        if bool(self.property("selected")) == on:  # değişmeyen öğe yeniden boyanmaz (24 menü öğesi × stil = ~19 ms)
            return
        self.setProperty("selected", on)
        w.repolish(self)
        for child in self.findChildren(QFrame):
            w.repolish(child)

    def set_count(self, on, total):
        self.count.setVisible(total > 0)
        self.count.setText(f"{on} / {total}")

    def set_tag(self, text):
        """Sayı yerine kısa etiket (ör. "PRO"); boş metin gizler."""
        self.count.setVisible(bool(text))
        self.count.setText(text)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self._on_click(self.key)
        else:
            super().keyPressEvent(event)

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.update()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.hasFocus():  # net odak halkası (mor yalnızca vurgu: odak halkası)
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(QPen(QColor(theme.palette()["purple"]), 2))
            painter.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 8, 8)

    def enterEvent(self, event):
        if self._on_hover:
            self._on_hover(self.key)
        super().enterEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._on_click(self.key)


class MainWindow(QMainWindow):
    # Testler sahte örnekleyici verir; None = Windows performans sayaçları.
    live_sampler_factory = None

    def __init__(self, controller):
        super().__init__()
        self.c = controller
        suffix = "" if controller.mode == MODE_NORMAL else f" — {t('ui.mod.' + controller.mode)}"
        self.setWindowTitle(t("uygulama.ad") + suffix)
        self.resize(1240, 820)
        self.setMinimumSize(900, 560)  # 1366×768 ekranda %125 ölçekte (≈1093×614 mantıksal) sığar
        self.worker = Worker()
        # Testlerde olay döngüsü testler arasında dönmez; orada kapalı (tests/__init__.py).
        self.stall_watch = StallWatch(self) if os.environ.get("PCOPT_BEKCI") != "kapali" else None
        self.live_monitor = LiveMonitor(self.live_sampler_factory)
        self.game_store = GameStore()
        self.game_watcher = None
        self.tray = None
        self.quitting = False
        self.skip_save = False  # "Kaldırmaya hazırla" verileri sildiyse hiçbir şey yazılmaz
        self.pages = {}
        self.current = None
        self._history = []   # önceki ekranlar (Alt+Sol / fare geri / Esc); sayfalar yığında kalır, kaydırma korunur
        self.busy = False
        self.scanning = False

        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        self.toast = w.Toast(self)
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._build_sidebar())
        right = QVBoxLayout()
        right.setContentsMargins(18, 12, 12, 4)
        right.setSpacing(6)
        self.banner_area = QVBoxLayout()
        self.banner_area.setSpacing(6)
        right.addLayout(self.banner_area)
        self.stack = QStackedWidget()
        right.addWidget(self.stack, 1)
        self.status = QLabel("")
        self.status.setObjectName("StatusBar")
        right.addWidget(self.status)
        outer.addLayout(right, 1)

        self._counts_timer = QTimer(self)
        self._counts_timer.setSingleShot(True)
        self._counts_timer.timeout.connect(self._update_counts)
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(lambda: self.worker.run(self.c.save_cache, serial=False))

        had_cache = self.c.load_cache()
        self.update_banners()
        self._auto_update_check()
        self.navigate("ozet")
        QShortcut(QKeySequence("Alt+Left"), self, self.go_back)
        QShortcut(QKeySequence("Esc"), self, self._escape)
        self._update_counts()
        if had_cache:
            self.set_status(t("ui.onbellekten_gosteriliyor"))
        QTimer.singleShot(0, self._start_background)
        QTimer.singleShot(300, self._prebuild_pages)
        QTimer.singleShot(500, self._start_games)
        self.update_tray()

    # ------------------------------------------------------------------ düzen
    def _build_sidebar(self):
        bar = QFrame()
        bar.setObjectName("Sidebar")
        bar.setMinimumWidth(252)  # uzun çeviriler için genişleyebilir; 16 px kaydırma çubuğu payı
        bar.setMaximumWidth(320)
        # Kısa pencerede / "Daha fazla" açıkken menü sıkışmasın: içerik kaydırılabilir.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.viewport().setAutoFillBackground(False)  # yoksa menü zemini açık gri boyanır
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        holder = QVBoxLayout(bar)
        holder.setContentsMargins(0, 0, 0, 0)
        holder.addWidget(scroll)
        inner = QWidget()
        scroll.setWidget(inner)
        inner.setAutoFillBackground(False)  # setWidget açar; menü zemini #Sidebar'dan gelmeli
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(10, 18, 10, 10)
        lay.setSpacing(2)
        name = QLabel(t("uygulama.ad"))
        name.setObjectName("Brand")
        mark = w.logo(40) or w.IconTile("F", theme.palette()["accent"], 38, letter=True)
        brand = w.hbox(mark, name, None, spacing=10)
        brand.layout().setContentsMargins(4, 0, 0, 0)
        lay.addWidget(brand)
        lay.addSpacing(18)
        self.nav = {}
        rare = {"PLC", "baslangic", "elle"}  # "Daha fazla" altında katlanır
        entries = [t("ui.menu.grup.basla"), ("ozet", t("ui.menu.ozet")), ("pc_detay", t("ui.menu.pc_detay")),
                   ("profiller", t("ui.menu.profiller")), ("oyunlar", t("ui.menu.oyunlar")), ("boost", t("ui.menu.boost")),
                   ("kaldirici", t("ui.menu.kaldirici")),
                   t("ui.menu.grup.ayarlar")]
        for c in self.c.categories:
            entries.append((c["id"], t(f"kategori.{c['id']}")))
            if c["id"] == "SYS":  # başlangıç ve servis yöneticisi Sistem'in hemen altında
                entries.append(("baslangic", t("ui.menu.baslangic")))
        entries.append(("elle", t("ui.menu.elle")))
        entries += [t("ui.menu.grup.takip"), ("degisiklikler", t("ui.menu.degisiklikler")),
                    ("rapor", t("ui.menu.rapor")), ("olcum", t("ui.menu.olcum")),
                    t("ui.menu.grup.uygulama"), ("ayarlar", t("ui.menu.ayarlar")),
                    ("bilgi", t("ui.menu.bilgi"))]
        self.nav_rare = []
        for entry in entries:
            if isinstance(entry, str):
                head = QLabel(entry.upper())
                head.setObjectName("NavGroup")
                lay.addSpacing(10)
                lay.addWidget(head)
                continue
            key, text = entry
            item = NavItem(key, theme.ICONS.get(key, ""), text, self.navigate, self._hover_nav)
            if key in rare:
                self.nav_rare.append(item)
                item.setVisible(False)
            lay.addWidget(item)
            self.nav[key] = item
            if key == "elle":
                self.nav_more = QLabel(t("ui.menu.daha_fazla"))
                self.nav_more.setObjectName("NavMore")
                self.nav_more.setCursor(Qt.CursorShape.PointingHandCursor)
                self.nav_more.mousePressEvent = lambda _e: self._show_rare(not self.nav_rare[0].isVisible())
                lay.addWidget(self.nav_more)
        pages = [e for e in entries if not isinstance(e, str)]
        self.search_box = SearchBox(self.c.tweaks, pages, self.go_to_tweak, self.navigate)
        lay.insertWidget(2, self.search_box)  # logo ile "Başla" arasında; marka satırından boşlukla ayrı
        lay.insertSpacing(3, 8)
        QShortcut(QKeySequence("Ctrl+K"), self, self.search_box.focus)
        lay.addStretch(1)
        url = about_data()["bagis_url"]
        if donate_url_ok(url):  # kaydırma alanının dışında: menü uzasa da hep görünür; sessiz, açılır pencere yok
            donate = QPushButton(t("ui.menu.bagis"))
            donate.setObjectName("DonateBtn")
            donate.setCursor(Qt.CursorShape.PointingHandCursor)
            donate.clicked.connect(lambda _=False: os.startfile(url))  # noqa: S606
            holder.addWidget(donate)
        return bar

    def _page(self, key):
        if key not in self.pages:
            if key == "ozet":
                page = SummaryPage(self)
            elif key == "profiller":
                page = ProfilesPage(self)
            elif key == "degisiklikler":
                page = ChangesPage(self)
            elif key == "rapor":
                page = ReportPage(self)
            elif key == "ayarlar":
                page = SettingsPage(self)
            elif key == "bilgi":
                page = AboutPage(self)
            elif key == "elle":
                page = ManualPage(self)
            elif key == "pc_detay":
                page = PcDetailsPage(self)
            elif key == "baslangic":
                page = StartupPage(self)
            elif key == "oyunlar":
                page = GamesPage(self)
            elif key == "olcum":
                page = MeasurePage(self)
            elif key == "boost":
                page = BoostPage(self)
            elif key == "kaldirici":
                page = UninstallerPage(self)
            else:
                page = CategoryPage(self, next(c for c in self.c.categories if c["id"] == key))
            self.pages[key] = page
            self.stack.addWidget(page)
        return self.pages[key]

    def _show_rare(self, on):
        for item in self.nav_rare:
            item.setVisible(on)
        self.nav_more.setText(t("ui.menu.daha_az" if on else "ui.menu.daha_fazla"))

    HISTORY_MAX = 30
    _TEXT_INPUTS = (QLineEdit, QPlainTextEdit, QAbstractSpinBox, QComboBox, QListWidget)

    def go_back(self):
        """Önceki ekrana döner (yoksa False). Önceki sayfa yığında durduğu için kaydırma konumu korunur."""
        while self._history:
            key = self._history.pop()
            if key != self.current and key in self.nav:
                self.navigate(key, _back=True)
                return True
        return False

    def _escape(self):
        """Esc: metin/seçim kutusunda yalnızca odağı bırakır (arama kutusu önce temizlenir); aksi halde önceki ekran."""
        focus = QApplication.focusWidget()
        if isinstance(focus, self._TEXT_INPUTS):
            if focus is self.search_box.edit:
                self.search_box.edit.clear()
            focus.clearFocus()
        else:
            self.go_back()

    def mousePressEvent(self, event):
        """Fare "geri" tuşu (işlenmeyen tıklama pencereye kadar çıkar): önceki ekran."""
        if event.button() == Qt.MouseButton.BackButton and self.go_back():
            event.accept()
            return
        super().mousePressEvent(event)

    def navigate(self, key, highlight=None, _back=False):
        if not _back and self.current and key != self.current:
            if not self._history or self._history[-1] != self.current:
                self._history.append(self.current)
                del self._history[:-self.HISTORY_MAX]
        if self.nav.get(key) in self.nav_rare:
            self._show_rare(True)
        for name, item in self.nav.items():
            item.set_selected(name == key)
        page = self._page(key)
        self.stack.setCurrentWidget(page)
        motion.fade_in(page)
        self.current = key
        page.on_show(highlight)

    def go_to_tweak(self, tweak_id):
        tweak = self.c.by_id.get(tweak_id)
        if tweak and tweak.get("liste_yoneticisi") in OWN_PAGE:  # kendi menüsünde yapılır
            self.navigate(OWN_PAGE[tweak["liste_yoneticisi"]])
        elif tweak and is_manual(tweak):
            self.navigate("elle", highlight=tweak_id)
        elif tweak:
            category = next(c for c in self.c.categories if c["ad"] == tweak["kategori"])
            self.navigate(category["id"], highlight=tweak_id)

    def _hover_nav(self, key):
        """Menü öğesinin üstünde duran imleç: sayfa kurulmamış/bayatsa tıklamadan önce arka planda kurulur (80 ms
        bekleme; geçip giden imleç boşuna kurdurmaz). Tarama ya da değişiklik sürerken hiçbir şey yapılmaz."""
        self._hover_key = key
        QTimer.singleShot(80, lambda: self._prebuild_hovered(key))

    def _prebuild_hovered(self, key):
        if key != getattr(self, "_hover_key", None) or key == self.current or self.busy or self.scanning:
            return
        page = self._page(key)
        if hasattr(page, "ensure_built") and (not page.built or page.stale):
            page.ensure_built()

    def _prebuild_pages(self):
        """Kategori sayfalarını boşta, birer birer kurar; ilk açılışta beklenmez."""
        keys = [c["id"] for c in self.c.categories] + ["profiller"]
        pending = [k for k in keys if k not in self.pages or not self.pages[k].built]
        if not pending:
            return
        self._page(pending[0]).ensure_built()
        QTimer.singleShot(30, self._prebuild_pages)

    # ------------------------------------------------------------------ güncelleme
    def _auto_update_check(self):
        """Kullanıcı Ayarlar'da açtıysa günde en çok bir kez yeni sürüm var mı diye bakar; yalnızca durum çubuğuna yazar."""
        if self.c.mode == MODE_PREVIEW or not settings.get("guncelleme_denetle"):
            return
        now = datetime.datetime.now(datetime.timezone.utc)
        try:
            last = datetime.datetime.fromisoformat(settings.get("guncelleme_son_deneme") or "")
        except ValueError:
            last = None
        if last is not None and last <= now and now - last < guncelleme.CHECK_INTERVAL:
            return
        settings.set("guncelleme_son_deneme", now.isoformat())
        self.worker.run(guncelleme.kontrol, lambda info: info and self.set_status(
            t("ui.guncelleme.var_kisa", surum=info["surum"])), lambda _e: None, serial=False)

    def reload_pages(self):
        """Tarama bittiğinde / toplu değişiklik sonrası: yalnız görünen sayfa hemen yeniden kurulur, diğerleri açılınca.
        Eskiden kurulmuş tüm sayfalar ana iş parçacığında birden kuruluyordu (Placebo tek başına ~2 sn): "yanıt vermiyor"."""
        for key, page in self.pages.items():
            if key == self.current:
                page.data_reloaded()
            elif page.built:
                page.stale = True
        if self.current:
            self.pages[self.current].on_show()

    # ------------------------------------------------------------------ şeritler ve durum
    def set_status(self, text, kind="bilgi"):
        self.status.setText(text)
        self.status.setProperty("fg", kind if kind in ("iyi", "sorun") else "")
        w.repolish(self.status)

    def _recover_backup(self):
        if not dialogs.ask_yes_no(self, t("ui.yedek_kurtar"), t("ui.yedek_kurtar_soru"),
                                  yes_text=t("ui.yedek_kurtar"), no_text=t("ui.vazgec")):
            return
        count = self.c.engine.store.recover()
        self.set_status(t("ui.yedek_kurtarildi", sayi=count), "iyi")
        self._after_backup_reset()

    def _dismiss_broken_backup(self):
        self.c.engine.store.dismiss_broken()
        self.set_status(t("ui.yedek_sifirlandi"), "uyari")
        self._after_backup_reset()

    def _after_backup_reset(self):
        self.update_banners()
        for tweak_id in list(self.c.by_id):
            self._tweak_updated(tweak_id)
        if self.current == "degisiklikler":
            self.pages[self.current].data_reloaded()

    def update_banners(self):
        w.clear_layout(self.banner_area)
        if self.c.mode != MODE_NORMAL:
            self.banner_area.addWidget(w.banner(t(f"ui.mod_aciklama.{self.c.mode}"), "uyari"))
        key = self.c.restart_message_key()
        if key:
            self.banner_area.addWidget(w.banner(t("ui.yeniden_gerekli") + " " + t(key), "bilgi"))
        if self.c.explorer_restart:
            self.banner_area.addWidget(w.banner(t("yeniden.gezgin"), "bilgi"))
        store = self.c.engine.store
        if store.tampered:
            buttons = [w.button(t("ui.yedek_sifirla"), self._dismiss_broken_backup)]
            if store.recoverable:
                buttons.insert(0, w.button(t("ui.yedek_kurtar"), self._recover_backup, primary=True))
            self.banner_area.addWidget(w.banner(t("ui.yedek_degistirilmis"), "sorun", *buttons))
        from app.engine import driver_tools  # noqa: WPS433
        if driver_tools.in_safe_mode():
            self.banner_area.addWidget(w.banner(t("ui.guvenli.banner_simdi"), "uyari"))
        elif self.c.engine.store.has(driver_tools.SAFE_MODE_ID):
            self.banner_area.addWidget(w.banner(t("ui.guvenli.banner"), "uyari"))

    def _update_counts(self):
        """Kenar menüde yalnızca önerilen ama açık olmayan ayar sayısı (her satırda "3 / 15" gürültüydü)."""
        waiting = {}
        if self.c.scan is not None:
            for pick in self.c.recommendations(99):
                cid = self.c.by_id[pick["id"]].get("kategori_id")
                waiting[cid] = waiting.get(cid, 0) + 1
        for category in self.c.categories:
            item = self.nav.get(category["id"])
            if item and category["id"] != "PLC":
                item.set_tag(str(waiting[category["id"]]) if waiting.get(category["id"]) else "")

    def _tweak_updated(self, tweak_id):
        for page in self.pages.values():
            page.tweak_updated(tweak_id)
        self._counts_timer.start(150)

    # ------------------------------------------------------------------ arka plan okuma
    def _start_background(self):
        """Durumları hemen, taramayı onunla birlikte başlatır (ikisi de salt okunur)."""
        self.worker.run(lambda: self.c.refresh_all(on_each=lambda tid: self.worker.call_soon(self._tweak_updated, tid)),
                        self._states_done, self._background_failed, serial=False)
        self.start_scan()

    def _states_done(self, _result):
        self._update_counts()
        self._save_timer.start(500)
        if not self.scanning:
            self.set_status(t("ui.durumlar_guncel"), "iyi")

    def _background_failed(self, _exc):
        self.set_status(t("ui.tarama_hatasi"), "sorun")

    def start_scan(self):
        if self.scanning:
            return
        self.scanning = True
        summary = self._page("ozet")
        summary.set_progress(t("ui.taraniyor"))

        def progress(done, total, name):
            self.worker.call_soon(summary.set_progress,
                                  t("tarama.ilerleme", bolum=t(f"bolum.{name}"), sira=done, toplam=total))

        def work():
            self.c.run_scan(progress=progress)
            # Tarama donanım profilini kesinleştirdi; uygunluğu tazele (okunmuş durumlar yeniden okunmaz).
            self.c.refresh_all(on_each=lambda tid: self.worker.call_soon(self._tweak_updated, tid), reread=False)

        def done(_):
            self.scanning = False
            self.reload_pages()
            summary.set_progress(t("tarama.bitti", sure=self.c.scan["toplam_sure"]), running=False)
            self.set_status(t("tarama.bitti", sure=self.c.scan["toplam_sure"]), "iyi")
            self._update_counts()
            self._save_timer.start(500)

        def failed(_exc):
            self.scanning = False
            summary.set_progress(t("ui.tarama_hatasi"), running=False)
            self.set_status(t("ui.tarama_hatasi"), "sorun")

        self.worker.run(work, done, failed, serial=False)

    def recheck_fix(self, tweak_id, done):
        """Çözümden sonra yalnız bu madde arka planda doğrulanır; arayüz beklemez."""
        def finished(changed):
            self._tweak_updated(tweak_id)
            done(bool(changed))
        self.worker.run(lambda: self.c.recheck(tweak_id), finished, lambda _e: done(False), serial=False)

    # ------------------------------------------------------------------ oyunlar
    def _start_games(self):
        """Önceki oturumdan yarım kalan oyun ayarlarını geri alır, sonra izleyiciyi gerekiyorsa başlatır."""
        if not self.c.can_modify:
            return
        system = self.c.engine.system

        def recover():
            return GameSession(system, ProcessOps()).recover()

        def done(recovered):
            if recovered:
                self.set_status(t("ui.oyun_oturumu_geri_alindi"), "bilgi")
            self.update_game_watcher()
        self.worker.run(recover, done, lambda _e: self.update_game_watcher(), serial=False)

    def watched_games(self):
        """Oyun sırasında ayarı uygulanacak oyunlar."""
        return self.game_store.runtime_games()

    def update_game_watcher(self):
        """Oyun sırasında ayarı olan oyun varsa izleyiciyi çalıştırır, yoksa durdurur."""
        if not self.c.can_modify:
            return
        needed = bool(self.watched_games())
        if needed and self.game_watcher is None:
            self.game_watcher = GameWatcher(self.game_store, self.c.engine.system, games=self.watched_games,
                                            on_event=lambda *a: self.worker.call_soon(self._game_event, *a))
            self.game_watcher.start()
        elif not needed and self.game_watcher is not None and not self.game_watcher.active:
            self.game_watcher.stop()
            self.game_watcher = None

    def _game_event(self, kind, game, results):
        store = self.c.engine.store
        failed = [key for key, ok, _ in results if not ok]
        if kind == "basladi":
            store.history("oyun_basladi", game["id"], not failed, ", ".join(failed))
            text = t("ui.oyun_ayarlar_uygulandi", ad=game["ad"])
            if failed:
                text += " " + t("ui.oyun_ayar_atlandi", liste=", ".join(t(f"ui.oyun_kisa.{k.split(':')[0]}")
                                                                          for k in failed))
            self.set_status(text, "uyari" if failed else "iyi")
            if game["profil"].get("pencereyi_kucult"):
                self.showMinimized()
        else:
            store.history("oyun_bitti", game["id"], True)
            self.set_status(t("ui.oyun_ayarlar_geri_alindi", ad=game["ad"]), "iyi")
        page = self.pages.get("oyunlar")
        if page is not None and page.built:
            page.data_reloaded()

    # ------------------------------------------------------------------ değişiklik akışı
    def ensure_prepared(self, proceed, cancel):
        engine = self.c.engine
        if engine.restore_point is not None and (engine.restore_point.ok or engine.accepted_without_restore_point):
            proceed()
            return
        if engine.restore_point is not None:
            self._restore_point_result(engine.restore_point, proceed, cancel)
            return
        choice = settings.get("rp_sorma")
        if not choice:
            choice, remember = dialogs.ask_restore_point(self)
            if choice is None:  # Esc / pencere kapatıldı: vazgeçildi, değişiklik yapılmaz
                cancel()
                return
            if remember:
                settings.set("rp_sorma", choice)
        if choice == "atla":
            engine.skip_restore_point()
            proceed()
            return
        waiting = dialogs.busy(self, t("ui.rp_baslik"), t("ui.rp_olusturuluyor"))

        def done(result):
            waiting.finish()
            self._restore_point_result(result, proceed, cancel)

        def failed(_exc):
            waiting.finish()
            cancel()

        self.worker.run(engine.prepare, done, failed)

    def _require_restore_point(self, proceed, cancel):
        """Geri yükleme noktası şart olan ayar: oturumda atlanmış olsa da yeniden denenir, olmazsa uygulanmaz."""
        engine = self.c.engine
        if engine.restore_point is not None and engine.restore_point.ok:
            proceed()
            return
        engine.restore_point = None
        waiting = dialogs.busy(self, t("ui.rp_baslik"), t("ui.rp_olusturuluyor"))

        def done(result):
            waiting.finish()
            if result.ok:
                self.set_status(t(f"rp.{result.status}", zaman=fmt_date(result.when)), "iyi")
                proceed()
                return

            def after(fixed):
                if fixed is not None:
                    proceed()
                else:
                    dialogs.show_message(self, t("ui.rp_baslik"), t("hata.geri_yukleme_zorunlu"), "sorun")
                    cancel()
            self.offer_system_protection(after)

        def failed(_exc):
            waiting.finish()
            cancel()

        self.worker.run(engine.prepare, done, failed)

    def _restore_point_result(self, result, proceed, cancel):
        if result.ok:
            self.set_status(t(f"rp.{result.status}", zaman=fmt_date(result.when)), "iyi")
            proceed()
            return

        def after(fixed):
            if fixed is not None:
                self._restore_point_result(fixed, proceed, cancel)
            elif dialogs.ask_yes_no(self, t("ui.rp_baslik"), t("rp.basarisiz") + "\n\n" + t("rp.devam_sorusu"),
                                    yes_text=t("ui.yine_de_devam"), no_text=t("ui.vazgec")):
                self.c.engine.accept_without_restore_point()
                proceed()
            else:
                cancel()
        self.offer_system_protection(after)

    def offer_system_protection(self, done):
        """Geri yükleme noktası oluşturulamadıysa Sistem Koruması kapalı mı bakılır; kapalıysa onayla açılır.
        done(RestorePointResult | None): koruma açılıp ilk nokta oluştuysa o sonuç, aksi halde None."""
        if not self.c.can_modify or not admin.is_admin():  # durum yönetici olmadan okunamaz
            done(None)
            return
        title = t("koruma.baslik")
        waiting = dialogs.busy(self, title, t("koruma.denetleniyor"))

        def read_failed(exc):
            waiting.finish()
            _log.warning("Sistem koruması durumu okunamadı: %s", exc)
            done(None)

        def read(data):
            waiting.finish()
            if data.get("acik") is not False:  # açık ya da okunamadı: sorun başka yerde, mevcut uyarı yeterli
                done(None)
                return
            reason = system_protection.blocker(data)
            if reason:
                dialogs.show_message(self, title, t(f"koruma.engel.{reason}", surucu=data["surucu"]), "uyari")
                done(None)
                return
            text = t("koruma.soru", surucu=data["surucu"], gb=system_protection.limit_gb(data["boyut"], data["bos"]),
                     bos=round(data["bos"] / system_protection.GB))
            services = system_protection.disabled_services(data)
            if services:
                text += "\n\n" + t("koruma.servis_not", liste=", ".join(services))
            if not dialogs.ask_yes_no(self, title, text, yes_text=t("koruma.ac"), no_text=t("ui.vazgec"), kind="bilgi"):
                done(None)
                return
            working = dialogs.busy(self, title, t("koruma.aciliyor"))

            def finished(res):
                working.finish()
                point = res["nokta"]
                if point is not None:
                    self.c.engine.restore_point = point
                self.c.engine.store.history("sistem_koruma", data["surucu"], res["basarili"], res["neden"] or "")
                good = res["basarili"] and point is not None and point.ok
                dialogs.show_message(self, title, self._protection_report(res, data),
                                     "iyi" if good else "uyari" if res["basarili"] else "sorun")
                done(point if good else None)

            def crashed(exc):
                working.finish()
                dialogs.show_message(self, title, t("koruma.sonuc.ac", hata=str(exc)), "sorun")
                done(None)
            self.worker.run(lambda: system_protection.enable(self.c.engine.system, data), finished, crashed)
        self.worker.run(system_protection.status, read, read_failed)

    @staticmethod
    def _protection_report(res, data):
        lines = [t("koruma.sonuc.servis", ad=detail) for key, ok, detail in res["adimlar"] if key == "servis" and ok]
        if not res["basarili"]:
            detail = next((d for k, ok, d in res["adimlar"] if k == "ac" and not ok), "")
            lines.append(t(f"koruma.sonuc.{res['neden']}", hata=detail))
            return "\n\n".join(lines)
        lines.append(t("koruma.sonuc.acildi", surucu=data["surucu"]))
        limit_ok = next((ok for k, ok, _d in res["adimlar"] if k == "sinir"), False)
        lines.append(t("koruma.sonuc.sinir", gb=res["sinir_gb"]) if limit_ok else t("koruma.sonuc.sinir_hata"))
        point = res["nokta"]
        if point.ok:
            lines.append(t(f"rp.{point.status}", zaman=fmt_date(point.when)))
        else:
            lines.append(t(f"koruma.sonuc.{res['neden']}", dk=data.get("siklik_dk")))
        return "\n\n".join(lines)

    def _confirm(self, tweak, enabling, level=None):
        """Seviye 2 (riskli): açarken ve kapatırken iki ekran. Seviye 1 (dikkatli)
        veya donanım uyarısı: yalnızca açarken tek ekran."""
        avail = self.c.availability.get(tweak["id"])
        level = self.c.engine.confirm_level(tweak) if level is None else level
        anti_cheat = self.c.meta.get("anti_cheat_uyarisi") if level else ""
        if level == 2:
            return dialogs.confirm_risky(self, tweak, avail, enabling, anti_cheat)
        if enabling and (level == 1 or (avail and avail.warnings)):
            return dialogs.confirm_careful(self, tweak, avail, anti_cheat)
        return True

    def _blocked(self):
        if self.c.can_modify:
            return False
        dialogs.show_message(self, t("ui.degistirilemez_baslik"), t(f"ui.mod_aciklama.{self.c.mode}"), "uyari")
        return True

    def _run_change(self, tweak_id, work, done, undoable=False):
        self.busy = True
        self.toast.hide()  # eski "Geri al" başka değişikliği geri almasın

        def finished(result):
            self.busy = False
            self.c.note_result(result)
            entry = self.c.engine.store.get(tweak_id) or {}
            name = self.c.by_id[tweak_id]["ad"] if tweak_id in self.c.by_id else entry.get("ad", tweak_id)
            self._report_result(result, name)
            if undoable and result.ok and self.c.engine.store.has(tweak_id):
                self.toast.show_text(t("ui.uygulandi_kisa", ad=name), 6000, action_label=t("ui.geri_al"),
                                     action=lambda: self.revert(tweak_id, lambda: None))
            self.update_banners()
            self._tweak_updated(tweak_id)
            if self.current == "degisiklikler":
                self.pages[self.current].data_reloaded()
            self._save_timer.start(500)
            done()

        def failed(_exc):
            self.busy = False
            dialogs.show_message(self, t("ui.hata_baslik"), t("hata.beklenmeyen"), "sorun")
            done()

        def task():
            result = work()
            if tweak_id in self.c.by_id:
                self.c.refresh_one(tweak_id)
            return result

        self.worker.run(task, finished, failed)

    def _report_result(self, result, name):
        text = f"{name}: {t(result.key, **result.params)}"
        for key, params in result.warnings:
            text += " " + t(key, **params)
        self.set_status(text, "iyi" if result.ok else "sorun")
        if not result.ok:
            dialogs.show_message(self, t("ui.hata_baslik"), text, "sorun")

    def toggle(self, tweak, desired, done):
        if self.busy or self._blocked():
            done()
            return
        if not self._confirm(tweak, desired):
            done()
            return
        engine = self.c.engine
        work = lambda: engine.set_enabled(tweak, desired, confirmed=True)  # onay yukarıda alındı
        needs_restore_point = desired or not engine.store.has(tweak["id"])
        start = lambda: self._run_change(tweak["id"], work, done, undoable=desired)
        if desired and tweak.get("geri_yukleme_zorunlu"):
            self._require_restore_point(start, done)
        elif needs_restore_point:
            self.ensure_prepared(start, done)
        else:
            start()

    def apply_selection(self, tweak, values, done):
        if self.busy or self._blocked():
            done()
            return
        work = lambda: self.c.engine.set_selection(tweak, values, confirmed=True)
        self.ensure_prepared(lambda: self._run_change(tweak["id"], work, done, undoable=True), done)

    def revert(self, tweak_id, done):
        if self.busy or self._blocked():
            done()
            return
        engine = self.c.engine
        level = engine.stored_confirm_level(tweak_id)
        if level == 2:
            tweak = self.c.by_id.get(tweak_id) or self.c.by_id.get(engine.stored_related(tweak_id) or "")
            ok = (self._confirm(tweak, False, level) if tweak else
                  dialogs.ask_yes_no(self, t("ui.risk2_baslik"), t("ui.risk2_metin")))
            if not ok:
                done()
                return
        self._run_change(tweak_id, lambda: engine.revert(tweak_id, confirmed=True), done)

    def apply_custom(self, change_id, name, steps, values, done, level=0, restart="yok", related=None, after=()):
        """Yöneticilerden gelen değişiklik (başlangıç öğesi, servis, MSI, aygıt gücü, monitör Hz).
        Onay ekranları çağıran tarafından gösterilir."""
        if self.busy or self._blocked():
            done()
            return
        work = lambda: self.c.engine.apply_custom(change_id, name, steps, values, level=level,  # noqa: E731
                                                  restart=restart, confirmed=True, related=related,
                                                  after=after)
        self.ensure_prepared(lambda: self._run_change(change_id, work, done, undoable=True), done)

    def run_npi(self, tweak, settings, done, sha256=None):
        """Yedek yöntem: NVIDIA Profile Inspector ile içe aktarma (geri alınamaz; işlem geçmişine yazılır)."""
        if self.busy or self._blocked():
            done()
            return
        engine = self.c.engine

        def work():
            from app.engine.engine import Result  # noqa: WPS433
            try:
                engine.system.run_npi_import(settings, sha256)
            except Exception as exc:
                engine.store.history("npi", tweak["id"], False, str(exc))
                return Result(False, "hata.npi_basarisiz")
            engine.store.history("npi", tweak["id"], True, str(settings))
            return Result(True, "sonuc.npi")
        self.ensure_prepared(lambda: self._run_change(tweak["id"], work, done), done)

    def run_action(self, tweak, action, done=lambda: None):
        """Tek seferlik eylem: geri alınamaz olduğu açıkça sorulur."""
        if self.busy or self._blocked():
            done()
            return
        if not dialogs.ask_yes_no(self, action["etiket"], t("ui.eylem_onay", ad=action["etiket"]),
                                  yes_text=t("ui.devam"), no_text=t("ui.vazgec")):
            done()
            return
        self._run_change(tweak["id"], lambda: self.c.engine.run_action(tweak, action["id"]), done)

    def _batch(self, title, task, done):
        waiting = dialogs.busy(self, title, t("ui.lutfen_bekleyin"))
        self.busy = True

        def finished(results):
            waiting.finish()
            self.busy = False
            for _, result in results:
                self.c.note_result(result)
            self._summarize(title, results)
            self.update_banners()
            self.reload_pages()
            self._update_counts()
            self._save_timer.start(500)
            done()

        def failed(_exc):
            waiting.finish()
            self.busy = False
            done()

        self.worker.run(task, finished, failed)

    def revert_all(self, done):
        if self.busy or self._blocked() or not self.c.changed():
            done()
            return
        if not dialogs.ask_yes_no(self, t("ui.tumunu_geri_al"), t("ui.tumunu_geri_al_soru")):
            done()
            return

        def task():
            results = self.c.engine.revert_all()
            for tweak_id, _ in results:
                if tweak_id in self.c.by_id:
                    self.c.refresh_one(tweak_id)
            return results

        self._batch(t("ui.tumunu_geri_al"), task, done)

    def apply_recommended(self, tweaks, done=lambda: None):
        """Toplu öneri: önce ÖNİZLEME (neler açılacak), onaydan sonra her zamanki yoldan uygulanır."""
        if self.busy or self._blocked():
            done()
            return
        ids = dialogs.choose_bulk(self, tweaks)
        if not ids:
            done()
            return
        self.apply_profile([{"id": i} for i in ids], done, title=t("ui.toplu.sonuc"))

    def apply_profile(self, rows, done, title=None):
        if self.busy or self._blocked():
            done()
            return
        choices = []
        for row in rows:
            tweak = self.c.by_id[row["id"]]
            if not self._confirm(tweak, True):
                continue
            choices.append((row["id"], True))
        if not choices:
            done()
            return

        def task():
            results = profile_module.apply(self.c.engine, self.c.by_id, choices)
            for tweak_id, _ in results:
                self.c.refresh_one(tweak_id)
            return results

        self.ensure_prepared(lambda: self._batch(title or t("ui.profil_sonuc"), task, done), done)

    def _summarize(self, title, results):
        ok = [r for r in results if r[1].ok]
        bad = [r for r in results if not r[1].ok]
        lines = [t("ui.sonuc_ozet", basarili=len(ok), basarisiz=len(bad))]
        for tweak_id, result in bad:
            name = self.c.by_id[tweak_id]["ad"] if tweak_id in self.c.by_id else tweak_id
            lines.append(f"• {name}: {t(result.key, **result.params)}")
        if bad:  # hata varsa ayrıntı için pencere; hepsi başarılıysa tıklama istemeyen yeşil onay
            dialogs.show_message(self, title, "\n".join(lines), "uyari")
        else:
            self.toast.show_text(f"{title} · {t('ui.sonuc_kisa', basarili=len(ok))}")

    # ------------------------------------------------------------------ tepsi simgesi
    def update_tray(self):
        """Ayar açıksa tepsi simgesini gösterir (Qt'nin kendi bileşeni; ek kütüphane yok)."""
        wanted = bool(settings.get("tepsiye_kucult")) and QSystemTrayIcon.isSystemTrayAvailable()
        if wanted and self.tray is None:
            self.tray = QSystemTrayIcon(app_icon(), self)
            self.tray.setToolTip(t("uygulama.ad"))
            menu = QMenu(self)
            show = QAction(t("ui.tepsi.goster"), menu)
            show.triggered.connect(self.show_from_tray)
            leave = QAction(t("ui.tepsi.cikis"), menu)
            leave.triggered.connect(self.quit_from_tray)
            menu.addAction(show)
            menu.addSeparator()
            menu.addAction(leave)
            self.tray.setContextMenu(menu)
            self.tray.activated.connect(lambda reason: self.show_from_tray()
                                        if reason == QSystemTrayIcon.ActivationReason.Trigger else None)
            self.tray.show()
        elif not wanted and self.tray is not None:
            self.tray.hide()
            self.tray.deleteLater()
            self.tray = None

    def show_from_tray(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def nativeEvent(self, event_type, message):
        """İkinci açılış (tek_ornek.claim) 'pencereni göster' der: tepsideyse bile pencere öne gelir."""
        if event_type == b"windows_generic_MSG":
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == tek_ornek.show_message_id():
                self.show_from_tray()
                return True, 0
        return super().nativeEvent(event_type, message)

    def quit_from_tray(self):
        self.quitting = True
        self.close()

    def restart_app(self):
        """Pencereyi kapatıp uygulamayı yeniden açar (dil değişikliğini uygulamak için)."""
        self.quitting = True
        if not self.close():
            return
        exe, args = restart_command()
        QProcess.startDetached(exe, args, str(paths.app_dir()))

    def changeEvent(self, event):
        """Küçültülünce veya başka pencere öne geçince animasyon çalışmaz (boşta CPU yükü yok)."""
        if event.type() in (QEvent.Type.WindowStateChange, QEvent.Type.ActivationChange):
            idle = self.isMinimized() or not self.isActiveWindow()
            motion.set_paused(idle, "arka_plan")
            self.live_monitor.set_window_active(not idle)
        super().changeEvent(event)

    def closeEvent(self, event):
        if self.tray is not None and not self.quitting:
            # Tepsiye küçült: pencere gizlenir, oyun izleyici çalışmaya devam eder.
            event.ignore()
            self.hide()
            self.c.save_cache()
            return
        if self.busy and not dialogs.ask_yes_no(self, t("ui.kapat"), t("ui.islem_suruyor")):
            event.ignore()
            self.quitting = False
            return
        if self.tray is not None:
            self.tray.hide()
        self._save_timer.stop()
        self._counts_timer.stop()
        self.live_monitor.stop()
        if self.game_watcher is not None:
            self.game_watcher.stop()  # açık oyunun oyun-sırası ayarları geri alınır
        if not self.skip_save:
            self.c.save_cache()
        self.worker.shutdown()
        event.accept()
        QApplication.instance().quit()  # tepsi modu için son pencere kapanınca otomatik çıkış kapalı


def app_icon():
    """Uygulama simgesi: data/logo.png kare tuvalin ortasında; dosya yoksa "F" harfli kendi çizimimiz."""
    mark = w.logo_pixmap(256)
    if mark is not None:
        icon = QIcon()
        for size in (16, 24, 32, 48, 64, 128, 256):
            canvas = QPixmap(size, size)
            canvas.fill(QColor(0, 0, 0, 0))
            scaled = mark.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio,
                                 Qt.TransformationMode.SmoothTransformation)
            painter = QPainter(canvas)
            painter.drawPixmap((size - scaled.width()) // 2, (size - scaled.height()) // 2, scaled)
            painter.end()
            icon.addPixmap(canvas)
        return icon
    pixmap = QPixmap(64, 64)
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor(theme.DARK["accent"]))
    painter.setPen(QColor(0, 0, 0, 0))
    painter.drawRoundedRect(4, 4, 56, 56, 14, 14)
    painter.setPen(QColor("white"))
    font = QFont(theme.ui_font(13, bold=True))
    font.setPixelSize(26)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), int(Qt.AlignmentFlag.AlignCenter), "F")
    painter.end()
    return QIcon(pixmap)


def apply_theme(qt_app):
    qt_app.setStyleSheet(theme.stylesheet())


def apply_language(qt_app):
    """Seçili dilin yazı yönünü (sağdan sola diller için) ve yazı tipini uygular."""
    rtl = i18n.direction() == "rtl"
    qt_app.setLayoutDirection(Qt.LayoutDirection.RightToLeft if rtl else Qt.LayoutDirection.LeftToRight)
    qt_app.setFont(theme.ui_font(13))


def restart_command():
    """Uygulamayı aynı modda yeniden açan komut (dil değişikliği için). Yeniden UAC sorulmaz:
    yönetici süreç yöneticiyi başlatır; salt okunur süreç salt okunur kalır."""
    args = [a for a in sys.argv[1:] if a != "--tepside"]
    if "--yukseltildi" not in args:
        args.append("--yukseltildi")
    if getattr(sys, "frozen", False):
        return sys.executable, args
    return sys.executable, ["-m", "app"] + args


def create_app():
    qt_app = QApplication.instance() or QApplication(sys.argv)
    apply_language(qt_app)
    apply_theme(qt_app)
    w.install_wheel_guard(qt_app)
    hints = QGuiApplication.styleHints()
    if hasattr(hints, "colorSchemeChanged"):
        hints.colorSchemeChanged.connect(lambda _scheme: apply_theme(qt_app))
    return qt_app


def _hold_timer_resolution(mode):
    """Kullanıcı Performans menüsünde istediyse, uygulama açık kaldıkça zamanlayıcı çözünürlüğünü ister.
    Önizleme modunda istenmez. Uygulama kapanınca Windows isteği kendiliğinden bırakır."""
    value = settings.get("zamanlayici_cozunurlugu")
    if not value or mode == MODE_PREVIEW:
        return
    try:
        from app.engine import timer_resolution  # noqa: WPS433
        timer_resolution.hold(int(value))
    except (OSError, AttributeError) as exc:
        _log.warning("Zamanlayıcı çözünürlüğü istenemedi: %s", exc)


def run(mode, in_tray=False):
    if mode != MODE_PREVIEW and not tek_ornek.claim():
        _log.info("Uygulama zaten açık: var olan pencere öne getirildi, bu kopya kapanıyor")
        return 0
    qt_app = create_app()
    qt_app.setWindowIcon(app_icon())
    qt_app.setQuitOnLastWindowClosed(False)  # tepsideyken pencere kapanınca uygulama kapanmasın
    # İlk açılışta dil seçimi (onaydan önce, çünkü onay metni seçilen dilde gösterilir).
    if not settings.get("dil"):
        language = dialogs.ask_language(i18n.available(), i18n.current()) or i18n.current()
        settings.set("dil", language)
        if language != i18n.current():
            i18n.load(language)
            apply_language(qt_app)
            apply_theme(qt_app)
    # İlk açılışta ve sürüm/metin değişince sorumluluk onayı; reddedilirse uygulama açılmaz.
    if not consent.is_accepted():
        if not dialogs.ask_consent(consent.text()):
            _log.info("Başlangıç onayı reddedildi; uygulama kapatılıyor")
            return 1
        consent.accept()
    window = MainWindow(Controller(mode))
    tek_ornek.allow_from_unelevated(int(window.winId()))
    _hold_timer_resolution(mode)
    if mode == MODE_PREVIEW:
        _log.info("Önizleme modu: hiçbir ayar değiştirilmeyecek")
    if in_tray and window.tray is not None:
        _log.info("Tepside başlatıldı")
    else:
        window.show()
    return qt_app.exec()
