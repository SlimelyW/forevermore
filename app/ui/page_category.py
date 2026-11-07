"""Kategori sayfaları: switch'ler, seçimler, tek seferlik eylemler, rehberler ve
bilgi kartları.

Özel bölümler: Ses (cihaz biçimleri), Mouse ve Klavye (polling rate),
Ekran Kartı (NVIDIA notu), Display (monitörler), Placebo (uygulanmış olanlar en üstte).
"""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QCheckBox, QComboBox, QHBoxLayout, QInputDialog, QLabel, QProgressBar, QSizePolicy,
                               QSlider, QVBoxLayout, QWidget)

from app.core import settings
from app.engine import driver_tools, timer_resolution, varsayilan
from app.core.i18n import t, value_label
from app.ui import dialogs, managers_ui, theme, widgets as w


def _name_label(tweak):
    name = QLabel(dialogs.display_name(tweak))
    name.setObjectName("CardTitle")
    name.setWordWrap(True)
    return name


LOUD_IMPACT = ("yüksek", "orta")  # satırda etki rozeti yalnızca bunlarda


def tweak_icon(tweak, size=36):
    """Ayarın kategori renginde simge kutusu."""
    key = tweak.get("kategori_id", "")
    return w.IconTile(theme.ICONS.get(key, theme.ICONS["info"]), theme.category_color(key), size)


def title_block(tweak):
    """Başlık + tek satırlık özet (ne işe yarar); ayrıntı (i) balonunda. Özet uzunsa kısaltılır, satırı büyütmez."""
    box = QWidget()
    lay = QVBoxLayout(box)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(2)
    lay.addWidget(_name_label(tweak))
    if tweak.get("sade_ad"):
        technical = QLabel(tweak["ad"])
        technical.setObjectName("Summary")
        technical.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        lay.addWidget(technical)
    summary = QLabel(w.summary_text(tweak.get("ne_ise_yarar"), limit=90))
    summary.setObjectName("Summary")
    summary.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)  # dar pencerede kırpılır
    lay.addWidget(summary)
    return box


def card_header(app, tweak, *extra):
    """Satır kartı başlığı: [simge] [başlık + özet] [ek düğmeler] [(i)]."""
    return w.hbox(tweak_icon(tweak), (title_block(tweak), 1), *extra,
                  w.info_button(lambda: dialogs.InfoDialog(app, tweak).exec()), spacing=12)


