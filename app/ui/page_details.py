"""PC Detayları: donanım, ekran kartları (hangisi oyunlarda kullanılır, hangi ekranı sürer),
ekranlar, depolama, güç ve en çok işlemci kullanan süreçler (canlı).

Bilgiler taramadan gelir (salt okunur). Seri numarası, kullanıcı adı gibi kişisel
bilgiler okunmaz (bkz. app/core/privacy.py).
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout

from app.core.i18n import fmt_number, fmt_percent, t, value_label
from app.scan import browser_ext
from app.scan.displays import label as display_label
from app.ui import dialogs, theme, widgets as w


def _card(glyph_key, heading, lines, extra=None, plain=False):
    """Simgeli bilgi kartı: başlık, satırlar ve isteğe bağlı rozetler."""
    card = w.Card(layout="h", spacing=12)
    card.lay.addWidget(w.IconTile(theme.ICONS[glyph_key], theme.category_color(glyph_key)), 0,
                       Qt.AlignmentFlag.AlignTop)
    text = QVBoxLayout()
    text.setSpacing(3)
    head = QLabel(heading)
    head.setObjectName("CardTitle")
    head.setWordWrap(True)
    text.addWidget(head)
    if extra:
        text.addWidget(w.hbox(*extra, None))
    for line in lines:
        if line:
            text.addWidget(w.label(line, muted=True, size=theme.SMALL_SIZE, selectable=True, plain=plain))
    text.addStretch(1)
    card.lay.addLayout(text, 1)
    return card


def display_name(display, index):
    return display_label(display, index)


class TopProcesses(w.Card):
    """En çok işlemci kullanan 5 süreç; canlı izlemeden beslenir."""

    def __init__(self):
        super().__init__(spacing=2)
        self.show_rows([])

    def show_rows(self, rows):
        lay = self.lay
        w.clear_layout(lay)
        head = QLabel(t("ui.canli.en_cok"))
        head.setObjectName("CardTitle")
        lay.addWidget(w.hbox((head, 1), w.label(t("ui.canli.islemci"), muted=True, size=12, wrap=False),
                             w.label(t("ui.canli.bellek"), muted=True, size=12, wrap=False)))
        if not rows:
            lay.addWidget(w.label(t("ui.canli.bekleniyor"), muted=True))
            return
        for row in rows[:5]:
            name = w.label(row["ad"], wrap=False)
            cpu = w.label(fmt_percent(row["cpu"], 1), wrap=False)
            mem = w.label(f"{fmt_number(row['bellek_mb'])} MB", muted=True, wrap=False)
            cpu.setMinimumWidth(70)
            mem.setMinimumWidth(90)
            cpu.setAlignment(Qt.AlignmentFlag.AlignRight)
            mem.setAlignment(Qt.AlignmentFlag.AlignRight)
            lay.addWidget(w.hbox((name, 1), cpu, mem))


class PcDetailsPage(w.Page):
    def __init__(self, app):
        super().__init__(app)
        self.top = None
        self.monitor = getattr(app, "live_monitor", None)
        if self.monitor is not None:
            self.monitor.sampled.connect(self._on_sample)

    # Sayfa görünürken canlı izleme çalışır (Özet sayfasıyla ortak; ikisi de kapanınca durur).
    def showEvent(self, event):
        super().showEvent(event)
        if self.monitor is not None:
            self.monitor.set_active(True, owner=self)

    def hideEvent(self, event):
        super().hideEvent(event)
        if self.monitor is not None:
            self.monitor.set_active(False, owner=self)

    def _on_sample(self, sample):
        if self.built and self.top is not None:
            try:
                self.top.show_rows(sample.get("en_cok") or [])
            except RuntimeError:  # sayfa yeniden kurulurken eski kart silinmiş olabilir
                pass

    def build(self):
        super().build()
        self.top = None
        self.header.addWidget(w.title(t("ui.menu.pc_detay")))
        self.header.addWidget(w.label(t("ui.pc_detay_aciklama"), muted=True))
        scan = self.c.scan
        if scan is None:
            self.body.addWidget(w.label(t("ui.taraniyor"), muted=True))
            return
        sections = scan["bolumler"]
        system, hw = sections.get("sistem") or {}, sections.get("donanim") or {}
        if hw:
            self._overview(system, hw)
            self._gpus(hw)
            self._displays(hw)
        self._others(sections, hw)
        self._browser_extensions()
        self.body.addWidget(w.section_title(t("ui.canli.baslik")))
        self.top = TopProcesses()
        self.body.addWidget(self.top)

    def _overview(self, system, hw):
        pc, cpu = hw["bilgisayar"], hw["cpu"]
        hero = w.Card(layout="h", spacing=14)
        hero.lay.addWidget(w.IconTile(theme.ICONS["pc_detay"], theme.category_color("pc_detay"), 52))
        text = QVBoxLayout()
        text.setSpacing(2)
        name = QLabel(f"{pc.get('uretici') or ''} {pc.get('model') or ''}".strip() or t("deger.bilinmiyor"))
        name.setObjectName("Hero")
        name.setWordWrap(True)
        text.addWidget(name)
        details = [t(f"deger.{pc['tur']}")]
        if system:
            win = system["windows"]
            details.append(f"{win['ad']} {win['surum_kodu']} (build {win['build']})")
        text.addWidget(w.label(" · ".join(details), muted=True))
        hero.lay.addLayout(text, 1)
        self.body.addWidget(hero)

        container, lay = w.grid(columns=2)
        cpu_lines = [t("ui.cpu_detay", cekirdek=cpu["cekirdek"], thread=cpu["is_parcacigi"])]
        if cpu.get("hibrit"):
            cpu_lines.append(t("ui.cpu_hibrit"))
        if cpu.get("x3d_cift_ccd"):
            cpu_lines.append(t("ui.cpu_x3d"))
        cards = [_card("CPU", cpu["ad"], cpu_lines)]
        ram = hw["ram"]
        if ram.get("moduller"):
            first = ram["moduller"][0]
            cards.append(_card("SYS", f"{ram['toplam_gb']} GB {first['tur']}", [
                t("deger.kanal_" + ram["kanal"]),
                t("ui.ram_hiz", hiz=first["calisan_hiz"], modul=first["modul_hizi"]),
                "XMP/EXPO: " + t("deger.xmp_" + ram["xmp_expo"]),
                t("rapor.bellek", yuzde=system["bellek"]["kullanim_yuzde"], bos=system["bellek"]["bos_gb"],
                  toplam=system["bellek"]["toplam_gb"]) if system else ""]))
        for i, card in enumerate(cards):
            lay.addWidget(card, i // 2, i % 2)
        self.body.addWidget(container)

    def _gpus(self, hw):
        gpus = hw.get("gpu") or []
        if not gpus:
            return
        self.body.addWidget(w.section_title(t("ui.kart.gpu_cogul") if len(gpus) > 1 else t("ui.kart.gpu")))
        displays = {d.get("aygit"): (i, d) for i, d in enumerate(hw.get("ekranlar") or [], 1)}
        # Oyunlarda kullanılan kart önce
        order = {"yuksek_performans": 0, "tek": 0, "guc_tasarrufu": 1}
        for gpu in sorted(gpus, key=lambda g: order.get(g.get("rol"), 2)):
            role = gpu.get("rol")
            extra = []
            if role:
                extra.append(w.badge(value_label("ui.gpu_rol_kisa", role),
                                     "iyi" if role in ("yuksek_performans", "tek") else "notr"))
            if gpu.get("birincil_ekran"):
                extra.append(w.badge(t("ui.birincil_ekran"), "bilgi"))
            lines = []
            if role:
                lines.append(t(f"ui.gpu_rol.{role}"))
            if gpu.get("vram_mb"):
                lines.append(t("ui.gpu_vram", gb=fmt_number(gpu["vram_mb"] / 1024, 1)))
            lines.append(t("ui.gpu_surucu", surum=gpu.get("surucu_surumu") or "—", tarih=gpu.get("surucu_tarihi") or "—"))
            driven = [display_name(displays[a][1], displays[a][0]) for a in gpu.get("ekran_suruyor") or []
                      if a in displays]
            if driven:
                lines.append(t("ui.gpu_suruyor", liste=", ".join(driven)))
            elif role == "yuksek_performans":
                lines.append(t("ui.gpu_ekran_yok"))
            self.body.addWidget(_card("GPU", gpu.get("ad") or t("deger.bilinmiyor"), lines, extra))

    def _displays(self, hw):
        displays = hw.get("ekranlar") or []
        if not displays:
            return
        self.body.addWidget(w.section_title(t("ui.kart.ekranlar")))
        container, lay = w.grid(columns=2)
        for i, d in enumerate(displays, 1):
            extra = [w.badge(t("ui.birincil_ekran"), "bilgi")] if d.get("birincil") else []
            lines = [f"{d['cozunurluk']} @ {d['yenileme_hz']} Hz",
                     t("ui.ekran_en_yuksek", hz=d["bu_cozunurlukte_en_yuksek_hz"],
                       cozunurluk=d.get("en_yuksek_cozunurluk") or d["cozunurluk"]),
                     t("ui.ekran_gpu", ad=d["ekran_karti"])]
            lay.addWidget(_card("DISP", display_name(d, i), lines, extra), (i - 1) // 2, (i - 1) % 2)
        self.body.addWidget(container)

    def _browser_extensions(self):
        """Yüklü tarayıcıların eklentileri (yerel dosyalardan, salt okunur). Hiçbiri yoksa bölüm gösterilmez."""
        groups = browser_ext.collect()
        if not groups:
            return
        self.body.addWidget(w.hbox((w.section_title(t("ui.bolum.tarayici_eklentileri")), 1),
                                   w.info_button(lambda: dialogs.show_message(
                                       self.app, t("ui.bolum.tarayici_eklentileri"), t("ui.tarayici.bilgi")))))
        container, lay = w.grid(columns=2)
        for i, group in enumerate(groups):
            exts = group["eklentiler"]
            on = [e for e in exts if e["etkin"]]
            name = group["tarayici"] + (f" ({group['profil']})" if group["profil"] else "")
            lines = [", ".join(e["ad"] + (f" — {t('ui.tarayici.tum_siteler')}" if e["tum_siteler"] else "") for e in on)]
            off = [e["ad"] for e in exts if not e["etkin"]]
            if off:
                lines.append(t("ui.tarayici.devre_disi", liste=", ".join(off)))
            lay.addWidget(_card("QOL", t("ui.tarayici.baslik", tarayici=name, toplam=len(exts), etkin=len(on)), lines, plain=True),
                          i // 2, i % 2)
        self.body.addWidget(container)

    def _others(self, sections, hw):
        cards = []
        storage = sections.get("depolama")
        if storage:
            cards.append(_card("SYS", t("ui.kart.depolama"),
                               [f"{d['ad']} — {d['tur']}, {t('ui.saglik')}: {d['saglik']}" for d in storage["diskler"]]
                               + [f"{v['surucu']} {v['bos_gb']} / {v['boyut_gb']} GB {t('ui.bos')}"
                                  for v in storage["birimler"]]))
        game = sections.get("oyun")
        if game:
            plan = game["guc_plani"]
            plan_name = plan["ad"] if plan["tur"] == "ozel" and plan["ad"] else t(f"deger.plan_{plan['tur']}")
            cards.append(_card("PWR", t("ui.kart.guc"), [
                t("rapor.guc_plani", ad=plan_name),
                t("rapor.guc_modu", prizde=t("deger.mod_" + game["guc_modu"]["prizde"]),
                  pilde=t("deger.mod_" + game["guc_modu"]["pilde"]))]))
        board = (hw or {}).get("anakart")
        if board:
            cards.append(_card("SYS", t("ui.kart.anakart"), [
                f"{board.get('uretici') or ''} {board.get('model') or ''}".strip(),
                f"BIOS {board.get('bios_surumu') or '—'} ({board.get('bios_tarihi') or '—'})"]))
        if not cards:
            return
        self.body.addWidget(w.section_title(t("ui.bolum.diger_bilgiler")))
        container, lay = w.grid(columns=2)
        for i, card in enumerate(cards):
            lay.addWidget(card, i // 2, i % 2)
        self.body.addWidget(container)
