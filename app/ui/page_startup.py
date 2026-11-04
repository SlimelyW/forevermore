"""Başlangıç ve servis yöneticisi (Autoruns vb. gömülmez; kendi kodumuz).

Sekmeler:
- Uygulamalar: Run anahtarları ve başlangıç klasörleri. Kapatma, Görev Yöneticisi'nin
  yaptığı gibi StartupApproved değeriyle yapılır; program silinmez.
- Zamanlanmış görevler: oturum açılışında veya önyüklemede çalışan, Microsoft dışı görevler.
- Servisler: başlangıç türü (Otomatik / Gecikmeli / Elle / Devre dışı). Kritik Windows
  servisleri ve anti-cheat servisleri kilitlidir. Başlangıç türüne göre ve "FPS'i etkileyebilecek
  servisler" listesine (data/fps_servisleri.json, kaynakları ilgili ayarda) göre süzülebilir.

Komut satırları yalnızca ekranda gösterilir; rapora ve önbelleğe yazılmaz.
"""

from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QLabel, QLineEdit, QSizePolicy, QVBoxLayout,
                               QWidget)

import json

from app.core import paths
from app.core.i18n import t, value_label
from app.ui import dialogs, theme, widgets as w

TABS = ("uygulamalar", "gorevler", "servisler")
START_FILTERS = {"tumu": None, "otomatik": ("Automatic", "AutomaticDelayed"), "el_ile": ("Manual",),
                 "devre_disi": ("Disabled",)}


