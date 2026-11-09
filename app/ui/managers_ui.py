"""Kategori sayfalarındaki "yönetici" kartları: listeyi uygulama kendisi okur ve değiştirir.

- MonitorsCard: her monitör için çözünürlük + Hz, ölçek, ölçekleme modu; çoklu ekran şeması, yön ve konum (DISP-001 kartı).
- DeviceListCard: MSI modu (GPU-018) ve aygıt güç yönetimi (PWR-005) aygıt listeleri.
- NvidiaSettingCard / AmdSettingCard: NVIDIA (NVAPI) ve AMD (ADLX) sürücü ayarları; kartta yöntem yazar.
- DriverToolsCard: DDU / NVCleanstall'ı tools klasöründen açar, Güvenli Modda yeniden başlatır (GPU-019).
- AudioDevicesCard: ses cihazları.
- UacCard / DefenderCard: UAC seviyesi ve Defender gerçek zamanlı koruması (Sistem menüsü).

"baslangic" ve "oyunlar" yöneticili ayarlar kategori sayfalarında gösterilmez; kendi
menülerinde yapılır (controller.OWN_PAGE). Eski yerinde "taşındı" kartı bırakılmaz.

Her değişiklik motorun `apply_custom` yolundan geçer: yedek, Değişiklikler kaydı ve
"Eski haline getir".
"""

import hashlib

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QSizePolicy, QSpinBox, QVBoxLayout, QWidget

from app.core.i18n import fmt_percent, t, value_label
from app.engine import defender, driver_tools, managers, uac, windows_update
from app.ui import dialogs, theme, widgets as w


def _title_row(app, tweak, *extra):
    from app.ui.page_category import card_header  # noqa: WPS433 - döngüsel içe aktarmayı önler
    return card_header(app, tweak, *extra)


def snap_layout(size, others, x, y, threshold):
    """Sürüklenen ekranın (genişlik, yükseklik) bırakıldığı (x, y) konumunu Windows'taki gibi düzeltir: ekran başka bir
    ekrana kenarından bitişik olur (üst üste binmez, aralık kalmaz) ve kenarları yakınsa hizalanır. `others`: (x, y, w, h)."""
    width, height = size

    def overlaps(px, py):
        return any(px < ox + ow and ox < px + width and py < oy + oh and oy < py + height for ox, oy, ow, oh in others)

    def snapped(value, targets):
        best = min(targets, key=lambda v: abs(v - value))
        return best if abs(best - value) <= threshold else value

    candidates = []
    for ox, oy, ow, oh in others:
        y_fit = snapped(min(max(y, oy - height + 1), oy + oh - 1), [oy, oy + oh - height])
        x_fit = snapped(min(max(x, ox - width + 1), ox + ow - 1), [ox, ox + ow - width])
        candidates += [(ox + ow, y_fit), (ox - width, y_fit), (x_fit, oy + oh), (x_fit, oy - height)]
    if not candidates:
        return x, y
    pool = [c for c in candidates if not overlaps(*c)] or candidates
    return min(pool, key=lambda c: (c[0] - x) ** 2 + (c[1] - y) ** 2)


class LayoutMap(QWidget):
    """Ekranların masaüstündeki yerleşim şeması. Bir ekrana tıklayınca seçilir (`on_select(aygit)`); birincil olmayan
    ekran sürüklenip bırakılınca yeni konum `on_move(aygit, x, y)` ile bildirilir (Windows'taki gibi kenara oturur)."""

    DRAG_PIXELS = 5

    def __init__(self, items, selected, on_select, on_move=None):
        super().__init__()
        self.items, self.selected, self.on_select, self.on_move = items, selected, on_select, on_move
        self._press = None   # (aygit, tıklama noktası, ekranın sol-üstüne uzaklık)
        self._drag = None    # (aygit, sürüklenen QRectF)
        self.setMinimumHeight(240)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setCursor(Qt.PointingHandCursor)

    PAD = 10

    def _span(self):
        """Çizilen masaüstü alanı: ekranların çevresinde, bir ekranı öteki yanlara taşıyabilmek için boşluk bırakılır."""
        mx = max(i["genislik"] for i in self.items) * 0.4
        my = max(i["yukseklik"] for i in self.items) * 0.4
        return (min(i["x"] for i in self.items) - mx, min(i["y"] for i in self.items) - my,
                max(i["x"] + i["genislik"] for i in self.items) + mx, max(i["y"] + i["yukseklik"] for i in self.items) + my)

    def _scale(self):
        left, top, right, bottom = self._span()
        return min((self.width() - 2 * self.PAD) / max(right - left, 1), (self.height() - 2 * self.PAD) / max(bottom - top, 1))

    def _rects(self):
        """(aygit, QRectF, sıra) listesi: sanal masaüstü pencereye sığacak biçimde ölçeklenir."""
        left, top, _r, _b = self._span()
        scale = self._scale()
        return [(i["aygit"], QRectF(self.PAD + (i["x"] - left) * scale, self.PAD + (i["y"] - top) * scale,
                                    i["genislik"] * scale, i["yukseklik"] * scale), n)
                for n, i in enumerate(self.items, 1)]

    def _movable(self, device):
        item = next(i for i in self.items if i["aygit"] == device)
        return self.on_move is not None and not item.get("birincil") and len(self.items) > 1

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        palette = self.palette()
        for device, rect, number in self._rects():
            dragging = self._drag is not None and self._drag[0] == device
            if dragging:
                rect = self._drag[1]
            chosen = device == self.selected or dragging
            painter.setPen(QPen(palette.highlight().color() if chosen else palette.mid().color(), 3 if chosen else 1))
            fill = QColor(palette.highlight().color())
            fill.setAlpha(110 if dragging else 70 if chosen else 20)
            painter.setBrush(fill)
            painter.drawRoundedRect(rect, 4, 4)
            painter.setPen(palette.text().color())
            painter.drawText(rect, Qt.AlignCenter, str(number))

    def mousePressEvent(self, event):
        for device, rect, _n in self._rects():
            if rect.contains(event.position()):
                self._press = (device, event.position(), event.position() - rect.topLeft())
                return

    def mouseMoveEvent(self, event):
        if self._press is None:
            return
        device, start, offset = self._press
        if self._drag is None and (event.position() - start).manhattanLength() < self.DRAG_PIXELS:
            return
        if self._movable(device):
            rect = next(r for d, r, _n in self._rects() if d == device)
            self._drag = (device, QRectF(event.position() - offset, rect.size()))
            self.update()

    def mouseReleaseEvent(self, _event):
        press, drag, self._press, self._drag = self._press, self._drag, None, None
        if press is None:
            return
        device = press[0]
        if drag is None:
            self.on_select(device)
            return
        left, top, _r, _b = self._span()
        scale = self._scale()
        moving = next(i for i in self.items if i["aygit"] == device)
        x = left + (drag[1].x() - self.PAD) / scale
        y = top + (drag[1].y() - self.PAD) / scale
        others = [(i["x"], i["y"], i["genislik"], i["yukseklik"]) for i in self.items if i["aygit"] != device]
        threshold = 0.1 * max(moving["genislik"], moving["yukseklik"])
        new_x, new_y = snap_layout((moving["genislik"], moving["yukseklik"]), others, x, y, threshold)
        self.update()
        self.on_move(device, round(new_x), round(new_y))


def tool_check_text(check):
    """Çalıştırılacak üçüncü parti aracın SHA-256 / imza özeti ve varsa uyarıları (yönetici olarak çalışacak)."""
    parts = [] if check["imza_gecerli"] else [t("ui.surucu_arac.imza_yok")]
    if driver_tools.tools_in_user_folder():
        parts.append(t("ui.surucu_arac.klasor_uyari"))
    parts.append(t("ui.surucu_arac.ozet", sha=check["sha256"], imzalayan=check["imzalayan"] or "—"))
    return "\n\n".join(parts)


