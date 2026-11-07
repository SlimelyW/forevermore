"""Oyunlar menüsü: üstte oyun seçimi, altında seçilen oyun için tek, sade bir sayfa.

İlk bakışta "Oyunu başlat" ve "Önerilen ayarları uygula"; diğerleri varsayılan olarak kapalı "Gelişmiş ayarlar"
bölümünde. Her terimin yanında tek cümlelik açıklama veren (i) düğmesi var.

Ayarlar yalnızca kalıcıdır (öncelik, GPU tercihi, tam ekran optimizasyonları): kaydedince motordan yazılır ve
Değişiklikler sayfasından geri alınır. Çalışan oyunla otomatik uygulama/geri alma YOK (oyun izleyici 7 Kasım 2026'da
kaldırıldı). Anti-cheat süreçlerine hiçbir ayar uygulanmaz (profiles.PROTECTED_EXES).
"""

import os
import time

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QButtonGroup, QComboBox, QFileDialog, QLabel, QProgressBar, QVBoxLayout, QWidget

from app.core import i18n, settings
from app.core.i18n import t, value_label
from app.games import canli_surec, discovery, guides, oyun_ayar, presets, profiles, recorder
from app.ui import dialogs, motion, theme, widgets as w
from app.ui.page_settings import about_data

PRIORITIES = ("Normal", "AboveNormal", "High")
GPU_PREFS = ("varsayilan", "guc_tasarrufu", "yuksek_performans")


