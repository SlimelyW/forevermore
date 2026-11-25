"""Kanıt döngüsü (Yol haritası Tur 1): oyun sayfasında tek düğme "Ölç ve hazırla".

ölç (kullanıcı "Oyundayım, başla" deyince) → hazırla → (oyna) → ölç → tek cümle sonuç + "Geri al". Yeni ölçüm kodu yok:
- korumasız oyun: presentmon.capture (Ölçüm sayfasıyla aynı yakalama), tekrar başına dongu.OYUN_SN;
- anti-cheat'li oyun (ya da PresentMon yoksa): oyun içi ölçüm YOK; oyun kapalıyken system_measure.sample_idle
  (işlemci, RAM, disk yükü, süreç sayısı) ve kart bunu açıkça yazar.
Hazırlık app.prepare_game'dir (motor: yedek + Değişiklikler + geri alma); isteğe bağlı Boost BoostPage.run_quiet.
Sonuç app/measure/dongu.py'de hesaplanır (fark / gürültü; yüzde yok). Durum yalnızca bellekte tutulur.
"""

import os
import threading

from PySide6.QtWidgets import QApplication, QCheckBox, QProgressBar, QVBoxLayout, QWidget

from app.core import settings
from app.core.i18n import t
from app.engine import driver_tools
from app.games import profiles
from app.games.runtime import ProcessOps
from app.measure import dongu, presentmon, system_measure
from app.ui import dialogs, motion, theme, widgets as w
from app.ui.managers_ui import tool_check_text
from app.ui.page_measure import _default_sampler, _fmt

ADIMLAR = ("once", "hazirla", "sonra", "bitti")


def sonuc_metni(sonuc):
    """Tek cümle: karar + o seviyedeki ölçümlerin adı. Yüzde yazılmaz."""
    karar = sonuc["karar"]
    if karar in ("yetersiz", "fark_yok"):
        return t(f"kanit.sonuc.{karar}")
    top = max(row[3] for row in sonuc["satirlar"])
    rows = [row for row in sonuc["satirlar"] if row[4] is not None and (karar == "karisik" or row[3] == top)]
    return t(f"kanit.sonuc.{karar}", liste=", ".join(
        t("kanit.iyilesti" if row[4] else "kanit.kotulesti", ad=t(f"olcum.metrik.{row[0]}")) for row in rows))


def sonuc_tonu(sonuc):
    if sonuc["karar"] in ("kucuk", "belirgin"):
        return "iyi" if any(row[4] for row in sonuc["satirlar"]) else "sorun"
    return "uyari" if sonuc["karar"] == "karisik" else None