class MonitorsCard(w.Card):
    """Her monitör için çözünürlük + yenileme hızı ve Windows ölçeği.

    Her değişiklik motorun `apply_custom` yolundan geçer (yedek, Değişiklikler kaydı, "Eski haline
    getir"). Ekran modu değişince Windows'taki gibi geri sayımlı onay sorulur; onaylanmazsa
    yalnızca bu değişiklikten önceki değere dönülür.

    Ölçekleme modu (ölçeklemeyi GPU mu monitör mü yapıyor) ekranı süren kartın sürücüsüyle okunur ve
    yazılır: NVIDIA'da NVAPI (NvAPI_DISP_SetDisplayConfig), AMD'de ADLX (GPU ölçekleme + ölçekleme modu).
    Windows'un SetDisplayConfig yolu bu bilgisayarda modu değiştirmedi (docs/EKRAN.md).
    """

    KINDS = (("mod", "ekran_modu", "ui.mon.degisiklik_mod"), ("olcek", "ekran_olcek", "ui.mon.degisiklik_olcek"),
             ("olcekleme", "ekran_olcekleme", "ui.mon.degisiklik_olcekleme"),
             ("yon", "ekran_yon", "ui.mon.degisiklik_yon"), ("konum", "ekran_konum", "ui.mon.degisiklik_konum"))
    # Sürücüye göre seçenekler, listede görünen sırayla (önce monitör, sonra GPU ölçeklemesi).
    SCALING_OPTIONS = {"nvidia": (6, 1, 7, 5, 2, 3, 8), "amd": (0, 1, 2, 3)}
    SCALING_METHOD = {"nvidia": "NVAPI", "amd": "ADLX"}
    CONFIRM_SECONDS = 15

    def __init__(self, app, tweak):
        super().__init__(spacing=10)
        self.app, self.c, self.tweak = app, app.c, tweak
        head = QLabel(t("ui.mon.baslik"))
        head.setObjectName("CardTitle")
        self.lay.addWidget(w.hbox(w.IconTile(theme.ICONS["DISP"], theme.category_color("DISP")), (head, 1),
                                  w.info_button(lambda: dialogs.InfoDialog(app, tweak).exec()), spacing=12))
        self.lay.addWidget(w.label(t("ui.mon.aciklama"), muted=True, size=12))
        self.rows = QWidget()
        self.rows_lay = QVBoxLayout(self.rows)
        self.rows_lay.setContentsMargins(0, 0, 0, 0)
        self.rows_lay.setSpacing(14)
        self.lay.addWidget(self.rows)
        self.monitors = None      # son okunan liste; çizim bundan yapılır
        self._reading = False
        self._after_read = []     # okuma bitince çalışacaklar (üst üste istekler tek okumada birleşir)
        self._read_again = False
        self.refresh()

    # ------------------------------------------------------------------ okuma
    def _read_monitors(self):
        try:
            return self.c.engine.system.list_monitors()
        except Exception:
            return []

    def reload(self, then=None):
        """Sürücü okuması (NVAPI/ADLX/EDID) ana iş parçacığında YAPILMAZ: hibrit GPU'lu laptopta ağır bir ayardan sonra
        sürücü meşgulken saniyeler sürüp pencereyi "yanıt vermiyor"a düşürüyordu. Değişiklik sırasında (serial) okunur ki
        bir ekran değişikliğiyle aynı anda sürücüye gidilmesin."""
        if then is not None:
            self._after_read.append(then)
        if self._reading:
            self._read_again = True
            return
        self._reading = True
        self.app.worker.run(self._read_monitors, self._read_done, lambda _e: self._read_done([]))

    def _read_done(self, monitors):
        self._reading = False
        if self._read_again:
            self._read_again = False
            self.reload()
            return
        self.monitors = monitors
        try:
            self._draw()
        except RuntimeError:  # kart bu arada kapatıldı
            return
        callbacks, self._after_read = self._after_read, []
        for callback in callbacks:
            callback(monitors)

    @staticmethod
    def change_id(monitor, kind):
        """Monitöre özgü, kalıcı değişiklik kimliği (ekran numarası değişse de aynı kalır)."""
        digest = hashlib.sha1((monitor.get("monitor_yolu") or monitor["aygit"]).lower().encode("utf-8")).hexdigest()
        return f"EKRAN-{digest[:8]}-{kind}"

    @staticmethod
    def step(monitor, action):
        return {"tur": "yerlesik", "eylem": action,
                "parametreler": {"aygit": monitor["aygit"], "monitor": monitor.get("monitor_yolu") or ""}}

    # ------------------------------------------------------------------ çizim
    def refresh(self):
        """Eldeki listeyi hemen çizer, güncelini arka planda okur."""
        self._draw()
        self.reload()

    def _draw(self):
        w.clear_layout(self.rows_lay)
        monitors = self.monitors
        if monitors is None:
            self.rows_lay.addWidget(w.label(t("ui.okunuyor_bekle"), muted=True))
            return
        if not monitors:
            self.rows_lay.addWidget(w.label(t("ui.ekran_okunamadi"), muted=True))
            return
        if any(m.get("yerlesim") for m in monitors):
            self.rows_lay.addWidget(self._layout_box(monitors))
        for monitor in monitors:
            self.rows_lay.addWidget(self._monitor_box(monitor))

    def _layout_box(self, monitors):
        """Şema + seçili ekranın yön/konum ayarı."""
        placed = [m for m in monitors if m.get("yerlesim")]
        if getattr(self, "selected", None) not in {m["aygit"] for m in placed}:
            self.selected = next((m["aygit"] for m in placed if m.get("birincil")), placed[0]["aygit"])
        monitor = next(m for m in placed if m["aygit"] == self.selected)
        layout = monitor["yerlesim"]
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        title = QLabel(t("ui.mon.yerlesim_baslik"))
        title.setObjectName("CardTitle")
        lay.addWidget(title)
        lay.addWidget(w.label(t("ui.mon.yerlesim_not"), muted=True, size=12))
        items = [dict(m["yerlesim"], aygit=m["aygit"], birincil=m.get("birincil")) for m in placed]
        lay.addWidget(LayoutMap(items, self.selected, self._select, self._moved if self.c.can_modify else None))
        lay.addWidget(w.label(t("ui.mon.secili", ad=f"{placed.index(monitor) + 1} · {monitor['ad']}"), bold=True))
        orientation = QComboBox()
        for name in ("yatay", "dikey", "yatay_ters", "dikey_ters"):
            orientation.addItem(t(f"ui.yon.{name}"), name)
        orientation.setCurrentIndex(max(0, orientation.findData(layout["yon"])))
        orientation.setMinimumWidth(170)
        orientation.setEnabled(self.c.can_modify)
        lay.addWidget(w.hbox(self._caption("ui.mon.yon"), orientation, None,
                             self._apply_button(lambda: self._change(monitor, "yon", orientation.currentData()))))
        if not monitor.get("birincil") and len(placed) > 1:
            spins = []
            for value in (layout["x"], layout["y"]):
                spin = QSpinBox()
                spin.setRange(-100000, 100000)
                spin.setValue(value)
                spin.setEnabled(self.c.can_modify)
                spins.append(spin)
            lay.addWidget(w.hbox(self._caption("ui.mon.konum"), *spins, None, self._apply_button(
                lambda: self._change(monitor, "konum", f"{spins[0].value()},{spins[1].value()}"))))
        return box

    def _select(self, device):
        self.selected = device
        self._draw()

    def _moved(self, device, x, y):
        """Şemada sürüklenen ekran: seçilir, yeni konum onay sorusuyla uygulanır (eski konuma dönülebilir)."""
        self.selected = device
        monitor = next(m for m in self.monitors or () if m["aygit"] == device)
        self._draw()
        self._change(monitor, "konum", f"{x},{y}")

    def _monitor_box(self, monitor):
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        name = QLabel(monitor["ad"])
        name.setObjectName("CardTitle")
        badges = [w.badge(t("ui.birincil_ekran"), "bilgi")] if monitor.get("birincil") else []
        lay.addWidget(w.hbox(name, *badges, None))
        lay.addWidget(w.label(t("ui.mon.baglanti", baglanti=value_label("deger.baglanti", monitor.get("baglanti")),
                                gpu=monitor.get("gpu") or "—"), muted=True, size=12))
        lay.addWidget(self._mode_row(monitor))
        if monitor.get("olcek"):
            lay.addWidget(self._scale_row(monitor))
        if monitor.get("surucu_olcekleme"):
            lay.addWidget(self._scaling_row(monitor))
        changed = [kind for kind, _a, _n in self.KINDS if self.c.engine.store.has(self.change_id(monitor, kind))]
        if changed:
            buttons = [w.badge(t("ui.degistirildi"), "bilgi")]
            if self.c.can_modify:
                buttons.append(w.button(t("ui.eski_haline"), lambda _=False, m=monitor, k=changed: self._revert(m, k)))
            lay.addWidget(w.hbox(*buttons, None))
        return box

    def _caption(self, key):
        caption = w.label(t(key), wrap=False)
        caption.setMinimumWidth(200)
        return caption

    def _apply_button(self, handler):
        button = w.button(t("ui.uygula"), handler, primary=True)
        button.setEnabled(self.c.can_modify)
        return button

    def _mode_row(self, monitor):
        modes = monitor["mod"]["modlar"]
        native = next(iter(modes), None)  # en büyük çözünürlük genelde yerel çözünürlüktür
        resolution = QComboBox()
        for res in modes:
            resolution.addItem(res + (f" ({t('ui.mon.yerel')})" if res == native else ""), res)
        resolution.setCurrentIndex(max(0, resolution.findData(monitor["mod"]["cozunurluk"])))
        refresh = QComboBox()

        def fill_rates():
            refresh.clear()
            rates = modes.get(resolution.currentData(), [])
            for hz in rates:
                refresh.addItem(f"{hz} Hz" + (f" ({t('ui.en_yuksek')})" if hz == rates[0] else ""), hz)
            wanted = monitor["mod"]["hz"] if resolution.currentData() == monitor["mod"]["cozunurluk"] else rates[0]
            refresh.setCurrentIndex(max(0, refresh.findData(wanted)))

        fill_rates()
        resolution.currentIndexChanged.connect(lambda _i: fill_rates())
        for combo in (resolution, refresh):
            combo.setMinimumWidth(170)
            combo.setEnabled(self.c.can_modify)
        apply = self._apply_button(lambda: self._change(monitor, "mod",
                                                        f"{resolution.currentData()}@{refresh.currentData()}"))
        return w.hbox(self._caption("ui.mon.cozunurluk"), resolution, refresh, None, apply)

    def _scale_row(self, monitor):
        scale = monitor["olcek"]
        combo = QComboBox()
        for pct in scale["secenekler"]:
            combo.addItem(fmt_percent(pct) + (f" ({t('ui.mon.onerilen')})" if pct == scale["onerilen"] else ""),
                          pct)
        combo.setCurrentIndex(max(0, combo.findData(scale["yuzde"])))
        combo.setMinimumWidth(170)
        combo.setEnabled(self.c.can_modify)
        apply = self._apply_button(lambda: self._change(monitor, "olcek", str(combo.currentData())))
        return w.hbox(self._caption("ui.mon.olcek"), combo, None, apply)

    def _scaling_row(self, monitor):
        info = monitor["surucu_olcekleme"]
        driver = info["surucu"]
        combo = QComboBox()
        for number in self.SCALING_OPTIONS[driver]:
            combo.addItem(t(f"ui.olc.{driver}.{number}"), f"{driver}:{number}")
        if combo.findData(info["deger"]) < 0:  # sürücünün başka bir değeri (ör. özel)
            combo.addItem(t("ui.olc.diger", deger=info["deger"].partition(":")[2]), info["deger"])
        combo.setCurrentIndex(combo.findData(info["deger"]))
        combo.setMinimumWidth(260)
        combo.setEnabled(self.c.can_modify)
        apply = self._apply_button(lambda: self._change(monitor, "olcekleme", combo.currentData()))
        return w.hbox(self._caption("ui.mon.olcekleme"), combo,
                      w.badge(t("ui.yontem", ad=self.SCALING_METHOD[driver]), "bilgi"), None, apply)

    # ------------------------------------------------------------------ değişiklik
    def _current(self, monitor, kind):
        if kind == "mod":
            return f"{monitor['mod']['cozunurluk']}@{monitor['mod']['hz']}"
        if kind == "olcekleme":
            return (monitor.get("surucu_olcekleme") or {}).get("deger")
        if kind == "yon":
            return monitor["yerlesim"]["yon"]
        if kind == "konum":
            return f"{monitor['yerlesim']['x']},{monitor['yerlesim']['y']}"
        return str(monitor["olcek"]["yuzde"])

    def _change(self, monitor, kind, value, confirm=True):
        previous = self._current(monitor, kind)
        if value in (None, "", previous) or value.startswith("None"):
            return
        action, name_key = next((a, n) for k, a, n in self.KINDS if k == kind)
        change_id = self.change_id(monitor, kind)
        step = self.step(monitor, action)

        def check(monitors):
            if not confirm or kind == "olcek":
                return
            now = next((m for m in monitors if m["aygit"] == monitor["aygit"]), None)
            if now is None or self._current(now, kind) != value:
                return  # değişmedi (hata durum satırında gösterildi)
            if not dialogs.ask_keep_display(self.app, self.CONFIRM_SECONDS):
                self.app.set_status(t("ui.mon.geri_donuldu"), "bilgi")
                self._change(now, kind, previous, confirm=False)

        def done():
            self.reload(check)

        self.app.apply_custom(change_id, t(name_key, ad=monitor["ad"]), [step], [value], done, related=self.tweak["id"])

    def _revert(self, monitor, kinds):
        ids = [self.change_id(monitor, k) for k in kinds]

        def next_one():
            if ids:
                self.app.revert(ids.pop(0), next_one)
            else:
                self.refresh()
        next_one()