class TweakRow(w.Card):
    """Switch satırı: ad, etiketler, not, (i), aç/kapa ve "eski haline getir"."""

    def __init__(self, app, tweak, show_reality=False):
        super().__init__(layout="h", spacing=12, hover=True)
        self.app, self.c, self.tweak = app, app.c, tweak
        self.show_reality = show_reality
        self.lay.addWidget(tweak_icon(tweak), 0, Qt.AlignmentFlag.AlignTop)
        text = QVBoxLayout()
        text.setSpacing(4)
        text.addWidget(title_block(tweak))
        self.meta = w.hbox(spacing=6)
        text.addWidget(self.meta)
        self.lay.addLayout(text, 1)
        self.revert_button = w.icon_button(theme.ICONS["undo"], t("ui.eski_haline"), self._revert)
        self.revert_button.setVisible(False)
        self.lay.addWidget(self.revert_button)
        self.lay.addWidget(w.info_button(self._info))
        self.state_label = w.label("", muted=True, wrap=False)
        self.lay.addWidget(self.state_label)
        self.switch = w.ToggleSwitch()
        self.switch.clicked.connect(self._on_switch)
        self.switch_box = w.hbox(spacing=12)
        self.switch_box.layout().addWidget(self.switch)
        self.lay.addWidget(self.switch_box)
        self.dc = None       # laptopta "Pilde" kopyası
        self.dc_switch = None
        self.dc_busy = False
        self.busy = False
        self.pending = None      # iyimser görünüm: tıklanan durum (sonuç gelince gerçek durum yazılır)
        self.dc_pending = None
        self.refresh()

    def _add_dc_switch(self):
        """Laptopta güç ayarı: prizde ve pilde iki ayrı düğme."""
        self.dc = self.c.dc_variants[self.tweak["id"]]
        lay = self.switch_box.layout()
        lay.removeWidget(self.switch)
        for caption, switch in ((t("ui.prizde"), self.switch), (t("ui.pilde"), None)):
            if switch is None:
                switch = self.dc_switch = w.ToggleSwitch()
                switch.clicked.connect(self._on_dc_switch)
            box = QWidget()
            box_lay = QVBoxLayout(box)
            box_lay.setContentsMargins(0, 0, 0, 0)
            box_lay.setSpacing(2)
            box_lay.addWidget(w.label(caption, muted=True, size=11, wrap=False))
            box_lay.addWidget(switch)
            box.setFixedHeight(box.sizeHint().height())
            lay.addWidget(box)

    def _on_dc_switch(self):
        desired = self.dc_switch.isChecked()
        self.dc_pending = desired
        self.dc_busy = True
        self.refresh()

        def done():
            self.dc_busy = False
            self.dc_pending = None
            self.refresh()
        self.app.toggle(self.dc, desired, done)

    def _info(self):
        dialogs.InfoDialog(self.app, self.tweak).exec()

    def refresh(self):
        w.clear_layout(self.meta.layout())
        meta = self.meta.layout()
        if self.tweak["performans_etkisi"]["seviye"] in LOUD_IMPACT:  # öteki seviyeler yalnızca (i) balonunda
            meta.addWidget(w.impact_badge(self.tweak["performans_etkisi"]["seviye"]))
        if self.tweak["risk"] != "güvenli":
            meta.addWidget(w.risk_badge(self.tweak["risk"]))
        if self.show_reality and self.tweak["gerceklik"]["durum"] != "gerçek":
            meta.addWidget(w.reality_badge(self.tweak["gerceklik"]["durum"]))
        changed = self.c.engine.store.has(self.tweak["id"])
        if changed:
            meta.addWidget(w.badge(t("ui.degistirildi"), "bilgi"))
        if self.c.engine.needs_update(self.tweak):
            meta.addWidget(w.badge(t("ui.guncellendi"), "uyari"))
            if self.c.can_modify and not self.busy:
                meta.addWidget(w.button(t("ui.yeniden_uygula"), self._reapply))
        avail = self.c.availability.get(self.tweak["id"])
        for key, params in (avail.warnings if avail else []):
            meta.addWidget(w.colored(t(key, **params), "uyari", wrap=False))
        meta.addStretch(1)

        state = self.c.states.get(self.tweak["id"])
        status = state.status if state else "bilinmiyor"
        fresh = self.c.is_fresh(self.tweak["id"])
        off_only = self.tweak["islem"].get("yalnizca_kapat")
        self.switch.setChecked(self.pending if self.busy and self.pending is not None else status == "acik")
        labels = {"kismen": t("ui.durum.kismen"), "bilinmiyor": t("ui.durum.bilinmiyor")}
        if self.busy:
            text = t("ui.durum.uygulaniyor")
        elif not fresh:
            text = t("ui.durum.okunuyor")
        else:
            text = labels.get(status, "")
        self.state_label.setText(text)
        # Yalnızca kapatılabilen (zararlı) ayar: kapalıysa uygulamadan açılamaz.
        blocked = off_only and status not in ("acik", "kismen")
        self.switch.set_waiting(self.busy)  # işlem sürerken tıklanmaz ama soluklaşmaz (iyimser)
        self.switch.setEnabled(self.busy or (fresh and status != "bilinmiyor" and self.c.can_modify and not blocked))
        self.switch.setToolTip(t("ui.yalnizca_kapat_ipucu") if off_only else "")
        if self.dc is None and self.tweak["id"] in self.c.dc_variants:
            self._add_dc_switch()
        dc_changed = False
        if self.dc is not None:
            dc_id = self.dc["id"]
            dc_state = self.c.states.get(dc_id)
            dc_changed = self.c.engine.store.has(dc_id)
            self.dc_switch.setChecked(self.dc_pending if self.dc_busy and self.dc_pending is not None
                                      else bool(dc_state) and dc_state.status == "acik")
            self.dc_switch.set_waiting(self.dc_busy)
            self.dc_switch.setEnabled(self.dc_busy or (self.c.is_fresh(dc_id) and self.c.can_modify
                                                       and bool(dc_state) and dc_state.status != "bilinmiyor"))
        self.revert_button.setVisible((changed or dc_changed) and self.c.can_modify and not self.busy)

    def _on_switch(self):
        """İyimser: anahtar tıklanan durumda kalır ("uygulanıyor"); onay reddedilir veya işlem başarısız olursa
        gerçek durum okununca geri döner."""
        desired = self.switch.isChecked()
        state = self.c.states.get(self.tweak["id"])
        self.busy = True
        self.pending = desired
        self.refresh()
        if state and state.status == "kismen":
            choice = dialogs.choose_partial(self.app, self.tweak)
            if choice is None:
                self._done()
                return
            desired = choice and not self.tweak["islem"].get("yalnizca_kapat")
        self.app.toggle(self.tweak, desired, self._done)

    def _done(self):
        self.busy = False
        self.pending = None
        self.refresh()

    def _reapply(self):
        """Katalogda güncellenen ayarı kullanıcı isteğiyle, aynı onay/yedek/geri alma yoluyla yeniden uygular."""
        self.busy, self.pending = True, True
        self.refresh()
        self.app.toggle(self.tweak, True, self._done)

    def _revert(self):
        self.busy = True
        self.refresh()
        ids = [i for i in (self.tweak["id"], self.dc["id"] if self.dc else None)
               if i and self.c.engine.store.has(i)]

        def next_one():
            if ids:
                self.app.revert(ids.pop(0), next_one)
            else:
                self._done()
        next_one()