def fps_services():
    """{servis adı (küçük harf): kayıt} — FPS'i etkileyebilecek servisler listesi."""
    try:
        data = json.loads((paths.data_dir() / "fps_servisleri.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {item["servis"].lower(): item for item in data.get("servisler", [])}


def fps_entry(service_name, entries):
    """Servisin listedeki kaydı; kullanıcıya özel ekli servisler (ad_1a2b3) önekle eşleşir."""
    lowered = service_name.lower()
    if lowered in entries:
        return entries[lowered]
    base = lowered.rsplit("_", 1)[0]
    entry = entries.get(base)
    return entry if entry and entry.get("onek") else None
START_TYPES = ("Automatic", "AutomaticDelayed", "Manual", "Disabled")


def service_card(app, row, fps=None, reload=lambda: None, extra_badges=()):
    """Tek servis satırı: başlangıç türü seçimi, Uygula ve Eski haline getir. fps: FPS listesindeki kayıt."""
    c = app.c
    card = w.Card(layout="h", spacing=10)
    name = w.label(row["ad"], wrap=False)
    name.setToolTip(row["servis"])
    name.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
    if fps:
        text = QVBoxLayout()
        text.setSpacing(2)
        text.addWidget(name)
        text.addWidget(w.hbox(w.badge(value_label("deger.gerceklik", fps["durum"]),
                                      theme.REALITY_TONE.get(fps["durum"], "notr")), *extra_badges, None))
        text.addWidget(w.label(t(f"fps_servis.{fps['servis']}"), muted=True, size=12))
        if fps.get("ilgili") in c.by_id:
            text.addWidget(w.hbox(w.button(t("ui.ayara_git"),
                                           lambda _=False, tid=fps["ilgili"]: app.go_to_tweak(tid)), None))
        card.lay.addLayout(text, 1)
    else:
        card.lay.addWidget(name, 1)
    if row["windows"]:
        card.lay.addWidget(w.badge(t("ui.windows_servisi"), "notr"))
    if c.engine.store.has(row["id"]):
        card.lay.addWidget(w.badge(t("ui.degistirildi"), "bilgi"))
    card.lay.addWidget(w.label(t("ui.calisiyor") if row["calisiyor"] else t("ui.durdu"), muted=True, wrap=False))
    combo = QComboBox()
    for kind in START_TYPES:
        combo.addItem(t(f"ui.baslangic_turu.{kind}"), kind)
    combo.setCurrentIndex(max(0, combo.findData(row["baslangic"])))
    combo.setFixedWidth(170)
    if row["kilit"]:
        combo.setEnabled(False)
        card.lay.addWidget(w.badge(t(f"ui.servis_kilit.{row['kilit']}"), "uyari"))
        card.setToolTip(t(f"ui.servis_kilit_neden.{row['kilit']}"))
    else:
        combo.setEnabled(c.can_modify)
    card.lay.addWidget(combo)
    apply = w.button(t("ui.uygula"), lambda: apply_service(app, row, combo.currentData(), reload))
    apply.setEnabled(c.can_modify and not row["kilit"])
    card.lay.addWidget(apply)
    if c.engine.store.has(row["id"]) and c.can_modify:
        card.lay.addWidget(w.button(t("ui.eski_haline"), lambda: app.revert(row["id"], reload)))
    return card


def apply_service(app, row, kind, reload=lambda: None):
    if kind == row["baslangic"] or row["kilit"]:
        return
    if row["windows"] and not dialogs.ask_yes_no(app, t("ui.dikkat"), t("ui.windows_servisi_onay", ad=row["ad"])):
        return
    step = {"tur": "servis", "ad": row["servis"]}
    value = {"baslangic": kind, "calisiyor": False if kind == "Disabled" else None}
    app.apply_custom(row["id"], t("ui.servis_degisiklik", ad=row["ad"]), [step], [value], reload,
                     restart="bilgisayar")


class StartupPage(w.Page):
    def __init__(self, app):
        super().__init__(app)
        self.tab = "uygulamalar"
        self.data = {}          # sekme -> liste (None: okunuyor)
        self.show_windows = False
        self.filter_text = ""
        self.start_filter = "tumu"
        self.fps_only = False

    def on_show(self, highlight=None):
        self.ensure_built()
        if self.tab not in self.data:
            self._load(self.tab)

    def build(self):
        super().build()
        self.header.addWidget(w.hbox(w.title(t("ui.menu.baslangic")), None,
                                     w.button(t("ui.yenile"), lambda: self._load(self.tab))))
        self.header.addWidget(w.label(t("ui.baslangic_aciklama"), muted=True))
        group = QButtonGroup(self)
        buttons = []
        for key in TABS:
            button = w.button(t(f"ui.baslangic_sekme.{key}"), lambda _=False, k=key: self._switch(k))
            button.setCheckable(True)
            button.setProperty("segment", True)
            button.setChecked(key == self.tab)
            group.addButton(button)
            buttons.append(button)
        self.header.addWidget(w.hbox(*buttons, None))
        self._content()

    def _switch(self, key):
        self.tab = key
        self.data_reloaded()
        if key not in self.data:
            self._load(key)

    def _load(self, tab):
        self.data[tab] = None
        if self.built and tab == self.tab:
            self.data_reloaded()
        method = {"uygulamalar": "list_startup_items", "gorevler": "list_logon_tasks",
                  "servisler": "list_services"}[tab]
        system = self.c.engine.system

        def done(rows):
            self.data[tab] = rows
            if tab == self.tab:
                self.data_reloaded()

        def failed(_exc):
            self.data[tab] = "hata"
            if tab == self.tab:
                self.data_reloaded()

        self.app.worker.run(getattr(system, method), done, failed, serial=False)

    def _content(self):
        rows = self.data.get(self.tab)
        if rows is None:
            self.body.addWidget(w.label(t("ui.okunuyor_bekle"), muted=True))
            return
        if rows == "hata":
            self.body.addWidget(w.label(t("ui.liste_okunamadi"), muted=True))
            return
        {"uygulamalar": self._apps, "gorevler": self._tasks, "servisler": self._services}[self.tab](rows)

    # ------------------------------------------------------------------ uygulamalar ve görevler
    def _apps(self, rows):
        self.body.addWidget(w.label(t("ui.baslangic_uygulama_aciklama", acik=sum(r["etkin"] for r in rows),
                                      toplam=len(rows)), muted=True))
        for item in sorted(rows, key=lambda r: (not r["etkin"], r["ad"].lower())):
            step = {"tur": "yerlesik", "eylem": "baslangic_onayi", "parametreler": dict(item["onay"])}
            self.body.addWidget(self._toggle_row(item, t(f"ui.baslangic_konum.{item['konum']}"), step,
                                                 lambda on: on, item["etkin"]))
        if not rows:
            self.body.addWidget(w.label(t("ui.liste_bos"), muted=True))

    def _tasks(self, rows):
        self.body.addWidget(w.label(t("ui.baslangic_gorev_aciklama"), muted=True))
        for item in sorted(rows, key=lambda r: (not r["etkin"], r["ad"].lower())):
            step = {"tur": "yerlesik", "eylem": "zamanlanmis_gorev", "parametreler": {"yol": item["yol"], "ad": item["ad"]}}
            self.body.addWidget(self._toggle_row(item, item["yol"], step,
                                                 lambda on: "Enabled" if on else "Disabled", item["etkin"]))
        if not rows:
            self.body.addWidget(w.label(t("ui.liste_bos"), muted=True))

    def _toggle_row(self, item, where, step, to_value, enabled):
        card = w.Card(layout="h", spacing=10)
        text = QWidget()
        text_lay = QVBoxLayout(text)
        text_lay.setContentsMargins(0, 0, 0, 0)
        text_lay.setSpacing(2)
        name = QLabel(item["ad"])
        name.setObjectName("CardTitle")
        text_lay.addWidget(name)
        command = w.label(item.get("komut") or "", muted=True, size=12, wrap=False)
        command.setToolTip(item.get("komut") or "")
        # Uzun komut satırı kartı genişletmesin (sağdaki düğme hep görünsün).
        command.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        name.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        text_lay.addWidget(command)
        card.lay.addWidget(text, 1)
        card.lay.addWidget(w.badge(where, "notr"))
        if self.c.engine.store.has(item["id"]):
            card.lay.addWidget(w.badge(t("ui.degistirildi"), "bilgi"))
        card.lay.addWidget(w.label(t("ui.baslangicta_acilsin"), muted=True, size=12, wrap=False))
        switch = w.ToggleSwitch()
        switch.setChecked(enabled)
        switch.setEnabled(self.c.can_modify)

        def clicked():
            desired = switch.isChecked()
            switch.setChecked(not desired)
            if self.c.engine.store.has(item["id"]) and desired == self._original(item["id"], enabled):
                self.app.revert(item["id"], self._reload)  # ilk hâline dönüyorsa yedekten geri al
                return
            name_text = t("ui.baslangic_degisiklik", ad=item["ad"])
            self.app.apply_custom(item["id"], name_text, [step], [to_value(desired)], self._reload, restart="bilgisayar")

        switch.clicked.connect(clicked)
        card.lay.addWidget(switch)
        return card

    def _original(self, change_id, current):
        """Yedekteki ilk durum (etkin miydi?)."""
        entry = self.c.engine.store.get(change_id) or {}
        for e in entry.get("adimlar", []):
            snap = e.get("anlik")
            if snap is not None:
                value = snap.get("deger")
                return value if isinstance(value, bool) else value == "Enabled"
        return current

    def _reload(self):
        self._load(self.tab)

    # ------------------------------------------------------------------ servisler
    def _services(self, rows):
        self.body.addWidget(w.label(t("ui.servis_aciklama"), muted=True))
        search = QLineEdit(self.filter_text)
        search.setPlaceholderText(t("ui.servis_ara"))
        search.setFixedWidth(280)
        search.returnPressed.connect(lambda: self._filter(search.text()))
        check = QCheckBox(t("ui.windows_servislerini_goster"))
        check.setChecked(self.show_windows or self.fps_only)
        check.setEnabled(not self.fps_only)
        check.toggled.connect(self._toggle_windows)
        self.body.addWidget(w.hbox(search, w.button(t("ui.ara"), lambda: self._filter(search.text())), check, None))
        start = QComboBox()
        for key in START_FILTERS:
            start.addItem(t(f"ui.servis_filtre.{key}"), key)
        start.setCurrentIndex(start.findData(self.start_filter))
        start.currentIndexChanged.connect(lambda _i: self._set_filter("start_filter", start.currentData()))
        fps = QCheckBox(t("ui.servis_fps"))
        fps.setChecked(self.fps_only)
        fps.toggled.connect(lambda on: self._set_filter("fps_only", on))
        self.body.addWidget(w.hbox(start, fps, None))
        entries = fps_services()
        if self.fps_only:
            self.body.addWidget(w.label(t("ui.servis_fps_aciklama"), muted=True, size=12))
        needle = self.filter_text.lower()
        kinds = START_FILTERS[self.start_filter]
        shown = [r for r in rows
                 if (self.show_windows or self.fps_only or not r["windows"])
                 and (not needle or needle in r["ad"].lower() or needle in r["servis"].lower())
                 and (kinds is None or r["baslangic"] in kinds)
                 and (not self.fps_only or fps_entry(r["servis"], entries))]
        for row in sorted(shown, key=lambda r: r["ad"].lower()):
            self.body.addWidget(self._service_row(row, fps_entry(row["servis"], entries) if self.fps_only else None))
        if not shown:
            self.body.addWidget(w.label(t("ui.liste_bos"), muted=True))

    def _set_filter(self, name, value):
        setattr(self, name, value)
        from PySide6.QtCore import QTimer  # noqa: WPS433
        QTimer.singleShot(0, self.data_reloaded)  # sinyal içinden widget silinmesin

    def _filter(self, text):
        self.filter_text = text.strip()
        self.data_reloaded()

    def _toggle_windows(self, on):
        self.show_windows = on
        from PySide6.QtCore import QTimer  # noqa: WPS433
        QTimer.singleShot(0, self.data_reloaded)  # sinyal içinden widget silinmesin

    def _service_row(self, row, fps=None):
        return service_card(self.app, row, fps, self._reload)

    def _apply_service(self, row, kind):
        apply_service(self.app, row, kind, self._reload)
