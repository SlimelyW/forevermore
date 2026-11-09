"""Önce / Sonra ölçümü sayfası."""

import datetime
import os
import threading

from app.core import log

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QCheckBox, QComboBox, QCompleter, QLabel, QProgressBar, QVBoxLayout, QWidget

from app.core import paths
from app.core.i18n import fmt_date, fmt_number, fmt_percent, t
from app.engine import driver_tools
from app.measure import GAME_METRICS, METRICS, SYSTEM_METRICS, MeasurementStore, compare, presentmon, system_measure
from app.ui import dialogs, motion, theme, widgets as w
from app.ui.managers_ui import tool_check_text

LABELS = ("once", "sonra", "diger")
_log = log.get("measure")


def _fmt(metric, value):
    if value is None:
        return "—"
    unit = METRICS[metric][1]
    text = fmt_number(value, 1) if isinstance(value, float) and not value.is_integer() else fmt_number(round(value))
    return f"{text} {unit}".strip()


def anti_cheat_game(games, exe):
    """Seçilen exe, anti-cheat'li kayıtlı bir oyunsa True (kayıtsız süreçlerde bilgi yok: False)."""
    name = (exe or "").lower()
    return any(g.get("anti_cheat") and os.path.basename(g.get("exe") or "").lower() == name for g in games)


def report_text(before, after):
    """Karşılaştırma raporu (düz metin)."""
    lines = [t("olcum.rapor_baslik"), "=" * 40,
             t("olcum.rapor_once", zaman=fmt_date(before["zaman"]), etiket=t(f"olcum.etiket.{before['etiket']}")),
             t("olcum.rapor_sonra", zaman=fmt_date(after["zaman"]), etiket=t(f"olcum.etiket.{after['etiket']}")),
             ""]
    for metric, a, b, diff, pct, better in compare(before, after):
        change = "" if pct is None else f" ({pct:+.1f}%)"
        verdict = {True: t("olcum.iyi"), False: t("olcum.kotu"), None: t("olcum.ayni")}[better]
        lines.append(f"{t(f'olcum.metrik.{metric}'):<34} {_fmt(metric, a):>12} -> {_fmt(metric, b):>12}{change}  {verdict}")
    lines += ["", t("olcum.durustluk")]
    return "\n".join(lines)