class SelectionRow(w.Card):
    """Değer seçilen ayarlar (fare hızı, klavye tekrar ayarları, DNS)."""

    def __init__(self, app, tweak, show_reality=False):
        super().__init__(hover=True)
        self.app, self.c, self.tweak = app, app.c, tweak
        self.lay.addWidget(card_header(app, tweak))
        if show_reality and tweak["gerceklik"]["durum"] != "gerçek":
            self.lay.addWidget(w.hbox(w.reality_badge(tweak["gerceklik"]["durum"]), None))
        self.fields = QWidget()
        self.fields_lay = QVBoxLayout(self.fields)
        self.fields_lay.setContentsMargins(0, 0, 0, 0)
        self.lay.addWidget(self.fields)
        self.footer = w.hbox()
        self.lay.addWidget(self.footer)
        self.controls = {}
        self.refresh()

    def refresh(self):
        w.clear_layout(self.fields_lay)
        w.clear_layout(self.footer.layout())
        state = self.c.states.get(self.tweak["id"])
        current = state.values if state else {}
        fresh = self.c.is_fresh(self.tweak["id"])
        for field in self.tweak["islem"]["alanlar"]:
            value = current.get(field["id"]) or field["adim"].get("yoksa") or field["onerilen"]
            value = str(value)
            caption = QLabel(field["etiket"])
            caption.setWordWrap(True)
            caption.setMinimumWidth(170)
            if field.get("aralik"):
                rng = field["aralik"]
                slider = QSlider(Qt.Orientation.Horizontal)
                slider.setRange(rng["min"], rng["max"])
                slider.setValue(int(value) if value.isdigit() else int(field["onerilen"]))
                slider.setFixedWidth(260)
                shown = QLabel(str(slider.value()))
                shown.setFixedWidth(30)
                slider.valueChanged.connect(lambda v, lbl=shown: lbl.setText(str(v)))
                control = slider
                self.controls[field["id"]] = ("aralik", slider)
                row = w.hbox(caption, slider, shown,
                             w.label(t("ui.onerilen", deger=field["onerilen"]), muted=True, wrap=False), None)
            else:
                combo = QComboBox()
                for option in field["secenekler"]:
                    combo.addItem(option["etiket"], option["deger"])
                if combo.findData(value) < 0:
                    # Bilinen seçeneklerden biri değil (ör. kendi DNS aracınız): olduğu gibi göster.
                    combo.addItem(t("ui.ozel_deger"), value)
                combo.setCurrentIndex(combo.findData(value))
                combo.setFixedWidth(260)
                control = combo
                self.controls[field["id"]] = ("secenek", combo)
                recommended = {o["deger"]: o["etiket"] for o in field["secenekler"]}[field["onerilen"]]
                row = w.hbox(caption, combo, w.label(t("ui.onerilen", deger=recommended), muted=True, wrap=False), None)
            control.setEnabled(fresh and self.c.can_modify)
            self.fields_lay.addWidget(row)
        footer = self.footer.layout()
        if self.c.engine.store.has(self.tweak["id"]):
            footer.addWidget(w.badge(t("ui.degistirildi"), "bilgi"))
            if self.c.can_modify:
                footer.addWidget(w.button(t("ui.eski_haline"), lambda: self.app.revert(self.tweak["id"], self.refresh)))
        footer.addStretch(1)
        self.apply_button = w.button(t("ui.uygula"), self._apply, primary=True)
        self.apply_button.setEnabled(fresh and self.c.can_modify)
        footer.addWidget(self.apply_button)

    def _apply(self):
        values = {}
        allowed = {f["id"]: {o["deger"] for o in f.get("secenekler", [])} for f in self.tweak["islem"]["alanlar"]}
        for field_id, (kind, control) in self.controls.items():
            if kind == "aralik":
                values[field_id] = str(control.value())
            elif control.currentData() in allowed[field_id]:
                values[field_id] = control.currentData()
        if not values:
            return
        self.apply_button.setEnabled(False)
        self.app.apply_selection(self.tweak, values, self.refresh)


class ActionRow(w.Card):
    """Tek seferlik, geri alınamaz eylem (ör. geçici dosyaları temizle)."""

    def __init__(self, app, tweak, show_reality=False):
        super().__init__(hover=True)
        self.app, self.tweak = app, tweak
        self.lay.addWidget(card_header(app, tweak))
        badges = [w.impact_badge(tweak["performans_etkisi"]["seviye"]), w.badge(t("ui.geri_alinamaz"), "uyari")]
        if show_reality and tweak["gerceklik"]["durum"] != "gerçek":
            badges.insert(1, w.reality_badge(tweak["gerceklik"]["durum"]))
        self.lay.addWidget(w.hbox(*badges, None))
        buttons = []
        for action in tweak["islem"]["eylemler"]:
            button = w.button(action["etiket"], lambda _=False, a=action: self.app.run_action(tweak, a))
            button.setEnabled(app.c.can_modify)
            buttons.append(button)
        self.lay.addWidget(w.hbox(*buttons, None))


class GuideCard(w.Card):
    """REHBER: elle yapılacak ayar; adımlar ve "Ayarı aç" düğmesi."""

    def __init__(self, app, tweak):
        super().__init__()
        self.app, self.tweak = app, tweak
        self.toggle_button = w.button(t("ui.nasil_yapilir"), self._toggle)
        self.lay.addWidget(card_header(app, tweak, self.toggle_button))
        badges = [w.impact_badge(tweak["performans_etkisi"]["seviye"])]
        if tweak["risk"] != "güvenli":
            badges.append(w.risk_badge(tweak["risk"]))
        badges.append(w.badge(t("ui.rehber"), "notr"))
        self.lay.addWidget(w.hbox(*badges, None))
        self.details = None

    def _toggle(self):
        if self.details is not None:
            self.details.deleteLater()
            self.details = None
            self.toggle_button.setText(t("ui.nasil_yapilir"))
            return
        self.toggle_button.setText(t("ui.gizle"))
        guide = self.tweak.get("rehber") or {}
        self.details = QWidget()
        lay = QVBoxLayout(self.details)
        lay.setContentsMargins(0, 4, 0, 0)
        for i, step in enumerate(guide.get("adimlar", []), 1):
            lay.addWidget(w.label(f"{i}. {step}"))
        if guide.get("kontrol"):
            lay.addWidget(w.label(t("ui.nasil_kontrol") + " " + guide["kontrol"], muted=True))
        if guide.get("geri_alma"):
            lay.addWidget(w.label(t("ui.nasil_geri") + " " + guide["geri_alma"], muted=True))
        if guide.get("ac"):
            def open_it():
                if not w.open_target(guide["ac"]):
                    self.app.set_status(t("ui.acilamadi"), "sorun")
            lay.addWidget(w.hbox(w.button(t("ui.ayari_ac"), open_it, primary=True), None))
        self.lay.addWidget(self.details)


