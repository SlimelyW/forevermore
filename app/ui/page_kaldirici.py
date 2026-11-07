"""Uygulama kaldırıcı sayfası: programın kendi kaldırıcısı çalışır, sonra kalan klasör ve kayıt anahtarları bulunur ve
yedeklenerek kaldırılır; her kaldırma geri yüklenebilir (app/engine/uninstaller.py)."""

from PySide6.QtWidgets import QCheckBox, QLabel, QLineEdit

from app.core.i18n import fmt_number, t
from app.engine import store_restore, uninstaller
from app.ui import dialogs, widgets as w

MAX_ROWS = 200
CHUNK = 40  # uzun liste parça parça çizilir: ilk parça hemen, gerisi aşağı kaydırdıkça (sayfa açılışı donmaz)


class UninstallerPage(w.Page):
    def __init__(self, app):
        super().__init__(app)
        self.programs = None    # None: okunuyor
        self.sessions = []
        self.pending = None     # kaldırıcısı başlatılan program
        self.leftovers = None   # pending için bulunan kalıntılar: [(öğe, QCheckBox)]
        self.filter_text = ""
        self._queue = []        # henüz çizilmemiş satırlar
        self._list = None
        self.scroll.verticalScrollBar().valueChanged.connect(self._near_end)
        self.apps = None        # Store ve Windows uygulamaları: None (bakılmadı) / "okunuyor" / store_restore.status()
        self.app_result = None  # son geri yükleme: (paket bilgisi, sonuç)

    def on_show(self, highlight=None):
        self.ensure_built()
        if self.programs is None:
            self.refresh()
        else:  # Temizlik gibi başka sayfa yedek eklemiş olabilir: yalnız yedek listesi yeniden okunur
            self.app.worker.run(uninstaller.list_sessions, self._sessions_read, lambda _exc: None, serial=False)

    def _sessions_read(self, sessions):
        if sessions != self.sessions:
            self.sessions = sessions
            self.data_reloaded()

    def refresh(self):
        self.programs = None
        self.app.worker.run(lambda: (uninstaller.list_programs(), uninstaller.list_sessions()), self._loaded,
                            lambda _exc: self._loaded(([], [])), serial=False)
        self.data_reloaded()

    def _loaded(self, result):
        self.programs, self.sessions = result
        self.data_reloaded()

    def build(self):
        super().build()
        self.header.addWidget(w.hbox(w.title(t("ui.menu.kaldirici")), None, w.button(t("ui.yenile"), self.refresh)))
        self.header.addWidget(w.label(t("ui.kaldirici.aciklama"), muted=True))
        if self.pending:
            self.body.addWidget(self._pending_card())
        if self.sessions:
            self.body.addWidget(self._sessions_card())
        self.body.addWidget(self._apps_card())
        if self.programs is None:
            self.body.addWidget(w.label(t("ui.kaldirici.okunuyor"), muted=True))
            return
        search = QLineEdit(self.filter_text)
        search.setPlaceholderText(t("ui.kaldirici.ara"))
        search.setFixedWidth(280)
        search.returnPressed.connect(lambda: self._filter(search.text()))
        self.body.addWidget(w.hbox(search, w.button(t("ui.ara"), lambda: self._filter(search.text())), None))
        needle = self.filter_text.lower()
        shown = [p for p in self.programs if not needle or needle in p["ad"].lower() or needle in p["yayinci"].lower()]
        self._list = w.RowList()
        self._queue = shown[:MAX_ROWS]
        if self._queue:
            self.body.addWidget(self._list)
            self._more_rows()
        if len(shown) > MAX_ROWS:
            self.body.addWidget(w.label(t("ui.kaldirici.daha_fazla", adet=len(shown) - MAX_ROWS), muted=True))
        if not shown:
            self.body.addWidget(w.label(t("ui.liste_bos"), muted=True))

    # ------------------------------------------------------------------ Store ve Windows uygulamaları (B1)
    def _apps_card(self):
        card = w.Card(spacing=6)
        title = QLabel(t("store_geri.baslik"))
        title.setObjectName("CardTitle")
        card.lay.addWidget(title)
        card.lay.addWidget(w.label(t("store_geri.aciklama"), muted=True, size=12))
        if self.apps is None:
            card.lay.addWidget(w.hbox(w.button(t("store_geri.kontrol"), self._check_apps), None))
            return card
        if self.apps == "okunuyor":
            card.lay.addWidget(w.label(t("store_geri.okunuyor"), muted=True, size=12))
            return card
        for key, params in self.apps["uyarilar"]:
            card.lay.addWidget(w.colored(t(key, **params), "uyari"))
        if self.app_result and not self.app_result[1]["basarili"]:
            card.lay.addWidget(self._failure(*self.app_result))
        missing = [p for p in self.apps["paketler"] if not p["kurulu"]]
        if not missing:
            card.lay.addWidget(w.colored(t("store_geri.hepsi_kurulu"), "iyi"))
        for package in self.apps["paketler"]:
            name = t(f"store_geri.paket.{package['anahtar']}")
            if package["kurulu"]:
                state = w.badge(t("store_geri.kurulu"), "iyi")
            elif package["manifest"] or package["saglanmis"]:
                state = w.badge(t("store_geri.eksik_dosya_var"), "uyari")
            else:
                state = w.badge(t("store_geri.eksik_dosya_yok"), "sorun")
            parts = [w.label(name, wrap=False), state, None]
            if not package["kurulu"]:
                button = w.button(t("store_geri.geri_yukle"), lambda _=False, p=package: self._restore_app(p))
                button.setEnabled(self.c.can_modify)
                parts.append(button)
            card.lay.addWidget(w.hbox(*parts))
        card.lay.addWidget(w.hbox(None, w.button(t("store_geri.yeniden_kontrol"), self._check_apps)))
        return card

    def _failure(self, package, result):
        box = w.Card(spacing=4)
        name = t(f"store_geri.paket.{package['anahtar']}")
        box.lay.addWidget(w.colored(t(f"store_geri.neden.{result['neden']}", ad=name), "sorun"))
        if result.get("hata"):
            box.lay.addWidget(w.label(t("store_geri.windows_hatasi", hata=result["hata"][:400]), muted=True, size=12))
        for key, params in store_restore.problems(self.apps, failed=True):
            if key == "store_geri.uyari.appx_hata":
                box.lay.addWidget(w.label(t(key, **params), muted=True, size=12))
        box.lay.addWidget(w.label(t("store_geri.alternatif"), size=12))
        return box

    def _check_apps(self):
        self.apps = "okunuyor"
        self.data_reloaded()

        def failed(exc):
            self.apps = None
            dialogs.show_message(self.app, t("ui.hata_baslik"), t("store_geri.okunamadi", hata=str(exc)[:300]), "sorun")
            self.data_reloaded()
        self.app.worker.run(store_restore.status, self._apps_read, failed, serial=False)

    def _apps_read(self, data):
        self.apps = data
        self.data_reloaded()

    def _restore_app(self, package):
        """Yönetici gerekir; önce geri yükleme noktası, sonra geri yükleme ve doğrulama (sahte başarı yok)."""
        name = t(f"store_geri.paket.{package['anahtar']}")
        build = int(self.apps.get("derleme") or 0)

        def proceed():
            waiting = dialogs.busy(self.app, t("store_geri.baslik"), t("store_geri.suruyor", ad=name))

            def work():
                result = store_restore.restore(package["ad"], package, build)
                return result, store_restore.status()

            def done(value):
                waiting.finish()
                result, self.apps = value
                self.app_result = (package, result)
                if result["basarili"]:
                    self.app.set_status(t("store_geri.basarili", ad=name), "iyi")
                else:
                    dialogs.show_message(self.app, t("store_geri.baslik"),
                                         t(f"store_geri.neden.{result['neden']}", ad=name), "sorun")
                self.data_reloaded()

            def failed(exc):
                waiting.finish()
                dialogs.show_message(self.app, t("ui.hata_baslik"), t("store_geri.okunamadi", hata=str(exc)[:300]),
                                     "sorun")
            self.app.worker.run(work, done, failed)
        self.app.ensure_prepared(proceed, lambda: None)

    def _filter(self, text):
        self.filter_text = text.strip()
        self.data_reloaded()

    # ------------------------------------------------------------------ liste
    def _more_rows(self):
        for program in self._queue[:CHUNK]:
            self._list.add(self._row(program))
        self._queue = self._queue[CHUNK:]

    def _near_end(self, value):
        bar = self.scroll.verticalScrollBar()
        if self._queue and self._list is not None and value >= bar.maximum() - 400:
            try:
                self._more_rows()
            except RuntimeError:  # sayfa bu arada yeniden kuruldu
                self._queue = []

    def _row(self, program):
        sub = " · ".join(x for x in (program["surum"], program["yayinci"],
                                     t("ui.kaldirici.mb", mb=fmt_number(program["boyut_kb"] / 1024, 0)) if program["boyut_kb"] else "")
                         if x)
        card = w.Card(layout="h", margins=(14, 8, 14, 8))
        parts = [(w.label(program["ad"], bold=True, wrap=False, plain=True), 2), (w.label(sub, muted=True, wrap=False, plain=True), 3)]
        if program["korumali"]:
            parts.append(w.badge(t("ui.boost.korumali"), "notr"))
        else:
            button = w.button(t("ui.kaldirici.kaldir"), lambda _=False, p=program: self._uninstall(p))
            button.setEnabled(self.c.can_modify)
            parts.append(button)
        card.lay.addWidget(w.hbox(*parts, spacing=10), 1)
        return card

    def _uninstall(self, program):
        question = (t("ui.kaldirici.kaldir_soru_kullanici", ad=program["ad"], komut=program["komut"]) if program["kok"] == "HKCU"
                    else t("ui.kaldirici.kaldir_soru", ad=program["ad"]))
        if not dialogs.ask_yes_no(self.app, t("ui.dikkat"), question):
            return
        if not uninstaller.start_uninstall(program):
            key = "ui.kaldirici.baslamadi_kullanici" if program["kok"] == "HKCU" else "ui.kaldirici.baslamadi"
            self.app.set_status(t(key, ad=program["ad"]), "sorun")
            return
        self.pending, self.leftovers = program, None
        self.app.set_status(t("ui.kaldirici.basladi", ad=program["ad"]), "bilgi")
        self.data_reloaded()

    # ------------------------------------------------------------------ kalıntılar
    def _pending_card(self):
        card = w.Card(spacing=8)
        head = QLabel(t("ui.kaldirici.kalinti_baslik", ad=self.pending["ad"]))
        head.setObjectName("CardTitle")
        card.lay.addWidget(head)
        if self.leftovers is None:
            card.lay.addWidget(w.label(t("ui.kaldirici.kalinti_not"), muted=True, size=12))
            card.lay.addWidget(w.hbox(w.button(t("ui.kaldirici.tara"), self._scan, primary=True),
                                      w.button(t("ui.vazgec"), self._cancel), None))
            return card
        if not self.leftovers:
            card.lay.addWidget(w.label(t("ui.kaldirici.kalinti_yok"), muted=True))
            card.lay.addWidget(w.hbox(w.button(t("ui.kaldirici.kapat"), self._cancel), None))
            return card
        card.lay.addWidget(w.label(t("ui.kaldirici.kalinti_secim"), muted=True, size=12))
        for item, box in self.leftovers:
            card.lay.addWidget(box)
        remove = w.button(t("ui.kaldirici.kalintilari_kaldir"), self._remove, primary=True)
        remove.setEnabled(self.c.can_modify)
        card.lay.addWidget(w.hbox(remove, w.button(t("ui.vazgec"), self._cancel), None))
        return card

    def _cancel(self):
        self.pending = self.leftovers = None
        self.data_reloaded()

    def _scan(self):
        program = self.pending
        self.app.set_status(t("ui.kaldirici.taraniyor"), "bilgi")
        self.app.worker.run(lambda: (uninstaller.list_programs(), uninstaller.find_leftovers(program)),
                            lambda result: self._scanned(program, *result),
                            lambda _exc: self.app.set_status(t("ui.kaldirici.taranamadi"), "sorun"), serial=False)

    def _scanned(self, program, current, found):
        self.programs = current
        if any(p["anahtar"] == program["anahtar"] and p["kok"] == program["kok"] for p in current):
            self.app.set_status(t("ui.kaldirici.hala_kurulu", ad=program["ad"]), "uyari")
            self.data_reloaded()
            return
        self.leftovers = []
        for item in found:
            size = f" ({fmt_number(item['boyut'] / 1048576, 1)} MB)" if item.get("boyut") else ""
            kind = t("ui.kaldirici.tur." + item["tur"])
            box = QCheckBox(f"{kind}: {item['yol']}{size}")
            box.setChecked(True)
            self.leftovers.append((item, box))
        self.app.set_status(t("ui.kaldirici.bulundu", adet=len(found)), "iyi" if not found else "bilgi")
        self.data_reloaded()

    def _remove(self):
        chosen = [item for item, box in self.leftovers if box.isChecked()]
        if not chosen:
            return
        if not dialogs.ask_yes_no(self.app, t("ui.dikkat"), t("ui.kaldirici.kalinti_soru", adet=len(chosen))):
            return
        name = self.pending["ad"]
        self.app.worker.run(lambda: uninstaller.remove_leftovers(name, chosen), lambda result: self._removed(result),
                            lambda _exc: self.app.set_status(t("ui.kaldirici.kaldirilamadi"), "sorun"), serial=False)

    def _removed(self, result):
        failed = result["basarisiz"]
        self.app.set_status(t("ui.kaldirici.kaldirildi", adet=result["kaldirilan"], hata=len(failed)),
                            "uyari" if failed else "iyi")
        if failed:
            dialogs.show_message(self.app, t("ui.menu.kaldirici"),
                                 t("ui.kaldirici.hata_listesi", liste="\n".join(f"{f['yol']}: {f['neden']}" for f in failed)), "uyari")
        self.pending = self.leftovers = None
        self.refresh()

    # ------------------------------------------------------------------ yedekler
    def _sessions_card(self):
        card = w.Card(spacing=6)
        head = QLabel(t("ui.kaldirici.yedekler"))
        head.setObjectName("CardTitle")
        card.lay.addWidget(head)
        card.lay.addWidget(w.label(t("ui.kaldirici.yedek_not"), muted=True, size=12))
        for session in self.sessions:
            restore = w.button(t("ui.kaldirici.geri_yukle"), lambda _=False, s=session: self._restore(s))
            restore.setEnabled(self.c.can_modify)
            if not self.c.can_modify:
                restore.setToolTip(t("ui.temizlik.yetki"))
            delete = w.button(t("ui.kaldirici.yedegi_sil"), lambda _=False, s=session: self._delete(s), warn=True)
            card.lay.addWidget(w.hbox((w.label(t("ui.kaldirici.yedek_satir", ad=session["program"], tarih=session["tarih"][:16].replace("T", " "),
                                                 adet=session["adet"]), wrap=False, plain=True), 1), restore, delete, spacing=10))
        return card

    def _restore(self, session):
        if not dialogs.ask_yes_no(self.app, t("ui.dikkat"), t("ui.kaldirici.geri_yukle_soru", ad=session["program"], adet=session["adet"])):
            return
        self.app.worker.run(lambda: uninstaller.restore(session["oturum"]), self._restored,
                            lambda _exc: self.app.set_status(t("ui.kaldirici.geri_yuklenemedi"), "sorun"), serial=False)

    def _restored(self, result):
        failed = result["basarisiz"]
        self.app.set_status(t("ui.kaldirici.geri_yuklendi", adet=result["geri_yuklenen"], hata=len(failed)), "uyari" if failed else "iyi")
        self.refresh()

    def _delete(self, session):
        if not dialogs.ask_yes_no(self.app, t("ui.dikkat"), t("ui.kaldirici.yedegi_sil_soru", ad=session["program"])):
            return
        self.app.worker.run(lambda: uninstaller.delete_session(session["oturum"]), lambda _r: self.refresh(),
                            lambda _exc: self.app.set_status(t("ui.kaldirici.kaldirilamadi"), "sorun"), serial=False)
