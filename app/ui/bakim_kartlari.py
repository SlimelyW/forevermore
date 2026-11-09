"""Temizlik sayfasının altındaki "Bakım araçları" kartları: sistem dosyalarını onar (sfc + DISM) ve sürücü optimizasyonu.

Mantık app/engine/bakim.py'dedir (Windows'un kendi araçları; ayar yazmaz). Burada yalnızca durum + çizim var.
Durum sayfa yeniden kurulsa da (data_reloaded) burada kalır; çalışırken ilerleme etiketi yerinde güncellenir.
Uzun işler arka plan havuzunda (serial=False) çalışır: Değişiklikler sırası 30 dakika boyunca beklemez.
"""

import threading

from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QCheckBox, QLabel, QPlainTextEdit, QProgressBar

from app.core.i18n import t
from app.engine import bakim
from app.ui import dialogs, widgets as w

_TON = {"temiz": "iyi", "onarildi": "iyi", "tamam": "iyi", "tekrar": "uyari", "belirsiz": "uyari", "iptal": "uyari",
        "kismen": "uyari", "yok": "uyari"}  # listede olmayan sonuç = sorun


class _Is:
    """Bir kartın çalışma durumu."""

    def __init__(self):
        self.calisiyor = False
        self.iptal = None       # threading.Event
        self.adim = None
        self.metin = ""
        self.yuzde = None       # None: belirsiz çubuk
        self.sonuc = None       # (metin, ton)
        self.cikti = ""
        self.detay = False
        self.etiket = self.cubuk = None