class InfoCard(w.Card):
    """BİLGİ: uygulamanın yapamadığı ayar (üçüncü parti program, sürücü, yasaklı liste)."""

    def __init__(self, app, tweak, detected=False, show_reality=False):
        super().__init__()
        self.lay.addWidget(card_header(app, tweak))
        badges = [w.risk_badge(tweak["risk"])]
        if show_reality and tweak["gerceklik"]["durum"] != "gerçek":
            badges.insert(0, w.reality_badge(tweak["gerceklik"]["durum"]))
        if detected:
            badges.append(w.badge(t("ui.bu_bilgisayarda_var"), "sorun"))
        self.lay.addWidget(w.hbox(*badges, None))
        info = tweak.get("bilgi") or {}
        if info.get("yapilamaz_nedeni"):
            self.lay.addWidget(w.label(info["yapilamaz_nedeni"], muted=True, size=12))
        if detected and tweak.get("tespit"):
            self.lay.addWidget(w.colored(tweak["tespit"]["mesaj"], "sorun"))
            if tweak["id"] in varsayilan.MANUAL:
                self.lay.addWidget(w.label(t(f"ui.varsayilan.elle.{tweak['id']}"), size=12))
            opener = (tweak.get("rehber") or {}).get("ac")
            if opener:
                self.lay.addWidget(w.hbox(w.button(t("ui.ayari_ac"), lambda: w.open_target(opener)), None))
            if tweak["id"] in varsayilan.SUPPORTED:
                self.default_button = w.button(t("ui.varsayilan.dugme"), self._restore_default, primary=True)
                self.default_button.setEnabled(app.c.can_modify)
                self.default_button.setToolTip(t("ui.varsayilan.ipucu"))
                self.lay.addWidget(w.hbox(self.default_button, None))
        self.app, self.tweak = app, tweak
        if tweak.get("ilgili") and tweak["ilgili"] in app.c.by_id:
            self.lay.addWidget(w.hbox(w.button(t("ui.ayara_git"), lambda: app.go_to_tweak(tweak["ilgili"])), None))

    def _restore_default(self):
        self.default_button.setEnabled(False)
        tweak_id = self.tweak["id"]
        # Bitince yalnız bu madde yeniden okunur; tespit kalkarsa Placebo sayfası "uygulanmış" bölümünü yeniden kurar.
        self.app.restore_default(self.tweak, lambda: self.app.recheck_fix(tweak_id, self._restored))

    def _restored(self, _changed):
        try:  # Vazgeç ya da hata: kart duruyorsa düğme yeniden açılır
            self.default_button.setEnabled(self.app.c.can_modify)
        except RuntimeError:  # sayfa bu arada yeniden kuruldu
            pass


class InputDevicesCard(w.Card):
    """Bağlı fare ve klavyeler: cihazın kendi adı, VID:PID; kullanıcı kendi adını verebilir (yerel)."""

    def __init__(self, app, devices):
        super().__init__(spacing=8)
        self.app, self.devices = app, devices
        self.refresh()

    def refresh(self):
        w.clear_layout(self.lay)
        head = QLabel(t("ui.bagli_cihazlar"))
        head.setObjectName("CardTitle")
        self.lay.addWidget(head)
        names = settings.get("cihaz_adlari") or {}
        for device in self.devices:
            custom = names.get(self.key(device))
            glyph = theme.ICONS["klavye"] if device.get("turler") == ["klavye"] else theme.ICONS["INP"]
            text = QVBoxLayout()
            text.setSpacing(1)
            title = QLabel(custom or device["ad"])
            title.setObjectName("CardTitle")
            text.addWidget(title)
            parts = [" + ".join(value_label("deger.cihaz_turu", k) for k in device.get("turler") or [device["tur"]]),
                     value_label("deger.baglanti", device["baglanti"])]
            if device.get("vid_pid"):
                parts.append(f"VID:PID {device['vid_pid']}")
            if device.get("uretici"):
                parts.append(device["uretici"])
            text.addWidget(w.label(" · ".join(parts), muted=True, size=12))
            if custom:
                text.addWidget(w.label(t("ui.giris.cihaz_adi", ad=device["ad"]), muted=True, size=12))
            elif not device.get("gercek_ad"):
                text.addWidget(w.label(t("ui.giris.genel_ad"), muted=True, size=12))
            row = QWidget()
            row_lay = QHBoxLayout(row)
            row_lay.setContentsMargins(0, 0, 0, 0)
            row_lay.setSpacing(12)
            row_lay.addWidget(w.IconTile(glyph, theme.category_color("INP"), 32), 0, Qt.AlignmentFlag.AlignTop)
            row_lay.addLayout(text, 1)
            page = driver_tools.INPUT_VENDOR_PAGES.get(device.get("uretici"))
            if page:
                row_lay.addWidget(w.button(t("ui.giris.yazilim_ac"), lambda _=False, u=page: self._open(u)))
            row_lay.addWidget(w.icon_button(theme.ICONS["edit"], t("ui.giris.yeniden_adlandir"),
                                            lambda _=False, d=device: self._rename(d)))
            self.lay.addWidget(row)
        self.lay.addWidget(w.label(t("ui.giris.dpi_not"), muted=True, size=12))

    def _open(self, url):
        try:
            self.app.c.engine.system.open_path(url)
        except OSError as exc:
            self.app.set_status(t("ui.surucu_arac.acilamadi", hata=exc), "sorun")

    @staticmethod
    def key(device):
        """Kalıcı anahtar: VID:PID (yoksa bağlantı + ad). Eski önbellekte "anahtar" alanı olmayabilir."""
        return device.get("anahtar") or f"{device.get('baglanti')}:{device['ad']}"

    def _rename(self, device):
        text, ok = QInputDialog.getText(self.app, t("ui.giris.yeniden_adlandir"), t("ui.giris.ad_sor"),
                                        text=(settings.get("cihaz_adlari") or {}).get(self.key(device), device["ad"]))
        if ok:
            self.set_name(device, text)

    def set_name(self, device, text):
        names = dict(settings.get("cihaz_adlari") or {})
        text = (text or "").strip()[:60]
        if text and text != device["ad"]:
            names[self.key(device)] = text
        else:
            names.pop(self.key(device), None)
        settings.set("cihaz_adlari", names)
        self.refresh()