class DeviceListCard(w.Card):
    """Aygıt listesi; her aygıt ayrı yedeklenir ve geri alınır."""

    KINDS = {
        # tür: (listeleme metodu, sütun başlığı anahtarı, ilgili ayar)
        "msi": ("list_pci_devices", "ui.msi_sutun", "GPU-018"),
        "cihaz_guc": ("list_power_managed_devices", "ui.cihaz_guc_sutun", "PWR-005"),
        "ses_aygit": ("list_audio_pnp_devices", "ui.ses_aygit_sutun", "AUD-006"),
        "ses_hfp": ("list_audio_pnp_devices", "ui.ses_aygit_sutun", "AUD-009"),
    }

    # Varsayılan olarak gösterilen aygıt sınıfları (köprüler, sistem aygıtları "tümü"nde)
    MAIN_CLASSES = {
        "msi": ("Display", "Net", "SCSIAdapter", "HDC", "USB", "MEDIA", "AudioEndpoint"),
        "cihaz_guc": ("USB", "Net", "HIDClass", "Bluetooth"),
        "ses_aygit": ("AudioEndpoint",),
        "ses_hfp": ("Bluetooth",),
    }

    def __init__(self, app, tweak):
        super().__init__()
        self.app, self.c, self.tweak = app, app.c, tweak
        self.kind = tweak["liste_yoneticisi"]
        self.devices = None
        self.toggle_button = w.button(t("ui.aygitlari_goster"), self._toggle_list)
        self.lay.addWidget(_title_row(app, tweak, self.toggle_button))
        badges = [w.impact_badge(tweak["performans_etkisi"]["seviye"])]
        if tweak["risk"] != "güvenli":
            badges.append(w.risk_badge(tweak["risk"]))
        self.lay.addWidget(w.hbox(*badges, None))
        if self.kind == "msi":
            self.lay.addWidget(w.colored(t("ui.msi_guvenli_mod"), "uyari"))
        self.body = None
        self.show_all = False

    def _toggle_list(self):
        if self.body is not None:
            self.body.deleteLater()
            self.body = None
            self.toggle_button.setText(t("ui.aygitlari_goster"))
            return
        self.toggle_button.setText(t("ui.gizle"))
        self.body = QWidget()
        self.body_lay = QVBoxLayout(self.body)
        self.body_lay.setContentsMargins(0, 4, 0, 0)
        self.lay.addWidget(self.body)
        self._load()

    def _load(self):
        if self.body is None:
            return
        w.clear_layout(self.body_lay)
        self.body_lay.addWidget(w.label(t("ui.okunuyor_bekle"), muted=True))
        method = getattr(self.c.engine.system, self.KINDS[self.kind][0])
        self.app.worker.run(method, self._show, lambda _e: self._failed(), serial=False)

    def _failed(self):
        if self.body is not None:
            w.clear_layout(self.body_lay)
            self.body_lay.addWidget(w.label(t("ui.liste_okunamadi"), muted=True))

    def _show(self, devices):
        self.devices = devices
        if self.body is None:
            return
        w.clear_layout(self.body_lay)
        rows = devices
        if not self.show_all:
            rows = [d for d in devices if d["sinif"] in self.MAIN_CLASSES[self.kind]]
        if not rows:
            self.body_lay.addWidget(w.label(t("ui.aygit_yok"), muted=True))
        header = w.label(t(self.KINDS[self.kind][1]), muted=True, size=12, wrap=False)
        self.body_lay.addWidget(w.hbox(None, header))
        for device in sorted(rows, key=lambda d: (d["sinif"], d["ad"].lower())):
            self.body_lay.addWidget(self._row(device))
        if len(rows) != len(devices):
            self.body_lay.addWidget(w.hbox(w.button(t("ui.tum_aygitlar", adet=len(devices)), self._all), None))

    def _all(self):
        self.show_all = True
        self._show(self.devices or [])

    def _row(self, device):
        changed = self.c.engine.store.has(device["id"])
        name = w.label(device["ad"], wrap=False)
        name.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        parts = [(name, 1), w.badge(device["sinif"] or "?", "notr")]
        if changed:
            parts.append(w.badge(t("ui.degistirildi"), "bilgi"))
        switch = w.ToggleSwitch()
        if self.kind == "msi":
            state = {True: t("ui.msi_acik"), False: t("ui.msi_kapali"), None: t("ui.msi_varsayilan")}[device["msi"]]
            parts.append(w.label(state, muted=True, wrap=False))
            switch.setChecked(bool(device["msi"]))
        elif self.kind in ("ses_aygit", "ses_hfp"):
            switch.setChecked(device["etkin"])  # açık = aygıt kullanılıyor
        else:
            switch.setChecked(not device["etkin"])  # açık = güç tasarrufu için kapatılmaz
        switch.setEnabled(self.c.can_modify)
        switch.clicked.connect(lambda _=False, d=device, sw=switch: self._toggle(d, sw))
        parts.append(switch)
        return w.hbox(*parts)

    def _toggle(self, device, switch):
        desired = switch.isChecked()
        switch.setChecked(not desired)  # gerçek durum okunana kadar eski görünüm
        change_id = device["id"]
        store = self.c.engine.store
        if self.kind in ("ses_aygit", "ses_hfp"):
            if desired and store.has(change_id):  # yeniden açmak = uygulamanın değişikliğini geri almak
                self.app.revert(change_id, self._load)
                return
            if not desired and not dialogs.ask_yes_no(self.app, t("ui.dikkat"), t("ui.ses_aygit_onay", ad=device["ad"])):
                return
            step = {"tur": "yerlesik", "eylem": "aygit_etkin", "parametreler": {"ornek": device["ornek"]}}
            self.app.apply_custom(change_id, t("ui.ses_aygit_degisiklik", ad=device["ad"]), [step], [desired],
                                  self._load, related=self.KINDS[self.kind][2])
            return
        if not desired and store.has(change_id):
            self.app.revert(change_id, self._load)
            return
        if self.kind == "msi":
            tweak = self.c.by_id["GPU-018"]
            if not dialogs.confirm_risky(self.app, tweak, None, desired):
                return
            step = {"tur": "registry", "kok": "HKLM", "yol": managers.msi_key(device["ornek"]), "ad": "MSISupported",
                    "veri_turu": "REG_DWORD", "acik": 1, "kapali": 0, "yoksa": None}
            self.app.apply_custom(change_id, t("ui.msi_degisiklik", ad=device["ad"]), [step], [1 if desired else 0],
                                  self._load, level=2, restart="bilgisayar", related="GPU-018")
        else:
            step = {"tur": "yerlesik", "eylem": "cihaz_guc", "parametreler": {"ornek": device["ornek"]}}
            self.app.apply_custom(change_id, t("ui.cihaz_guc_degisiklik", ad=device["ad"]), [step], [not desired],
                                  self._load, related="PWR-005")