def _when(iso):
    """"2026-11-07T12:00:05" -> "2026-11-07 12:00"."""
    return (iso or "").replace("T", " ")[:16]


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
        self.draft = None          # seçili oyunun düzenlenen profili
        self.candidates = {}       # oyun kimliği -> .exe adayları
        self.advanced_open = False
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
        self.ensure_built()
        # Oturum açılışında tepside başlayınca ilk tarama sürücüler hazır olmadan yapılmış olabilir: boş sonuç kalıcı olmasın.
        empty_and_old = self.scanned and not self.found and time.monotonic() - self.scan_finished > 60
        if (not self.scanned or empty_and_old) and not self.scanning:
            self._rescan()

    # ------------------------------------------------------------------ kurulum
    def build(self):
        super().build()
        self.header.addWidget(w.hbox(w.title(t("ui.menu.oyunlar")), None,
                                     self._scan_button(),
                                     w.button(t("ui.oyun_elle_ekle"), self._add_manual)))
        self.header.addWidget(w.label(t("ui.oyunlar_aciklama"), muted=True))
        if not self.c.can_modify:
            self.body.addWidget(w.banner(t("ui.oyun_izleyici_mod"), "uyari"))
        if self.store.load_error:  # oyun listesi dosyası bozuktu (ör. zorla kapatma): sessizce boş liste gösterilmez
            self.body.addWidget(w.banner(t(f"ui.oyun_liste_{self.store.load_error}"), "uyari"))
        if not self.scanned and not self.scanning:
            self._discover()  # uygulama açılınca (sayfa önceden kurulurken) arka planda
        self.store.ensure_anti_cheat()
        if self.editing is None or self.store.get(self.editing) is None:
            first = (self.store.games or [None])[0]
            self.editing = first["id"] if first else None
            self.draft = None
        self.body.addWidget(self._picker())
        game = self.store.get(self.editing) if self.editing else None
        if game is not None:
            self.body.addWidget(self._game_page(game))

    def _useful_card(self, items):
        """Bilgi sayfasından taşınan faydalı dış bağlantılar (data/hakkinda.json 'faydali'); tarayıcıda açılır."""
        card = w.Card(spacing=6)
        head = QLabel(t("ui.oyun_faydali.baslik"))
        head.setObjectName("CardTitle")
        card.lay.addWidget(head)
        card.lay.addWidget(w.label(t("ui.oyun_faydali.not"), muted=True, size=12))
        for item in items:
            parts = [(w.label(f"{item.get('etiket', '').removeprefix('Faydalı: ')}: {item.get('deger', '')}", selectable=True, wrap=False), 1)]
            if str(item.get("url", "")).startswith("https://"):
                parts.append(w.button(t("ui.bilgi.ac"), lambda _=False, u=item["url"]: os.startfile(u)))
            card.lay.addWidget(w.hbox(*parts))
        return card

    def _picker(self):
        """Tek açılır liste: önce listemdeki oyunlar, sonra bilgisayarda bulunup henüz eklenmemiş olanlar."""
        card = w.Card()
        combo = QComboBox()
        favorites = set(settings.get("favori_oyunlar") or [])
        for game in sorted(self.store.games, key=lambda g: g["id"] not in favorites):  # kararlı sıralama: favoriler üstte
            combo.addItem(("★ " if game["id"] in favorites else "") + game["ad"], ("oyun", game["id"]))
        remaining = self._remaining()
        if remaining:
            if self.store.games:
                combo.insertSeparator(combo.count())
            for game in remaining:
                combo.addItem(t("ui.oyun_ekle_secenek", ad=game["ad"], kaynak=game["kaynak"]), ("bulunan", game))
        # findData Python demetlerinde güvenilir değil (uygulamada -1 dönüyordu; kutu hep ilk oyunu gösteriyordu)
        combo.setCurrentIndex(next((i for i in range(combo.count()) if combo.itemData(i) == ("oyun", self.editing)), 0))
        combo.setMinimumWidth(420)
        combo.setMinimumHeight(36)
        combo.activated.connect(lambda _i: self._picked(combo.currentData()))
        caption = QLabel(t("ui.oyun_sec"))
        caption.setObjectName("CardTitle")
        card.lay.addWidget(w.hbox(caption, combo, None, spacing=12))
        if not self.store.games:  # liste varken tarama durumu Gelişmiş'te
            card.lay.addWidget(self._scan_status(len(remaining)))
            card.lay.addWidget(w.label(t("ui.oyun_yok"), muted=True))
        return card

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
        elif value != self.editing:
            self.editing, self.draft = value, None
            QTimer.singleShot(0, self.data_reloaded)

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
        self.editing = added["id"]
        self.draft = None
        QTimer.singleShot(0, self.data_reloaded)

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
        self.editing = added["id"]
        self.draft = None
        self.data_reloaded()

    def _remove(self, game):
        if dialogs.ask_yes_no(self.app, t("ui.oyun_kaldir"), t("ui.oyun_kaldir_soru", ad=game["ad"])):
            self.store.remove(game["id"])
            if self.editing == game["id"]:
                self.editing, self.draft = None, None
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
        if target:
            # tıklayınca: eski kayıtta Steam/Epic kısayolu yoksa yeniden bulunur (TEST_FAZI A7: oyun Steam'siz açılıyordu)
            start = w.button(t("ui.oyun_baslat"),
                             lambda: os.startfile(profiles.launch_target(game, rediscover=True) or target), primary=True)
            start.setMinimumHeight(44)
            parts.append(start)
        done, total = presets.recommended_count(game["profil"], self._two_gpus())
        if total and done == total:
            parts.append(w.badge(t("ui.oyun_oner_tamam", n=done, m=total), "iyi"))
        elif total:
            apply = w.button(t("ui.oyun_onerilen", n=done, m=total), lambda: self._apply_recommended(game))
            apply.setMinimumHeight(44)
            apply.setToolTip(t("ui.oyun_onerilen_ipucu"))
            apply.setEnabled(self.c.can_modify)
            parts.append(apply)
        return w.hbox(*parts, None, spacing=12)

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
            card.lay.addWidget(w.label(t("ui.oyun_kayit.arka", liste=", ".join(f"{p['ad']} %{p['cpu']}" for p in usage["arka_plan"])),
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

    def _guide_row(self, game):
        """Oyun içi grafik ayarı için dış rehber bağlantıları (tarayıcıda açılır; uygulama bağlanmaz)."""
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        sources = guides.find(game["ad"])
        lay.addWidget(self._ingame_card(game))
        lay.addWidget(w.hbox(self._caption(t("ui.oyun_rehber"), "rehber"), None))
        if not sources:
            lay.addWidget(w.label(t("ui.oyun_rehber.yok"), muted=True, size=12))
            return box
        buttons = []
        for source in sources:
            text = f"{source['site']}: {source['icerik']}"
            button = w.button(text if len(text) <= 56 else text[:55] + "…", lambda _=False, u=source["url"]: os.startfile(u))
            button.setToolTip(source["icerik"])
            buttons.append(button)
        lay.addWidget(w.flow(*buttons))
        lay.addWidget(w.label(t("ui.oyun_rehber.not"), muted=True, size=12))
        return box

    def _ingame_card(self, game):
        """Oyun içi ayarlar: her oyunda aranacak genel maddeler (kanıt rozetiyle) ve bu oyunun doğrulanmış desteği."""
        card = w.Card(spacing=6)
        head = QLabel(t("ui.oyun_ici.baslik"))
        head.setObjectName("CardTitle")
        card.lay.addWidget(head)
        card.lay.addWidget(w.label(t("ui.oyun_ici.aciklama"), muted=True, size=12))
        support = guides.support(game["ad"])["reflex"]
        state = {True: "var", False: "yok", None: "bilinmiyor"}[support]
        card.lay.addWidget(w.hbox(w.label(t("ui.oyun_ici.reflex_destek"), bold=True, wrap=False),
                                  w.badge(t(f"ui.oyun_ici.destek.{state}"), "iyi" if support else "notr"), None))
        game_id = oyun_ayar.find(game["ad"])
        if game_id:
            card.lay.addWidget(self._file_section(game_id))
        for item in guides.ingame_items(i18n.current()):
            card.lay.addWidget(w.hbox((w.label(item["baslik"], bold=True), 1), w.badge(t(f"ui.oyun_ici.kanit.{item['kanit']}"),
                                                                                        "iyi" if item["kanit"] in ("belgeli", "olculmus") else "notr")))
            card.lay.addWidget(w.label(item["metin"], muted=True, size=12))
            if item["kaynak"]:
                card.lay.addWidget(w.label(t("ui.oyun_ici.kaynak", kaynak=item["kaynak"]), muted=True, size=11))
        return card

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
        lay.addWidget(w.colored(t("ui.anti_cheat_oyun", liste=", ".join(game["anti_cheat"])), "uyari") if game.get("anti_cheat")
                      else w.label(t("ui.anti_cheat_bulunamadi"), muted=True, size=12))
        lay.addWidget(w.colored(t("ui.anti_cheat_genel"), "uyari"))
        lay.addWidget(self._scan_status(len(self._remaining())))
        lay.addWidget(w.hbox(w.button(t("ui.oyun_kaldir"), lambda: self._remove(game)), None))

        lay.addWidget(w.section_title(t("ui.oyun_grp.rehber")))
        lay.addWidget(self._guide_row(game))
        useful = about_data()["faydali"]
        if useful:
            lay.addWidget(self._useful_card(useful))
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
