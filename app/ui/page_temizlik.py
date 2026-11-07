"""Temizlik: bilinen önbellek/döküm klasörlerini yedek klasörüne TAŞIR (silmez; geri yüklenebilir).

Taşınacak öğeler arayüzden gelmez: yalnızca temizleyici kimlikleri gider, engine/cleaners.py her seferinde yeniden tarar.
Geri yükleme ve yedeği silme Uygulama kaldırıcı sayfasının "Yedekler" bölümündedir (aynı mekanizma).
"""

from PySide6.QtWidgets import QCheckBox, QLabel, QVBoxLayout

from app.core import temizlik_olcum
from app.core.i18n import fmt_date, fmt_number, t
from app.engine import cleaners, uninstaller
from app.ui import dialogs, widgets as w
from app.ui.bakim_kartlari import BakimKartlari


MAX_MOVES = 5


def _mb(size):
    return fmt_number(size / 1048576, 1)


def _list_moves():
    """Yalnız Temizlik'in taşımaları (kaldırıcı oturumları değil), yeni önce."""
    try:
        return [s for s in uninstaller.list_sessions() if s.get("tur") == "temizlik"][:MAX_MOVES]
    except OSError:  # yedek klasörü okunamadı (yetki): liste boş, sayfa yine çalışır
        return []


