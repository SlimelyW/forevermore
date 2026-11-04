"""Oyunlar menüsü: üstte oyun seçimi, altında seçilen oyun için tek, sade bir sayfa.

Ana kontroller (öncelik, çekirdekler, bildirimleri sustur, iki ekran kartı varsa GPU tercihi ve
"oyun açılınca otomatik uygula") büyük düğmelerle; diğerleri varsayılan olarak kapalı "Gelişmiş
ayarlar" bölümünde. Her terimin yanında tek cümlelik açıklama veren (i) düğmesi var.

Kalıcı ayarlar (öncelik, GPU tercihi, tam ekran optimizasyonları) kaydedince yazılır ve
Değişiklikler sayfasından geri alınır. Oyun sırasında ayarları (çekirdekler, bildirimler...)
uygulama açıkken, oyun açılınca uygulanır ve oyun kapanınca geri alınır. Anti-cheat süreçlerine
hiçbir ayar uygulanmaz (profiles.PROTECTED_EXES).
"""

import os
import time

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QFileDialog, QGridLayout, QLabel, QProgressBar,
                               QSizePolicy, QVBoxLayout, QWidget)

from app.core import i18n
from app.core.i18n import t, value_label
from app.engine import cpu_topology
from app.games import discovery, guides, presets, profiles
from app.ui import dialogs, motion, theme, widgets as w
from app.ui.page_settings import about_data

