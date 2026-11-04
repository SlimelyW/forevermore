"""Boost: oyundan önce hangi programlar ne kadar bellek tutuyor; gerekmeyeni onayla kapatma (ADIM 2);
Boost listesi ve tek tıkla Boost (ADIM 3).

Bellek "temizleme" yok: Windows belleği kendi yönetir ve çalışan programların belleğini zorla boşaltan araçlar
genelde yavaşlatır (katalogda PLC-001, zararlı). Gerçek kazanç, gerekmeyen bir programı KAPATMAKTIR; sonraki adımlar
bunu kullanıcı onayıyla yapar (kapatma, Boost listesi, oyun açılınca otomatik). Rakamlar çalışma kümesidir
(Working Set): birden çok sürecin toplamıdır, paylaşılan bellek çift sayılabilir.
"""

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QLabel

from app.core import settings
from app.core.i18n import fmt_number, t
from app.engine import closer
from app.scan import software
from app.ui import dialogs, theme, widgets as w

# Tek tuş Boost'un açtığı ayarlar: yalnızca ölçülmüş ya da belgeli, güvenli ve geri alınabilir olanlar (Oyun Modu, Game DVR).
# Bellek boşaltma, pano silme ve servis/Windows Update durdurma BİLEREK yok (docs/KANIT_INCELEMESI.md).
BOOST_TWEAKS = ("PERF-001", "PERF-002")


