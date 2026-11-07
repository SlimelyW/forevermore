"""Ana ekran (sade): tarama özeti, canlı sistem durumu ve bulgular ("Çöz" düğmeleriyle).

Donanım ayrıntıları ve en çok işlemci kullanan süreçler PC Detayları sayfasındadır."""

import datetime
from collections import deque

from PySide6.QtCore import QPoint, QPointF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget

from app.core import settings
from app.core.i18n import fmt_number, fmt_percent, t
from app.engine import fixes, varsayilan
from app.scan.report import finding_text
from app.ui import dialogs, motion, theme, widgets as w

HISTORY = 60  # saniye
LIVE_PRIMARY = ("cpu", "ram", "gpu")  # öteki canlı kartlar "Daha fazla" ile açılır
# Bulgu grupları önem sırasıyla; önem rozeti grup başlığında bir kez (her satırda tekrar yok, §11).
FINDING_GROUPS = ("sorun", "uyari", "bilgi", "iyi")


def _rate(value, unit="B"):
    """Bayt/sn -> okunur metin (ağ için bit/sn)."""
    if value is None:
        return "—"
    if unit == "bit":
        value *= 8
        for limit, suffix in ((1e9, "Gbps"), (1e6, "Mbps"), (1e3, "Kbps")):
            if value >= limit:
                return f"{fmt_number(value / limit, 1)} {suffix}"
        return f"{fmt_number(value)} bps"
    for limit, suffix in ((2 ** 30, "GB/s"), (2 ** 20, "MB/s"), (2 ** 10, "KB/s")):
        if value >= limit:
            return f"{fmt_number(value / limit, 1)} {suffix}"
    return f"{fmt_number(value)} B/s"


class Sparkline(QWidget):
    """Son 60 saniyenin küçük çizgi grafiği (QPainter; çok hafif).
    scale=0: ölçek, görünen en yüksek değere göre ayarlanır (ağ, süreç sayısı)."""

    def __init__(self, history, tone, scale=100.0):
        super().__init__()
        self.history, self.scale = history, scale
        self.color = QColor(theme.TONES.get(tone, theme.TONES["bilgi"]))
        self.setMinimumHeight(38)

    def sizeHint(self):
        return QSize(160, 38)

    def paintEvent(self, _event):
        values = [v for v in self.history if v is not None]
        if len(values) < 2:
            return
        top = self.scale or max(max(values) * 1.15, 1.0)
        width, height = self.width(), self.height() - 2
        step = width / (HISTORY - 1)
        start = HISTORY - len(self.history)
        points = [QPointF((start + i) * step, 1 + height - min(value / top, 1.0) * height)
                  for i, value in enumerate(self.history) if value is not None]
        path = QPainterPath()
        path.moveTo(points[0])
        for point in points[1:]:
            path.lineTo(point)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        fill = QPainterPath(path)
        fill.lineTo(points[-1].x(), height + 1)
        fill.lineTo(points[0].x(), height + 1)
        shade = QColor(self.color)
        shade.setAlpha(45)
        painter.fillPath(fill, shade)
        painter.setPen(QPen(self.color, 1.6))
        painter.drawPath(path)


class LiveTile(w.Card):
    """Alçak canlı kutu: solda ad, değer ve ayrıntı; sağda grafik (önce yarısı boş, yüksek kutulardı)."""

    def __init__(self, title, history, tone, scale=100.0):
        super().__init__(layout="h", margins=(16, 12, 16, 12), spacing=12)
        text = QVBoxLayout()
        text.setSpacing(0)
        head = w.label(title, muted=True, size=12, wrap=False)
        self.value = QLabel("—")
        self.value.setObjectName("LiveNum")
        theme.tabular(self.value)
        self.detail = w.label("", muted=True, size=12, wrap=False)
        for widget in (head, self.value, self.detail):
            text.addWidget(widget)
        self.lay.addLayout(text)
        self.chart = Sparkline(history, tone, scale)
        self.lay.addWidget(self.chart, 1, Qt.AlignmentFlag.AlignBottom)

    def show_values(self, value, detail):
        self.value.setText(value)
        self.detail.setText(detail)
        self.chart.update()