EXCLUSIVE_KEY = "{b3f8fa53-0004-438e-9003-51a46e139bfc}"


def exclusive_steps(device):
    """Ses cihazının "Uygulamaların özel denetim almasına izin ver" (,3) ve "özel moda öncelik ver" (,4)
    değerleri. BELGELENMEMİŞ (topluluk tarafından bildirilen yerleşim); değer yoksa Windows izin verir."""
    path = rf"SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio\Render\{device}\Properties"
    return [{"tur": "registry", "kok": "HKLM", "yol": path, "ad": f"{EXCLUSIVE_KEY},{n}", "veri_turu": "REG_DWORD",
             "acik": 1, "kapali": 0, "yoksa": None} for n in (3, 4)]


def nvidia_card_name(scan):
    """Taramadaki NVIDIA ekran kartının adı (yoksa None)."""
    hw = ((scan or {}).get("bolumler") or {}).get("donanim") or {}
    return next((g["ad"] for g in hw.get("gpu") or [] if g.get("uretici") == "NVIDIA"), None)


# Sürücü ayarı -> etkisini gösteren süreç (A4). 0x90DE9159 bindirmenin oyuna EKLENMESİNİ engeller; NVIDIA app'in
# "NVIDIA Overlay.exe" süreçlerini kapatmaz. Uygulandı demek yerine süreçlerin gerçek durumu yazılır.
SETTING_PROCESS = {0x90DE9159: "nvidia overlay.exe"}


def _undo_badge():
    """Sürücü ayarı kartları: değişiklik yedeklenir, Değişiklikler'den / "Eski haline getir" ile geri döner."""
    badge = w.badge(t("ui.geri_alinabilir"), "notr")
    badge.setToolTip(t("ui.geri_alinabilir_ipucu"))
    return badge


def running_count(exe):
    try:
        from app.games.runtime import ProcessOps  # noqa: WPS433
        return sum(1 for _pid, name in ProcessOps().list_processes() if name == exe)
    except (AttributeError, OSError):
        return 0