class CleanerPage(w.Page):
    def __init__(self, app):
        super().__init__(app)
        self.found = None   # None: taranıyor
        self.checks = {}
        self.olcum = None   # haftalık ölçüm görevi: None okunuyor
        self.moves = []     # "Son taşımalar": bu sayfanın taşıdıkları, yeni önce (en çok MAX_MOVES)
        self.last_move = None  # taşımadan hemen sonraki tek satır: (oturum, adet, mb); geri getirilince/yeni taşımada değişir
        self.bakim = BakimKartlari(self)

    def on_show(self, highlight=None):
        self.ensure_built()
        if self.olcum is None:
            self.app.worker.run(temizlik_olcum.is_enabled, self._olcum_read, lambda _e: self._olcum_read(False))
        self.bakim.yukle()
        if self.found is None:
            self.refresh()

    def _olcum_read(self, enabled):
        self.olcum = bool(enabled)
        self.data_reloaded()

    def refresh(self):
        self.found = None
        self.app.worker.run(lambda: (cleaners.scan(), _list_moves()), self._loaded, lambda _exc: self._loaded(([], [])),
                            serial=False)
        self.data_reloaded()

    def _loaded(self, result):
        self.found, self.moves = result
        self.data_reloaded()

    def build(self):
        super().build()
        self.header.addWidget(w.hbox(w.title(t("ui.menu.temizlik")), None, w.button(t("ui.yenile"), self.refresh)))
        self.header.addWidget(w.label(t("ui.temizlik.aciklama"), muted=True))
        if self.last_move:
            self.body.addWidget(self._moved_line())
        self.checks = {}
        if self.found is None:
            self.body.addWidget(w.label(t("ui.temizlik.taraniyor"), muted=True))
            for card in self.bakim.widgets():  # bakım araçları temizlik taramasını beklemez
                self.body.addWidget(card)
            return
        if not any(i["adet"] for i in self.found):
            self.body.addWidget(w.label(t("ui.temizlik.bos"), muted=True))
        else:
            self.body.addWidget(w.label(t("ui.temizlik.toplam", mb=_mb(sum(i["boyut"] for i in self.found))), bold=True))
        for item in self.found:
            self.body.addWidget(self._row(item))
        if any(i["adet"] for i in self.found):
            if not self.c.can_modify:
                self.body.addWidget(w.banner(t("ui.temizlik.yetki"), "uyari"))
            selected = w.button(t("ui.temizlik.dugme"), self._clean)
            everything = w.button(t("ui.temizlik.hepsi"), self._clean_all, primary=True)
            selected.setEnabled(self.c.can_modify)
            everything.setEnabled(self.c.can_modify)
            self.body.addWidget(w.hbox(None, selected, everything))
        if self.moves:
            self.body.addWidget(self._moves_card())
        self.body.addWidget(self._schedule_card())
        for card in self.bakim.widgets():
            self.body.addWidget(card)
        self.body.addWidget(w.label(t("ui.temizlik.not"), muted=True, size=12))

    def _moved_line(self):
        """Taşımadan hemen sonra: tek yeşil satır ve yanında tek düğme."""
        session, count, mb = self.last_move
        card = w.Card(layout="h", spacing=10)
        card.lay.addWidget(w.colored("✓  " + t("ui.temizlik.sonuc", adet=count, mb=mb), "iyi"), 1)
        card.lay.addWidget(self._bring_back_button(session, primary=True))
        return card

    def _moves_card(self):
        card = w.Card(spacing=6)
        head = QLabel(t("ui.temizlik.son_tasimalar"))
        head.setObjectName("CardTitle")
        card.lay.addWidget(head)
        for move in self.moves:
            line = t("ui.temizlik.tasima_satir", tarih=fmt_date(move["tarih"]), adet=move["adet"], mb=_mb(move["boyut"]))
            card.lay.addWidget(w.hbox((w.label(line, wrap=False, plain=True), 1), self._bring_back_button(move["oturum"]),
                                      spacing=10))
        return card

    def _bring_back_button(self, session, primary=False):
        button = w.button(t("ui.temizlik.geri_getir"), lambda _=False, s=session: self._bring_back(s), primary=primary)
        button.setEnabled(self.c.can_modify)
        if not self.c.can_modify:
            button.setToolTip(t("ui.temizlik.yetki"))
        return button

    def _bring_back(self, session):
        """Tek tık: sorusuz geri getirir (hiçbir şey silinmez; yerinde yeni bir şey varsa o dosya atlanır ve söylenir)."""
        self.app.worker.run(lambda: uninstaller.restore(session), lambda result: self._brought_back(session, result),
                            lambda _exc: self.app.set_status(t("ui.temizlik.geri_getirilemedi"), "sorun"), serial=False)

    def _brought_back(self, session, result):
        failed = result["basarisiz"]
        if self.last_move and self.last_move[0] == session and not failed:
            self.last_move = None
        text = (t("ui.temizlik.geri_getirildi", adet=result["geri_yuklenen"]) if not failed
                else t("ui.temizlik.geri_getirildi_eksik", adet=result["geri_yuklenen"], hata=len(failed)))
        self.app.set_status(text, "uyari" if failed else "iyi")
        if not failed:
            self.app.toast.show_text(text)
        self.refresh()

    def _schedule_card(self):
        card = w.Card(layout="h", spacing=10)
        text = QVBoxLayout()
        name = QLabel(t("ui.temizlik.olcum"))
        name.setObjectName("CardTitle")
        text.addWidget(name)
        text.addWidget(w.label(t("ui.temizlik.olcum_aciklama"), muted=True, size=12))
        last = temizlik_olcum.last()
        text.addWidget(w.label(t("ui.temizlik.son_olcum", tarih=last["tarih"].replace("T", " "), mb=_mb(last["boyut"]))
                               if last else t("ui.temizlik.son_olcum_yok"), muted=True, size=12))
        card.lay.addLayout(text, 1)
        switch = w.ToggleSwitch()
        switch.setChecked(bool(self.olcum))
        switch.setEnabled(self.c.can_modify and self.olcum is not None)
        switch.setAccessibleName(t("ui.temizlik.olcum"))
        switch.toggled.connect(self._set_olcum)
        card.lay.addWidget(switch)
        return card

    def _set_olcum(self, on):
        if on == self.olcum:
            return

        def done(_):
            self.olcum = on
            self.c.engine.store.history("uygulama_ayari", "temizlik_olcum", True, str(on))
            self.app.set_status(t("ui.temizlik.olcum_acik" if on else "ui.temizlik.olcum_kapali"), "iyi")
            self.data_reloaded()

        def failed(_exc):
            dialogs.show_message(self.app, t("ui.hata_baslik"), t("ui.temizlik.olcum_hata"), "sorun")
            self.data_reloaded()

        self.app.worker.run(temizlik_olcum.enable if on else temizlik_olcum.disable, done, failed)

    def _row(self, item):
        card = w.Card(layout="h", spacing=10)
        text = QVBoxLayout()
        name = QLabel(t(f"ui.temizlik.{item['id']}"))
        name.setObjectName("CardTitle")
        text.addWidget(name)
        text.addWidget(w.label(t(f"ui.temizlik.{item['id']}_not"), muted=True, size=12))
        if item["calisiyor"]:
            text.addWidget(w.colored(t("ui.temizlik.calisiyor"), "uyari"))
        card.lay.addLayout(text, 1)
        card.lay.addWidget(w.label(t("ui.temizlik.boyut", mb=_mb(item["boyut"])) if item["adet"] else t("ui.temizlik.temiz"),
                                   muted=True, wrap=False))
        usable = item["adet"] > 0 and not item["calisiyor"]
        box = QCheckBox()
        box.setChecked(usable)
        box.setEnabled(usable)
        box.setAccessibleName(t(f"ui.temizlik.{item['id']}"))
        self.checks[item["id"]] = box
        card.lay.addWidget(box)
        return card

    def _clean_all(self):
        for box in self.checks.values():
            if box.isEnabled():
                box.setChecked(True)
        self._clean()

    def _clean(self):
        chosen = [i for i in self.found if self.checks[i["id"]].isChecked()]
        if not chosen:
            return
        total = sum(i["boyut"] for i in chosen)
        listing = "\n".join("• " + t("ui.temizlik." + i["id"]) + ": " + _mb(i["boyut"]) + " MB" for i in chosen)
        if not dialogs.ask_yes_no(self.app, t("ui.dikkat"), t("ui.temizlik.soru_liste", liste=listing, mb=_mb(total))):
            return
        ids = [i["id"] for i in chosen]
        self.app.worker.run(lambda: cleaners.clean(ids, t("ui.temizlik.oturum_adi")), self._cleaned,
                            lambda _exc: self.app.set_status(t("hata.beklenmeyen"), "sorun"), serial=False)

    def _cleaned(self, result):
        failed = result["basarisiz"]
        text = t("ui.temizlik.sonuc", adet=result["kaldirilan"], mb=_mb(result["boyut"]))
        if failed:
            text = t("ui.temizlik.sonuc_hata", adet=result["kaldirilan"], hata=len(failed))
        self.app.set_status(text, "uyari" if failed or result["atlanan"] else "iyi")
        if result.get("oturum"):
            self.last_move = (result["oturum"], result["kaldirilan"], _mb(result["boyut"]))
        if failed or result["atlanan"]:
            lines = [f"{f['yol']}: {f['neden']}" for f in failed]
            if result["atlanan"]:
                lines.append(t("ui.temizlik.atlandi", liste=", ".join(t(f"ui.temizlik.{i}") for i in result["atlanan"])))
            dialogs.show_message(self.app, t("ui.menu.temizlik"), "\n".join(lines), "uyari")
        self.refresh()