class MeasurePage(w.Page):
    def __init__(self, app):
        super().__init__(app)
        self.store = MeasurementStore()
        self.selected = []      # karşılaştırma için en fazla iki ölçüm
        self.running = None     # "sistem" / "oyun"
        self.progress_text = ""
        self.status = None      # ölçüm sürerken canlı durum etiketi (sayfa yeniden kurulmadan güncellenir)
        self.failure = None     # son oyun ölçümü başarısızsa teşhis (presentmon.MeasureError.diag)
        self.choices = []       # ölçülebilecek süreçler (presentmon.candidates)
        self.choice = None      # seçili exe
        self.game_seconds = 60
        self.limits = None      # sürücü FPS sınırı ve düşük gecikme modu (NVIDIA)
        self.cancel = threading.Event()

    def on_show(self, highlight=None):
        super().on_show(highlight)
        if not self.running:  # sayfa boştayken önceden kurulmuş olabilir: liste her gösterimde tazelenir
            self._refresh_choices(background=True)
            self._load_limits()

    def build(self):
        super().build()
        self.header.addWidget(w.title(t("ui.menu.olcum")))
        self.header.addWidget(w.label(t("olcum.aciklama"), muted=True))
        self.body.addWidget(w.banner(t("olcum.durustluk"), "uyari"))
        self._system_card()
        self._game_card()
        self.status = None
        if self.running:
            bar = QProgressBar()
            bar.setRange(0, 0)
            self.body.addWidget(bar)
            self.status = w.label(self.progress_text, muted=True)
            self.body.addWidget(self.status)
            if self.running == "oyun":
                self.body.addWidget(w.hbox(None, w.button(t("olcum.durdur"), self.cancel.set)))
        self._comparison()
        self._list()

    # ------------------------------------------------------------------ sistem ölçümü
    def _label_combo(self):
        combo = QComboBox()
        for key in LABELS:
            combo.addItem(t(f"olcum.etiket.{key}"), key)
        combo.setFixedWidth(140)
        return combo

    def _system_card(self):
        card = w.Card()
        head = QLabel(t("olcum.sistem_baslik"))
        head.setObjectName("CardTitle")
        card.lay.addWidget(head)
        card.lay.addWidget(w.label(t("olcum.sistem_aciklama"), muted=True, size=12))
        label = self._label_combo()
        seconds = QComboBox()
        for value in (30, 60, 120):
            seconds.addItem(t("olcum.saniye", sn=value), value)
        start = w.button(t("olcum.baslat"), lambda: self._run_system(label.currentData(), seconds.currentData()),
                         primary=True)
        start.setEnabled(self.running is None)
        card.lay.addWidget(w.hbox(w.label(t("olcum.etiket_sec"), wrap=False), label,
                                  w.label(t("olcum.bosta_sure"), wrap=False), seconds, None, start))
        self.body.addWidget(card)

    def _run_system(self, label, seconds):
        self.running = "sistem"
        self.progress_text = t("olcum.sistem_suruyor", sn=seconds)
        self.data_reloaded()
        system = self.c.engine.system
        factory = self.app.live_sampler_factory or _default_sampler

        def progress(done, total):
            self.app.worker.call_soon(self._progress, t("olcum.sistem_ilerleme", sn=done, toplam=total))

        def done(result):
            values, details = result
            item = self.store.add("sistem", label, values, details)
            self.running = None
            self.app.set_status(t("olcum.kaydedildi"), "iyi")
            self._auto_select(item)

        self.app.worker.run(lambda: system_measure.measure(system, factory, seconds, progress), done,
                            self._failed, serial=False)

    # ------------------------------------------------------------------ oyun ölçümü
    def _refresh_choices(self, rebuild=True, background=False):
        """Çalışan pencereli süreçler + kayıtlı oyunlar; ön plandaki pencere ve çalışan oyunlar başta.
        background: pencereler arka planda okunur, sayfa yalnızca liste değiştiyse yeniden kurulur."""
        games = list(self.app.game_store.games)

        def read():
            try:
                return presentmon.candidates(games)
            except Exception as exc:  # noqa: BLE001 - liste sessizce boş kalmasın: kayıtlı oyunlar yine listelenir
                _log.warning("Süreç listesi okunamadı: %s", exc)
                return presentmon.candidates(games, _NoDesktop())

        def done(found):
            changed = found != self.choices
            self.choices = found
            if self.choice is None or all(c["exe"] != self.choice for c in found):
                self.choice = next((c["exe"] for c in found if c["oyun"] and c["calisiyor"]), None)
            if rebuild and changed and not self.running:
                self.data_reloaded()

        if background:
            self.app.worker.run(read, done, lambda _e: None, serial=False)
        else:
            done(read())

    def _load_limits(self):
        """Uygulanmış NVIDIA sürücü FPS sınırı ve düşük gecikme modu: ölçülen FPS'i doğrudan etkiler."""
        specs = {tid: self.c.by_id[tid]["nvidia"] for tid in ("GPU-007", "GPU-002") if tid in self.c.by_id}
        system = self.c.engine.system
        if len(specs) < 2 or not getattr(system, "nvidia_available", lambda: False)():
            return

        def read():
            return system.get_nvidia_settings([int(spec["ayar"], 16) for spec in specs.values()])

        def done(values):
            def label(tid):
                spec = specs[tid]
                info = (values or {}).get(int(spec["ayar"], 16))
                value = info["deger"] if info and info.get("ozel") else None
                if value is None:
                    return next((o["etiket"] for o in spec["secenekler"] if o.get("varsayilan")), "—"), 0
                return next((o["etiket"] for o in spec["secenekler"] if o["deger"] == value), str(value)), value
            self.limits = {"fps": label("GPU-007"), "gecikme": label("GPU-002")[0]}
            if self.built and not self.running:
                self.data_reloaded()
        self.app.worker.run(read, done, lambda _e: None, serial=False)

    def _choice_label(self, item):
        name = item["oyun"] or item["baslik"] or item["exe"]
        state = (t("olcum.surec_on_planda") if item["on_planda"] else
                 t("olcum.surec_calisiyor") if item["calisiyor"] else t("olcum.surec_calismiyor"))
        star = "★ " if item["oyun"] else ""
        return f"{star}{name} — {item['exe']} ({state})"

    def _game_card(self):
        card = w.Card()
        head = QLabel(t("olcum.oyun_baslik"))
        head.setObjectName("CardTitle")
        card.lay.addWidget(head)
        card.lay.addWidget(w.label(t("olcum.oyun_aciklama"), muted=True, size=12))
        exe = presentmon.find_presentmon()
        if not exe:
            card.lay.addWidget(w.colored(t("olcum.presentmon_yok"), "uyari"))
            self.body.addWidget(card)
            return
        label = self._label_combo()
        process = QComboBox()
        process.setEditable(True)  # arama: yazdıkça süzülür; listede olmayan bir exe adı da yazılabilir
        process.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        for item in self.choices:
            process.addItem(self._choice_label(item), item["exe"])
        process.completer().setFilterMode(Qt.MatchFlag.MatchContains)
        process.completer().setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        index = process.findData(self.choice)
        process.setCurrentIndex(index if index >= 0 else -1)
        if index < 0:
            process.setEditText("")
        process.lineEdit().setPlaceholderText(t("olcum.surec_ara"))
        process.setMinimumWidth(320)
        process.activated.connect(lambda i: setattr(self, "choice", process.itemData(i)))
        seconds = QComboBox()
        for value in (30, 60, 90, 120):
            seconds.addItem(t("olcum.saniye", sn=value), value)
        seconds.setCurrentIndex(max(0, seconds.findData(self.game_seconds)))
        refresh = w.button(t("olcum.liste_yenile"), lambda: self._refresh_choices())
        refresh.setEnabled(self.running is None)

        def chosen():
            text = process.currentText().strip()
            if process.currentIndex() >= 0 and text == process.itemText(process.currentIndex()):
                return process.currentData()
            name = text.split(" — ")[-1].split(" (")[0].strip() if " — " in text else text
            return (name if name.lower().endswith(".exe") else name + ".exe") if name else None

        def start_game():
            name = chosen()
            if not name:
                process.setFocus()
                return
            self.choice = name
            self.game_seconds = seconds.currentData()
            if anti_cheat_game(self.app.game_store.games, name):  # canlı FPS'i kapattıran aynı ETW yöntemi
                self.app.set_status(t("ui.canli_fps.oyunda_kapali"), "sorun")
                return
            # imza denetimi (PowerShell) arayüzü dondurmasın: işçi iş parçacığında
            etiket = label.currentData()  # sayfa o sırada yeniden kurulursa kutu silinmiş olabilir
            self.app.worker.run(lambda: driver_tools.verify(exe), lambda check: signed(etiket, name, check),
                                lambda e: self.app.set_status(str(e), "sorun"), serial=False)

        def signed(etiket, name, check):
            if self.running is not None:  # çift tıklama: ikinci ölçüm başlamasın
                return
            if not check["imza_gecerli"] or driver_tools.tools_in_user_folder():
                # yönetici olarak çalışacak üçüncü parti exe: imzasızsa veya tools kullanıcı klasöründeyse sor
                if not dialogs.ask_yes_no(self.app, t("ui.dikkat"), tool_check_text(check)):
                    return
            self._run_game(etiket, name, self.game_seconds, check["sha256"], exe)

        start = w.button(t("olcum.baslat"), start_game, primary=True)
        start.setEnabled(self.running is None and self.c.can_modify)
        card.lay.addWidget(w.hbox((process, 1), refresh))
        card.lay.addWidget(w.hbox(w.label(t("olcum.etiket_sec"), wrap=False), label, seconds, None, start))
        foreground = next((c for c in self.choices if c["on_planda"]), None)
        if foreground and foreground["exe"] != self.choice and self.running is None:
            suggest = w.button(t("olcum.on_plan_oner", ad=foreground["oyun"] or foreground["baslik"] or foreground["exe"]),
                               lambda: (setattr(self, "choice", foreground["exe"]), self.data_reloaded()))
            card.lay.addWidget(w.hbox(suggest, None))
        if self.limits:
            fps_text, fps_value = self.limits["fps"]
            text = t("olcum.sinir", fps=fps_text, gecikme=self.limits["gecikme"])
            card.lay.addWidget(w.colored(text + " " + t("olcum.sinir_uyari", fps=fps_value), "uyari")
                               if fps_value else w.label(text, muted=True, size=12))
        card.lay.addWidget(w.label(t("olcum.oyun_ipucu", sn=presentmon.COUNTDOWN_SN), muted=True, size=12))
        card.lay.addWidget(w.label(t("olcum.not_ac_tam_ekran"), muted=True, size=12))
        self.body.addWidget(card)
        if self.failure:
            self.body.addWidget(self._failure_card(start_game, seconds))

    def _failure_card(self, retry, seconds_combo):
        """'Yeterli kare yok' için açık teşhis: neyin izlendiği, ne yakalandığı, ne yapılmalı."""
        diag = self.failure
        card = w.Card(spacing=6)
        title = QLabel(t("olcum.hata_baslik"))
        title.setObjectName("CardTitle")
        card.lay.addWidget(title)
        reason = diag.get("neden", "on_plan")
        card.lay.addWidget(w.colored(t(f"olcum.neden.{reason}"), "sorun"))
        rows = [(t("olcum.teshis.surec"), diag.get("surec", "—")),
                (t("olcum.teshis.calisiyor"), t("olcum.evet_pid", pid=", ".join(map(str, diag["pidler"])))
                 if diag.get("pidler") else t("olcum.hayir")),
                (t("olcum.teshis.kare"), t("olcum.teshis.kare_deger", hedef=diag.get("kare_hedef", 0),
                                           on=diag.get("kare_on_planda", 0), dwm=diag.get("kare_dwm", 0),
                                           en_az=presentmon.MIN_FRAMES)),
                (t("olcum.teshis.on_plan"), t("olcum.saniye", sn=diag.get("on_plan_sn", 0))),
                (t("olcum.teshis.yontem"), diag.get("yontem", "—"))]
        if diag.get("sunum_modu"):
            rows.append((t("olcum.teshis.sunum"), diag["sunum_modu"]))
        for key, value in rows:
            card.lay.addWidget(w.label(f"<b>{key}:</b> {value}", size=12))
        if diag.get("ozel_tam_ekran"):
            card.lay.addWidget(w.colored(t("olcum.ozel_tam_ekran"), "uyari"))
        card.lay.addWidget(w.label(t("olcum.cozum"), size=12))

        def longer():
            index = min(seconds_combo.currentIndex() + 1, seconds_combo.count() - 1)
            seconds_combo.setCurrentIndex(index)
            self.game_seconds = seconds_combo.currentData()
            retry()

        def copy():
            QApplication.clipboard().setText(presentmon.diagnosis_text(diag))
            self.app.set_status(t("olcum.log_kopyalandi"), "iyi")

        def close():
            self.failure = None
            self.data_reloaded()

        card.lay.addWidget(w.flow(w.button(t("olcum.yeniden_dene"), retry, primary=True),
                                  w.button(t("olcum.sureyi_uzat"), longer),
                                  w.button(t("olcum.log_kopyala"), copy), w.button(t("olcum.kapat"), close)))
        return card

    def _run_game(self, label, process_name, seconds, sha256=None, exe=None):
        self.running = "oyun"
        self.failure = None
        self.cancel.clear()
        self.progress_text = t("olcum.geri_sayim", sn=presentmon.COUNTDOWN_SN, surec=process_name)
        self.data_reloaded()
        motion.set_paused(True)  # ölçüm sürerken animasyon yok
        self.app.showMinimized()  # oyuna dönmek kolay olsun; bitince odak çalınmaz, görev çubuğu yanıp söner
        limits = dict(self.limits or {})

        def progress(stage, info):
            if stage == "geri_sayim":
                text = t("olcum.geri_sayim", sn=info["kalan"], surec=process_name)
            elif not info["calisiyor"]:
                text = t("olcum.oyun_calismiyor", surec=process_name)
            elif not info["on_planda"]:
                text = t("olcum.oyuna_don", surec=process_name, sn=round(info["sayilan"]), toplam=info["toplam"])
            else:
                text = t("olcum.oyun_suruyor", surec=process_name, sn=round(info["sayilan"]), toplam=info["toplam"])
            self.app.worker.call_soon(self._progress, text)

        def finish():
            self.running = None
            motion.set_paused(False)
            QApplication.alert(self.app, 0)

        def done(result):
            values, details = result
            if limits:
                details["fps_siniri"], details["dusuk_gecikme"] = limits["fps"][0], limits["gecikme"]
            item = self.store.add("oyun", label, values, details, note=process_name)
            finish()
            self.app.set_status(t("olcum.kaydedildi"), "iyi")
            self._auto_select(item)

        def failed(exc):
            finish()
            if isinstance(exc, presentmon.MeasureError):
                if exc.code != "iptal":
                    self.failure = exc.diag
                self.data_reloaded()
                return
            self._failed(exc)

        self.app.worker.run(lambda: presentmon.capture(process_name, seconds, exe, sha256, progress=progress,
                                                       cancel=self.cancel.is_set), done, failed, serial=False)

    def _progress(self, text):
        self.progress_text = text
        if self.status is not None:
            self.status.setText(text)

    def _failed(self, exc):
        self.running = None
        key = {"az_kare": "olcum.hata_az_kare", "presentmon_yok": "olcum.presentmon_yok"}.get(str(exc), "olcum.hata")
        dialogs.show_message(self.app, t("ui.hata_baslik"), t(key), "sorun")
        self.data_reloaded()

    # ------------------------------------------------------------------ liste ve karşılaştırma
    def _auto_select(self, item):
        """Yeni "Sonra" ölçümü, aynı türdeki en yeni "Önce" ile otomatik karşılaştırılır."""
        if item["etiket"] == "sonra":
            before = next((m for m in self.store.items if m["tur"] == item["tur"] and m["etiket"] == "once"), None)
            if before:
                self.selected = [before["id"], item["id"]]
        self.data_reloaded()

    def _toggle(self, item_id, on):
        if on and item_id not in self.selected:
            self.selected = (self.selected + [item_id])[-2:]
        elif not on and item_id in self.selected:
            self.selected.remove(item_id)
        self.data_reloaded()

    def _list(self):
        self.body.addWidget(w.section_title(t("olcum.liste")))
        if not self.store.items:
            self.body.addWidget(w.label(t("olcum.liste_bos"), muted=True))
        for item in self.store.items:
            card = w.Card(layout="h", spacing=10)
            box = QCheckBox()
            box.setChecked(item["id"] in self.selected)
            box.toggled.connect(lambda on, i=item["id"]: self._toggle(i, on))
            card.lay.addWidget(box)
            metrics = SYSTEM_METRICS if item["tur"] == "sistem" else GAME_METRICS
            summary = ", ".join(t("olcum.kisa." + m) + " " + _fmt(m, item["degerler"][m]) for m in metrics
                                if m in item["degerler"])
            title = t("olcum.tur." + item["tur"]) + " — " + t("olcum.etiket." + item["etiket"])
            if item.get("not"):
                title += f" — {item['not']}"
            when = fmt_date(item["zaman"])
            text = w.label(f"<b>{title}</b><br>{when} · {summary}", size=12)
            card.lay.addWidget(text, 1)
            card.lay.addWidget(w.button(t("olcum.sil"), lambda _=False, i=item["id"]: self._delete(i)))
            self.body.addWidget(card)

    def _delete(self, item_id):
        if dialogs.ask_yes_no(self.app, t("olcum.sil"), t("olcum.sil_soru")):
            self.store.remove(item_id)
            self.selected = [i for i in self.selected if i != item_id]
            self.data_reloaded()

    def _pair(self):
        items = [self.store.get(i) for i in self.selected]
        items = [i for i in items if i]
        if len(items) != 2:
            return None
        return tuple(sorted(items, key=lambda m: m["zaman"]))

    def _comparison(self):
        self.body.addWidget(w.section_title(t("olcum.karsilastirma")))
        pair = self._pair()
        if not pair:
            self.body.addWidget(w.label(t("olcum.karsilastirma_sec"), muted=True))
            return
        before, after = pair
        rows = compare(before, after)
        card = w.Card(spacing=4)
        if before["tur"] != after["tur"]:
            card.lay.addWidget(w.colored(t("olcum.farkli_tur"), "uyari"))
        header = [w.label(t("olcum.sutun.metrik"), bold=True), w.label(t("olcum.sutun.once"), bold=True),
                  w.label(t("olcum.sutun.sonra"), bold=True), w.label(t("olcum.sutun.fark"), bold=True)]
        if rows:
            card.lay.addWidget(w.label(self._verdict(rows), bold=True))
        table = QWidget()
        table_lay = QVBoxLayout(table)
        table_lay.setContentsMargins(0, 0, 0, 0)
        table_lay.setSpacing(4)
        table.setVisible(False)  # sonuç cümlesi önde, rakamlar isteyene
        toggle = w.button(t("olcum.detay_goster"), lambda: None)
        toggle.clicked.connect(lambda: (table.setVisible(not table.isVisible()), toggle.setText(
            t("olcum.detay_gizle") if table.isVisible() else t("olcum.detay_goster"))))
        card.lay.addWidget(w.hbox(toggle, None))
        card.lay.addWidget(table)
        table_lay.addWidget(self._row(header))
        for metric, a, b, diff, pct, better in rows:
            tone = {True: "iyi", False: "sorun", None: None}[better]
            change = (_fmt(metric, round(diff, 2)) if diff else "0") + ("" if pct is None else f"  ({'+' if pct > 0 else ''}{fmt_percent(pct, 1)})")
            cells = [w.label(t(f"olcum.metrik.{metric}")), w.label(_fmt(metric, a)), w.label(_fmt(metric, b)),
                     w.colored(change, tone) if tone else w.label(change, muted=True)]
            for cell in cells[1:]:
                theme.tabular(cell)  # FPS / ms sütunları hizalı kalır
            table_lay.addWidget(self._row(cells))
        if not rows:
            card.lay.addWidget(w.label(t("olcum.ortak_yok"), muted=True))
        card.lay.addWidget(w.hbox(None, w.button(t("olcum.rapor_kaydet"), lambda: self._save_report(before, after))))
        self.body.addWidget(card)

    @staticmethod
    def _verdict(rows):
        """Tek cümlelik sonuç; %3'ten küçük değişim ölçüm gürültüsü sayılır."""
        good = sum(1 for r in rows if r[5] is True and r[4] is not None and abs(r[4]) >= 3)
        bad = sum(1 for r in rows if r[5] is False and r[4] is not None and abs(r[4]) >= 3)
        if good and bad:
            return t("olcum.sonuc.karisik", iyi=good, kotu=bad)
        if good:
            return t("olcum.sonuc.iyi", n=good)
        if bad:
            return t("olcum.sonuc.kotu", n=bad)
        return t("olcum.sonuc.fark_yok")

    @staticmethod
    def _row(cells):
        for cell, width in zip(cells, (300, 150, 150, 220)):
            cell.setMinimumWidth(width)
            cell.setMaximumWidth(int(width * 1.4))
        return w.hbox(*cells, None)

    def _save_report(self, before, after):
        name = "olcum_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + ".txt"
        path = paths.reports_dir() / name
        try:
            path.write_text(report_text(before, after), encoding="utf-8")
        except OSError:
            dialogs.show_message(self.app, t("ui.hata_baslik"), t("ui.bakim.dosya_yazilamadi"), "sorun")
            return
        self.app.set_status(t("olcum.rapor_kaydedildi", dosya=name), "iyi")
        os.startfile(paths.reports_dir())


def _default_sampler():
    from app.scan.live import LiveSampler  # noqa: WPS433
    return LiveSampler(with_processes=False)


class _NoDesktop:
    """Pencere listesi okunamazsa: yalnızca kayıtlı oyunlar listelenir."""

    def processes(self):
        return []

    def windows(self):
        return {}

    def foreground(self):
        return 0
