"""Boost: ana ekranda tek büyük düğme (hazır güvenli kümeyi + kullanıcının listesini kapatır, sonucu ÖLÇÜP yazar);
program seçimi, liste ve bellek tablosu "Gelişmiş" katlanır bölümünde (ADIM 2-3).

Bellek "temizleme" yok: Windows belleği kendi yönetir ve çalışan programların belleğini zorla boşaltan araçlar
genelde yavaşlatır (katalogda PLC-001, zararlı). Gerçek kazanç, gerekmeyen bir programı KAPATMAKTIR; sonraki adımlar
bunu kullanıcı onayıyla yapar (kapatma, Boost listesi, oyun açılınca otomatik). Rakamlar çalışma kümesidir
(Working Set): birden çok sürecin toplamıdır, paylaşılan bellek çift sayılabilir.
"""

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from app.core import settings
from app.core.i18n import fmt_number, t
from app.engine import boost, closer
from app.scan import software
from app.ui import dialogs, motion, theme, widgets as w

# Tek tuş Boost'un açtığı ayarlar: yalnızca ölçülmüş ya da belgeli, güvenli ve geri alınabilir olanlar (Oyun Modu, Game DVR).
# Bellek boşaltma, pano silme ve servis/Windows Update durdurma BİLEREK yok (docs/KANIT_INCELEMESI.md).
BOOST_TWEAKS = ("PERF-001", "PERF-002")