class BoostPage(w.Page):
    def __init__(self, app):
        super().__init__(app)
        self.data = None
        self.loading = False
        self._opened = []       # bu Boost'ta açılan ayarlar

    def on_show(self, highlight=None):
        self.ensure_built()
        if self.data is None and not self.loading:
            self.refresh()

    def refresh(self):
        self.loading = True
        self.app.worker.run(software.collect_processes, self._loaded, self._failed, serial=False)
        self.data_reloaded()

    def _loaded(self, data):
        self.loading, self.data = False, data
        self.data_reloaded()

    def _failed(self, _exc):
        self.loading, self.data = False, {}
        self.data_reloaded()

    # ------------------------------------------------------------------ Boost listesi
    def _listed(self):
        return {name.lower(): name for name in settings.get("boost_listesi") or []}

    def _toggle_listed(self, name, on):
        listed = self._listed()
        listed[name.lower()] = name
        if not on:
            listed.pop(name.lower())
        settings.set("boost_listesi", sorted(listed.values(), key=str.lower))
        position = self.scroll.verticalScrollBar().value()
        self.data_reloaded()  # liste kartı güncellensin; kaydırma konumu korunur
        QTimer.singleShot(0, lambda: self.scroll.verticalScrollBar().setValue(position))

    def _boost_card(self):
        names = sorted(self._listed().values(), key=str.lower)
        card = w.Card(spacing=6)
        head = QLabel(t("ui.boost.liste_baslik"))
        head.setObjectName("CardTitle")
        card.lay.addWidget(head)
        if names:
            card.lay.addWidget(w.label(", ".join(names), plain=True))
        else:
            card.lay.addWidget(w.label(t("ui.boost.liste_bos"), muted=True))
        card.lay.addWidget(w.label(t("ui.boost.liste_not"), muted=True, size=12))
        card.lay.addWidget(w.label(t("ui.boost.tek_kart"), muted=True, size=12))
        button = w.button(t("ui.boost.boost_et"), self._boost, primary=True)
        button.setEnabled(self.c.can_modify)
        buttons = [None]
        if self._boost_ids():
            undo = w.button(t("ui.boost.geri_al"), self._undo_boost)
            undo.setEnabled(self.c.can_modify)
            buttons.append(undo)
        card.lay.addWidget(w.hbox(*buttons, button))
        return card

    # ------------------------------------------------------------------ Boost'un açtığı ayarlar
    def _pending_tweaks(self):
        """Boost'un açacağı, bu bilgisayarda görünen ve henüz açık olmayan ayarlar."""
        result = []
        for tweak_id in BOOST_TWEAKS:
            tweak, state = self.c.by_id.get(tweak_id), self.c.states.get(tweak_id)
            avail = self.c.availability.get(tweak_id)
            if tweak and state and not state.is_on and not (avail is not None and not avail.visible):
                result.append(tweak)
        return result

    def _boost_ids(self):
        """Boost'un açtığı ve hâlâ Değişiklikler'de duran ayarlar (geri alınabilir)."""
        return [i for i in settings.get("boost_ayarlari") or [] if self.c.engine.store.has(i)]

    def _apply_tweaks(self, tweaks, then):
        if not tweaks:
            then()
            return
        first, rest = tweaks[0], tweaks[1:]

        def done():
            if self.c.states.get(first["id"]) and self.c.states[first["id"]].is_on:
                self._opened.append(first["id"])
            self._apply_tweaks(rest, then)

        self.app.toggle(first, True, done)

    def _undo_boost(self):
        ids = self._boost_ids()
        settings.set("boost_ayarlari", [])

        def next_one():
            if ids:
                self.app.revert(ids.pop(0), next_one)
            else:
                self.app.set_status(t("ui.boost.geri_alindi", adet=count), "iyi")
                self.data_reloaded()

        count = len(ids)
        next_one()

    def _boost(self):
        names = sorted(self._listed().values(), key=str.lower)
        self.app.worker.run(lambda: closer.running(names), self._confirm_boost,
                            lambda _exc: self.app.set_status(t("ui.boost.kapatilamadi", ad="Boost"), "sorun"),
                            serial=False)

    def _confirm_boost(self, running):
        tweaks = self._pending_tweaks()
        if not running and not tweaks:
            self.app.set_status(t("ui.boost.zaten"), "iyi")
            return
        parts = [t("ui.boost.tek_baslik")]
        if tweaks:
            parts.append(t("ui.boost.tek_ayarlar", liste="\n".join("• " + tw["ad"] for tw in tweaks)))
        if running:
            parts.append(t("ui.boost.tek_programlar", liste="\n".join("• " + name for name in running)))
        if running:
            parts.append(t("ui.boost.tek_not"))
        if not dialogs.ask_yes_no(self.app, t("ui.dikkat"), "\n\n".join(parts)):
            return
        self._opened = []
        self._apply_tweaks(tweaks, lambda: self._close_listed(running))

    def _close_listed(self, running):
        settings.set("boost_ayarlari", sorted(set(self._boost_ids()) | set(self._opened)))
        if not running:
            self._boost_done([], [])
            return
        self.app.set_status(t("ui.boost.kapatiliyor", ad=", ".join(running)), "bilgi")
        self.app.worker.run(lambda: closer.close_many(running), self._boosted,
                            lambda _exc: self.app.set_status(t("ui.boost.kapatilamadi", ad="Boost"), "sorun"),
                            serial=False)

    def _boosted(self, results):
        stuck = [name for name, result in results.items() if result == "calisiyor"]
        closed = [name for name, result in results.items() if result in ("kapandi", "yok")]
        if stuck and dialogs.ask_yes_no(self.app, t("ui.dikkat"), t("ui.boost.toplu_zorla_soru", liste=", ".join(stuck)),
                                        yes_text=t("ui.boost.zorla"), no_text=t("ui.vazgec")):
            self.app.worker.run(lambda: [closer.kill(name) for name in stuck],
                                lambda _killed: self._boost_done(closed + stuck, []),
                                lambda _exc: self.app.set_status(t("ui.boost.kapatilamadi", ad="Boost"), "sorun"),
                                serial=False)
            return
        self._boost_done(closed, stuck)

    def _boost_done(self, closed, left):
        opened = len(getattr(self, "_opened", []))
        self.app.set_status(t("ui.boost.tek_sonuc", ayar=opened, kapanan=len(closed), acik=len(left)), "uyari" if left else "iyi")
        self._opened = []
        self.refresh()

    def _close(self, row):
        """Onay -> nazikçe kapat -> kapanmazsa ikinci onayla zorla sonlandır. Korumalı programlar kapatılmaz."""
        name = row["ad"]
        if not dialogs.ask_yes_no(self.app, t("ui.dikkat"), t("ui.boost.kapat_soru", ad=name, adet=row["adet"])):
            return
        self.app.set_status(t("ui.boost.kapatiliyor", ad=name), "bilgi")
        self.app.worker.run(lambda: closer.close_gently(name), lambda result: self._closed(name, result),
                            lambda _exc: self.app.set_status(t("ui.boost.kapatilamadi", ad=name), "sorun"),
                            serial=False)

    def _closed(self, name, result):
        if result == "calisiyor":
            if dialogs.ask_yes_no(self.app, t("ui.dikkat"), t("ui.boost.zorla_soru", ad=name),
                                  yes_text=t("ui.boost.zorla"), no_text=t("ui.vazgec")):
                self.app.worker.run(lambda: closer.kill(name), lambda _n: self._finish(name, "zorla"),
                                    lambda _exc: self.app.set_status(t("ui.boost.kapatilamadi", ad=name), "sorun"),
                                    serial=False)
                return
            result = "acik"
        self._finish(name, result)

    def _finish(self, name, result):
        tone = "iyi" if result in ("kapandi", "zorla", "yok") else "uyari"
        self.app.set_status(t(f"ui.boost.sonuc.{result}", ad=name), tone)
        self.refresh()

    def build(self):
        super().build()
        self.header.addWidget(w.title(t("ui.menu.boost")))
        self.header.addWidget(w.label(t("ui.boost.aciklama"), muted=True))
        top = w.hbox(None, w.button(t("ui.boost.yenile"), self.refresh))
        self.header.addWidget(top)
        memory = (((self.c.scan or {}).get("bolumler") or {}).get("sistem") or {}).get("bellek") or {}
        self.body.addWidget(self._boost_card())
        if memory:
            self.body.addWidget(self._memory_card(memory))
        if self.loading:
            self.body.addWidget(w.label(t("ui.boost.okunuyor"), muted=True))
            return
        if not self.data:
            self.body.addWidget(w.label(t("ui.boost.okunamadi"), muted=True))
            return
        self.body.addWidget(w.section_title(t("ui.boost.en_cok")))
        for row in self.data.get("en_cok_bellek") or []:
            self.body.addWidget(self._row(row))
        background = self.data.get("bilinen_arka_plan") or []
        if background:
            self.body.addWidget(w.section_title(t("ui.boost.gerekmeyebilir")))
            self.body.addWidget(w.label(t("ui.boost.gerekmeyebilir_aciklama"), muted=True, size=12))
            for row in background:
                self.body.addWidget(self._row(row))

    def _memory_card(self, memory):
        card = w.Card(spacing=4)
        head = QLabel(t("ui.boost.bellek"))
        head.setObjectName("CardTitle")
        card.lay.addWidget(w.hbox(w.IconTile(theme.ICONS["boost"], theme.category_color("boost")), (head, 1), spacing=12))
        card.lay.addWidget(w.label(t("ui.boost.bellek_satir", yuzde=memory.get("kullanim_yuzde", 0),
                                     toplam=fmt_number(memory.get("toplam_gb", 0), 1))))
        card.lay.addWidget(w.label(t("ui.boost.onbellek_notu"), muted=True, size=12))
        return card

    def _row(self, row):
        parts = [(w.label(row["ad"] + (f" ×{row['adet']}" if row["adet"] > 1 else ""), bold=True, wrap=False, plain=True), 1)]
        if row.get("kategori"):
            parts.append(w.badge(t(f"surec_kategori.{row['kategori']}"), "notr"))
        parts.append(w.label(t("ui.boost.mb", mb=fmt_number(row["bellek_mb"], 0)), muted=True, wrap=False))
        if closer.is_protected(row["ad"]):
            parts.append(w.badge(t("ui.boost.korumali"), "notr"))
        else:
            switch = w.ToggleSwitch()
            switch.setChecked(row["ad"].lower() in self._listed())
            switch.setToolTip(t("ui.boost.listeye_ekle"))
            switch.toggled.connect(lambda on, n=row["ad"]: self._toggle_listed(n, on))
            button = w.button(t("ui.boost.kapat"), lambda _=False, r=row: self._close(r))
            button.setEnabled(self.c.can_modify)
            parts += [switch, button]
        card = w.Card(layout="h", margins=(14, 8, 14, 8))
        card.lay.addWidget(w.hbox(*parts, spacing=10), 1)
        return card