class FindingCard(w.Card):
    """Bir bulgu; uygulama çözebiliyorsa "Çöz" düğmesi (ayara yönlendirmez, kendisi yapar)."""

    def __init__(self, page, finding):
        super().__init__(layout="h", spacing=12)
        self.page, self.app, self.c = page, page.app, page.c
        self.finding = finding
        self.fix = fixes.fix_for(finding, self.c.by_id)
        avail = self.c.availability.get(self.fix["id"]) if self.fix else None
        if self.fix and avail is not None and not avail.visible:
            self.fix = None
        text = QVBoxLayout()
        text.setSpacing(2)
        heading, body = finding_text(finding)
        head = QLabel(heading)
        head.setObjectName("CardTitle")
        head.setWordWrap(True)
        text.addWidget(head)
        text.addWidget(w.label(body, muted=True))
        if finding["kod"] == "tespit" and finding["ilgili"][0] in varsayilan.MANUAL:
            text.addWidget(w.label(t(f"ui.varsayilan.elle.{finding['ilgili'][0]}"), size=12))
        self.lay.addLayout(text, 1)
        self.actions = w.hbox(spacing=6)
        self.lay.addWidget(self.actions)
        self.refresh()

    @property
    def busy(self):
        return bool(self.fix) and self.fix["id"] in self.page.busy_fixes

    def refresh(self):
        lay = self.actions.layout()
        w.clear_layout(lay)
        if self.fix is None:
            related = [self.c.by_id[tid].get("ilgili") or tid for tid in self.finding["ilgili"] if tid in self.c.by_id]
            if related:
                lay.addWidget(w.button(t("ui.ayara_git"), lambda _=False, tid=related[0]: self.app.go_to_tweak(tid)))
            return
        tweak_id = self.fix["id"]
        if self.busy:
            key = "ui.durum.dogrulaniyor" if self.fix["id"] in self.page.verifying else "ui.durum.uygulaniyor"
            lay.addWidget(w.label(t(key), muted=True, wrap=False))
            return
        if fixes.is_resolved(self.fix, self.c.states.get(tweak_id), self.page.done_actions):
            lay.addWidget(w.badge(t("ui.cozuldu"), "iyi"))
            if self.fix["tur"] == "ac" and self.c.engine.store.has(tweak_id) and self.c.can_modify:
                lay.addWidget(w.button(t("ui.geri_al"), self._undo))
            return
        fixable = self.c.can_modify and (self.fix["tur"] in ("eylem", "varsayilan") or self.c.is_fresh(tweak_id))
        # Tespit edilen (başka programın uyguladığı) ayar: kapatmak Windows varsayılanını yazar.
        to_default = self.fix["tur"] == "varsayilan" or (self.finding["kod"] == "tespit"
                                                          and not self.c.engine.store.has(tweak_id))
        button = w.button(t("ui.varsayilan.dugme" if to_default else "ui.coz"), self._solve, primary=True)
        button.setEnabled(fixable)
        button.setToolTip(t("ui.coz_ipucu") if fixable else t("ui.durum.okunuyor"))
        lay.addWidget(button)

    # İşlem sürerken sayfa yeniden kurulabilir; bu yüzden bitiş sayfaya bildirilir, karta değil.
    def _solve(self):
        tweak = self.c.by_id[self.fix["id"]]
        done = self.page.fix_started(self.fix)
        self.refresh()
        if self.fix["tur"] == "eylem":
            action = next(a for a in tweak["islem"]["eylemler"] if a["id"] == self.fix["eylem"])
            self.app.run_action(tweak, action, done)
        elif self.fix["tur"] == "varsayilan":
            self.app.restore_default(tweak, done)
        elif self.fix["tur"] == "kapat" and self.c.engine.store.has(tweak["id"]):
            self.app.revert(tweak["id"], done)
        else:
            self.app.toggle(tweak, self.fix["tur"] == "ac", done)

    def _undo(self):
        done = self.page.fix_started(self.fix)
        self.refresh()
        self.app.revert(self.fix["id"], done)