class NvidiaSettingCard(w.Card):
    """NVIDIA Denetim Masası genel ayarı: NVAPI (DRS) ile okunur ve yazılır."""

    def __init__(self, app, tweak):
        super().__init__()
        self.app, self.c, self.tweak = app, app.c, tweak
        self.spec = tweak["nvidia"]
        self.setting_id = int(self.spec["ayar"], 16)
        self.lay.addWidget(_title_row(app, tweak))
        self.lay.addWidget(w.hbox(w.impact_badge(tweak["performans_etkisi"]["seviye"]), w.badge("NVIDIA", "iyi"),
                                  w.badge(t("ui.yontem", ad="NVAPI"), "bilgi"), _undo_badge(), None))
        target = nvidia_card_name(self.c.scan)
        if target:  # iki kartlı laptopta ayarın hangi karta uygulandığı açıkça yazılır
            self.lay.addWidget(w.label(t("ui.nvidia_hedef_kart", ad=target), size=12))
        for note in tweak.get("notlar") or []:
            self.lay.addWidget(w.label(note, muted=True, size=12))
        self.row = w.hbox()
        self.lay.addWidget(self.row)
        self.process_state = w.label("", size=12)
        self.process_state.setVisible(False)
        self.lay.addWidget(self.process_state)
        self.value = "okunuyor"
        self.refresh()

    def _show_process_state(self):
        """Ayar yasak durumdaysa ilgili süreçlerin şu anki durumu (her yeniden okumada tazelenir)."""
        exe = SETTING_PROCESS.get(self.setting_id)
        blocked = isinstance(self.value, dict) and self.value.get("ozel") and self.value.get("deger") == 1
        if not exe or not blocked:
            self.process_state.setVisible(False)
            return
        count = running_count(exe)
        self.process_state.setText(t("ui.nvidia_bindirme_suruyor", adet=count) if count
                                   else t("ui.nvidia_bindirme_kapali"))
        self.process_state.setProperty("fg", "uyari" if count else "iyi")
        w.repolish(self.process_state)
        self.process_state.setVisible(True)

    def set_value(self, info):
        """info: {'deger', 'ozel'} veya hata için None."""
        self.value = info
        self.refresh()

    def _option_label(self, value):
        for option in self.spec["secenekler"]:
            if option["deger"] == value:
                return option["etiket"]
        return None

    def refresh(self):
        lay = self.row.layout()
        w.clear_layout(lay)
        self._show_process_state()
        if self.value == "okunuyor":
            lay.addWidget(w.label(t("ui.okunuyor_bekle"), muted=True))
            return
        if self.value is None:
            lay.addWidget(w.label(t("ui.nvidia_okunamadi"), muted=True))
            if self.c.engine.system.npi_available() and self.c.can_modify:
                lay.addWidget(w.badge(t("ui.yontem", ad=t("ui.yontem_npi")), "uyari"))
                lay.addWidget(w.button(t("ui.npi_ile_uygula"), self._npi))
            return
        combo = QComboBox()
        for option in self.spec["secenekler"]:
            combo.addItem(option["etiket"], option["deger"])
        current = self.value["deger"] if self.value["ozel"] else None
        index = combo.findData(current)
        if index < 0 and current is not None:
            combo.addItem(t("ui.ozel_deger_nvidia", deger=current), current)
            index = combo.count() - 1
        if index < 0:  # özelleştirilmemiş: sürücü varsayılanı
            default = next((o["deger"] for o in self.spec["secenekler"] if o.get("varsayilan")), None)
            index = max(0, combo.findData(default))
        combo.setCurrentIndex(index)
        combo.setFixedWidth(280)
        combo.setEnabled(self.c.can_modify)
        self.combo = combo
        recommended = self._option_label(self.spec.get("onerilen"))
        parts = [combo]
        if recommended:
            parts.append(w.label(t("ui.onerilen", deger=recommended), muted=True, wrap=False))
        parts.append(None)
        if self.c.engine.store.has(self.tweak["id"]):
            parts.append(w.badge(t("ui.degistirildi"), "bilgi"))
            if self.c.can_modify:
                parts.append(w.button(t("ui.eski_haline"), lambda: self.app.revert(self.tweak["id"], self._reload)))
        apply = w.button(t("ui.uygula"), self._apply, primary=True)
        apply.setEnabled(self.c.can_modify)
        parts.append(apply)
        for part in parts:
            lay.addStretch(1) if part is None else lay.addWidget(part)

    def _apply(self):
        value = self.combo.currentData()
        current = self.value["deger"] if self.value["ozel"] else None
        if value == current:
            return
        step = {"tur": "yerlesik", "eylem": "nvidia_drs", "parametreler": {"ayar": self.spec["ayar"]}}
        self.app.apply_custom(self.tweak["id"], self.tweak["ad"], [step], [value], self._reload,
                              restart="uygulama", related=self.tweak["id"])

    def _npi(self):
        value = self.spec.get("onerilen")
        if value is None:
            return
        # imza denetimi (PowerShell) arayüzü dondurmasın: işçi iş parçacığında
        self.app.worker.run(self.c.engine.system.npi_check, lambda check: self._npi_ask(value, check),
                            lambda e: self.app.set_status(t("ui.surucu_arac.acilamadi", hata=e), "sorun"), serial=False)

    def _npi_ask(self, value, check):
        if check is None:
            return
        text = t("ui.npi_onay") + "\n\n" + tool_check_text(check)
        if not dialogs.ask_yes_no(self.app, t("ui.dikkat"), text):
            return
        self.app.run_npi(self.tweak, [(self.setting_id, value)], self._reload, sha256=check["sha256"])

    def _reload(self):
        for page in self.app.pages.values():  # kart Ekran Kartı veya Placebo sayfasında olabilir
            if hasattr(page, "load_nvidia") and self.tweak["id"] in getattr(page, "rows", {}):
                page.load_nvidia()


class AmdSettingCard(w.Card):
    """AMD Software'deki genel 3B ayarlar (Anti-Lag, Chill, Boost, Enhanced Sync): ADLX ile okunur ve yazılır.
    Değerler sayfa tarafından tek ADLX oturumunda, arka planda okunur (CategoryPage.load_amd)."""

    def __init__(self, app, tweak):
        super().__init__()
        self.app, self.c, self.tweak = app, app.c, tweak
        self.features = tweak["amd"]["ozellikler"]
        self.lay.addWidget(_title_row(app, tweak))
        self.lay.addWidget(w.hbox(w.impact_badge(tweak["performans_etkisi"]["seviye"]), w.badge("AMD", "iyi"),
                                  w.badge(t("ui.yontem", ad="ADLX"), "bilgi"), _undo_badge(), None))
        for note in tweak.get("notlar") or []:
            self.lay.addWidget(w.label(note, muted=True, size=12))
        self.rows = QWidget()
        self.rows_lay = QVBoxLayout(self.rows)
        self.rows_lay.setContentsMargins(0, 0, 0, 0)
        self.rows_lay.setSpacing(6)
        self.lay.addWidget(self.rows)
        self.values = "okunuyor"
        self.refresh()

    @staticmethod
    def change_id(gpu, feature):
        return managers.item_id("AMD", gpu, feature)

    def set_values(self, values):
        """values: {GPU adı: {özellik: {'destek', 'acik'}}} veya okunamadıysa None."""
        self.values = values
        self.refresh()

    def refresh(self):
        w.clear_layout(self.rows_lay)
        if self.values == "okunuyor":
            self.rows_lay.addWidget(w.label(t("ui.okunuyor_bekle"), muted=True))
            return
        if not self.values:
            self.rows_lay.addWidget(w.label(t("ui.amd_okunamadi"), muted=True))
            return
        many = len(self.values) > 1
        for gpu, features in self.values.items():
            if many:
                self.rows_lay.addWidget(w.label(gpu, size=12))
            for feature in self.features:
                self.rows_lay.addWidget(self._row(gpu, feature, features.get(feature)))

    def _row(self, gpu, feature, info):
        parts = [(w.label(t(f"ui.amd.ozellik.{feature}"), wrap=False), 1)]
        if not info or not info.get("destek"):
            parts.append(w.label(t("ui.amd_desteklenmiyor"), muted=True, wrap=False))
            return w.hbox(*parts)
        change_id = self.change_id(gpu, feature)
        if self.c.engine.store.has(change_id):
            parts.append(w.badge(t("ui.degistirildi"), "bilgi"))
        parts.append(w.label(t("ui.amd.durum.acik") if info["acik"] else t("ui.amd.durum.kapali"), muted=True, size=12, wrap=False))
        switch = w.ToggleSwitch()
        switch.setChecked(bool(info["acik"]))
        switch.setEnabled(self.c.can_modify)
        switch.clicked.connect(lambda _=False, g=gpu, f=feature, sw=switch: self._toggle(g, f, sw))
        parts.append(switch)
        return w.hbox(*parts)

    def _toggle(self, gpu, feature, switch):
        desired = switch.isChecked()
        switch.setChecked(not desired)  # sonuç okununca kart yeniden çizilir
        change_id = self.change_id(gpu, feature)
        if self.c.engine.store.has(change_id):  # uygulamanın değişikliğini geri almak = önceki hâl
            self.app.revert(change_id, self._reload)
            return
        step = {"tur": "yerlesik", "eylem": "amd_adlx", "parametreler": {"gpu": gpu, "ozellik": feature}}
        name = t("ui.amd.degisiklik", ozellik=t(f"ui.amd.ozellik.{feature}"), ad=gpu)
        self.app.apply_custom(change_id, name, [step], [desired], self._reload, restart="uygulama",
                              related=self.tweak["id"])

    def _reload(self):
        page = self.app.pages.get("GPU")
        if page is not None and hasattr(page, "load_amd"):
            page.load_amd()