PRIORITIES = ("Normal", "AboveNormal", "High")
GPU_PREFS = ("varsayilan", "guc_tasarrufu", "yuksek_performans")
CORE_PRESETS = ("tum", "performans", "fiziksel", "vcache", "ozel")
# Gelişmiş bölümdeki oyun sırasında ayarları (bildirimler ana bölümde)
ADVANCED_RUNTIME = tuple(k for k in profiles.RUNTIME_KEYS if k != "bildirimleri_kapat")


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
        self.topology = None
        self.advanced_open = False

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
        self.body.addWidget(self._watcher_banner())
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
        useful = about_data()["faydali"]
        if useful:
            self.body.addWidget(self._useful_card(useful))

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

    def _watcher_banner(self):
        watcher = self.app.game_watcher
        if not self.c.can_modify:
            return w.banner(t("ui.oyun_izleyici_mod"), "uyari")
        if watcher is not None and watcher.active:
            return w.banner(t("ui.oyun_izleyici_aktif", ad=watcher.active[0]["ad"]), "iyi")
        if self.store.runtime_games():
            return w.banner(t("ui.oyun_izleyici_hazir"), "bilgi")
        return w.banner(t("ui.oyun_izleyici_kapali"), "bilgi")

    def _picker(self):
        """Tek açılır liste: önce listemdeki oyunlar, sonra bilgisayarda bulunup henüz eklenmemiş olanlar."""
        card = w.Card()
        combo = QComboBox()
        for game in self.store.games:
            combo.addItem(game["ad"], ("oyun", game["id"]))
        added = {g["klasor"].lower() for g in self.store.games}
        remaining = [g for g in self.found or [] if g["klasor"].lower() not in added]
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
        card.lay.addWidget(self._scan_status(len(remaining)))
        if not self.store.games:
            card.lay.addWidget(w.label(t("ui.oyun_yok"), muted=True))
        card.lay.addWidget(w.colored(t("ui.anti_cheat_genel"), "uyari"))
        return card

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
            added = self.store.add(game["ad"], game["klasor"], game["kaynak"], game.get("exe"))
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
            self.app.update_game_watcher()
            self.data_reloaded()

    # ------------------------------------------------------------------ seçili oyunun sayfası
    def _game_page(self, game):
        if self.draft is None:
            self.draft = dict(game["profil"])
            if game.get("exe") and self.draft.get("otomatik", True):
                # kalıcı ayarlarda sisteme güvenilir, profil dosyasına değil
                self.draft.update(profiles.read_persistent(game, self._read_reg))
        if self.topology is None:
            try:
                self.topology = cpu_topology.read()
            except Exception:
                self.topology = {"cpular": [], "hibrit": False, "smt": False, "l3_gruplari": [], "vcache_l3": None}
        card = w.Card(spacing=12)
        card.lay.addWidget(self._game_header(game))
        if game.get("anti_cheat"):
            card.lay.addWidget(w.colored(t("ui.anti_cheat_oyun", liste=", ".join(game["anti_cheat"])), "uyari"))
        else:
            card.lay.addWidget(w.label(t("ui.anti_cheat_bulunamadi"), muted=True, size=12))
        card.lay.addWidget(self._exe_row(game))
        if not game.get("exe"):
            return card

        card.lay.addWidget(self._preset_row())
        card.lay.addWidget(self._guide_row(game))
        card.lay.addWidget(self._switch_row("otomatik", t("ui.oyun_otomatik"), "otomatik", bold=True))
        if not self.draft.get("otomatik", True):
            card.lay.addWidget(w.label(t("ui.oyun_otomatik_kapali"), muted=True, size=12))
        card.lay.addWidget(self._segment_row(t("ui.oyun_oncelik"), "oncelik", "oncelik", PRIORITIES,
                                             lambda v: t(f"ui.oncelik.{v}")))
        card.lay.addWidget(self._cores_row())
        card.lay.addWidget(self._switch_row("bildirimleri_kapat", t("ui.oyun_ayar.bildirimleri_kapat"), "bildirim"))
        if self._dual_gpu():
            card.lay.addWidget(self._segment_row(t("ui.oyun_gpu"), "gpu_tercihi", "gpu", GPU_PREFS,
                                                 lambda v: t(f"ui.gpu_tercihi.{v}")))

        # sayfa yeniden kurulmaz: bölüm yerinde açılır, kaydırma konumu korunur
        advanced = self._advanced()
        advanced.setVisible(self.advanced_open)
        toggle = w.button(t("ui.oyun_gelismis_gizle") if self.advanced_open else t("ui.oyun_gelismis_goster"),
                          lambda: self._toggle_advanced(toggle, advanced))
        card.lay.addWidget(w.hbox(toggle, None))
        card.lay.addWidget(advanced)

        save = w.button(t("ui.oyun_kaydet"), lambda: self._save(game), primary=True)
        save.setEnabled(self.c.can_modify)
        save.setMinimumHeight(36)
        card.lay.addWidget(w.hbox((w.label(t("ui.oyun_kaydet_aciklama"), muted=True, size=12), 1), save))
        return card

    def _game_header(self, game):
        name = QLabel(game["ad"])
        name.setObjectName("Title")
        parts = [w.IconTile(theme.ICONS["oyunlar"], theme.category_color("oyunlar"), 40),
                 (name, 1), w.badge(value_label("ui.oyun_kaynak", game["kaynak"]), "notr")]
        if game.get("anti_cheat"):
            badge = w.badge(t("ui.anti_cheat_rozet", liste=", ".join(game["anti_cheat"])), "uyari")
            badge.setToolTip(t("ui.anti_cheat_oyun", liste=", ".join(game["anti_cheat"])))
            parts.append(badge)
        watcher = self.app.game_watcher
        if watcher is not None and watcher.active and watcher.active[0]["id"] == game["id"]:
            parts.append(w.badge(t("ui.oyun_calisiyor"), "iyi"))
        if game.get("exe") and os.path.exists(game["exe"]):
            parts.append(w.button(t("ui.oyun_baslat"), lambda: os.startfile(game["exe"])))
        parts.append(w.button(t("ui.oyun_kaldir"), lambda: self._remove(game)))
        return w.hbox(*parts, spacing=10)

    def _preset_row(self):
        """Görsel öncelik / Dengeli / Performans: profil taslağını doldurur, "Kaydet"e kadar uygulanmaz."""
        now = presets.current(self.draft, self.topology, self._two_gpus())
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
        for item in guides.ingame_items(i18n.current()):
            card.lay.addWidget(w.hbox((w.label(item["baslik"], bold=True), 1), w.badge(t(f"ui.oyun_ici.kanit.{item['kanit']}"),
                                                                                        "iyi" if item["kanit"] in ("belgeli", "olculmus") else "notr")))
            card.lay.addWidget(w.label(item["metin"], muted=True, size=12))
            if item["kaynak"]:
                card.lay.addWidget(w.label(t("ui.oyun_ici.kaynak", kaynak=item["kaynak"]), muted=True, size=11))
        return card

    def _apply_preset(self, preset):
        self.draft.update(presets.build(preset, self.topology, self._two_gpus()))
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

    def _advanced(self):
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        lay.addWidget(w.label(t("ui.oyun_gelismis_aciklama"), muted=True, size=12))
        lay.addWidget(self._switch_row("fso_kapali", t("ui.oyun_fso"), "fso", bold=False))
        for key in ADVANCED_RUNTIME:
            lay.addWidget(self._switch_row(key, t(f"ui.oyun_ayar.{key}"), key, bold=False))
        lay.addWidget(w.label(t("ui.oyun_smt_bios"), muted=True, size=12))
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

    # ------------------------------------------------------------------ çekirdekler
    def _cores_row(self):
        topo = self.topology
        widget = QWidget()
        lay = QVBoxLayout(widget)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        available = ["tum"]
        if topo["hibrit"]:
            available.append("performans")
        if topo["smt"]:
            available.append("fiziksel")
        if topo["vcache_l3"] is not None:
            available.append("vcache")
        available.append("ozel")
        group = QButtonGroup(widget)
        buttons = []
        for preset in available:
            button = w.button(t(f"ui.cekirdek.{preset}"), lambda _=False, p=preset: self._preset(p))
            button.setCheckable(True)
            button.setProperty("segment", True)
            button.setMinimumHeight(34)
            button.setChecked(self.draft["cekirdek_secimi"] == preset)
            button.setEnabled(self.c.can_modify)
            group.addButton(button)
            buttons.append(button)
        lay.addWidget(w.hbox(self._caption(t("ui.oyun_cekirdek"), "cekirdek"), (w.flow(*buttons), 1), spacing=12))
        selected = set(self.draft.get("cekirdekler") or [])
        if self.draft["cekirdek_secimi"] == "ozel":
            tools = [("ui.cekirdek_tumu", self._grid_all), ("ui.cekirdek_hicbiri", self._grid_none)]
            if topo["smt"]:
                tools += [("ui.cekirdek_smt_acik", self._grid_smt_on), ("ui.cekirdek_smt_kapali", self._grid_smt_off)]
            if len(topo["l3_gruplari"]) > 1:
                tools.append(("ui.cekirdek_ccd1_kapat", self._grid_no_ccd1))
            if topo["hibrit"]:
                tools.append(("ui.cekirdek_e_kapat", self._grid_no_e))
            lay.addWidget(w.flow(*[w.button(t(k), f) for k, f in tools]))
            for index, group_info in enumerate(topo["l3_gruplari"]):
                members = [c for c in topo["cpular"] if c["no"] in group_info["cpular"]]
                kind = ""
                if topo["hibrit"]:
                    kind = " — " + (t("ui.cekirdek_p") if members and members[0]["p"] else t("ui.cekirdek_e"))
                lay.addWidget(w.label(t("ui.cekirdek_grup", no=index, mb=group_info["boyut_mb"]) + kind,
                                      bold=True, size=12))
                grid_widget = QWidget()
                grid = QGridLayout(grid_widget)
                grid.setContentsMargins(0, 0, 0, 0)
                for i, cpu in enumerate(members):
                    box = QCheckBox(f"CPU {cpu['no']}")
                    box.setChecked(cpu["no"] in selected)
                    box.toggled.connect(lambda on, n=cpu["no"]: self._toggle_cpu(n, on))
                    grid.addWidget(box, i // 8, i % 8)
                lay.addWidget(grid_widget)
            lay.addWidget(w.label(t("ui.cekirdek_secili", adet=len(selected), toplam=len(topo["cpular"])),
                                  muted=True, size=12))
        else:
            numbers = cpu_topology.preset_ids(topo, self.draft["cekirdek_secimi"]) if topo["cpular"] else []
            preview = w.label(t("ui.cekirdek_onizleme", liste=self._ranges(numbers)), muted=True, size=12)
            preview.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            lay.addWidget(preview)
        return widget

    @staticmethod
    def _ranges(numbers):
        numbers = sorted(numbers)
        parts, start = [], None
        for i, n in enumerate(numbers):
            if start is None:
                start = n
            if i + 1 == len(numbers) or numbers[i + 1] != n + 1:
                parts.append(f"{start}–{n}" if n != start else str(n))
                start = None
        return ", ".join(parts) or "—"

    def _preset(self, preset):
        self.draft["cekirdek_secimi"] = preset
        if preset == "ozel" and not self.draft.get("cekirdekler"):
            self.draft["cekirdekler"] = [c["no"] for c in self.topology["cpular"]]
        QTimer.singleShot(0, self.data_reloaded)

    def _set_cpus(self, numbers):
        self.draft["cekirdekler"] = sorted(set(numbers))
        QTimer.singleShot(0, self.data_reloaded)

    def _toggle_cpu(self, number, on):
        current = set(self.draft.get("cekirdekler") or [])
        current.add(number) if on else current.discard(number)
        self.draft["cekirdekler"] = sorted(current)

    def _grid_all(self):
        self._set_cpus([c["no"] for c in self.topology["cpular"]])

    def _grid_none(self):
        self._set_cpus([])

    def _grid_smt_on(self):
        cores = {c["cekirdek"] for c in self.topology["cpular"] if c["no"] in set(self.draft.get("cekirdekler") or [])}
        self._set_cpus([c["no"] for c in self.topology["cpular"] if c["cekirdek"] in cores])

    def _grid_smt_off(self):
        selected = set(self.draft.get("cekirdekler") or [])
        self._set_cpus([c["no"] for c in self.topology["cpular"] if c["no"] in selected and c["ilk_is_parcacigi"]])

    def _grid_no_ccd1(self):
        second = self.topology["l3_gruplari"][1]["cpular"]
        self._set_cpus([n for n in (self.draft.get("cekirdekler") or []) if n not in second])

    def _grid_no_e(self):
        e_cores = {c["no"] for c in self.topology["cpular"] if not c["p"]}
        self._set_cpus([n for n in (self.draft.get("cekirdekler") or []) if n not in e_cores])

    # ------------------------------------------------------------------ kaydet
    def _save(self, game):
        draft = dict(self.draft)
        if draft["cekirdek_secimi"] == "ozel" and not draft.get("cekirdekler"):
            dialogs.show_message(self.app, t("ui.dikkat"), t("ui.cekirdek_bos"), "uyari")
            return
        if draft.get("otomatik", True) and draft["oncelik"] == "High" and \
                not dialogs.ask_yes_no(self.app, t("ui.dikkat"), t("ui.oncelik_yuksek_onay")):
            return
        self.store.update_profile(game["id"], draft)
        # Otomatik uygulama kapalıysa seçimler saklanır ama sisteme Windows varsayılanı yazılır.
        effective = draft if draft.get("otomatik", True) else dict(draft, **profiles.PERSISTENT_DEFAULTS)
        changes = profiles.persistent_changes(game, effective, self._read_reg)

        def next_change():
            if not changes:
                self.app.update_game_watcher()
                self.app.set_status(t("ui.oyun_kaydedildi", ad=game["ad"]), "iyi")
                self.draft = None
                self.data_reloaded()
                return
            change_id, name_key, step, value = changes.pop(0)
            self.app.apply_custom(change_id, t(name_key, ad=game["ad"]), [step], [value], next_change,
                                  restart="uygulama")
        next_change()