class RecommendationsCard(w.Card):
    """Sayfanın kahramanı: "Sıradaki en iyi hamle" Sıralama kazanç tahmini değildir
    (bkz. app/engine/recommend.py); "Uygula" ayarı her zamanki yoldan (onay, yedek, geri alma) açar."""

    def __init__(self, page):
        super().__init__(spacing=8, margins=(26, 22, 26, 22))
        self.setProperty("hero", True)
        self.page, self.app, self.c = page, page.app, page.c
        self.pos = 0       # "Sonra" ile ilerleyen sıra
        self.applied = None  # son uygulanan öneri: bir süre "Uygulandı" satırı
        self.body = QVBoxLayout()
        self.body.setSpacing(8)
        self.lay.addLayout(self.body)

    def fill(self):  # sayfaya eklendikten sonra çağrılır: üst öğesiz setVisible(True) ayrı pencere açardı
        w.clear_layout(self.body)
        self.setVisible(True)
        done = self.applied
        if done and self.c.states.get(done["id"]) and self.c.states[done["id"]].is_on:
            line = w.label(t("ui.oneri.uygulandi", ad=dialogs.display_name(done)), wrap=False)
            line.setObjectName("HeroDone")
            self.body.addWidget(line)
        picks = self.c.recommendations()
        if not picks:
            self.body.addWidget(w.label(t("ui.oneri.bos"), muted=True))
            return
        self.pos %= len(picks)
        pick = picks[self.pos]
        tweak = self.c.by_id[pick["id"]]
        reason = {"gpu": lambda: t("ui.oneri.neden.gpu", deger=pick["deger"]),
                  "form": lambda: t(f"ui.oneri.neden.{pick['deger']}")}.get(pick["neden"], lambda: t("ui.oneri.neden.genel"))()
        self.body.addWidget(w.label(t("ui.oneri.baslik"), muted=True, wrap=False))
        title = w.label(dialogs.display_name(tweak))
        title.setObjectName("HeroTitle")
        self.body.addWidget(title)
        summary = (tweak.get("ne_ise_yarar") or "").split(". ")[0].strip()
        if summary:
            self.body.addWidget(w.label(summary if summary.endswith(".") else summary + ".", muted=True))
        self.body.addWidget(w.hbox(w.impact_badge(tweak["performans_etkisi"]["seviye"]),
                                   w.label(reason, muted=True, size=12, wrap=False), None))
        apply_button = w.button(t("ui.uygula"), lambda _=False, tw=tweak: self._apply(tw), primary=True)
        apply_button.setEnabled(self.c.can_modify)
        buttons = [apply_button]
        if len(picks) > 1:
            buttons.append(w.button(t("ui.oneri.sonra"), self._next))
            buttons.append(w.button(t("ui.toplu.hepsi", n=len(picks)), lambda: self._apply_all(picks)))
        self.body.addSpacing(6)
        self.body.addWidget(w.hbox(*buttons, None, w.label(t("ui.oneri.sayac", k=self.pos + 1, n=len(picks)),
                                                            muted=True, size=12, wrap=False)))
        self.body.addWidget(w.label(t("ui.oneri.not"), muted=True, size=11))

    def _next(self):
        self.pos += 1
        self.fill()

    def _apply_all(self, picks):
        self.app.apply_recommended([self.c.by_id[p["id"]] for p in picks], self.fill)

    def _apply(self, tweak):
        self.applied = tweak
        self.app.toggle(tweak, True, self.fill)