class DriverToolsCard(w.Card):
    """GPU-019: resmi sürücü sayfası tarayıcıda açılır. DDU ve NVCleanstall tools klasöründen açılır (yoksa resmi indirme sayfası). DDU'nun önerdiği
    Güvenli Mod iki ayrı uyarıdan sonra açılır ve geri alınabilir (bcdedit safeboot)."""

    def __init__(self, app, tweak):
        super().__init__()
        self.app, self.c, self.tweak = app, app.c, tweak
        self.lay.addWidget(_title_row(app, tweak))
        for note in tweak.get("notlar") or []:
            self.lay.addWidget(w.label(note, muted=True, size=12))
        self.rows = QWidget()
        self.rows_lay = QVBoxLayout(self.rows)
        self.rows_lay.setContentsMargins(0, 0, 0, 0)
        self.rows_lay.setSpacing(8)
        self.lay.addWidget(self.rows)
        self.refresh()

    def refresh(self):
        w.clear_layout(self.rows_lay)
        hw = ((self.c.scan or {}).get("bolumler") or {}).get("donanim") or {}
        pages = driver_tools.driver_pages(hw.get("gpu") or [])
        for vendor, url in pages:
            self.rows_lay.addWidget(w.hbox((w.label(t("ui.surucu_sayfa.ad", uretici=vendor), wrap=False), 1),
                                           w.button(t("ui.surucu_sayfa.ac"), lambda _=False, u=url: self._open(u))))
        if pages and (hw.get("bilgisayar") or {}).get("tur") == "laptop":
            self.rows_lay.addWidget(w.label(t("ui.surucu_sayfa.dizustu"), muted=True, size=12))
        for tool in driver_tools.TOOLS:
            self.rows_lay.addWidget(self._tool_row(tool))
        self.rows_lay.addWidget(self._safe_mode_row())

    def _tool_row(self, tool):
        path = driver_tools.find(tool)
        name = w.label(t(f"ui.surucu_arac.{tool}"), wrap=False)
        if path is not None:
            state = w.label(t("ui.surucu_arac.bulundu", yol=path.name), muted=True, size=12, wrap=False)
            button = w.button(t("ui.surucu_arac.ac"), lambda _=False, p=path: self._open_tool(p))
            button.setEnabled(self.c.can_modify)  # araç sürücüyü değiştirir; önizlemede açılmaz
        else:
            state = w.label(t("ui.surucu_arac.yok", klasor=driver_tools.TOOLS[tool][0]), muted=True, size=12)
            button = w.button(t("ui.surucu_arac.indir"),
                              lambda _=False, u=driver_tools.download_page(tool): self._open(u))
        return w.hbox((name, 0), (state, 1), button)

    def _open_tool(self, path):
        """Aracı açmadan önce SHA-256 ve imza denetimi; imza geçerli değilse kullanıcıya sorulur."""
        self.app.worker.run(lambda: driver_tools.verify(str(path)), lambda check: self._tool_checked(path, check),
                            lambda e: self.app.set_status(t("ui.surucu_arac.acilamadi", hata=e), "sorun"), serial=False)

    def _tool_checked(self, path, check):
        text = tool_check_text(check)
        if not check["imza_gecerli"] or driver_tools.tools_in_user_folder():
            if not dialogs.ask_yes_no(self.app, t("ui.dikkat"), text):
                return
        else:
            self.app.set_status(text, "iyi")
        self._open(path)

    def _open(self, target):
        try:
            self.c.engine.system.open_path(target)
        except OSError as exc:
            self.app.set_status(t("ui.surucu_arac.acilamadi", hata=exc), "sorun")

    def _safe_mode_row(self):
        name = w.label(t("ui.guvenli.ad"), wrap=False)
        if self.c.engine.store.has(driver_tools.SAFE_MODE_ID):
            parts = [(name, 0), (w.colored(t("ui.guvenli.acik"), "uyari"), 1)]
            if self.c.can_modify:
                parts.append(w.button(t("ui.guvenli.normal"), self._normal_boot, primary=True))
            return w.hbox(*parts)
        button = w.button(t("ui.guvenli.yeniden_baslat"), self._safe_mode, warn=True)
        button.setEnabled(self.c.can_modify)
        return w.hbox((name, 0), (w.label(t("ui.guvenli.aciklama"), muted=True, size=12), 1), button)

    def _safe_mode(self):
        # İki ayrı uyarı: önce ne olacağı, sonra nasıl geri dönüleceği. İkisi de onaylanmazsa hiçbir şey yapılmaz.
        if not dialogs.ask_yes_no(self.app, t("ui.dikkat"), t("ui.guvenli.uyari1", sn=driver_tools.RESTART_SECONDS)):
            return
        if not dialogs.ask_yes_no(self.app, t("ui.guvenli.son_onay"), t("ui.guvenli.uyari2"),
                                  yes_text=t("ui.guvenli.evet")):
            return

        def done():
            self.refresh()
            self.app.update_banners()
            if not self.c.engine.store.has(driver_tools.SAFE_MODE_ID):
                return  # bcdedit yazılamadı; hata durum satırında
            try:
                self.c.engine.system.restart_computer(driver_tools.RESTART_SECONDS)
                self.app.set_status(t("ui.guvenli.baslatiliyor", sn=driver_tools.RESTART_SECONDS), "uyari")
            except Exception as exc:
                self.app.set_status(t("ui.guvenli.baslatilamadi", hata=exc), "sorun")

        self.app.apply_custom(driver_tools.SAFE_MODE_ID, t("ui.guvenli.ad"), [driver_tools.SAFE_MODE_STEP],
                              [driver_tools.SAFE_MODE_VALUE], done, level=1, restart="bilgisayar",
                              related=self.tweak["id"])

    def _normal_boot(self):
        def done():
            self.refresh()
            self.app.update_banners()
        self.app.revert(driver_tools.SAFE_MODE_ID, done)


