"""Profiller, Değişiklikler ve Rapor sayfaları."""

import os
import re

from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QFileDialog, QInputDialog, QLabel, QPlainTextEdit, QVBoxLayout,
                               QWidget)

from app.core import paths, privacy
from app.core.i18n import fmt_date, t
from app.engine import profiles as profile_module, user_presets
from app.scan import report
from app.ui import dialogs, widgets as w


class ProfilesPage(w.Page):
    def __init__(self, app):
        super().__init__(app)
        self.selected = "guvenli"
        self.rows = []
        self.checks = {}

    def build(self):
        super().build()
        self.header.addWidget(w.title(t("ui.menu.profiller")))
        self.header.addWidget(w.label(t("ui.profil_giris"), muted=True))
        if self.selected not in {p["id"] for p in self.c.profiles} and self.app.preset_store.get(self.selected) is None:
            self.selected = "guvenli"  # silinen preset
        self.segments = QButtonGroup(self)
        buttons = []
        entries = [(p["id"], t(f"profil.{p['id']}.ad")) for p in self.c.profiles]
        entries += [(p["id"], p["ad"].replace("&", "&&")) for p in self.app.preset_store.presets]  # "&": kısayol sayılmasın
        for entry_id, text in entries:
            button = w.button(text)
            button.setCheckable(True)
            button.setProperty("segment", True)
            button.setChecked(entry_id == self.selected)
            button.clicked.connect(lambda _=False, pid=entry_id: self._select(pid))
            self.segments.addButton(button)
            buttons.append(button)
        self.body.addWidget(w.flow(*buttons))
        self.body.addWidget(self._preset_bar())
        self.list_widget = QWidget()
        self.list_lay = QVBoxLayout(self.list_widget)
        self.list_lay.setContentsMargins(0, 0, 0, 0)
        self.list_lay.setSpacing(4)
        self.body.addWidget(self.list_widget)
        self._show()

    def _select(self, profile_id):
        self.selected = profile_id
        self._rebuild()  # preset düğmeleri (dışa aktar/sil...) seçime göre değişir

    def _rebuild(self):
        w.Page.data_reloaded(self)
        self.scroll_top()

    def _user_preset(self):
        return self.app.preset_store.get(self.selected)

    def _show(self):
        """Profil listesi önbellekteki durumlarla hemen çizilir (sistemi yeniden okumaz)."""
        w.clear_layout(self.list_lay)
        preset = self._user_preset()
        self.list_lay.addWidget(w.label(t("ui.preset.aciklama", adet=len(preset["ayarlar"])) if preset
                                        else t(f"profil.{self.selected}.aciklama")))
        if self.c.meta.get("anti_cheat_uyarisi"):
            self.list_lay.addWidget(w.colored(t("ui.anti_cheat_kisa"), "uyari"))
        self.rows = self._plan()
        self.checks = {}
        if not self.rows:
            self.list_lay.addWidget(w.label(t("ui.profil_bos"), muted=True))
            return
        listing = w.RowList()
        self.list_lay.addWidget(listing)
        for row in self.rows:
            card = w.Card(layout="h")
            box = QCheckBox(row["ad"])
            box.setChecked(row["secili"] or row["zaten_acik"])
            card.lay.addWidget(box, 1)
            if row["zaten_acik"]:
                box.setEnabled(False)
                card.lay.addWidget(w.badge(t("ui.zaten_acik"), "iyi"))
            else:
                self.checks[row["id"]] = box
            if row["onay_gerekli"]:
                card.lay.addWidget(w.badge(t("ui.risk.dikkatli"), "uyari"))
            for key, params in row["uyarilar"]:
                card.lay.addWidget(w.colored(t(key, **params), "uyari"))
            tweak = self.c.by_id[row["id"]]
            card.lay.addWidget(w.info_button(
                lambda _=False, tw=tweak: dialogs.InfoDialog(self.app, tw, self.c.availability.get(tw["id"])).exec()))
            listing.add(card)
        self.apply_button = w.button(t("ui.secilenleri_uygula"), self._apply, primary=True)
        self.apply_button.setEnabled(self.c.can_modify)
        self.list_lay.addWidget(w.hbox(None, self.apply_button))

    def _plan(self):
        rows = []
        preset = self._user_preset()
        items = ([{"id": i, "secili": not self.c.by_id[i]["onay_gerekli"]} for i in preset["ayarlar"]  # dikkatli: asla işaretli gelmez
                  if i in self.c.by_id and user_presets.usable(self.c.by_id[i])]
                 if preset else profile_module.expand(self.c.profiles, self.selected))
        for item in items:
            tweak = self.c.by_id[item["id"]]
            avail = self.c.availability.get(tweak["id"])
            if avail is None or not avail.visible:
                continue
            state = self.c.states.get(tweak["id"])
            on = bool(state and state.is_on)
            rows.append({"id": tweak["id"], "ad": tweak["ad"], "secili": item["secili"] and not on,
                         "zaten_acik": on, "onay_gerekli": tweak["onay_gerekli"], "uyarilar": avail.warnings})
        return rows

    def data_reloaded(self):
        if self.built:
            self._show()

    # ------------------------------------------------------------------ kullanıcı presetleri
    def _preset_bar(self):
        buttons = [w.button(t("ui.preset.kaydet_secili"), self._save_checked),
                   w.button(t("ui.preset.kaydet_acik"), self._save_on),
                   w.button(t("ui.preset.ice_aktar"), self._import_preset)]
        if self._user_preset():
            buttons += [w.button(t("ui.preset.disa_aktar"), self._export_preset),
                        w.button(t("ui.preset.ad_degistir"), self._rename_preset),
                        w.button(t("ui.preset.sil"), self._delete_preset, warn=True)]
        return w.flow(*buttons)

    def _error(self, exc):
        dialogs.show_message(self.app, t("ui.hata_baslik"), t(f"ui.preset.hata.{exc.code}"), "sorun")

    def _saved(self, preset, dropped):
        self.selected = preset["id"]
        self._rebuild()
        if dropped:
            dialogs.show_message(self.app, t("ui.preset.baslik"), t("ui.preset.atilan", ad=preset["ad"], adet=dropped), "uyari")
        else:
            self.app.set_status(t("ui.preset.kaydedildi", ad=preset["ad"], adet=len(preset["ayarlar"])), "iyi")

    def _ask_name(self, default=""):
        name, ok = QInputDialog.getText(self.app, t("ui.preset.baslik"), t("ui.preset.ad_sor", en=user_presets.MAX_NAME), text=default)
        return name if ok else None

    def _save_ids(self, ids):
        name = self._ask_name()
        if name is None:
            return
        try:
            self._saved(*self.app.preset_store.add(name, ids, self.c.by_id))
        except user_presets.PresetError as exc:
            self._error(exc)

    def _save_checked(self):
        """Listede işaretli (ve zaten açık) ayarlar."""
        self._save_ids([r["id"] for r in self.rows
                        if r["zaten_acik"] or (r["id"] in self.checks and self.checks[r["id"]].isChecked())])

    def _save_on(self):
        """Bu bilgisayarda şu an açık olan, preset'e girebilen ayarlar."""
        self._save_ids([tid for tid, state in self.c.states.items()
                        if state and state.is_on and tid in self.c.by_id and user_presets.usable(self.c.by_id[tid])])

    def _rename_preset(self):
        preset = self._user_preset()
        name = self._ask_name(preset["ad"]) if preset else None
        if name is None:
            return
        try:
            self.app.preset_store.rename(preset["id"], name)
        except user_presets.PresetError as exc:
            self._error(exc)
            return
        self._rebuild()

    def _delete_preset(self):
        preset = self._user_preset()
        if preset and dialogs.ask_yes_no(self.app, t("ui.preset.sil"), t("ui.preset.sil_soru", ad=preset["ad"])):
            self.app.preset_store.remove(preset["id"])
            self.selected = "guvenli"
            self._rebuild()

    def _export_preset(self):
        preset = self._user_preset()
        if preset is None:
            return
        safe = re.sub(r"[^\w.-]+", "_", preset["ad"]).strip("_") or "preset"
        path, _ = QFileDialog.getSaveFileName(self.app, t("ui.preset.disa_aktar"),
                                              str(paths.user_data_dir() / f"{safe}.json"), "JSON (*.json)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.app.preset_store.export_text(preset["id"]))
        except OSError:
            dialogs.show_message(self.app, t("ui.hata_baslik"), t("ui.bakim.dosya_yazilamadi"), "sorun")
            return
        self.app.set_status(t("ui.preset.disa_aktarildi"), "iyi")

    def _import_preset(self):
        """Dosya yalnızca listeye eklenir; hiçbir ayar kendiliğinden uygulanmaz."""
        path, _ = QFileDialog.getOpenFileName(self.app, t("ui.preset.ice_aktar"), str(paths.user_data_dir()), "JSON (*.json)")
        if not path:
            return
        try:
            with open(path, "rb") as f:
                raw = f.read(user_presets.MAX_BYTES + 1)
            self._saved(*self.app.preset_store.import_bytes(raw, self.c.by_id))
        except OSError:
            dialogs.show_message(self.app, t("ui.hata_baslik"), t("ui.preset.hata.gecersiz"), "sorun")
        except user_presets.PresetError as exc:
            self._error(exc)

    def _apply(self):
        chosen = [row for row in self.rows if row["id"] in self.checks and self.checks[row["id"]].isChecked()]
        if not chosen:
            return
        self.apply_button.setEnabled(False)
        self.app.apply_profile(chosen, self._show)


class ChangesPage(w.Page):
    def build(self):
        super().build()
        rows = self.c.changed()
        parts = [w.title(t("ui.menu.degisiklikler")), None]
        if rows and self.c.can_modify:
            parts.append(w.button(t("ui.tumunu_geri_al"), lambda: self.app.revert_all(self.data_reloaded), warn=True))
        self.header.addWidget(w.hbox(*parts))
        self.header.addWidget(w.label(t("ui.degisiklik_aciklama"), muted=True))
        if not rows:
            self.body.addWidget(w.label(t("ui.degisiklik_yok"), muted=True))
        changes = w.RowList()
        if rows:
            self.body.addWidget(changes)
        for tweak_id, name, when in rows:
            card = w.Card(layout="h")
            title = QLabel(name)
            title.setObjectName("CardTitle")
            card.lay.addWidget(title)
            card.lay.addWidget(w.label(when, muted=True, wrap=False))
            card.lay.addStretch(1)
            if self.c.can_modify:
                card.lay.addWidget(w.button(t("ui.eski_haline"),
                                            lambda _=False, tid=tweak_id: self.app.revert(tid, self.data_reloaded)))
            changes.add(card)
        self.body.addWidget(w.label(t("ui.elle_kurtarma", klasor=str(paths.backups_dir())), muted=True))
        from app.ui.report_extra import irreversible_records  # noqa: WPS433
        actions = irreversible_records(self.c.engine.store, limit=10)
        if actions:
            # Geri alınamaz tek seferlik işlemler: yalnızca kayıt olarak gösterilir.
            self.body.addWidget(w.section_title(t("ui.bolum.geri_alinamaz")))
            records = w.RowList()
            self.body.addWidget(records)
            for record in actions:
                tweak = self.c.by_id.get(record["id"])
                name = dialogs.display_name(tweak) if tweak else record["id"]
                tone = "iyi" if record["basarili"] else "sorun"
                card = w.Card(layout="h")
                card.lay.addWidget(w.label(name), 1)
                card.lay.addWidget(w.colored(t("ui.basarili") if record["basarili"] else t("ui.basarisiz"), tone,
                                             wrap=False))
                card.lay.addWidget(w.label(fmt_date(record["zaman"]), muted=True, wrap=False))
                records.add(card)

    def on_show(self, highlight=None):
        self.data_reloaded() if self.built else self.build()


class ReportPage(w.Page):
    def build(self):
        super().build()
        parts = [w.title(t("ui.menu.rapor")), None]
        if self.c.scan is not None:
            parts += [w.button(t("ui.raporu_kaydet"), self._save, primary=True),
                      w.button(t("ui.klasoru_ac"), lambda: os.startfile(paths.reports_dir()))]
        self.header.addWidget(w.hbox(*parts))
        self.header.addWidget(w.label(t("ui.rapor_aciklama"), muted=True))
        if self.c.scan is None:
            self.body.addWidget(w.label(t("ui.once_tarama"), muted=True))
            return
        text = privacy.scrub_text(report.build_text(privacy.scrub(self.c.scan, export=True), self._extra()))
        box = QPlainTextEdit()
        box.setReadOnly(True)
        box.setPlainText(text)
        box.setMinimumHeight(560)
        self.body.addWidget(box)

    def _extra(self):
        from app.ui import report_extra  # noqa: WPS433
        try:
            return report_extra.sections(self.c, getattr(self.app, "game_store", None))
        except Exception:  # etkinlik bölümü bozuksa tarama raporu yine gösterilsin
            return []

    def _save(self):
        try:
            txt_path, _json_path = report.save(self.c.scan, extra=self._extra())
        except OSError:
            dialogs.show_message(self.app, t("ui.hata_baslik"), t("ui.rapor_kaydedilemedi"), "sorun")
            return
        dialogs.show_message(self.app, t("ui.raporu_kaydet"),
                             t("ui.rapor_kaydedildi", dosya=txt_path.name, klasor=str(txt_path.parent)), "iyi")

    def on_show(self, highlight=None):
        self.data_reloaded() if self.built else self.build()