class StatTile(w.Card):
    """Tarama özeti kutusu: tıklanınca (veya Enter / Boşluk) ilgili listeyi açar."""

    clicked = Signal()

    def __init__(self):
        super().__init__(layout="h", margins=(14, 8, 14, 8), spacing=12, hover=True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setToolTip(t("ui.stat_ipucu"))

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.clicked.emit()
            return
        super().keyPressEvent(event)


class SummaryPage(w.Page):
    STATS = ("uygun", "acik", "degisen", "bulgu")

    def __init__(self, app):
        super().__init__(app)
        self._progress = None
        self.history = {key: deque(maxlen=HISTORY) for key in ("cpu", "ram", "gpu", "disk", "ag", "surec")}
        self.tiles = {}
        self.last_sample = None
        self.finding_cards = []
        self.done_actions = set()  # bu oturumda "Çöz" ile çalıştırılan tek seferlik eylemler
        self.busy_fixes = set()
        self.verifying = set()  # çözüldü, yalnız bu madde yeniden okunuyor
        self.stat_labels = []
        self.stat_tiles = {}
        self.detail_kind = None    # açık liste: "uygun", "acik", "degisen" (bulgular sayfada zaten var)
        self.detail_lay = None
        self.findings_title = None
        self.finding_groups = {}   # seviye -> (satır listesi, aç/kapa düğmesi)
        self.live_more = True  # 6 kart açık: boş alanı doldurur, canlı veri dikkat çeker (Kubilay geri bildirimi)
        self.monitor = getattr(app, "live_monitor", None)
        if self.monitor is not None:
            self.monitor.sampled.connect(self._on_sample)
            self.monitor.failed.connect(self._on_failed)

    # Sayfa görünürken canlı izleme çalışır; gizlenince (başka sayfa / küçültme) durur.
    def showEvent(self, event):
        super().showEvent(event)
        if self.monitor is not None:
            self.monitor.set_active(True, owner=self)

    def hideEvent(self, event):
        super().hideEvent(event)
        if self.monitor is not None:
            self.monitor.set_active(False, owner=self)

    def fix_started(self, fix):
        """Çözüm başlarken çağrılır; bitince çağrılacak fonksiyonu döndürür."""
        self.busy_fixes.add(fix["id"])
        started = datetime.datetime.now().isoformat(timespec="seconds")

        def verified(changed):
            self.busy_fixes.discard(fix["id"])
            self.verifying.discard(fix["id"])
            if changed and self.built:
                self.data_reloaded()  # çözülen tespit bulgusu listeden kalkar; yalnız bu sayfa yeniden kurulur
            else:
                self.tweak_updated(fix["id"])

        def finished():
            if fix["tur"] == "eylem":
                latest = self.c.engine.store.read_history("eylem", limit=1)
                if latest and latest[0]["id"] == fix["id"] and latest[0]["basarili"] and latest[0]["zaman"] >= started:
                    self.done_actions.add(fix["id"])
            self.verifying.add(fix["id"])
            self.tweak_updated(fix["id"])
            self.app.recheck_fix(fix["id"], verified)
        return finished

    def tweak_updated(self, tweak_id):
        if self.built and self.c.scan is not None and self.stat_labels:
            for label, value in zip(self.stat_labels, self._stat_values()):
                label.setText(str(value))
            if self.detail_kind:
                self._fill_detail()
        for card in self.finding_cards:
            if card.fix and card.fix["id"] == tweak_id:
                card.refresh()
        if self.built and getattr(self, "recommendations", None) is not None:
            self.recommendations.fill()

    def build(self):
        super().build()
        self.finding_cards = []
        self.stat_labels = []
        self.stat_tiles = {}
        self.detail_lay = None
        self.findings_title = None
        self.finding_groups = {}
        top = w.hbox(w.title(t("ui.ozet_baslik")), None,
                     w.button(t("ui.menu.rapor"), lambda: self.app.navigate("rapor")),
                     w.button(t("ui.yeniden_tara"), self.app.start_scan, primary=True))
        self.header.addWidget(top)
        self.status_label = w.label("", muted=True)
        self.header.addWidget(self.status_label)
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)
        self.header.addWidget(self._progress)
        if self.c.scan is not None:
            self._stats()
            self._content()
        self._live_panel()
        if self.c.scan is None:  # ilk açılış (önbellek yok): boş ekran yerine sayfanın iskeleti
            box = w.Card()
            box.lay.addWidget(w.label(t("ui.taraniyor"), bold=True))
            box.lay.addWidget(w.label(t("ui.tarama_salt_okunur"), muted=True))
            box.lay.addWidget(w.skeleton(22, 420))
            box.lay.addWidget(w.skeleton(14, 260))
            self.body.insertWidget(0, box)
            self.body.insertWidget(1, w.hbox(*(w.skeleton(40) for _ in range(4)), spacing=8))

    def set_progress(self, text, running=True):
        self.ensure_built()
        self.status_label.setText(text)
        self._progress.setVisible(running)

    def _content(self):
        """Bulgular varsayılan açık, önem sırasıyla gruplu. Kullanıcının daralttığı gruplar ayarlarda kalır
        (varsayılan: yalnızca "iyi" daralı; yapılacak bir şey yok)."""
        scan = self.c.scan
        self.findings_title = w.section_title(f"{t('bolum.bulgular')} ({len(scan['bulgular'])})")
        self.body.addWidget(self.findings_title)
        collapsed = set(settings.get("bulgu_daralt") or [])
        for level in FINDING_GROUPS:
            items = [f for f in scan["bulgular"] if f["seviye"] == level]
            if not items:
                continue
            toggle = w.button("", lambda _=False, lv=level: self._toggle_group(lv))
            self.body.addWidget(w.hbox(w.badge(f"{t('seviye.' + level)} ({len(items)})", level),
                                       (w.label(t(f"ui.bulgu_grup.{level}"), muted=True), 1), toggle, spacing=12))
            rows = w.RowList()
            for finding in items:
                card = FindingCard(self, finding)
                self.finding_cards.append(card)
                rows.add(card)
            self.body.addWidget(rows)
            self.finding_groups[level] = (rows, toggle)
            self._show_group(level, level not in collapsed)
        if scan.get("hatalar"):
            names = ", ".join(t(f"bolum.{k}") for k in scan["hatalar"] if k != "tespit")
            self.body.addWidget(w.label(t("ui.okunamayan", liste=names), muted=True))

    def _toggle_group(self, level):
        show = self.finding_groups[level][0].isHidden()
        collapsed = set(settings.get("bulgu_daralt") or [])
        settings.set("bulgu_daralt", sorted(collapsed - {level} if show else collapsed | {level}))
        self._show_group(level, show, animate=True)

    def _show_group(self, level, show, animate=False):
        rows, toggle = self.finding_groups[level]
        if animate:
            motion.expand(rows, show)
        else:
            rows.setVisible(show)
        toggle.setText(t("ui.gizle") if show else t("ui.goster"))
        toggle.setAccessibleName(f"{t('seviye.' + level)}: {toggle.text()}")

    # ------------------------------------------------------------------ canlı izleme
    def _live_panel(self):
        self.live_toggle = w.button("", self._toggle_live)
        self.body.addWidget(w.hbox(w.section_title(t("ui.canli.baslik")), None,
                                   w.label(t("ui.canli.aciklama"), muted=True, size=12, wrap=False), self.live_toggle))
        if self.monitor is None:
            self.body.addWidget(w.label(t("ui.canli.okunamadi"), muted=True))
            return
        container, lay = w.grid(columns=3)
        specs = [("cpu", "ui.canli.cpu", "bilgi", 100.0), ("ram", "ui.canli.ram", "mor", 100.0),
                 ("gpu", "ui.canli.gpu", "iyi", 100.0), ("disk", "ui.canli.disk", "uyari", 100.0),
                 ("ag", "ui.canli.ag", "turkuaz", 0.0), ("surec", "ui.canli.surecler", "notr", 0.0)]
        self.tiles = {}
        for i, (key, title, tone, scale) in enumerate(specs):
            tile = LiveTile(t(title), self.history[key], tone, scale)
            self.tiles[key] = tile
            lay.addWidget(tile, i // 3, i % 3)
        self.body.addWidget(container)
        self._show_live_more()
        if self.last_sample:
            self._show(self.last_sample)

    def _toggle_live(self):
        self.live_more = not self.live_more
        self._show_live_more()

    def _show_live_more(self):
        for key, tile in self.tiles.items():
            tile.setVisible(self.live_more or key in LIVE_PRIMARY)
        self.live_toggle.setText(t("ui.canli.daha_az") if self.live_more else t("ui.canli.daha_fazla"))

    def _on_failed(self):
        for tile in self.tiles.values():
            tile.show_values("—", t("ui.canli.okunamadi"))

    def _on_sample(self, sample):
        total = sample.get("ram_toplam")
        ram_pct = sample["ram_kullanilan"] / total * 100 if total else None
        net = (sample.get("ag_alinan") or 0) + (sample.get("ag_gonderilen") or 0)
        for key, value in (("cpu", sample.get("cpu")), ("ram", ram_pct), ("gpu", sample.get("gpu")),
                           ("disk", sample.get("disk")), ("ag", net), ("surec", sample.get("surec_sayisi"))):
            self.history[key].append(value)
        sample["ram_yuzde"] = ram_pct
        self.last_sample = sample
        if self.built and self.tiles:
            self._show(sample)

    def _show(self, s):
        def pct(value):
            return "—" if value is None else fmt_percent(value)

        gb = 2 ** 30
        self.tiles["cpu"].show_values(pct(s.get("cpu")),
                                      t("ui.canli.ghz", ghz=s["cpu_ghz"]) if s.get("cpu_ghz") else "")
        ram = (t("ui.canli.ram_alt", kullanilan=fmt_number(s['ram_kullanilan'] / gb, 1),
                 toplam=fmt_number(s['ram_toplam'] / gb, 1))
               if s.get("ram_toplam") else "")
        self.tiles["ram"].show_values(pct(s.get("ram_yuzde")), ram)
        vram = s.get("gpu_bellek")
        used, total = s.get("gpu_bellek_kart") or (None, None)
        if used is not None and total and used <= total:  # paylaşımlı belleğe taşan (tümleşik kart) değer toplamı aşar: yalnızca kullanılanı yaz
            vram_text = t("ui.canli.vram_toplam", kullanilan=fmt_number(used / gb, 1), toplam=fmt_number(total / gb, 1))
        else:
            vram_text = t("ui.canli.vram", gb=fmt_number(vram / gb, 1)) if vram is not None else ""
        self.tiles["gpu"].show_values(pct(s.get("gpu")), vram_text)
        self.tiles["disk"].show_values(pct(s.get("disk")), t("ui.canli.disk_alt", okuma=_rate(s.get("disk_okuma")),
                                                             yazma=_rate(s.get("disk_yazma"))))
        self.tiles["ag"].show_values("↓ " + _rate(s.get("ag_alinan"), "bit"),
                                     "↑ " + _rate(s.get("ag_gonderilen"), "bit"))
        count = s.get("surec_sayisi")
        self.tiles["surec"].show_values("—" if count is None else str(int(count)), t("ui.canli.surec_alt"))

    # ------------------------------------------------------------------ tarama özeti
    def _suitable(self):
        return [tw for tw in self.c.tweaks if tw["sinif"] == "SWITCH"
                and self.c.availability.get(tw["id"]) and self.c.availability[tw["id"]].visible]

    def _is_on(self, tweak):
        state = self.c.states.get(tweak["id"])
        return bool(state and state.is_on)

    def _stat_values(self):
        visible = self._suitable()
        on = sum(1 for tw in visible if self._is_on(tw))
        return len(visible), on, len(self.c.changed()), len(self.c.scan["bulgular"])

    def _stats(self):
        self.recommendations = RecommendationsCard(self)  # kahraman kart: istatistiklerin üstünde
        self.body.addWidget(self.recommendations)
        self.recommendations.fill()
        row = QHBoxLayout()
        row.setSpacing(8)
        texts = (t("ui.stat_uygun"), t("ui.stat_acik"), t("ui.stat_degistirilen"), t("ui.stat_bulgu"))
        for kind, value, text in zip(self.STATS, self._stat_values(), texts):
            card = StatTile()
            card.clicked.connect(lambda k=kind: self._stat_clicked(k))
            self.stat_tiles[kind] = card
            big = QLabel(str(value))  # sayı ve adı tek satırda: dört büyük rakam yarışmasın
            big.setObjectName("StatNum")
            theme.tabular(big)
            self.stat_labels.append(big)
            card.lay.addWidget(big)
            card.lay.addWidget(w.label(text, muted=True, size=theme.SMALL_SIZE), 1)
            row.addWidget(card)
        self.body.addLayout(row)
        box = QWidget()
        self.detail_lay = QVBoxLayout(box)
        self.detail_lay.setContentsMargins(0, 0, 0, 0)
        self.body.addWidget(box)
        self._fill_detail()

    # ------------------------------------------------------------------ özet kutularının listeleri
    def _stat_clicked(self, kind):
        if kind == "bulgu":  # bulgular bu sayfada: o bölüme kaydır
            if self.findings_title is not None:
                QTimer.singleShot(0, lambda: self.scroll.verticalScrollBar().setValue(
                    self.findings_title.mapTo(self.body_widget, QPoint(0, 0)).y()))
            return
        self.detail_kind = None if self.detail_kind == kind else kind
        self._fill_detail()

    def _fill_detail(self):
        if self.detail_lay is None:
            return
        try:
            w.clear_layout(self.detail_lay)
        except RuntimeError:  # sayfa bu arada yeniden kuruldu
            return
        for kind, tile in self.stat_tiles.items():
            tile.set_highlight(kind == self.detail_kind)
        if not self.detail_kind:
            return
        kind = self.detail_kind
        card = w.Card(spacing=8)
        if kind == "degisen":
            rows = self.c.changed()
        else:
            rows = self._suitable()
            if kind == "acik":
                rows = [tw for tw in rows if self._is_on(tw)]
        title = QLabel(t(f"ui.stat_liste.{kind}", adet=len(rows)))
        title.setObjectName("CardTitle")
        card.lay.addWidget(w.hbox((title, 1), w.button(t("ui.kapat"), lambda: self._stat_clicked(kind))))
        card.lay.addWidget(w.label(t(f"ui.stat_liste_aciklama.{kind}"), muted=True, size=12))
        if not rows:
            card.lay.addWidget(w.label(t("ui.liste_bos"), muted=True))
        elif kind == "degisen":
            for tweak_id, name, when in rows:
                parts = [(w.label(name), 1), w.label(when, muted=True, wrap=False, size=12)]
                if tweak_id in self.c.by_id:
                    parts.append(w.button(t("ui.ayara_git"), lambda _=False, i=tweak_id: self.app.go_to_tweak(i)))
                card.lay.addWidget(w.hbox(*parts, spacing=10))
            card.lay.addWidget(w.hbox(None, w.button(t("ui.stat_degisiklikleri_ac"),
                                                     lambda: self.app.navigate("degisiklikler"), primary=True)))
        else:
            for category in self.c.categories:
                items = [tw for tw in rows if tw["kategori"] == category["ad"]]
                if not items:
                    continue
                card.lay.addWidget(w.label(f"{t('kategori.' + category['id'])} ({len(items)})", bold=True, size=12))
                for tweak in items:
                    parts = [(w.label(tweak["ad"]), 1)]
                    if kind == "uygun" and self._is_on(tweak):
                        parts.append(w.badge(t("ui.stat_rozet_acik"), "iyi"))
                    parts.append(w.button(t("ui.ayara_git"), lambda _=False, i=tweak["id"]: self.app.go_to_tweak(i)))
                    card.lay.addWidget(w.hbox(*parts, spacing=10))
        self.detail_lay.addWidget(card)