class AudioDevicesCard(w.Card):
    """Ses çıkış cihazları: cihaz başına ses geliştirmeleri (AUD-001) veya varsayılan biçim (AUD-002)."""

    def __init__(self, app, tweak):
        super().__init__()
        self.app, self.c, self.tweak = app, app.c, tweak
        self.kind = tweak["liste_yoneticisi"]
        self.lay.addWidget(_title_row(app, tweak))
        self.lay.addWidget(w.hbox(w.impact_badge(tweak["performans_etkisi"]["seviye"]), None))
        for note in tweak.get("notlar") or []:
            self.lay.addWidget(w.label(note, muted=True, size=12))
        if self.kind == "ses_bicimi":
            # Uygulamadan yazma her cihazda çalışmayabilir (Windows reddedebilir); yedek yol hep görünür.
            self.lay.addWidget(w.hbox(w.label(t("ui.ses_bicimi_yedek"), muted=True, size=12), None,
                                      w.button(t("ui.ses_paneli_ac"),
                                               lambda: w.open_target({"tur": "denetim_masasi", "hedef": "mmsys.cpl"}))))
        self.body = QWidget()
        self.body_lay = QVBoxLayout(self.body)
        self.body_lay.setContentsMargins(0, 0, 0, 0)
        self.lay.addWidget(self.body)
        self.load()

    def _devices(self):
        tweak = self.c.by_id["AUD-001"]  # aynı çözümleyici: etkin ses çıkış cihazları
        avail = self.c.engine.availability(tweak)
        return avail.resolution.contexts if avail.visible and avail.resolution else []

    def load(self):
        w.clear_layout(self.body_lay)
        self.body_lay.addWidget(w.label(t("ui.okunuyor_bekle"), muted=True))
        devices = self._devices()
        system, engine = self.c.engine.system, self.c.engine
        base = self.c.by_id["AUD-001"]["islem"]["adimlar"][0]

        def read():
            from app.engine import handlers, resolvers  # noqa: WPS433
            rows = []
            for d in devices:
                row = {"cihaz": d["ses_cihazi"], "ad": d.get("ses_cihazi_adi") or d["ses_cihazi"]}
                if self.kind == "ses_gelistirme":
                    step = resolvers.substitute(base, d)
                    row["adim"] = step
                    row["kapali"] = handlers.state(step, handlers.snapshot(system, step)) == "acik"
                elif self.kind == "ses_ozel_mod":
                    row["adimlar"] = exclusive_steps(d["ses_cihazi"])
                    found = [system.read_reg(s["kok"], s["yol"], s["ad"]) for s in row["adimlar"]]
                    row["izinli"] = all(f is None or f[0] != 0 for f in found)  # değer yoksa Windows izin verir
                else:
                    try:
                        row.update(system.get_audio_format(d["ses_cihazi"]))
                    except Exception:
                        row["hata"] = True
                rows.append(row)
            return rows
        _ = engine
        self.app.worker.run(read, self._show, lambda _e: self._show(None), serial=False)

    def _show(self, rows):
        w.clear_layout(self.body_lay)
        if rows is None:
            self.body_lay.addWidget(w.label(t("ui.liste_okunamadi"), muted=True))
            return
        if not rows:
            self.body_lay.addWidget(w.label(t("ui.aygit_yok"), muted=True))
        for row in rows:
            self.body_lay.addWidget(self._row(row))

    def _change_id(self, row):
        prefix = {"ses_gelistirme": "SESG", "ses_ozel_mod": "SESO"}.get(self.kind, "SESB")
        return managers.item_id(prefix, row["cihaz"])

    def _row(self, row):
        change_id = self._change_id(row)
        name = w.label(row["ad"], wrap=False)
        name.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        parts = [(name, 1)]
        if self.c.engine.store.has(change_id):
            parts.append(w.badge(t("ui.degistirildi"), "bilgi"))
            if self.c.can_modify:
                parts.append(w.button(t("ui.eski_haline"), lambda: self.app.revert(change_id, self.load)))
        if self.kind == "ses_ozel_mod":
            parts.append(w.label(t("ui.ozel_mod_izin"), muted=True, size=12, wrap=False))
            switch = w.ToggleSwitch()
            switch.setChecked(row["izinli"])
            switch.setEnabled(self.c.can_modify)
            switch.clicked.connect(lambda _=False, r=row, sw=switch: self._toggle_exclusive(r, sw))
            parts.append(switch)
        elif self.kind == "ses_gelistirme":
            parts.append(w.label(t("ui.gelistirmeler_kapali"), muted=True, size=12, wrap=False))
            switch = w.ToggleSwitch()
            switch.setChecked(row["kapali"])
            switch.setEnabled(self.c.can_modify)
            switch.clicked.connect(lambda _=False, r=row, sw=switch: self._toggle(r, sw))
            parts.append(switch)
        elif row.get("hata"):
            parts.append(w.label(t("ui.bicim_okunamadi"), muted=True, wrap=False))
        else:
            combo = QComboBox()
            for value in row["desteklenen"] or [row["deger"]]:
                rate, bits = value.split("/")
                combo.addItem(t("ui.ses_bicim_etiket", hz=rate, bit=bits), value)
            if combo.findData(row["deger"]) < 0:
                rate, bits = row["deger"].split("/")
                combo.addItem(t("ui.ses_bicim_etiket", hz=rate, bit=bits), row["deger"])
            combo.setCurrentIndex(combo.findData(row["deger"]))
            combo.setFixedWidth(200)
            combo.setEnabled(self.c.can_modify)
            current = w.colored(row["deger"].replace("/", " Hz / ") + " bit", "uyari", wrap=False) \
                if int(row["deger"].split("/")[0]) > 48000 else w.label(row["deger"].replace("/", " Hz / ") + " bit",
                                                                         muted=True, wrap=False)
            apply = w.button(t("ui.uygula"), lambda _=False, r=row, cb=combo: self._set_format(r, cb.currentData()))
            apply.setEnabled(self.c.can_modify)
            parts += [current, combo, apply]
        return w.hbox(*parts)

    def _toggle(self, row, switch):
        desired = switch.isChecked()
        switch.setChecked(not desired)
        change_id = self._change_id(row)
        if not desired and self.c.engine.store.has(change_id):
            self.app.revert(change_id, self.load)
            return
        step = row["adim"]
        self.app.apply_custom(change_id, t("ui.ses_gelistirme_degisiklik", ad=row["ad"]), [step],
                              [step["acik"] if desired else step["kapali"]], self.load, restart="ses_servisi",
                              related="AUD-001", after=["ses_servisini_yeniden_baslat"])

    def _toggle_exclusive(self, row, switch):
        desired = switch.isChecked()
        switch.setChecked(not desired)
        change_id = self._change_id(row)
        if desired and self.c.engine.store.has(change_id):
            self.app.revert(change_id, self.load)
            return
        value = 1 if desired else 0
        self.app.apply_custom(change_id, t("ui.ozel_mod_degisiklik", ad=row["ad"]), row["adimlar"], [value, value],
                              self.load, restart="ses_servisi", related="AUD-003",
                              after=["ses_servisini_yeniden_baslat"])

    def _set_format(self, row, value):
        if value == row["deger"]:
            return
        step = {"tur": "yerlesik", "eylem": "ses_bicimi", "parametreler": {"cihaz": row["cihaz"]}}
        self.app.apply_custom(self._change_id(row), t("ui.ses_bicimi_degisiklik", ad=row["ad"]), [step], [value],
                              self.load, related="AUD-002")


class WindowsUpdateCard(w.Card):
    """Windows Update modu: Varsayılan / Güvenlik (WinUtil yöntemi) / 2100'e kadar duraklat (riskli)."""

    def __init__(self, app, tweak):
        super().__init__(spacing=8)
        self.app, self.c, self.tweak = app, app.c, tweak
        self.lay.addWidget(_title_row(app, tweak))
        self.body = QWidget()
        self.body_lay = QVBoxLayout(self.body)
        self.body_lay.setContentsMargins(0, 0, 0, 0)
        self.body_lay.setSpacing(8)
        self.lay.addWidget(self.body)
        self.refresh()

    def refresh(self):
        w.clear_layout(self.body_lay)
        try:
            current = windows_update.detect(self.c.engine.system)
        except Exception:
            current = None
        for mode in windows_update.MODES:
            text = QVBoxLayout()
            text.setSpacing(2)
            head = QLabel(t(f"ui.wu.mod.{mode}"))
            head.setObjectName("CardTitle")
            badges = []
            if mode == current:
                badges.append(w.badge(t("ui.wu.su_an"), "iyi"))
            if mode == "duraklat":
                badges.append(w.risk_badge("riskli"))
            text.addWidget(w.hbox(head, *badges, None))
            text.addWidget(w.label(t(f"ui.wu.aciklama.{mode}"), muted=True, size=12))
            button = w.button(t("ui.wu.uygula"), lambda _=False, m=mode: self._set(m), primary=mode != "duraklat")
            button.setEnabled(self.c.can_modify and mode != current)
            row = QWidget()
            row_lay = QHBoxLayout(row)
            row_lay.setContentsMargins(0, 0, 0, 0)
            row_lay.addLayout(text, 1)
            row_lay.addWidget(button)
            self.body_lay.addWidget(row)
        self.body_lay.addWidget(w.label(t("ui.wu.not"), muted=True, size=12))

    def _pseudo(self, mode):
        """Onay pencereleri için ayar benzeri sözlük (metinler dil dosyasından)."""
        return {"id": windows_update.CHANGE_ID, "ad": t(f"ui.wu.mod.{mode}"),
                "ne_ise_yarar": t(f"ui.wu.aciklama.{mode}"), "artilar": [t(f"ui.wu.arti.{mode}")],
                "eksiler": [t(f"ui.wu.eksi.{mode}")], "dokunmamali": [t(f"ui.wu.dokunmamali.{mode}")],
                "notlar": [t(f"ui.wu.dikkat.{mode}")], "gerceklik": {"durum": "gerçek"}, "varsayilan": "—",
                "yeniden_baslatma_kodu": "yok", "risk": "riskli" if mode == "duraklat" else "dikkatli"}

    def _set(self, mode):
        if mode == "guvenlik" and not dialogs.confirm_careful(self.app, self._pseudo(mode)):
            return
        if mode == "duraklat" and not dialogs.confirm_risky(self.app, self._pseudo(mode), None, True):
            return
        store = self.c.engine.store

        def apply():
            if mode == "varsayilan":
                self.refresh()
                return
            self.app.apply_custom(windows_update.CHANGE_ID, t("ui.wu.degisiklik", mod=t(f"ui.wu.mod.{mode}")),
                                  windows_update.steps(), windows_update.values(mode), self.refresh,
                                  related=self.tweak["id"])

        # Mod değişirken önce uygulamanın önceki değişikliği geri alınır; böylece modlar karışmaz.
        if store.has(windows_update.CHANGE_ID):
            self.app.revert(windows_update.CHANGE_ID, apply)
        else:
            apply()


