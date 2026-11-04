"""Profiller, Değişiklikler ve Rapor sayfaları."""

import os

from PySide6.QtWidgets import QButtonGroup, QCheckBox, QLabel, QPlainTextEdit, QVBoxLayout, QWidget

from app.core import paths, privacy
from app.core.i18n import fmt_date, t
from app.engine import profiles as profile_module
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
        self.segments = QButtonGroup(self)
        buttons = []
        for profile in self.c.profiles:
            button = w.button(t(f"profil.{profile['id']}.ad"))
            button.setCheckable(True)
            button.setProperty("segment", True)
            button.setChecked(profile["id"] == self.selected)
            button.clicked.connect(lambda _=False, pid=profile["id"]: self._select(pid))
            self.segments.addButton(button)
            buttons.append(button)
        self.body.addWidget(w.hbox(*buttons, None))
        self.list_widget = QWidget()
        self.list_lay = QVBoxLayout(self.list_widget)
        self.list_lay.setContentsMargins(0, 0, 0, 0)
        self.list_lay.setSpacing(4)
        self.body.addWidget(self.list_widget)
        self._show()

    def _select(self, profile_id):
        self.selected = profile_id
        self._show()

    def _show(self):
        """Profil listesi önbellekteki durumlarla hemen çizilir (sistemi yeniden okumaz)."""
        w.clear_layout(self.list_lay)
        self.list_lay.addWidget(w.label(t(f"profil.{self.selected}.aciklama")))
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
        for item in profile_module.expand(self.c.profiles, self.selected):
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