class TimerResolutionCard(w.Card):
    """Zamanlayıcı çözünürlüğü: uygulama açıkken istenir (kalıcı sistem değişikliği yok, yedek gerekmez)."""

    LABELS = {0: "ui.zr.secenek.windows", 10000: "ui.zr.secenek.1", 5000: "ui.zr.secenek.05"}

    def __init__(self, app):
        super().__init__(spacing=6)
        self.app, self.c = app, app.c
        head = QLabel(t("ui.zr.baslik"))
        head.setObjectName("CardTitle")
        head.setWordWrap(True)
        self.lay.addWidget(w.hbox(w.IconTile(theme.ICONS["PERF"], theme.category_color("PERF")), (head, 1),
                                  spacing=12))
        self.lay.addWidget(w.hbox(w.impact_badge("belirsiz"), None))
        self.lay.addWidget(w.label(t("ui.zr.aciklama"), muted=True, size=12))
        self.status = w.label("", size=12)
        self.lay.addWidget(self.status)
        combo = QComboBox()
        for value in timer_resolution.CHOICES:
            combo.addItem(t(self.LABELS[value]), value)
        combo.setCurrentIndex(max(0, combo.findData(settings.get("zamanlayici_cozunurlugu"))))
        combo.setMinimumWidth(220)
        combo.setEnabled(self.c.can_modify)
        apply = w.button(t("ui.uygula"), lambda: self._apply(combo.currentData()), primary=True)
        apply.setEnabled(self.c.can_modify)
        self.lay.addWidget(w.hbox(combo, None, apply))
        notes = [t("ui.zr.not_acik"), t("ui.zr.not_pil"), t("ui.zr.not_olcum")]
        self.lay.addWidget(w.label("\n".join(f"• {n}" for n in notes), muted=True, size=12))
        if "CPU-009" in self.c.by_id:
            state = self.c.states.get("CPU-009")
            key = "ui.zr.global_acik" if state and state.status == "acik" else "ui.zr.global_kapali"
            self.lay.addWidget(w.hbox((w.label(t(key), size=12), 1),
                                      w.button(t("ui.ayara_git"), lambda: self.app.go_to_tweak("CPU-009"))))
        self.refresh()

    def refresh(self):
        info = timer_resolution.query()
        held = settings.get("zamanlayici_cozunurlugu")
        if info is None:
            self.status.setText(t("ui.zr.okunamadi"))
            return
        text = t("ui.zr.su_an", ms=info["su_an"], ince=info["en_ince"], kaba=info["en_kaba"])
        if held:
            text += " " + t("ui.zr.istek", ms=held / 10000)
        self.status.setText(text)

    def _apply(self, value):
        try:
            timer_resolution.hold(int(value or 0))
        except OSError:
            self.app.set_status(t("ui.zr.uygulanamadi"), "sorun")
            return
        settings.set("zamanlayici_cozunurlugu", int(value or 0))
        self.c.engine.store.history("uygulama_ayari", "zamanlayici_cozunurlugu", True, str(value))
        self.app.set_status(t("ui.zr.uygulandi"), "iyi")
        self.refresh()


def make_row(app, tweak, show_reality=False, detected=False):
    if tweak.get("liste_yoneticisi"):
        return managers_ui.make_manager(app, tweak)
    if tweak["id"] == "DISP-001" and tweak["sinif"] == "SWITCH":
        return managers_ui.MonitorsCard(app, tweak)
    if tweak["sinif"] == "SWITCH":
        control = tweak["islem"]["kontrol"]
        cls = {"switch": TweakRow, "secim": SelectionRow, "eylem": ActionRow}[control]
        return cls(app, tweak, show_reality=show_reality)
    if tweak["sinif"] == "REHBER":
        return GuideCard(app, tweak)
    return InfoCard(app, tweak, detected=detected, show_reality=show_reality)


class ManualPage(w.Page):
    """Elle yapılacaklar: uygulamanın yapamadığı ayarlar, nedenine göre (BIOS, ağ, oyun içi, sürücü...)."""

    def __init__(self, app):
        super().__init__(app)
        self.rows = {}

    def on_show(self, highlight=None):
        self.ensure_built()
        if highlight and highlight in self.rows:
            row = self.rows[highlight]
            self.scroll.ensureWidgetVisible(row)
            row.set_highlight(True)
            QTimer.singleShot(1800, lambda: row.set_highlight(False))

    def build(self):
        super().build()
        self.rows = {}
        self.header.addWidget(w.title(t("ui.menu.elle")))
        self.header.addWidget(w.label(t("ui.elle.aciklama"), muted=True))
        detected = self.c.detected_ids()
        for reason, items in self.c.manual_items().items():
            self.body.addWidget(w.section_title(t(f"ui.elle.neden.{reason}")))
            self.body.addWidget(w.label(t(f"ui.elle.neden_aciklama.{reason}"), muted=True, size=12))
            for tweak in items:
                row = make_row(self.app, tweak, detected=tweak["id"] in detected)
                self.body.addWidget(row)
                self.rows[tweak["id"]] = row