class UacCard(w.Card):
    """Kullanıcı Hesabı Denetimi seviyesi: Windows'un dört kaydırıcı konumu (uac.py)."""

    def __init__(self, app, tweak):
        super().__init__(spacing=8)
        self.app, self.c, self.tweak = app, app.c, tweak
        self.lay.addWidget(_title_row(app, tweak))
        self.body = QWidget()
        self.body_lay = QVBoxLayout(self.body)
        self.body_lay.setContentsMargins(0, 0, 0, 0)
        self.body_lay.setSpacing(8)
        self.lay.addWidget(self.body)
        self.refresh()

    def refresh(self):
        w.clear_layout(self.body_lay)
        try:
            current = uac.detect(self.c.engine.system)
        except Exception:
            current = None
        if current in ("kapali", "ozel"):
            self.body_lay.addWidget(w.colored(t(f"ui.uac.durum.{current}"), "uyari"))
        for level in uac.LEVELS:
            text = QVBoxLayout()
            text.setSpacing(2)
            head = QLabel(t(f"ui.uac.seviye.{level}"))
            head.setObjectName("CardTitle")
            badges = [w.badge(t("ui.wu.su_an"), "iyi")] if level == current else []
            if uac.RISK[level] != "güvenli":
                badges.append(w.risk_badge(uac.RISK[level]))
            text.addWidget(w.hbox(head, *badges, None))
            text.addWidget(w.label(t(f"ui.uac.aciklama.{level}"), muted=True, size=12))
            button = w.button(t("ui.uac.uygula"), lambda _=False, lv=level: self._set(lv),
                              primary=uac.RISK[level] == "güvenli")
            button.setEnabled(self.c.can_modify and level != current)
            row = QWidget()
            row_lay = QHBoxLayout(row)
            row_lay.setContentsMargins(0, 0, 0, 0)
            row_lay.addLayout(text, 1)
            row_lay.addWidget(button)
            self.body_lay.addWidget(row)
        self.body_lay.addWidget(w.label(t("ui.uac.not"), muted=True, size=12))

    def _pseudo(self, level):
        return {"id": uac.CHANGE_ID, "ad": t(f"ui.uac.seviye.{level}"), "ne_ise_yarar": t(f"ui.uac.aciklama.{level}"),
                "artilar": [t("ui.uac.arti")], "eksiler": [t(f"ui.uac.eksi.{level}")], "dokunmamali": [],
                "notlar": [t("ui.uac.geri_alma")], "gerceklik": {"durum": "gerçek"}, "varsayilan": "—",
                "yeniden_baslatma_kodu": "yok", "risk": uac.RISK[level]}

    def _set(self, level):
        if uac.RISK[level] == "dikkatli" and not dialogs.confirm_careful(self.app, self._pseudo(level)):
            return
        if uac.RISK[level] == "riskli" and not dialogs.confirm_risky(self.app, self._pseudo(level), None, True):
            return
        store = self.c.engine.store

        def apply():
            # Önceki değişiklik geri alındıktan sonra seçilen seviye zaten geçerliyse yazmaya gerek yok.
            if uac.detect(self.c.engine.system) == level:
                self.refresh()
                return
            self.app.apply_custom(uac.CHANGE_ID, t("ui.uac.degisiklik", seviye=t(f"ui.uac.seviye.{level}")),
                                  uac.steps(), uac.values(level), self.refresh, related=self.tweak["id"])

        if store.has(uac.CHANGE_ID):
            self.app.revert(uac.CHANGE_ID, apply)
        else:
            apply()


class DefenderCard(w.Card):
    """Windows Defender gerçek zamanlı koruması (defender.py). Varsayılan: açık; kapatmak iki ayrı uyarıyla
    sorulur, "Korumayı geri aç" tek tıkla uygulamanın değişikliğini geri alır. Kurcalama koruması açıkken
    uygulama yazmayı denemez; kullanıcıyı Windows Güvenliği'ne yönlendirir."""

    def __init__(self, app, tweak):
        super().__init__(spacing=8)
        self.app, self.c, self.tweak = app, app.c, tweak
        self.lay.addWidget(_title_row(app, tweak))
        self.lay.addWidget(w.banner(t("ui.defender.uyari"), "uyari"))
        self.body = QWidget()
        self.body_lay = QVBoxLayout(self.body)
        self.body_lay.setContentsMargins(0, 0, 0, 0)
        self.body_lay.setSpacing(8)
        self.lay.addWidget(self.body)
        self.refresh()

    def refresh(self):
        w.clear_layout(self.body_lay)
        self.body_lay.addWidget(w.label(t("ui.okunuyor_bekle"), muted=True))
        self.app.worker.run(self.c.engine.system.get_defender_status, self._show, lambda _e: self._show(None),
                            serial=False)

    def _show(self, status):
        try:
            w.clear_layout(self.body_lay)
        except RuntimeError:  # kart bu arada kaldırıldı
            return
        status = status or {}
        realtime, tamper = status.get("gercek_zamanli"), status.get("kurcalama")
        changed = self.c.engine.store.has(defender.CHANGE_ID)

        def state(value):
            if value is None:
                return t("ui.defender.okunamadi")
            return t("ui.defender.acik") if value else t("ui.defender.kapali")

        rows = [(t("ui.defender.gercek_zamanli"), state(realtime), "iyi" if realtime else "uyari"),
                (t("ui.defender.kurcalama"), state(tamper), "notr")]
        for name, value, tone in rows:
            self.body_lay.addWidget(w.hbox(w.label(name, wrap=False), w.badge(value, tone), None))
        if status.get("mod") and status["mod"] != "Normal":
            self.body_lay.addWidget(w.label(t("ui.defender.mod", mod=status["mod"]), muted=True, size=12))

        buttons = []
        if realtime is None:
            self.body_lay.addWidget(w.label(t("ui.defender.okunamadi_aciklama"), muted=True, size=12))
        elif realtime and tamper:
            self.body_lay.addWidget(w.colored(t("ui.defender.kurcalama_acik"), "uyari"))
        elif realtime:
            off = w.button(t("ui.defender.kapat"), self._turn_off, warn=True)
            off.setEnabled(self.c.can_modify)
            buttons.append(off)
        elif changed:
            back = w.button(t("ui.defender.geri_ac"), self._restore, primary=True)
            back.setEnabled(self.c.can_modify)
            buttons.append(back)
        else:
            self.body_lay.addWidget(w.colored(t("ui.defender.disarida_kapali"), "uyari"))
        buttons += [w.button(t("ui.defender.guvenlik_ac"), lambda: w.open_target(defender.SECURITY_PAGE)),
                    w.button(t("ui.defender.yeniden_oku"), self.refresh)]
        self.body_lay.addWidget(w.flow(*buttons))
        self.body_lay.addWidget(w.label(t("ui.defender.not"), muted=True, size=12))

    def _pseudo(self):
        return {"id": defender.CHANGE_ID, "ad": t("ui.defender.kapat"), "ne_ise_yarar": t("ui.defender.ne_yapar"),
                "artilar": [t("ui.defender.arti")], "eksiler": [t("ui.defender.eksi")],
                "dokunmamali": [t("ui.defender.dokunmamali")], "notlar": [t("ui.defender.geri_alma")],
                "gerceklik": {"durum": "zararlı"}, "varsayilan": t("ui.defender.acik"),
                "yeniden_baslatma_kodu": "yok", "risk": "riskli"}

    def _turn_off(self):
        if not dialogs.confirm_risky(self.app, self._pseudo(), None, True):
            return
        # Onay burada alındı; seviye 0 kaydedilir ki "Korumayı geri aç" yeniden onay sormadan tek tıkla çalışsın.
        self.app.apply_custom(defender.CHANGE_ID, t("ui.defender.degisiklik"), [defender.step()], [False],
                              self.refresh, related=self.tweak["id"])

    def _restore(self):
        self.app.revert(defender.CHANGE_ID, self.refresh)


def make_manager(app, tweak):
    kind = tweak["liste_yoneticisi"]
    if kind == "windows_update":
        return WindowsUpdateCard(app, tweak)
    if kind == "uac":
        return UacCard(app, tweak)
    if kind == "defender":
        return DefenderCard(app, tweak)
    if kind == "nvidia":
        return NvidiaSettingCard(app, tweak)
    if kind == "amd":
        return AmdSettingCard(app, tweak)
    if kind == "surucu_araclari":
        return DriverToolsCard(app, tweak)
    if kind in ("ses_gelistirme", "ses_bicimi", "ses_ozel_mod"):
        return AudioDevicesCard(app, tweak)
    return DeviceListCard(app, tweak)
