"""Ekstra ayarlar (uygulamanın kendi ayarları, bakım araçları) ve Bilgi sayfası.

Windows ayarlarına dokunan tek seçenek "Windows'la başlat"tır (zamanlanmış görev;
varsayılan kapalı). Bilgi sayfasındaki ad, iletişim ve bağlantılar data/hakkinda.json
dosyasından gelir; uygulama hiçbir yere kendiliğinden bağlanmaz.
"""

import json
import os
import re

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QCheckBox, QComboBox, QFileDialog, QLabel, QPlainTextEdit, QVBoxLayout

from app import COPYRIGHT_YEAR, __author__, __version__
from app.core import autostart, guncelleme, i18n, paths, settings
from app.core.i18n import t
from app.games.profiles import DEFAULT_PROFILE
from app.ui import dialogs, theme, widgets as w


def about_data():
    """{"yapimci": ..., "satirlar": [...], "baglantilar": [...]}; eski biçimdeki "baslik" ve "iletisim" de okunur."""
    try:
        data = json.loads((paths.data_dir() / "hakkinda.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    return {"yapimci": data.get("yapimci") or data.get("baslik") or "", "satirlar": data.get("satirlar") or data.get("iletisim") or [],
            "baglantilar": data.get("baglantilar") or [], "faydali": data.get("faydali") or [],
            "katkida": data.get("katkida_bulunanlar") or [], "bagis_url": data.get("bagis_url") or ""}


def donate_url_ok(url):
    """Gönüllü bağış bağlantısı: yalnızca https ve Buy Me a Coffee adresi (data/hakkinda.json "bagis_url")."""
    return bool(re.fullmatch(r"https://(?:[a-z0-9-]+\.)*buymeacoffee\.com(?:/[A-Za-z0-9._~/-]*)?", url or ""))


def licenses_text(name="THIRD-PARTY-NOTICES.txt"):
    """Programın yanındaki metin dosyası (derlenmiş pakette de, depo kökünde de aynı yerde)."""
    for path in (paths.app_dir() / name,):
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            continue
    return t("ui.lisans_bulunamadi")


class SettingsPage(w.Page):
    def __init__(self, app):
        super().__init__(app)
        self.autostart = None  # None: okunuyor

    def on_show(self, highlight=None):
        self.ensure_built()
        if self.autostart is None:
            self.app.worker.run(autostart.is_enabled, self._autostart_read, lambda _e: self._autostart_read(False),
                                serial=False)

    def _autostart_read(self, enabled):
        self.autostart = bool(enabled)
        self.data_reloaded()

    def build(self):
        super().build()
        self.header.addWidget(w.title(t("ui.menu.ayarlar")))
        self.header.addWidget(w.label(t("ui.ayarlar_aciklama"), muted=True))

        self.body.addWidget(w.section_title(t("ui.bolum.uygulama_ayarlari")))
        self.body.addWidget(self._language_card())
        self.body.addWidget(self._toggle_card(t("ui.ayar.ekstra_bilgi"), t("ui.ayar.ekstra_bilgi_aciklama"),
                                              settings.get("ekstra_bilgi"), lambda on: settings.set("ekstra_bilgi", on)))
        self.body.addWidget(self._toggle_card(
            t("ui.ayar.rp_sor"), t("ui.ayar.rp_sor_aciklama"), not settings.get("rp_sorma"),
            lambda on: settings.set("rp_sorma", "" if on else "olustur")))
        self.body.addWidget(self._toggle_card(t("ui.ayar.tepsi"), t("ui.ayar.tepsi_aciklama"),
                                              settings.get("tepsiye_kucult"), self._set_tray))
        autostart_card = self._toggle_card(t("ui.ayar.windows_ile_baslat"), t("ui.ayar.windows_ile_baslat_aciklama"),
                                           bool(self.autostart), self._set_autostart,
                                           enabled=self.c.can_modify and self.autostart is not None)
        self.body.addWidget(autostart_card)
        if self.autostart and paths.in_user_profile(paths.app_dir()):  # eski sürümde profilde açılmış görev
            self.body.addWidget(w.banner(t("ui.ayar.windows_ile_baslat_profil_acik"), "uyari"))

        self.body.addWidget(w.section_title(t("ui.erisim.baslik")))
        self.body.addWidget(self._toggle_card(t("ui.erisim.okunabilir"), t("ui.erisim.okunabilir_aciklama"),
                                              settings.get("okunabilir_yazi"),
                                              lambda on: self._set_look("okunabilir_yazi", on)))
        self.body.addWidget(self._toggle_card(t("ui.erisim.hareket"), t("ui.erisim.hareket_aciklama"),
                                              settings.get("hareket_azalt"),
                                              lambda on: settings.set("hareket_azalt", on)))
        self.body.addWidget(self._toggle_card(t("ui.erisim.karsitlik"), t("ui.erisim.karsitlik_aciklama"),
                                              settings.get("yuksek_karsitlik"),
                                              lambda on: self._set_look("yuksek_karsitlik", on)))

        self.body.addWidget(w.section_title(t("ui.bolum.guncelleme")))
        self.body.addWidget(self._toggle_card(t("ui.guncelleme.otomatik"), t("ui.guncelleme.otomatik_aciklama"),
                                              settings.get("guncelleme_denetle"),
                                              lambda on: settings.set("guncelleme_denetle", on)))
        card = w.Card(layout="h", spacing=10)
        text = QVBoxLayout()
        name = QLabel(t("ui.guncelleme.simdi"))
        name.setObjectName("CardTitle")
        text.addWidget(name)
        text.addWidget(w.label(t("ui.guncelleme.simdi_aciklama", surum=__version__), muted=True, size=12))
        card.lay.addLayout(text, 1)
        card.lay.addWidget(w.button(t("ui.guncelleme.simdi"), self._check_update))
        self.body.addWidget(card)

        self.body.addWidget(w.section_title(t("ui.bolum.bakim")))
        tools = [
            ("ui.bakim.log", "ui.bakim.log_aciklama", lambda: os.startfile(paths.logs_dir()), True),
            ("ui.bakim.yeniden_algila", "ui.bakim.yeniden_algila_aciklama", self._redetect, True),
            ("ui.bakim.tanilama", "ui.bakim.tanilama_aciklama", self._diagnose, True),
            ("ui.bakim.geri_yukleme", "ui.bakim.geri_yukleme_aciklama", self._restore_point, self.c.can_modify),
            ("ui.bakim.disa_aktar", "ui.bakim.disa_aktar_aciklama", self._export, True),
            ("ui.bakim.ice_aktar", "ui.bakim.ice_aktar_aciklama", self._import, True),
            ("ui.bakim.sifirla", "ui.bakim.sifirla_aciklama", self._reset, True),
            ("ui.kaldir.baslik", "ui.kaldir.aciklama", self._uninstall, self.c.can_modify),
        ]
        for title_key, text_key, action, enabled in tools:
            card = w.Card(layout="h", spacing=10)
            text = QVBoxLayout()
            name = QLabel(t(title_key))
            name.setObjectName("CardTitle")
            text.addWidget(name)
            text.addWidget(w.label(t(text_key), muted=True, size=12))
            card.lay.addLayout(text, 1)
            button = w.button(t(title_key), action)
            button.setEnabled(enabled)
            card.lay.addWidget(button)
            self.body.addWidget(card)

    def _check_update(self):
        if self.app.busy:
            return
        self.app.busy = True
        self.app.set_status(t("ui.guncelleme.denetleniyor"))
        self.app.worker.run(guncelleme.kontrol, self._update_found, self._update_failed, serial=False)

    def _update_failed(self, exc):
        self.app.busy = False
        key = exc.kod if isinstance(exc, guncelleme.GuncellemeHatasi) else "baglanti"
        self.app.set_status(t(f"ui.guncelleme.hata.{key}"), "sorun")

    def _update_found(self, info):
        self.app.busy = False
        if info is None:
            self.app.set_status(t("ui.guncelleme.guncel"), "iyi")
            return
        size = f"{info['boyut'] / 1048576:.0f} MB" if info["boyut"] else "?"
        if not dialogs.ask_yes_no(self.app, t("ui.guncelleme.baslik"),
                                  t("ui.guncelleme.var", surum=info["surum"], boyut=size, suanki=__version__),
                                  yes_text=t("ui.guncelleme.kur")):
            return
        waiting = dialogs.busy(self.app, t("ui.guncelleme.baslik"), t("ui.guncelleme.indiriliyor"))
        self.app.busy = True

        def done(folder):
            waiting.finish()
            self.app.busy = False
            try:
                guncelleme.degisimi_baslat(folder)
            except guncelleme.GuncellemeHatasi as exc:
                self.app.set_status(t(f"ui.guncelleme.hata.{exc.kod}"), "sorun")
                return
            self.app.quit_from_tray()

        def failed(exc):
            waiting.finish()
            self._update_failed(exc)

        self.app.worker.run(lambda: guncelleme.indir_ve_hazirla(info), done, failed, serial=False)

    def _toggle_card(self, title, description, checked, on_change, enabled=True):
        card = w.Card(layout="h", spacing=10)
        text = QVBoxLayout()
        name = QLabel(title)
        name.setObjectName("CardTitle")
        text.addWidget(name)
        text.addWidget(w.label(description, muted=True, size=12))
        card.lay.addLayout(text, 1)
        switch = w.ToggleSwitch()
        switch.setChecked(bool(checked))
        switch.setEnabled(enabled)
        switch.toggled.connect(on_change)
        card.lay.addWidget(switch)
        return card

    def _language_card(self):
        card = w.Card(layout="h", spacing=10)
        text = QVBoxLayout()
        name = QLabel(t("ui.ayar.dil"))
        name.setObjectName("CardTitle")
        text.addWidget(name)
        text.addWidget(w.label(t("ui.ayar.dil_aciklama"), muted=True, size=12))
        if t("ui.ayar.dil_ceviri_notu"):
            text.addWidget(w.label(t("ui.ayar.dil_ceviri_notu"), muted=True, size=12))
        card.lay.addLayout(text, 1)
        combo = QComboBox()
        for item in i18n.available():
            combo.addItem(item["yerel_ad"], item["kod"])
        combo.setCurrentIndex(max(0, combo.findData(i18n.current())))
        combo.currentIndexChanged.connect(lambda _i: self._set_language(combo.currentData()))
        card.lay.addWidget(combo)
        return card

    def _set_language(self, code):
        if not code or code == settings.get("dil"):
            return
        settings.set("dil", code)
        if dialogs.ask_yes_no(self.app, t("ui.ayar.dil"), t("ui.ayar.dil_kaydedildi"),
                              yes_text=t("ui.ayar.dil_yeniden"), no_text=t("ui.ayar.dil_sonra")):
            self.app.restart_app()

    def _set_look(self, key, on):
        """Yazı ve renk yeniden başlatınca uygulanır (yarım uygulanmış bir görünüm yerine temiz açılış)."""
        settings.set(key, on)
        if dialogs.ask_yes_no(self.app, t("ui.erisim.baslik"), t("ui.erisim.yeniden"),
                              yes_text=t("ui.ayar.dil_yeniden"), no_text=t("ui.ayar.dil_sonra")):
            self.app.restart_app()

    # ------------------------------------------------------------------ uygulama ayarları
    def _set_tray(self, on):
        settings.set("tepsiye_kucult", on)
        self.app.update_tray()

    def _set_autostart(self, on):
        if on == self.autostart:
            return

        def done(_):
            self.autostart = on
            self.c.engine.store.history("uygulama_ayari", "windows_ile_baslat", True, str(on))
            self.app.set_status(t("ui.ayar.windows_ile_baslat_acik" if on else "ui.ayar.windows_ile_baslat_kapali"),
                                "iyi")
            if on and not settings.get("tepsiye_kucult"):
                settings.set("tepsiye_kucult", True)  # tepside başlamak için tepsi simgesi gerekir
                self.app.update_tray()
            self.data_reloaded()

        def failed(exc):
            text = (t("ui.ayar.windows_ile_baslat_profil", klasor=str(exc))
                    if isinstance(exc, autostart.ProfileFolderError) else t("ui.ayar.windows_ile_baslat_hata"))
            dialogs.show_message(self.app, t("ui.hata_baslik"), text, "sorun")
            self.data_reloaded()

        self.app.worker.run(autostart.enable if on else autostart.disable, done, failed)

    # ------------------------------------------------------------------ bakım
    def _redetect(self):
        self.app.c.fresh.clear()
        self.app.reload_pages()
        self.app._start_background()
        self.app.set_status(t("ui.bakim.yeniden_algilaniyor"))

    def _diagnose(self):
        from app.engine import tanilama  # noqa: WPS433
        self.app.set_status(t("ui.bakim.tanilama_calisiyor"))
        profile = self.c.engine.profile

        def work():
            path = paths.logs_dir() / "durum_tanilama.txt"
            path.write_text(tanilama.rapor(profile), encoding="utf-8")
            return path

        def done(path):
            self.app.set_status(t("ui.bakim.tanilama_bitti"), "iyi")
            os.startfile(path.parent)

        self.app.worker.run(work, done, lambda _e: self.app.set_status(t("hata.beklenmeyen"), "sorun"))

    def _restore_point(self):
        engine = self.c.engine
        waiting = dialogs.busy(self.app, t("ui.rp_baslik"), t("ui.rp_olusturuluyor"))

        def done(result):
            waiting.finish()
            engine.restore_point = result
            self.app._restore_point_result(result, lambda: None, lambda: None)

        def failed(_exc):
            waiting.finish()
            dialogs.show_message(self.app, t("ui.hata_baslik"), t("rp.basarisiz"), "sorun")

        from app.engine import restore_point  # noqa: WPS433
        self.app.worker.run(lambda: restore_point.ensure(engine.system), done, failed)

    def _export(self):
        path, _ = QFileDialog.getSaveFileName(self.app, t("ui.bakim.disa_aktar"),
                                              str(paths.user_data_dir() / "forevermore_ayarlar.json"), "JSON (*.json)")
        if not path:
            return
        data = {"uygulama": EXPORT_MARKER, "surum": __version__, "uygulama_ayarlari": dict(settings.load()),
                "oyunlar": self.app.game_store.games}
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except OSError:
            dialogs.show_message(self.app, t("ui.hata_baslik"), t("ui.bakim.dosya_yazilamadi"), "sorun")
            return
        self.app.set_status(t("ui.bakim.disa_aktarildi"), "iyi")

    def _import(self):
        path, _ = QFileDialog.getOpenFileName(self.app, t("ui.bakim.ice_aktar"), str(paths.user_data_dir()),
                                              "JSON (*.json)")
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            imported = import_settings(data, self.app.game_store)
        except (OSError, ValueError):
            dialogs.show_message(self.app, t("ui.hata_baslik"), t("ui.bakim.gecersiz_dosya"), "sorun")
            return
        self.app.update_tray()
        self.app.update_game_watcher()
        self.app.set_status(t("ui.bakim.ice_aktarildi", adet=imported), "iyi")
        self.data_reloaded()

    def _reset(self):
        if not dialogs.ask_yes_no(self.app, t("ui.bakim.sifirla"), t("ui.bakim.sifirla_soru")):
            return
        for key, value in settings.DEFAULTS.items():
            settings.set(key, value)
        self.app.update_tray()
        self.app.set_status(t("ui.bakim.sifirlandi"), "iyi")
        self.data_reloaded()

    def _uninstall(self):
        dialog = UninstallDialog(self.app, bool(self.c.engine.changed_ids()))
        if not dialog.exec():
            return
        revert, delete = dialog.revert.isChecked(), dialog.delete.isChecked()
        engine = self.c.engine
        if self.app.game_watcher is not None:
            self.app.game_watcher.stop()
            self.app.game_watcher = None
        waiting = dialogs.busy(self.app, t("ui.kaldir.baslik"), t("ui.lutfen_bekleyin"))

        def work():
            from app.core import uninstall  # noqa: WPS433
            return uninstall.cleanup(engine, revert_changes=revert, delete_data=delete)

        def done(report):
            waiting.finish()
            lines = [t("ui.kaldir.sonuc_gorev") if report["gorev"] else t("ui.kaldir.sonuc_gorev_yok"),
                     t("ui.kaldir.sonuc_geri", adet=report["geri_alinan"]) if revert else t("ui.kaldir.sonuc_geri_yok")]
            if report["geri_alinamayan"]:
                lines.append(t("ui.kaldir.sonuc_geri_hata", liste=", ".join(report["geri_alinamayan"])))
            lines.append(t("ui.kaldir.sonuc_veri") if report["veri_silindi"] else t("ui.kaldir.sonuc_veri_yok"))
            lines.append(t("ui.kaldir.son"))
            dialogs.show_message(self.app, t("ui.kaldir.baslik"), "\n".join(lines),
                                 "uyari" if report["geri_alinamayan"] else "iyi")
            # Veriler silindiyse kapanırken önbellek yeniden yazılıp klasör geri oluşturulmasın.
            self.app.skip_save = report["veri_silindi"]
            self.app.quit_from_tray()

        def failed(_exc):
            waiting.finish()
            dialogs.show_message(self.app, t("ui.hata_baslik"), t("hata.beklenmeyen"), "sorun")

        self.app.worker.run(work, done, failed)


class UninstallDialog(dialogs._Dialog):  # noqa: SLF001 - ortak pencere tabanı
    """Kaldırmaya hazırlık: ne yapılacağını seçtirir."""

    def __init__(self, parent, has_changes):
        super().__init__(parent, t("ui.kaldir.baslik"), width=600, height=380)
        self.heading(t("ui.kaldir.baslik"), size=16)
        self.outer.addWidget(w.label(t("ui.kaldir.metin")))
        self.revert = QCheckBox(t("ui.kaldir.geri_al"))
        self.revert.setChecked(has_changes)
        self.revert.setEnabled(has_changes)
        self.delete = QCheckBox(t("ui.kaldir.veri_sil"))
        self.delete.setEnabled(not has_changes)
        self.revert.toggled.connect(lambda on: self.delete.setEnabled(on or not has_changes))
        self.revert.toggled.connect(lambda on: self.delete.setChecked(False) if not on and has_changes else None)
        self.outer.addWidget(self.revert)
        self.outer.addWidget(self.delete)
        self.outer.addWidget(w.label(t("ui.kaldir.not"), muted=True, size=12))
        self.outer.addStretch(1)
        self.outer.addWidget(w.hbox(None, w.button(t("ui.vazgec"), self.reject),
                                    w.button(t("ui.kaldir.basla"), self.accept, primary=True)))


class AboutPage(w.Page):
    """Bilgi: üstte uygulamanın amacı ve tanıtımı (lang: ui.bilgi.amac / ui.bilgi.hikaye), sürüm, gizlilik,
    lisanslar; en altta yapımcı ve iletişim (data/hakkinda.json)."""

    def build(self):
        super().build()
        self.header.addWidget(w.title(t("ui.menu.bilgi")))
        self.header.addWidget(w.label(t("ui.bilgi_aciklama"), muted=True))
        data = about_data()

        app_card = w.Card(spacing=10)
        head = QLabel(t("uygulama.ad"))
        head.setObjectName("Hero")
        mark = w.logo(48)
        app_card.lay.addWidget(w.hbox(*([mark] if mark else []), head, None, spacing=14))
        app_card.lay.addWidget(w.label(t("ui.bilgi.surum", surum=__version__), muted=True))
        app_card.lay.addWidget(w.label(t("ui.bilgi.amac")))
        story = QLabel(t("ui.bilgi.hikaye_baslik"))
        story.setObjectName("CardTitle")
        app_card.lay.addWidget(story)
        app_card.lay.addWidget(w.label(t("ui.bilgi.hikaye")))
        app_card.lay.addWidget(w.label(t("ui.bilgi.gizlilik"), muted=True, size=theme.SMALL_SIZE))
        app_card.lay.addWidget(w.label(t("ui.bilgi.telif", yil=COPYRIGHT_YEAR, ad=__author__), muted=True,
                                       size=theme.SMALL_SIZE))
        app_card.lay.addWidget(w.hbox(
            w.button(t("ui.bilgi.kullanim_lisansi"),
                     lambda: LicensesDialog(self.app, t("ui.bilgi.kullanim_lisansi"), "LICENSE").exec()),
            w.button(t("ui.bilgi.lisanslar"), lambda: LicensesDialog(self.app).exec()), None))
        self.body.addWidget(app_card)

        person = w.Card(spacing=6)
        title = QLabel(t("ui.bilgi.yapimci"))
        title.setObjectName("CardTitle")
        person.lay.addWidget(title)
        col = person.lay
        if data["yapimci"]:
            col.addWidget(w.label(data["yapimci"], bold=True, selectable=True))
        for item in data["satirlar"] + data["baglantilar"]:   # iletişim ve resmî adresler tek kartta, yapımcının altında
            col.addWidget(self._link_row(item))
        if donate_url_ok(data["bagis_url"]):  # küçük, sessiz bir bağlantı: pencere, uyarı ya da engel yok
            col.addWidget(self._donate_link(data["bagis_url"]))
        self.body.addWidget(person)
        if data["katkida"]:
            thanks = w.Card(spacing=6)
            head = QLabel(t("ui.bilgi.katkida"))
            head.setObjectName("CardTitle")
            thanks.lay.addWidget(head)
            thanks.lay.addWidget(w.label(t("ui.bilgi.katkida_aciklama"), muted=True, size=12))
            thanks.lay.addWidget(w.label(" · ".join(str(name) for name in data["katkida"])))
            self.body.addWidget(thanks)

    def _link_row(self, item):
        parts = [w.label(f"{item.get('etiket', '')}: {item.get('deger', '')}".rstrip(": "), selectable=True, wrap=False)]
        if item.get("deger"):
            parts.append(w.button(t("ui.bilgi.kopyala"), lambda _=False, v=item["deger"]: self._copy(v)))
        if str(item.get("url", "")).startswith("https://"):
            parts.append(w.button(t("ui.bilgi.ac"), lambda _=False, u=item["url"]: os.startfile(u)))
        return w.hbox(*parts, None)

    @staticmethod
    def _donate_link(url):
        link = QLabel(f'<a href="{url}">{t("ui.bilgi.bagis")}</a>')
        link.setTextInteractionFlags(Qt.TextInteractionFlag.LinksAccessibleByMouse
                                     | Qt.TextInteractionFlag.LinksAccessibleByKeyboard)
        link.linkActivated.connect(lambda target: os.startfile(target) if donate_url_ok(target) else None)  # noqa: S606
        return link

    def _copy(self, value):
        QGuiApplication.clipboard().setText(value)
        self.app.set_status(t("ui.bilgi.kopyalandi", deger=value), "iyi")


class LicensesDialog(dialogs._Dialog):  # noqa: SLF001 - ortak pencere tabanı
    def __init__(self, parent, title=None, name="THIRD-PARTY-NOTICES.txt"):
        title = title or t("ui.bilgi.lisanslar")
        super().__init__(parent, title, width=760, height=560)
        self.heading(title, size=16)
        viewer = QPlainTextEdit(licenses_text(name))
        viewer.setReadOnly(True)
        self.outer.addWidget(viewer, 1)
        self.outer.addWidget(w.hbox(None, w.button(t("ui.tamam"), self.accept, primary=True)))


EXPORT_MARKER = "Forevermore"
LEGACY_EXPORT_MARKERS = ("PC Optimizer",)  # eski adla dışa aktarılmış dosyalar da kabul edilir


def import_settings(data, store):
    """Dışa aktarılan dosyayı içe alır: bilinen uygulama ayarları ve oyun profilleri.
    Kalıcı oyun ayarları (öncelik vb.) burada YAZILMAZ; kullanıcı oyunu açıp kaydedince uygulanır."""
    if not isinstance(data, dict) or data.get("uygulama") not in (EXPORT_MARKER, *LEGACY_EXPORT_MARKERS):
        raise ValueError("gecersiz")
    for key, value in (data.get("uygulama_ayarlari") or {}).items():
        if key in settings.DEFAULTS and isinstance(value, type(settings.DEFAULTS[key])):
            settings.set(key, value)
    count = 0
    for game in data.get("oyunlar") or []:
        if not isinstance(game, dict) or not game.get("ad") or not game.get("klasor"):
            continue
        try:
            added = store.add(game["ad"], game["klasor"], game.get("kaynak", ""), game.get("exe"))
        except ValueError:  # anti-cheat / başlatıcı: alınmaz
            continue
        profile = {k: v for k, v in (game.get("profil") or {}).items() if k in DEFAULT_PROFILE}
        store.update_profile(added["id"], dict(added["profil"], **profile))
        count += 1
    return count
