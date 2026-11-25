"""Temizlik sayfasının altındaki "Bakım araçları" kartları: sistem dosyalarını onar (sfc + DISM), sürücü optimizasyonu,
ağ sıfırlama, Windows Update onarma, disk taraması, bileşen deposu, ayrılmış depolama ve Windows panelleri.

Mantık app/engine/bakim.py ve bakim_araclari.py'dedir (Windows'un kendi araçları; ayar yazmaz). Burada yalnızca durum + çizim var.
Durum sayfa yeniden kurulsa da (data_reloaded) burada kalır; çalışırken ilerleme etiketi yerinde güncellenir.
Uzun işler arka plan havuzunda (serial=False) çalışır: Değişiklikler sırası 30 dakika boyunca beklemez.
"""

import threading

from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QCheckBox, QLabel, QPlainTextEdit, QProgressBar

from app.core.i18n import t
from app.engine import bakim, bakim_araclari
from app.ui import dialogs, widgets as w

_TON = {"temiz": "iyi", "onarildi": "iyi", "tamam": "iyi", "tekrar": "uyari", "belirsiz": "uyari", "iptal": "uyari",
        "kismen": "uyari", "yok": "uyari", "bilgi": "uyari"}  # listede olmayan sonuç = sorun

# Kart -> düğmeleri (bakim_araclari.ARACLAR kimlikleri). Kart başlığı/notu: ui.bakim.<kart>, ui.bakim.<kart>_not.
_ARAC_KARTLARI = {"ag_sifirla": ("ag_sifirla",), "wu_onar": ("wu_onar", "wu_onar_sert"), "disk_tara": ("disk_tara",),
                  "bilesen_temizle": ("bilesen_temizle",), "ayrilmis": ("ayrilmis_kapat", "ayrilmis_ac")}