class KanitDongusu:
    def __init__(self, page):
        self.page, self.app = page, page.app
        self.oyun = None        # döngünün oyunu (id): adımlar yalnızca o oyunun sayfasında görünür
        self.asama = None       # None (boşta) / "once" / "hazirla" / "sonra" / "bitti"
        self.tur = "oyun"       # "oyun" (PresentMon) / "sistem" (anti-cheat'li oyun ya da PresentMon yok)
        self.boost = False      # "Arka plan programlarını da kapat" kutusu (varsayılan kapalı)
        self.pm = (None, None)  # PresentMon yolu ve onaylanan özeti
        self.boost_plan = ([], [])
        self.olcum = {}         # {"once": [tekrar başına değerler], "sonra": [...]}
        self.sonuc = None       # dongu.karsilastir çıktısı
        self.mesaj = ""         # sonuç yoksa nedeni (durduruldu / ölçülemedi / hiçbir şey değişmedi)
        self.boost_metin, self.boost_acilan = "", []
        self.ilerleme, self.status = "", None
        self.rakamlar_acik = False
        self.bekliyor = False   # "önce": oyun açıldı, kullanıcının "Oyundayım, başla"sı bekleniyor (menü kareleri ölçülmesin)
        self.cancel = threading.Event()
        self.calisan = lambda: {exe for _pid, exe in ProcessOps().list_processes()}  # testte değiştirilir

    @property
    def calisiyor(self):
        return self.asama in ("once", "hazirla", "sonra")

    def gosteriyor(self, game):
        return self.asama is not None and self.oyun == game["id"]

    def _hazir(self, game):
        return self.app.prepared_game is not None and self.app.prepared_game["id"] == game["id"]

    def _sure(self):
        return dongu.TEKRAR * (dongu.OYUN_SN if self.tur == "oyun" else dongu.SISTEM_SN)

    # ------------------------------------------------------------------ akış
    def baslat(self, game):
        app = self.app
        if self.calisiyor or app.busy or app._blocked():
            return
        secili = profiles.runtime_selected(game)
        if not secili and not self.boost:
            app.set_status(t("kanit.secenek_yok"), "uyari")
            return
        exe = None if game.get("anti_cheat") else presentmon.find_presentmon()  # korumalı oyunda oyun içi ölçüm yok
        tur = "oyun" if exe else "sistem"

        def onay(running, tweaks, check):
            if self.calisiyor:  # çift tıklama
                return
            if not (secili or running or tweaks):
                app.set_status(t("kanit.secenek_yok"), "uyari")
                return
            parts = []
            if secili:
                parts.append(t("kanit.onay.hazirla", liste=", ".join(t(f"ui.hazirla.ad.{k}") for k in secili)))
            if running:
                parts.append(t("ui.boost.onizleme", liste=", ".join(running)) + " " + t("kanit.onay.boost_not"))
            if tweaks:
                parts.append(t("ui.boost.tek_ayarlar", liste=", ".join(tw["ad"] for tw in tweaks)) + " "
                             + t("kanit.onay.boost_ayar"))  # oyun kapanınca geri alınan yalnızca hazırlık (Denetim YAYIN K4)
            sn = dongu.TEKRAR * (dongu.OYUN_SN if tur == "oyun" else dongu.SISTEM_SN)
            parts.append(t(f"kanit.onay.olcum_{tur}", sn=sn))
            if tur == "oyun":  # anti-cheat izi yok ≠ koruma yok (Denetim YAYIN A1)
                parts.append(t("kanit.onay.koruma_bilinmiyor"))
            parts.append(t("kanit.onay.geri"))
            if not dialogs.ask_yes_no(app, t("kanit.dugme"), "\n\n".join(parts), yes_text=t("kanit.dugme"),
                                      no_text=t("ui.vazgec")):
                return
            if check and (not check["imza_gecerli"] or driver_tools.tools_in_user_folder()):
                # yönetici olarak çalışacak üçüncü parti exe: Ölçüm sayfasıyla aynı soru
                if not dialogs.ask_yes_no(app, t("ui.dikkat"), tool_check_text(check)):
                    return
            self.oyun, self.tur = game["id"], tur
            self.pm, self.boost_plan = (exe, check["sha256"] if check else None), (running, tweaks)
            self.olcum, self.sonuc, self.mesaj, self.boost_metin, self.boost_acilan = {}, None, "", "", []
            # geri yükleme noktası sorusu ölçümden ÖNCE: oyun açıkken pencere çıkmasın
            app.ensure_prepared(lambda: self._olc(game, "once"), lambda: None)

        def imza(running, tweaks):
            if not exe:
                onay(running, tweaks, None)
                return
            app.worker.run(lambda: driver_tools.verify(exe), lambda check: onay(running, tweaks, check),
                           lambda exc: app.set_status(str(exc), "sorun"), serial=False)

        if self.boost:
            app._page("boost").preview(imza)
        else:
            imza([], [])

    def _olc(self, game, taraf):
        self.asama, self.ilerleme = taraf, ""
        self.cancel.clear()
        if self.tur == "oyun":
            motion.set_paused(True)  # ölçüm sürerken animasyon yok (Ölçüm sayfasıyla aynı)
            if taraf == "once":
                # HAZIRLAMADAN, normal kullanıcı yetkisiyle açılır: "önce" ölçümü ayarsız hâli görmeli
                if os.path.basename(game["exe"]).lower() not in self.calisan() and not profiles.launch(game):
                    self.app.set_status(t("ui.oyun_baslatilamadi"), "uyari")
                # Ölçüm oyun açılır açılmaz başlarsa menü/yükleme kareleri ölçülür ve sonuç yanlış çıkar (Denetim YAYIN K1)
                self.bekliyor = True
                self.page.data_reloaded()
                return
        self._olcume_basla(game, taraf)

    def oyundayim(self, game):
        """"Oyundayım, başla": kullanıcı maça/haritaya girdi; "önce" ölçümü şimdi başlar (ilk tekrarda geri sayım: oyuna dönme payı)."""
        if self.bekliyor and self.asama == "once":
            self.bekliyor = False
            self._olcume_basla(game, "once")

    def durdur(self):
        if self.bekliyor:  # henüz ölçüm başlamadı: iş parçacığı yok, döngü burada biter
            self._bitir(None, mesaj=t("kanit.durduruldu"))
        else:
            self.cancel.set()

    def _olcume_basla(self, game, taraf):
        app = self.app
        name = os.path.basename(game["exe"]).lower()
        exe, sha = self.pm
        oyun, toplam = self.tur == "oyun", self._sure()
        self.page.data_reloaded()
        factory = app.live_sampler_factory or _default_sampler

        def say(text):
            app.worker.call_soon(self._ilerle, text)

        def job():
            runs, atlanan, adim = [], 0, 0
            for i in range(dongu.TEKRAR + (1 if oyun else 0)):  # oyunda bir tekrar fazla: geçişe denk gelen atılır
                if len(runs) >= dongu.TEKRAR:
                    break
                if self.cancel.is_set():
                    raise presentmon.MeasureError("iptal")
                try:
                    if oyun:
                        def progress(stage, info, base=i * dongu.OYUN_SN):
                            if stage == "geri_sayim":
                                say(t("kanit.ilerleme.geri_sayim", sn=info["kalan"]))
                            elif not info["calisiyor"]:
                                say(t("kanit.ilerleme.calismiyor"))
                            else:
                                say(t("kanit.ilerleme.suruyor" if info["on_planda"] else "kanit.ilerleme.arkada",
                                      sn=base + round(info["sayilan"]), toplam=toplam))
                        values, ayrinti = presentmon.capture(
                            name, dongu.OYUN_SN, exe, sha, progress=progress, cancel=self.cancel.is_set,
                            countdown=presentmon.COUNTDOWN_SN if taraf == "once" and i == 0 else 0)
                        if ayrinti.get("adim"):  # tekrarın ortasında kare hızı basamak gibi değişti: menü/yükleme -> oyun geçişi
                            adim += 1
                            continue
                    else:
                        acik = name in self.calisan()
                        values, _details = system_measure.sample_idle(
                            factory, dongu.SISTEM_SN,
                            lambda done, _total, base=i * dongu.SISTEM_SN: say(
                                t("kanit.ilerleme.suruyor", sn=base + done, toplam=toplam)), cancel=self.cancel.is_set)
                        if self.cancel.is_set():  # Durdur yarım tekrarı sonuca katmaz (Denetim YAYIN K8)
                            raise presentmon.MeasureError("iptal")
                        if acik or name in self.calisan():  # oyun açıkken ölçülen yük ayara yazılmasın (Denetim YAYIN K7)
                            atlanan += 1
                            continue
                except presentmon.MeasureError as exc:
                    if exc.code == "iptal" or len(runs) < dongu.EN_AZ_TEKRAR:
                        raise
                    break  # eksik tekrarla devam: sonuçta kaç tekrar ölçüldüğü yazılır
                runs.append(values)
            if len(runs) < dongu.EN_AZ_TEKRAR and adim:
                raise presentmon.MeasureError("gecis")
            if atlanan and len(runs) < dongu.EN_AZ_TEKRAR:
                raise presentmon.MeasureError("oyun_acik")
            return runs

        app.worker.run(job, lambda runs: self._olculdu(game, taraf, runs), self._hata, serial=False)

    def _ilerle(self, text):
        self.ilerleme = text
        if self.status is not None:
            self.status.setText(text)

    def _olculdu(self, game, taraf, runs):
        self.olcum[taraf] = runs
        if taraf == "once":
            self._hazirla(game)
        else:
            self._bitir(game, sonuc=dongu.karsilastir(self.olcum["once"], runs, self.tur))

    def _hazirla(self, game):
        app = self.app
        self.asama, self.ilerleme = "hazirla", ""
        self.page.data_reloaded()

        def boost_bitti(text="", opened=()):
            self.boost_metin, self.boost_acilan = text or "", list(opened)
            if self._hazir(game) or self.boost_metin:
                self._olc(game, "sonra")
            else:  # hepsi zaten öyleydi / hazırlık yapılamadı: ikinci ölçüm bir şey göstermez
                # "yapılamadı" (meşgul / hata) "zaten öyleydi" gibi gösterilmesin (Denetim YAYIN K6)
                yapilamadi = bool(profiles.runtime_selected(game)) and app.prep_results is None
                self._bitir(game, mesaj=t("kanit.hazirlanamadi" if yapilamadi else "kanit.degisiklik_yok"))

        def hazirlandi():
            running, tweaks = self.boost_plan
            if running or tweaks:
                app._page("boost").run_quiet(running, tweaks, boost_bitti)
            else:
                boost_bitti()

        if profiles.runtime_selected(game):
            app.prepare_game(game, done=hazirlandi)
        else:
            hazirlandi()

    def _bitir(self, game, sonuc=None, mesaj=""):
        motion.set_paused(False)
        self.bekliyor = False
        self.asama, self.sonuc, self.mesaj = "bitti", sonuc, mesaj
        if sonuc:  # Ölçüm sayfasının listesine de düşer: taraf başına tek kayıt (tekrarların ortalaması)
            page = self.app._page("olcum")
            for taraf in ("once", "sonra"):
                page.store.add(self.tur, taraf, dongu.ortalama(self.olcum[taraf]),
                               {"tekrar": len(self.olcum[taraf]), "kanit_dongusu": True}, note=os.path.basename(game["exe"]))
            page.stale = True
        QApplication.alert(self.app, 0)  # odak çalınmaz; görev çubuğu yanıp söner
        self.page.data_reloaded()

    def _hata(self, exc):
        if isinstance(exc, presentmon.MeasureError) and exc.code == "oyun_acik":
            mesaj = t("kanit.oyun_acik")
        elif isinstance(exc, presentmon.MeasureError) and exc.code == "gecis":
            mesaj = t("kanit.gecis")
        elif isinstance(exc, presentmon.MeasureError):
            mesaj = t("kanit.durduruldu") if exc.code == "iptal" else t(f"olcum.neden.{exc.diag.get('neden', 'on_plan')}")
        else:
            mesaj = t("olcum.hata")
        self._bitir(None, mesaj=mesaj)

    def geri_alinabilir(self, game):
        return self._hazir(game) or any(self.app.c.engine.store.has(i) for i in self.boost_acilan)

    def geri_al(self, game):
        """Hazırlık (motor) ve bu döngüde Boost'un açtığı ayarlar geri alınır. Kapatılan programlar geri açılmaz."""
        store = self.app.c.engine.store
        ids = [i for i in self.boost_acilan if store.has(i)]

        def sonraki():
            if ids:
                self.app.revert(ids.pop(0), sonraki)
                return
            if self.boost_acilan:  # geri alınamayan (hâlâ Değişiklikler'de duran) Boost listesinde kalır
                settings.set("boost_ayarlari", [i for i in settings.get("boost_ayarlari") or []
                                                if i not in self.boost_acilan or store.has(i)])
            self.kapat()

        if self._hazir(game):
            self.app.unprepare_game(then=sonraki)
        else:
            sonraki()

    def kapat(self):
        self.oyun = self.asama = self.sonuc = None
        self.bekliyor = False
        self.boost_acilan = []
        self.page.data_reloaded()

    # ------------------------------------------------------------------ görünüm
    def dugme(self, game):
        """Ana satırın tek birincil düğmesi."""
        hazir = self._hazir(game)
        start = w.button(t("kanit.dugme"), lambda: self.baslat(game), primary=True)
        start.setMinimumHeight(44)
        start.setEnabled(self.page.c.can_modify and not self.calisiyor and not hazir)
        start.setToolTip(t("kanit.hazir_ipucu" if hazir else "kanit.dugme_ipucu"))
        return start

    def kart(self, game):
        """Düğmenin altı. Boşta: tek satır + Boost kutusu. Çalışırken: adımlar, yönerge, ilerleme. Bitince: sonuç + Geri al."""
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        self.status = None
        if not self.gosteriyor(game):
            key = "sistem" if game.get("anti_cheat") else "oyun" if presentmon.find_presentmon() else "pm_yok"
            lay.addWidget(w.label(t(f"kanit.aciklama_{key}"), muted=True, size=12))
            kutu = QCheckBox(t("kanit.boost_kutu"))
            kutu.setChecked(self.boost)
            kutu.setEnabled(not self.calisiyor)
            kutu.toggled.connect(lambda on: setattr(self, "boost", on))
            lay.addWidget(kutu)
            return box
        if self.calisiyor:
            lay.addWidget(self._adimlar())
            key = "hazirla" if self.asama == "hazirla" else "once_bekle" if self.bekliyor else f"{self.asama}_{self.tur}"
            yonerge = w.label(t(f"kanit.yonerge.{key}", sn=self._sure()), bold=True)
            yonerge.setFont(theme.ui_font(16, True))
            lay.addWidget(yonerge)
            if self.bekliyor:
                basla = w.button(t("kanit.oyundayim"), lambda: self.oyundayim(game), primary=True)
                basla.setMinimumHeight(44)
                lay.addWidget(w.hbox(basla, w.button(t("olcum.durdur"), self.durdur), None))
                return box
            bar = QProgressBar()
            bar.setRange(0, 0)
            lay.addWidget(bar)
            self.status = w.label(self.ilerleme, muted=True)
            lay.addWidget(self.status)
            if self.asama != "hazirla":
                lay.addWidget(w.hbox(w.button(t("olcum.durdur"), self.durdur), None))
            return box
        buttons = []
        if self.sonuc:
            lay.addWidget(self._adimlar())
            ton, metin = sonuc_tonu(self.sonuc), sonuc_metni(self.sonuc)
            head = w.colored(metin, ton) if ton else w.label(metin)
            head.setFont(theme.ui_font(16, True))
            lay.addWidget(head)
            once, sonra = self.sonuc["tekrar"]
            lay.addWidget(w.label(t("kanit.tekrar", once=once, sonra=sonra), muted=True, size=12))
            if self.tur == "sistem":
                lay.addWidget(w.label(t("kanit.not_sistem"), muted=True, size=12))
        else:
            lay.addWidget(w.label(self.mesaj, bold=True))
        if self.boost_metin:
            lay.addWidget(w.label(self.boost_metin + " " + t("kanit.onay.boost_not"), muted=True, size=12, plain=True))
        if self.geri_alinabilir(game):
            buttons.append(w.button(t("ui.hazirla.geri_al"), lambda: self.geri_al(game)))
        table = self._rakamlar() if self.sonuc else None
        if table is not None:
            toggle = w.button(t("olcum.detay_gizle" if self.rakamlar_acik else "olcum.detay_goster"))

            def flip():
                self.rakamlar_acik = not self.rakamlar_acik
                table.setVisible(self.rakamlar_acik)
                toggle.setText(t("olcum.detay_gizle" if self.rakamlar_acik else "olcum.detay_goster"))
            toggle.clicked.connect(flip)
            buttons.append(toggle)
        buttons.append(w.button(t("olcum.kapat"), self.kapat))
        lay.addWidget(w.hbox(*buttons, None))
        if table is not None:
            lay.addWidget(table)
            table.setVisible(self.rakamlar_acik)  # çocuk olduktan sonra: ebeveynsiz setVisible(True) üst pencere olur
        return box

    def _adimlar(self):
        """Dört adımlı ince şerit: biten ✓, sıradaki yeşil rozet, bekleyen soluk."""
        index = ADIMLAR.index(self.asama)
        parts = []
        for i, adim in enumerate(ADIMLAR):
            text = t(f"kanit.adim.{f'sonra_{self.tur}' if adim == 'sonra' else adim}")
            if i == index:
                parts.append(w.badge(f"{i + 1}  {text}", "iyi"))
            else:
                parts.append(w.label(("✓ " if i < index else f"{i + 1}  ") + text, muted=True, wrap=False, size=12))
        return w.hbox(*parts, None, spacing=14)

    def _rakamlar(self):
        """"Rakamları göster": tekrarların ortalaması; fark sütunu ve yüzde bilerek yok (karar gürültüye göre verilir)."""
        table = QWidget()
        lay = QVBoxLayout(table)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        rows = [[w.label(t(f"olcum.sutun.{k}"), bold=True) for k in ("metrik", "once", "sonra")]]
        for metric, once, sonra, _level, _better in self.sonuc["satirlar"]:
            rows.append([w.label(t(f"olcum.metrik.{metric}")), theme.tabular(w.label(_fmt(metric, once))),
                         theme.tabular(w.label(_fmt(metric, sonra)))])
        for cells in rows:
            for cell, width in zip(cells, (300, 130, 130)):
                cell.setMinimumWidth(width)
                cell.setMaximumWidth(int(width * 1.4))
            lay.addWidget(w.hbox(*cells, None))
        return table