class BoostPage(w.Page):
    def __init__(self, app):
        super().__init__(app)
        self.data = None
        self.loading = False
        self._opened = []       # bu Boost'ta açılan ayarlar
        self.advanced_open = False
        self.busy = False       # Boost çalışırken ikinci tıklama yok
        self.last = None        # son Boost sonucu (yalnızca bellekte): {"metin": ..., "kapanan": [...], "ton": ...}
        self._boost_button = None

    def on_show(self, highlight=None):
        self.ensure_built()
        if self.data is None and not self.loading:
            self.refresh()

    def refresh(self):
        self.loading = True
        self.app.worker.run(self._collect, self._loaded, self._failed, serial=False)
        self.data_reloaded()

    def _collect(self):
        data = software.collect_processes()
        data["hedefler"] = boost.targets(data.get("bilinen_arka_plan"), self._listed().values())
        return data

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
        if self.data is not None:
            self.data["hedefler"] = boost.targets(self.data.get("bilinen_arka_plan"), listed.values())
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

    def _targets(self):
        return (self.data or {}).get("hedefler") or []

    def _boost(self):
        if self.busy:
            return
        names = [row["ad"] for row in self._targets()]
        self.app.worker.run(lambda: closer.running(names), self._confirm_boost, self._boost_failed, serial=False)

    def _boost_failed(self, _exc):
        self.busy = False
        self.app.set_status(t("ui.boost.kapatilamadi", ad="Boost"), "sorun")

    def _confirm_boost(self, running):
        tweaks = self._pending_tweaks()
        if not running and not tweaks:
            self.app.set_status(t("ui.boost.zaten"), "iyi")
            return
        parts = []
        if running:
            parts.append(t("ui.boost.onizleme", liste=self._names_text(running)))
        if tweaks:
            parts.append(t("ui.boost.tek_ayarlar", liste=", ".join(tw["ad"] for tw in tweaks)))
        if running:
            parts.append(t("ui.boost.tek_not"))
        if not dialogs.ask_yes_no(self.app, t("ui.boost.boost_et"), "\n\n".join(parts), yes_text=t("ui.boost.boost_et"),
                                  no_text=t("ui.vazgec")):
            return
        self._opened = []
        self.busy = True
        if self._boost_button is not None:
            self._boost_button.setEnabled(False)
        self._apply_tweaks(tweaks, lambda: self._close_listed(running))

    def _close_listed(self, running):
        settings.set("boost_ayarlari", sorted(set(self._boost_ids()) | set(self._opened)))
        if not running:
            self._boost_done(None)
            return
        self.app.set_status(t("ui.boost.kapatiliyor", ad=self._names_text(running)), "bilgi")

        def job():
            run = boost.Run(running)  # önce-ölçüm kapatmadan hemen önce alınır
            return run, run.close()
        self.app.worker.run(job, self._closed_all, self._boost_failed, serial=False)

    def _closed_all(self, outcome):
        run, stuck = outcome
        if stuck and dialogs.ask_yes_no(self.app, t("ui.dikkat"), t("ui.boost.toplu_zorla_soru", liste=", ".join(stuck)),
                                        yes_text=t("ui.boost.zorla"), no_text=t("ui.vazgec")):
            self.app.worker.run(lambda: (run.force(stuck), run.result())[1], self._boost_done, self._boost_failed,
                                serial=False)
            return
        self.app.worker.run(run.result, self._boost_done, self._boost_failed, serial=False)

    @staticmethod
    def _names_text(names, limit=6):
        text = ", ".join(names[:limit])
        return text + (" " + t("ui.boost.ve_daha", n=len(names) - limit) if len(names) > limit else "")

    @staticmethod
    def _memory_text(mb):
        return t("ui.boost.gb", gb=fmt_number(mb / 1024, 1)) if mb >= 1024 else t("ui.boost.mb", mb=fmt_number(mb, 0))

    def result_text(self, result, opened):
        """Tek satırlık sonuç: yalnızca ölçülen sayılar; boşalan bellek ölçülemediyse (fark yok) o cümle yazılmaz."""
        parts = []
        if result is not None:
            adet = len(result["kapanan"])
            if result["bosalan_mb"]:
                parts.append(t("ui.boost.sonuc_bellek", adet=adet, bellek=self._memory_text(result["bosalan_mb"])))
            else:
                parts.append(t("ui.boost.sonuc_bellek_yok", adet=adet))
            if result["acik"]:
                parts.append(t("ui.boost.sonuc_acik", adet=len(result["acik"])))
        if opened:
            parts.append(t("ui.boost.sonuc_ayar", adet=opened))
        return " ".join(parts)

    def _boost_done(self, result):
        opened = len(self._opened)
        self._opened = []
        self.busy = False
        text = self.result_text(result, opened)
        tone = "uyari" if result and result["acik"] else "iyi"
        self.last = {"metin": text, "kapanan": (result or {}).get("kapanan") or [], "ton": tone,
                     "bellek": bool(result and result["bosalan_mb"])}
        self.app.set_status(text, tone)
        if tone == "iyi":
            self.app.toast.show_text(text, ms=6000)
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
        self.header.addWidget(w.hbox(w.title(t("ui.menu.boost")), None, w.button(t("ui.boost.yenile"), self.refresh)))
        self.header.addWidget(w.label(t("ui.boost.aciklama"), muted=True))
        self.body.addWidget(self._hero())
        advanced = self._advanced()
        advanced.setVisible(False) if not self.advanced_open else None  # açıkken görünürlüğe dokunulmaz (ebeveynsiz setVisible(True) üst pencere olur)
        toggle = w.button(t("ui.boost.gelismis_gizle") if self.advanced_open else t("ui.boost.gelismis_goster"),
                          lambda: self._toggle_advanced(toggle, advanced))
        self.body.addWidget(w.hbox(toggle, None))
        self.body.addWidget(advanced)

    def _toggle_advanced(self, toggle, box):
        self.advanced_open = not self.advanced_open
        toggle.setText(t("ui.boost.gelismis_gizle") if self.advanced_open else t("ui.boost.gelismis_goster"))
        motion.expand(box, self.advanced_open)

    def _hero(self):
        """Tek büyük düğme; üstünde tek satır önizleme, altında son sonucun büyük, açık yazısı."""
        card = w.Card(spacing=12)
        targets = self._targets()
        if self.loading and not self.data:
            preview = w.label(t("ui.boost.okunuyor"), muted=True)
        elif targets:
            preview = w.label(t("ui.boost.onizleme", liste=self._names_text([row["ad"] for row in targets])), plain=True)
        else:
            preview = w.label(t("ui.boost.hedef_yok"), muted=True)
        card.lay.addWidget(preview)
        tweaks = self._pending_tweaks()
        if tweaks:
            card.lay.addWidget(w.label(t("ui.boost.ayar_satir", liste=", ".join(tw["ad"] for tw in tweaks)), muted=True,
                                       size=12))
        button = w.button(t("ui.boost.boost_et"), self._boost, primary=True)
        button.setMinimumHeight(56)
        button.setFont(theme.ui_font(18, True))
        button.setEnabled(self.c.can_modify and not self.busy and not (self.loading and not self.data))
        self._boost_button = button
        buttons = [None]
        if self._boost_ids():
            undo = w.button(t("ui.boost.geri_al"), self._undo_boost)
            undo.setEnabled(self.c.can_modify)
            buttons.append(undo)
        card.lay.addWidget(button)
        if len(buttons) > 1:
            card.lay.addWidget(w.hbox(*buttons))
        if self.last:
            result = w.colored(self.last["metin"], self.last["ton"])
            result.setFont(theme.ui_font(18, True))
            card.lay.addWidget(result)
            if self.last["kapanan"]:
                card.lay.addWidget(w.label(t("ui.boost.kapanan_liste", liste=self._names_text(self.last["kapanan"])),
                                           muted=True, size=12, plain=True))
            if self.last["bellek"]:
                card.lay.addWidget(w.label(t("ui.boost.sonuc_not"), muted=True, size=12))
            card.lay.addWidget(w.label(t("ui.boost.sonuc_not_kisa"), muted=True, size=12))
        return card

    def _advanced(self):
        """Gelişmiş: Boost listesi, bellek durumu ve tek tek program kapatma (eski Boost ekranı)."""
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)
        memory = (((self.c.scan or {}).get("bolumler") or {}).get("sistem") or {}).get("bellek") or {}
        lay.addWidget(self._boost_card())
        if memory:
            lay.addWidget(self._memory_card(memory))
        if self.loading:
            lay.addWidget(w.label(t("ui.boost.okunuyor"), muted=True))
            return box
        if not self.data:
            lay.addWidget(w.label(t("ui.boost.okunamadi"), muted=True))
            return box
        lay.addWidget(w.section_title(t("ui.boost.en_cok")))
        for row in self.data.get("en_cok_bellek") or []:
            lay.addWidget(self._row(row))
        background = self.data.get("bilinen_arka_plan") or []
        if background:
            lay.addWidget(w.section_title(t("ui.boost.gerekmeyebilir")))
            lay.addWidget(w.label(t("ui.boost.gerekmeyebilir_aciklama"), muted=True, size=12))
            for row in background:
                lay.addWidget(self._row(row))
        return box

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