class CategoryPage(w.Page):
    def __init__(self, app, category):
        super().__init__(app)
        self.category = category
        self.rows = {}
        self.show_hidden = False

    def on_show(self, highlight=None):
        self.ensure_built()
        if highlight and highlight in self.rows:
            row = self.rows[highlight]
            self.scroll.ensureWidgetVisible(row)
            row.set_highlight(True)
            QTimer.singleShot(1800, lambda: row.set_highlight(False))

    def _status_line(self, cid):
        """"4 / 7 ayar açık" + ince ilerleme çubuğu: sayfanın ilk bakışta okunan durumu (menü sayacıyla aynı veri)."""
        self.status_big = self.status_bar = None
        if cid == "PLC" or self.c.scan is None:
            return
        on, total = self.c.category_counts(self.category["ad"])
        if not total:
            return
        self.status_big = w.label("", bold=True, size=20, wrap=False)
        self.status_bar = QProgressBar()
        self.status_bar.setObjectName("Thin")
        self.status_bar.setTextVisible(False)
        self.header.addWidget(w.hbox(self.status_big, w.label(t("ui.kategori.acik"), muted=True, wrap=False), None, spacing=8))
        self.header.addWidget(self.status_bar)
        self._status_refresh()

    def _status_refresh(self):
        if getattr(self, "status_big", None) is None:
            return
        on, total = self.c.category_counts(self.category["ad"])
        self.status_big.setText(f"{on} / {total}")
        self.status_bar.setRange(0, max(total, 1))
        self.status_bar.setValue(on)

    def tweak_updated(self, tweak_id):
        self._status_refresh()
        row = self.rows.get(tweak_id)
        if row is not None and hasattr(row, "refresh"):
            row.refresh()
        if self.category["id"] == "PLC" and self.built:
            self._refresh_applied_section()

    def build(self):
        super().build()
        self.rows = {}
        cid = self.category["id"]
        self.header.addWidget(w.title(t(f"kategori.{cid}")))
        self.header.addWidget(w.label(self.category.get("aciklama", ""), muted=True))
        self._status_line(cid)
        picks = [self.c.by_id[p["id"]] for p in self.c.recommendations(99)
                 if self.c.by_id[p["id"]].get("kategori_id") == cid]
        if picks:  # tek tıkla: önizleme açılır, onaydan sonra uygulanır
            self.header.addWidget(w.hbox(w.button(t("ui.toplu.kategori", n=len(picks)),
                                                  lambda _=False, p=picks: self.app.apply_recommended(p), primary=True),
                                         None))
        if cid == "PLC":
            self._placebo()
            return
        if self.c.scan is not None:
            special = {"INP": self._input_section, "PERF": self._timer_section, "PWR": self._gpu_mode_section,
                                                "GPU": lambda: (self._gpu_choice_section(), self._rebar_section())}.get(cid)
            if special:
                special()
        groups = self.c.category_items(self.category["ad"], include_hidden=self.show_hidden)
        detected = self.c.detected_ids()
        for key, title in (("switch", "ui.bolum.ayarlar"), ("rehber", "ui.bolum.rehberler"), ("bilgi", "ui.bolum.bilgi")):
            if groups[key]:
                self.body.addWidget(w.section_title(t(title)))
                for heading, tweaks, note in (self._by_gpu(groups[key]) if cid == "GPU" else [(None, groups[key], None)]):
                    if heading:
                        self.body.addWidget(w.label(heading, bold=True))
                    if note:
                        self.body.addWidget(w.label(note, muted=True, size=12))
                    rows = w.RowList()
                    for tweak in tweaks:
                        self.rows[tweak["id"]] = rows.add(make_row(self.app, tweak, detected=tweak["id"] in detected))
                    self.body.addWidget(rows)
        self._hidden_section(groups["gizli"])
        self.load_nvidia()
        self.load_amd()

    def load_nvidia(self):
        """NVIDIA kartlarının değerlerini tek NVAPI oturumunda, arka planda okur."""
        cards = [row for row in self.rows.values() if isinstance(row, managers_ui.NvidiaSettingCard)]
        if not cards:
            return
        system = self.c.engine.system
        ids = [card.setting_id for card in cards]

        def read():
            if not system.nvidia_available():
                return None
            return system.get_nvidia_settings(ids)

        def done(values):
            for card in cards:
                try:
                    card.set_value(None if values is None else values.get(card.setting_id))
                except RuntimeError:  # sayfa bu arada yeniden kurulduysa eski kart silinmiştir
                    pass
        self.app.worker.run(read, done, lambda _e: done(None), serial=False)

    def load_amd(self):
        """AMD kartlarının değerlerini tek ADLX oturumunda, arka planda okur."""
        cards = [row for row in self.rows.values() if isinstance(row, managers_ui.AmdSettingCard)]
        if not cards:
            return

        def done(values):
            for card in cards:
                try:
                    card.set_values(values)
                except RuntimeError:  # sayfa bu arada yeniden kurulduysa eski kart silinmiştir
                    pass
        self.app.worker.run(self.c.engine.system.get_amd_settings, done, lambda _e: done(None), serial=False)

    def _hidden_section(self, hidden):
        hidden_count = sum(1 for tw in self.c.tweaks if tw["kategori"] == self.category["ad"]
                           and self.c.availability.get(tw["id"]) and not self.c.availability[tw["id"]].visible)
        if not hidden_count:
            return
        box = QCheckBox(t("ui.uymayanlari_goster", adet=hidden_count))
        box.setChecked(self.show_hidden)

        def toggled(on):
            self.show_hidden = on
            bar = self.scroll.verticalScrollBar()
            pos = bar.value()

            def reload():
                self.data_reloaded()
                self.body_widget.adjustSize()  # kaydırma aralığı güncellensin, sonra konum geri yüklensin
                QTimer.singleShot(0, lambda: bar.setValue(pos))

            QTimer.singleShot(0, reload)  # sinyal içinden widget silinmesin

        box.toggled.connect(toggled)
        self.body.addWidget(box)
        for tweak in hidden:
            card = w.Card()
            card.setEnabled(False)
            card.lay.addWidget(w.label(dialogs.display_name(tweak), muted=True))
            key, params = self.c.availability[tweak["id"]].reasons[0]
            card.lay.addWidget(w.label(t(key, **params), muted=True))
            self.body.addWidget(card)

    # ------------------------------------------------------------------ özel bölümler
    def _gpu_mode_section(self):
        """Laptopta iki ekran kartı varsa: dahili ekranı hangi kart sürüyor (hibrit mi, yalnızca harici mi).
        MUX'un varlığı Windows'tan okunamıyor; değiştirmek üretici yazılımıyla yapılır (Elle yapılacaklar)."""
        hw = self.c.scan["bolumler"].get("donanim") or {}
        gpus = hw.get("gpu") or []
        internal = next((d for d in hw.get("ekranlar") or [] if d.get("dahili")), None)
        if (hw.get("bilgisayar") or {}).get("tur") != "laptop" or len(gpus) < 2 or internal is None:
            return
        mode = "harici" if internal.get("gpu_rol") == "yuksek_performans" else "hibrit"
        card = w.Card(spacing=6)
        head = QLabel(t("ui.mux.baslik"))
        head.setObjectName("CardTitle")
        card.lay.addWidget(w.hbox(w.IconTile(theme.ICONS["GPU"], theme.category_color("PWR")), (head, 1), spacing=12))
        card.lay.addWidget(w.label(t(f"ui.mux.mod.{mode}", kart=internal.get("ekran_karti") or "—")))
        card.lay.addWidget(w.label(t("ui.mux.aciklama"), muted=True, size=12))
        if "PWR-006" in self.c.by_id:
            card.lay.addWidget(w.hbox(None, w.button(t("ui.ayara_git"), lambda: self.app.go_to_tweak("PWR-006"))))
        self.body.addWidget(card)

    def _gpus(self):
        return ((self.c.scan or {}).get("bolumler", {}).get("donanim") or {}).get("gpu") or []

    def _by_gpu(self, tweaks):
        """Ekran Kartı sayfası: ayarlar karta göre ayrı başlıklar altında (hibritte iki kart açıkça ayrılır).
        Başlıkta kartın adı ve rolü (oyunları çizen / ekranı süren) yazar; markaya bağlı olmayanlar en sonda.
        Dönen: [(başlık, ayarlar, not)]. Not: hibritte oyunları başka kart çiziyorsa bu kartın ayarları oyunu etkilemez."""
        gpus = self._gpus()
        renderer = next((g.get("uretici") for g in gpus if g.get("rol") == "yuksek_performans"), None)
        result, rest = [], [tw for tw in tweaks if not tw["uyumluluk"].get("gpu")]
        for vendor in ("NVIDIA", "AMD", "Intel"):
            items = [tw for tw in tweaks if vendor in (tw["uyumluluk"].get("gpu") or [])]
            if not items:
                continue
            cards = [g for g in gpus if g.get("uretici") == vendor]
            names = ", ".join(g["ad"] for g in cards) or vendor
            roles = []
            for g in cards:
                if g.get("rol") == "yuksek_performans":
                    roles.append(t("ui.gpu_grup.cizen"))
                if g.get("ekran_suruyor"):
                    roles.append(t("ui.gpu_grup.ekran"))
            heading = t("ui.gpu_grup.baslik", ad=names) + (f" ({', '.join(roles)})" if roles else "")
            note = t("ui.gpu_grup.cizmiyor") if cards and renderer and renderer != vendor else None
            result.append((heading, items, note))
        if rest:
            result.append((t("ui.gpu_grup.genel") if result else None, rest, None))
        return result

    def _gpu_choice_section(self):
        """Ekran kartı algılanamadıysa: markaya özel ayarlar gizlidir; kullanıcı markayı elle seçebilir."""
        if self.c.engine.profile.gpu_vendors and not settings.get("gpu_markasi_elle"):
            return
        card = w.Card(spacing=6)
        chosen = settings.get("gpu_markasi_elle")
        card.lay.addWidget(w.colored(t("ui.gpu_elle.secildi", marka=chosen) if chosen else t("ui.gpu_elle.algilanamadi"),
                                     "uyari"))

        def pick(vendor):
            settings.set("gpu_markasi_elle", vendor or "")
            self.app.start_scan()

        buttons = [w.button(v, lambda _=False, v=v: pick(v), primary=v == chosen) for v in ("NVIDIA", "AMD", "Intel")]
        if chosen:
            buttons.append(w.button(t("ui.gpu_elle.temizle"), lambda: pick(None)))
        card.lay.addWidget(w.hbox(*buttons, None))
        self.body.addWidget(card)

    def _rebar_section(self):
        """Resizable BAR açık mı: nvidia-smi'nin bildirdiği BAR1 boyutu (kapalıyken 256 MiB). Yalnızca NVIDIA'da
        okunur; açmak BIOS'tan yapılır (GPU-017 rehberi)."""
        rows = [r for r in (self.c.scan["bolumler"].get("donanim") or {}).get("nvidia_smi") or []
                if r.get("bar1_mb")]
        if not rows:
            return
        card = w.Card(spacing=6)
        head = QLabel(t("ui.rebar.baslik"))
        head.setObjectName("CardTitle")
        card.lay.addWidget(w.hbox(w.IconTile(theme.ICONS["GPU"], theme.category_color("GPU")), (head, 1), spacing=12))
        for row in rows:
            on = row["bar1_mb"] > 256
            card.lay.addWidget(w.colored(t("ui.rebar.acik" if on else "ui.rebar.kapali", kart=row["ad"], mb=row["bar1_mb"]),
                                         "iyi" if on else "uyari"))
        card.lay.addWidget(w.label(t("ui.rebar.aciklama"), muted=True, size=12))
        if "GPU-017" in self.c.by_id:
            card.lay.addWidget(w.hbox(None, w.button(t("ui.ayara_git"), lambda: self.app.go_to_tweak("GPU-017"))))
        self.body.addWidget(card)

    def _timer_section(self):
        self.body.addWidget(TimerResolutionCard(self.app))

    def _input_section(self):
        devices = (self.c.scan["bolumler"].get("giris") or {}).get("cihazlar", [])
        if devices:
            self.body.addWidget(InputDevicesCard(self.app, devices))

    # ------------------------------------------------------------------ placebo menüsü
    def _applied_placebo(self):
        """Bu bilgisayarda uygulanmış placebo/zararlı ayarlar (gerçek durum + tespitler)."""
        detected = self.c.detected_ids()
        applied = []
        for tweak in self.c.tweaks:
            if tweak["gerceklik"]["durum"] not in ("placebo", "zararlı") and tweak["kategori"] != "Placebo":
                continue
            state = self.c.states.get(tweak["id"])
            if tweak["sinif"] == "SWITCH" and (tweak["id"] in detected or state and state.status in ("acik", "kismen")):
                applied.append(tweak)
            elif tweak["sinif"] == "BILGI" and tweak["id"] in detected:
                applied.append(tweak)
        return applied

    def _placebo_services(self):
        """FPS listesinde 'placebo' olan ve bu sayfada başka bir anahtarla gösterilmeyen servisler: başlangıç türü
        buradan değiştirilir. Devre dışı olanlar "bu bilgisayarda uygulanmış" sayılır."""
        from app.ui import page_startup  # noqa: WPS433 - döngüsel içe aktarmayı önler
        entries = {k: e for k, e in page_startup.fps_services().items()
                   if e["durum"] == "placebo" and e.get("ilgili") not in self.rows}
        if not entries:
            return
        self.body.addWidget(w.section_title(t("ui.bolum.placebo_servisler")))
        self.body.addWidget(w.label(t("ui.placebo_servisler_aciklama"), muted=True))
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        lay.addWidget(w.label(t("ui.okunuyor_bekle"), muted=True))
        self.body.addWidget(box)

        def done(rows):
            try:
                w.clear_layout(lay)
            except RuntimeError:  # sayfa bu arada yeniden kuruldu
                return
            found = [(r, page_startup.fps_entry(r["servis"], entries)) for r in rows or []]
            found = sorted([(r, e) for r, e in found if e], key=lambda p: (p[0]["baslangic"] != "Disabled", p[0]["ad"]))
            for row, entry in found:
                badges = [w.badge(t("ui.placebo_uygulanmis_rozet"), "uyari")] if row["baslangic"] == "Disabled" else []
                lay.addWidget(page_startup.service_card(self.app, row, entry, self.data_reloaded, badges))
            if not found:
                lay.addWidget(w.label(t("ui.liste_bos"), muted=True))
        self.app.worker.run(self.c.engine.system.list_services, done, lambda _e: done([]), serial=False)

    def _refresh_applied_section(self):
        ids = [t_["id"] for t_ in self._applied_placebo()]
        if ids != getattr(self, "_applied_ids", None):
            QTimer.singleShot(0, self.data_reloaded)

    def _placebo(self):
        menu = self.c.placebo_menu
        self.body.addWidget(w.label(t("ui.placebo_menu_aciklama")))
        applied = self._applied_placebo()
        self._applied_ids = [t_["id"] for t_ in applied]
        detected = self.c.detected_ids()
        self.body.addWidget(w.section_title(t("ui.bolum.uygulanmis_placebo")))
        if applied:
            self.body.addWidget(w.label(t("ui.uygulanmis_placebo_aciklama"), muted=True))
            for tweak in applied:
                row = make_row(self.app, tweak, show_reality=True, detected=tweak["id"] in detected)
                self.body.addWidget(row)
                self.rows.setdefault(tweak["id"], row)
        else:
            self.body.addWidget(w.label(t("ui.uygulanmis_placebo_yok"), muted=True))
        self.body.addWidget(w.section_title(t("ui.bolum.placebo")))
        for tweak in self.c.tweaks:
            if tweak["kategori"] == "Placebo" and tweak["id"] not in self._applied_ids:
                avail = self.c.availability.get(tweak["id"])
                if avail is not None and not avail.visible:
                    continue
                row = make_row(self.app, tweak, show_reality=True, detected=tweak["id"] in detected)
                self.body.addWidget(row)
                self.rows[tweak["id"]] = row
        others = menu.get("diger_kategorilerde_placebo_veya_zararli", [])
        if others:
            self.body.addWidget(w.section_title(t("ui.bolum.diger_placebo")))
            self.body.addWidget(w.label(t("ui.diger_placebo_aciklama"), muted=True))
            for item in others:
                tweak = self.c.by_id.get(item["id"])
                avail = self.c.availability.get(item["id"])
                if item["id"] in self._applied_ids or (avail is not None and not avail.visible):
                    continue
                if tweak is not None and tweak["sinif"] == "SWITCH":  # burada da açılıp kapatılır
                    row = make_row(self.app, tweak, show_reality=True, detected=item["id"] in detected)
                    self.body.addWidget(row)
                    self.rows.setdefault(item["id"], row)
                    continue
                card = w.Card()
                name = QLabel(f"{item['ad']} ({item['id']})")
                name.setObjectName("CardTitle")
                name.setWordWrap(True)
                parts = [(name, 1)]
                if item["id"] in self.c.by_id:
                    parts.append(w.button(t("ui.ayara_git"), lambda _=False, tid=item["id"]: self.app.go_to_tweak(tid)))
                card.lay.addWidget(w.hbox(*parts))
                card.lay.addWidget(w.label(item.get("neden", "")))
                self.body.addWidget(card)
        self._placebo_services()
        self.load_nvidia()