# Araca özel sonuç metni olanlar (ui.bakim.<araç>_<sonuç>); gerisi ortak: ui.bakim.arac_<sonuç>.
_OZEL_SONUC = {"ag_sifirla": ("tamam", "kismen", "yedeklenemedi"), "wu_onar": ("tamam",), "wu_onar_sert": ("tamam",),
               "disk_tara": ("temiz", "bilgi", "sorun"), "bilesen_temizle": ("tamam",), "ayrilmis_kapat": ("tamam",),
               "ayrilmis_ac": ("tamam",)}


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
        self.araclar = {kart: _Is() for kart in _ARAC_KARTLARI}
        self.suruculer = None   # None: okunuyor
        self.secim = {}         # harf -> işaretli mi (sayfa yeniden kurulunca korunur)
        self.tara_secim = {}    # disk taraması için aynı
        self._tara_dugme = None
        self._yukleniyor = False

    # ------------------------------------------------------------------ ortak
    @property
    def mesgul(self):
        return self.onar.calisiyor or self.surucu.calisiyor or any(s.calisiyor for s in self.araclar.values())

    def kapanista_iptal(self):
        """Pencere kapanırken çalışan her aracın iptal işaretini verir (hizmetleri yeniden başlatan son adımlar yine çalışır)."""
        for state in (self.onar, self.surucu, *self.araclar.values()):
            if state.calisiyor and state.iptal is not None:
                state.iptal.set()

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
        return ([head, self._onar_karti(), self._surucu_karti()] + [self._arac_karti(k) for k in _ARAC_KARTLARI]
                + [self._paneller_karti()])

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

    # ------------------------------------------------------------------ ağ, Windows Update, disk taraması, bileşen deposu, ayrılmış depolama
    def _arac_karti(self, kart):
        card = self._kart(kart)
        state = self.araclar[kart]
        if not self.page.c.can_modify:
            card.lay.addWidget(w.banner(t("ui.bakim.yetki"), "uyari"))
        if not state.calisiyor:
            if kart == "disk_tara":
                self._tara_satirlari(card)
            buttons = []
            for index, arac in enumerate(_ARAC_KARTLARI[kart]):
                button = w.button(t(f"ui.bakim.{arac}_dugme"), lambda a=arac: self._arac_sor(a), primary=index == 0)
                button.setEnabled(self.page.c.can_modify and not self.mesgul and (kart != "disk_tara" or bool(self._tara_secilen())))
                if kart == "disk_tara":
                    self._tara_dugme = button
                buttons.append(button)
            card.lay.addWidget(w.hbox(None, *buttons))
        self._calisma(card, state, t("ui.bakim.iptal_not"))
        return card

    def _ntfs(self):
        return [d["harf"] for d in self.suruculer or [] if d.get("fs") == "NTFS"]

    def _tara_satirlari(self, card):
        if self.suruculer is None:
            card.lay.addWidget(w.label(t("ui.bakim.surucu_okunuyor"), muted=True))
        elif not self._ntfs():
            card.lay.addWidget(w.label(t("ui.bakim.tara_yok"), muted=True))
        for letter in self._ntfs():
            box = QCheckBox(f"{letter}:")
            box.setChecked(self.tara_secim.get(letter, True))
            box.toggled.connect(lambda on, h=letter: self._tara_degisti(h, on))
            card.lay.addWidget(box)

    def _tara_degisti(self, letter, on):
        self.tara_secim[letter] = on
        try:  # sayfayı yeniden kurmadan: Başlat düğmesi yalnızca en az bir sürücü işaretliyken açık
            self._tara_dugme.setEnabled(self.page.c.can_modify and not self.mesgul and bool(self._tara_secilen()))
        except (AttributeError, RuntimeError):
            pass

    def _tara_secilen(self):
        return [h for h in self._ntfs() if self.tara_secim.get(h, True)]

    def _arac_kart_adi(self, arac):
        return next(kart for kart, araclar in _ARAC_KARTLARI.items() if arac in araclar)

    def _arac_sor(self, arac):
        spec = bakim_araclari.ARACLAR[arac]
        letters = self._tara_secilen() if arac == "disk_tara" else ()
        if arac == "disk_tara" and not letters:
            return
        commands = "\n".join(bakim_araclari.onizleme(arac, letters)).replace("\\", "\\​")  # uzun yollar satır kırabilsin
        parts = [t(f"ui.bakim.{arac}_onizleme")]
        if spec["geri_alinamaz"]:
            parts.insert(0, t("ui.bakim.geri_alinamaz"))  # en üstte: kaydırmadan görünsün
        if spec["yeniden_baslat"]:
            parts.append(t("ui.bakim.yeniden_baslat_not"))
        parts.append(t("ui.bakim.komutlar", liste=commands))
        if not dialogs.ask_yes_no(self.app, t(f"ui.bakim.{arac}_dugme"), "\n\n".join(parts),
                                  yes_text=t("ui.devam"), no_text=t("ui.vazgec"), height=480):
            return
        start = lambda: self._arac_basla(arac, letters)  # noqa: E731
        if spec["geri_yukleme"]:
            self.app.ensure_prepared(start, lambda: None)  # geri yükleme noktası önerisi (ayarlardaki seçime uyar)
        else:
            start()

    def _arac_basla(self, arac, letters):
        state = self.araclar[self._arac_kart_adi(arac)]
        state.calisiyor, state.iptal, state.sonuc, state.cikti, state.adim, state.yuzde = True, threading.Event(), None, "", 0, None
        state.metin = t("ui.bakim.arac_basliyor")
        cancel = state.iptal

        def progress(step, total, percent, name):  # çalıştıran iş parçacığından gelir: arayüze sinyalle taşınır
            self.app.worker.call_soon(self._arac_ilerle, arac, step, total, percent, name)

        failed = {"sonuc": "hata", "cikti": "", "yeniden_baslat": False, "yedek": None, "suruculer": []}
        self.app.worker.run(lambda: bakim_araclari.calistir_arac(arac, cancel, progress, harfler=letters),
                            lambda result: self._arac_bitti(arac, result), lambda _e: self._arac_bitti(arac, failed),
                            serial=False)
        self.page.data_reloaded()

    def _arac_ilerle(self, arac, step, total, percent, name):
        state = self.araclar[self._arac_kart_adi(arac)]
        if not state.calisiyor or state.iptal.is_set():
            return
        if percent is not None or step != state.adim:
            state.yuzde = percent
        state.adim = step
        state.metin = t("ui.bakim.adim", n=step, toplam=total, ad=t(f"ui.bakim.adim_{name}"))
        self._canli(state)

    def _arac_bitti(self, arac, result):
        code = result["sonuc"]
        key = f"ui.bakim.{arac}_{code}" if code in _OZEL_SONUC[arac] else f"ui.bakim.arac_{code}"
        lines = [t(key)]
        if result["yedek"]:
            lines.append(t("ui.bakim.ag_yedek", klasor=result["yedek"]))
        if result["birakilan"]:
            lines.append(t("ui.bakim.bak_birakilan", liste="\n".join(result["birakilan"])))
        if result["yeniden_baslat"]:
            lines.append(t("ui.bakim.yeniden_baslat_simdi"))
        if arac == "disk_tara" and result["suruculer"]:
            lines.append(t("ui.bakim.tara_surucu", liste=", ".join(h + ":" for h in result["suruculer"])))
        self._bitir(self.araclar[self._arac_kart_adi(arac)], "\n".join(lines), _TON.get(code, "sorun"), result["cikti"],
                    None if code == "yetki" else code, arac, code in ("tamam", "temiz"))

    # ------------------------------------------------------------------ Windows panelleri
    def _paneller_karti(self):
        card = self._kart("paneller")
        card.lay.addWidget(w.flow(*[w.button(t(f"ui.bakim.panel_{name}"),
                                             lambda h=target: w.open_target({"tur": "program", "hedef": h}))
                                    for name, target in bakim_araclari.PANELLER]))
        return card