class BakimKartlari:
    def __init__(self, page):
        self.page = page
        self.app = page.app
        self.onar = _Is()
        self.surucu = _Is()
        self.suruculer = None   # None: okunuyor
        self.secim = {}         # harf -> işaretli mi (sayfa yeniden kurulunca korunur)
        self._yukleniyor = False

    # ------------------------------------------------------------------ ortak
    @property
    def mesgul(self):
        return self.onar.calisiyor or self.surucu.calisiyor

    def yukle(self):
        if self.suruculer is None and not self._yukleniyor:
            self._yukleniyor = True
            self.app.worker.run(bakim.suruculer, self._suruculer_geldi, lambda _e: self._suruculer_geldi([]), serial=False)

    def _suruculer_geldi(self, rows):
        self._yukleniyor = False
        self.suruculer = rows
        self.page.data_reloaded()

    def widgets(self):
        head = w.label(t("ui.bakim.baslik"), bold=True, size=15)
        return [head, self._onar_karti(), self._surucu_karti()]

    def _kart(self, key):
        card = w.Card(spacing=8)
        name = QLabel(t(f"ui.bakim.{key}"))
        name.setObjectName("CardTitle")
        card.lay.addWidget(name)
        card.lay.addWidget(w.label(t(f"ui.bakim.{key}_not"), muted=True, size=12))
        return card

    def _calisma(self, card, state, cancel_text):
        """İlerleme, İptal, sonuç ve Ayrıntı alanı."""
        if state.calisiyor:
            state.etiket = w.label(state.metin)
            state.cubuk = QProgressBar()
            card.lay.addWidget(state.etiket)
            card.lay.addWidget(state.cubuk)
            self._canli(state)
            stop = w.button(t("ui.bakim.iptal"), lambda: self._iptal(state))
            stop.setEnabled(not state.iptal.is_set())
            card.lay.addWidget(w.hbox(w.label(cancel_text, muted=True, size=12), None, stop))
            return
        if state.sonuc:
            card.lay.addWidget(w.colored(*state.sonuc))
        if state.cikti:
            toggle = w.button(t("ui.bakim.detay_gizle" if state.detay else "ui.bakim.detay"),
                              lambda: self._detay(state))
            card.lay.addWidget(w.hbox(None, toggle))
            if state.detay:
                box = QPlainTextEdit()
                box.setReadOnly(True)
                box.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
                box.setPlainText(state.cikti)
                box.setMaximumHeight(240)
                box.setAccessibleName(t("ui.bakim.detay"))
                card.lay.addWidget(box)

    def _canli(self, state):
        """Çalışırken sayfayı yeniden kurmadan etiketi ve çubuğu günceller."""
        try:
            if state.etiket is not None:
                state.etiket.setText(state.metin)
            if state.cubuk is not None:
                state.cubuk.setRange(0, 0 if state.yuzde is None else 100)
                if state.yuzde is not None:
                    state.cubuk.setValue(state.yuzde)
        except RuntimeError:  # sayfa yeniden kuruldu, widget gitti
            pass

    def _iptal(self, state):
        state.iptal.set()
        state.metin = t("ui.bakim.durduruluyor")
        self.page.data_reloaded()

    def _detay(self, state):
        state.detay = not state.detay
        self.page.data_reloaded()

    def _bitir(self, state, text, tone, output, kind, ident, ok):
        state.calisiyor, state.sonuc, state.cikti, state.detay = False, (text, tone), output, False
        if kind:
            self.page.c.engine.store.history("bakim", ident, ok, kind)
        self.app.set_status(text.split("\n")[0], tone if tone in ("iyi", "sorun") else "")
        self.page.data_reloaded()

    # ------------------------------------------------------------------ sistem dosyalarını onar
    def _onar_karti(self):
        card = self._kart("onar")
        state = self.onar
        if not self.page.c.can_modify:
            card.lay.addWidget(w.banner(t("ui.bakim.yetki"), "uyari"))
        if not state.calisiyor:
            start = w.button(t("ui.bakim.onar_dugme"), self._onar_sor, primary=True)
            start.setEnabled(self.page.c.can_modify and not self.mesgul)
            card.lay.addWidget(w.hbox(None, start))
        self._calisma(card, state, t("ui.bakim.iptal_not"))
        return card

    def _onar_sor(self):
        if not dialogs.ask_yes_no(self.app, t("ui.dikkat"), t("ui.bakim.onar_soru")):
            return
        self.app.ensure_prepared(self._onar_basla, lambda: None)  # geri yükleme noktası önerisi (ayarlardaki seçime uyar)

    def _onar_basla(self):
        state = self.onar
        state.calisiyor, state.iptal, state.sonuc, state.cikti, state.adim, state.yuzde = True, threading.Event(), None, "", 1, None
        state.metin = t("ui.bakim.adim", n=1, toplam=2, ad=t("ui.bakim.adim_sfc"))
        cancel = state.iptal

        def progress(step, total, percent):  # çalıştıran iş parçacığından gelir: arayüze sinyalle taşınır
            self.app.worker.call_soon(self._onar_ilerle, step, total, percent)

        self.app.worker.run(lambda: bakim.sistem_onar(cancel, progress), self._onar_bitti, self._onar_hata, serial=False)
        self.page.data_reloaded()

    def _onar_ilerle(self, step, total, percent):
        state = self.onar
        if not state.calisiyor or state.iptal.is_set():
            return
        if percent is not None or step != state.adim:
            state.yuzde = percent
        state.adim = step
        state.metin = t("ui.bakim.adim", n=step, toplam=total, ad=t("ui.bakim.adim_sfc" if step == 1 else "ui.bakim.adim_dism"))
        self._canli(state)

    def _onar_bitti(self, result):
        code = result["sonuc"]
        text = t(f"ui.bakim.onar_{code}")
        self._bitir(self.onar, text, _TON.get(code, "sorun"), result["cikti"], None if code == "yetki" else code,
                    "sistem_onar", code in ("temiz", "onarildi"))

    def _onar_hata(self, _exc):
        self._bitir(self.onar, t("ui.bakim.onar_baslatilamadi"), "sorun", "", "baslatilamadi", "sistem_onar", False)

    # ------------------------------------------------------------------ sürücüyü optimize et
    def _surucu_karti(self):
        card = self._kart("surucu")
        state = self.surucu
        if not self.page.c.can_modify:
            card.lay.addWidget(w.banner(t("ui.bakim.yetki"), "uyari"))
        if self.suruculer is None:
            card.lay.addWidget(w.label(t("ui.bakim.surucu_okunuyor"), muted=True))
        elif not self.suruculer:
            card.lay.addWidget(w.label(t("ui.bakim.surucu_yok"), muted=True))
        elif not state.calisiyor:
            for drive in self.suruculer:
                card.lay.addWidget(self._surucu_satiri(drive))
            start = w.button(t("ui.bakim.surucu_dugme"), self._surucu_sor, primary=True)
            start.setEnabled(self.page.c.can_modify and not self.mesgul)
            card.lay.addWidget(w.hbox(None, start))
        self._calisma(card, state, "")
        return card

    def _surucu_satiri(self, drive):
        known = drive["tur"] in ("SSD", "HDD")
        box = QCheckBox(f"{drive['harf']}:  {t('ui.bakim.tur_' + drive['tur'].lower())}")
        box.setEnabled(known)
        box.setChecked(known and self.secim.get(drive["harf"], True))
        box.toggled.connect(lambda on, h=drive["harf"]: self.secim.__setitem__(h, on))
        self.secim.setdefault(drive["harf"], known)
        return box

    def _secilen(self):
        return [d["harf"] for d in self.suruculer or [] if d["tur"] in ("SSD", "HDD") and self.secim.get(d["harf"], True)]

    def _surucu_sor(self):
        chosen = self._secilen()
        if chosen and dialogs.ask_yes_no(self.app, t("ui.dikkat"), t("ui.bakim.surucu_soru", liste=", ".join(h + ":" for h in chosen))):
            self._surucu_basla(chosen)

    def _surucu_basla(self, letters):
        state = self.surucu
        state.calisiyor, state.iptal, state.sonuc, state.cikti, state.yuzde = True, threading.Event(), None, "", None
        state.metin = t("ui.bakim.surucu_adim", harf=letters[0], n=1, toplam=len(letters))
        cancel = state.iptal

        def progress(index, total, letter):
            self.app.worker.call_soon(self._surucu_ilerle, index, total, letter)

        self.app.worker.run(lambda: bakim.optimize(letters, cancel, progress), self._surucu_bitti,
                            lambda _e: self._surucu_bitti({"sonuc": "hata", "suruculer": [], "cikti": ""}), serial=False)
        self.page.data_reloaded()

    def _surucu_ilerle(self, index, total, letter):
        state = self.surucu
        if state.calisiyor and not state.iptal.is_set():
            state.metin = t("ui.bakim.surucu_adim", harf=letter, n=index, toplam=total)
            self._canli(state)

    def _surucu_bitti(self, result):
        code = result["sonuc"]
        lines = [t("ui.bakim.islem_tamam" if d["tamam"] else "ui.bakim.islem_hata", harf=d["harf"],
                   islem=t("ui.bakim.islem_" + d["islem"])) for d in result["suruculer"]]
        text = "\n".join([t(f"ui.bakim.surucu_{code}")] + lines)
        self._bitir(self.surucu, text, _TON.get(code, "sorun"), result["cikti"], None if code == "yetki" else code,
                    "surucu_optimize", code == "tamam")
