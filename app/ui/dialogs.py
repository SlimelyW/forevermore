"""Pencereler: bilgi (i), onaylar (dikkatli: tek, riskli: iki aşama), kısmen
uygulanmış ayar seçimi, başlangıç onayı, evet/hayır, mesaj, bekleme."""

import os

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QDialog, QFrame, QLabel, QProgressBar, QRadioButton,
                               QScrollArea, QVBoxLayout, QWidget)

from app.core import settings
from app.core.i18n import t, value_label
from app.ui import widgets as w


class _Dialog(QDialog):
    def __init__(self, parent, title, width=640, height=560):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(width, height)
        self.setModal(True)
        self.outer = QVBoxLayout(self)
        self.outer.setContentsMargins(16, 14, 16, 12)
        self.outer.setSpacing(8)

    def scroll_body(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        body.setObjectName("PageBody")
        lay = QVBoxLayout(body)
        lay.setContentsMargins(0, 0, 6, 0)
        lay.setSpacing(8)
        lay.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(body)
        self.outer.addWidget(scroll, 1)
        return lay

    def heading(self, text, size=None):
        label = QLabel(text)
        label.setObjectName("Title")
        label.setWordWrap(True)
        if size:
            label.setFont(w.theme.ui_font(size, bold=True))
        self.outer.addWidget(label)


def _section(lay, heading, body=None, items=None, tone=None):
    if not body and not items:
        return
    if tone:
        frame = QFrame()
        frame.setProperty("banner", tone)
        inner = QVBoxLayout(frame)
        inner.setContentsMargins(12, 8, 12, 8)
    else:
        frame = w.Card()
        inner = frame.lay
    head = QLabel(heading)
    head.setObjectName("CardTitle")
    inner.addWidget(head)
    if body:
        inner.addWidget(w.label(body))
    for item in items or []:
        inner.addWidget(w.label(f"• {item}"))
    lay.addWidget(frame)


def display_name(tweak):
    """Ad + işe yaramayanlar için "(placebo)" / "(zararlı)" etiketi."""
    reality = tweak["gerceklik"]["durum"]
    suffix = {"placebo": t("ui.etiket.placebo"), "zararlı": t("ui.etiket.zararli")}.get(reality, "")
    return f"{tweak['ad']} {suffix}".strip()


def _pros_cons(lay, tweak, pros_title=None, cons_title=None):
    """Artılar solda, eksiler sağda: tek balon."""
    if not tweak["artilar"] and not tweak["eksiler"]:
        return
    card = w.Card(layout="h", spacing=18)
    for heading, items, tone in ((pros_title or t("ui.artilar"), tweak["artilar"], "iyi"),
                                 (cons_title or t("ui.eksiler"), tweak["eksiler"], "sorun")):
        column = QVBoxLayout()
        column.setSpacing(4)
        column.addWidget(w.colored(heading, tone, wrap=False))
        for item in items or [t("ui.yok")]:
            column.addWidget(w.label(f"• {item}"))
        column.addStretch(1)
        card.lay.addLayout(column, 1)
    lay.addWidget(card)


def _sources(lay, tweak):
    if not tweak.get("kaynaklar"):
        return
    card = w.Card()
    head = QLabel(t("ui.kaynaklar"))
    head.setObjectName("CardTitle")
    card.lay.addWidget(head)
    for url in tweak["kaynaklar"]:
        link = QLabel(f'<a href="{url}">{url}</a>')
        link.setWordWrap(True)
        # Bağlantı yalnızca kullanıcı tıklarsa tarayıcıda açılır.
        link.setTextInteractionFlags(Qt.TextInteractionFlag.LinksAccessibleByMouse)
        link.linkActivated.connect(os.startfile)
        card.lay.addWidget(link)
    lay.addWidget(card)


def fill_tweak_details(lay, tweak):
    """Bilgi (i) penceresi: yalnızca ne yapar, artılar/eksiler, kimler dokunmamalı ve
    tahmini performans etkisi. "Ekstra ayar bilgileri" açıksa ayrıntılar da eklenir."""
    level = tweak["performans_etkisi"]["seviye"]
    why = (tweak.get("bilgi") or {}).get("neden")
    _section(lay, t("ui.ne_ise_yarar"), "\n\n".join(x for x in (tweak["ne_ise_yarar"], why) if x))
    _pros_cons(lay, tweak)
    _section(lay, t("ui.dikkat"), items=tweak.get("notlar"), tone="uyari")
    if tweak.get("dokunmamali"):
        _section(lay, t("ui.dokunmamali"), items=tweak["dokunmamali"], tone="uyari")
    level_text = value_label("deger.etki", level)
    _section(lay, t("ui.performans_etkisi", seviye=level_text), tweak["performans_etkisi"].get("gerekce") or level_text)
    if settings.get("ekstra_bilgi"):
        reality = value_label("deger.gerceklik", tweak["gerceklik"]["durum"])
        reality_text = tweak["gerceklik"].get("aciklama") or ""
        if tweak["gerceklik"].get("celiski"):
            reality_text += "\n\n" + t("ui.celiski") + " " + tweak["gerceklik"]["celiski"]
        _section(lay, t("ui.gerceklik_baslik", durum=reality), reality_text or reality)
        _section(lay, t("ui.windows"), tweak["uyumluluk"]["kaynak_metin"]["windows"])
        _section(lay, t("ui.varsayilan"), tweak.get("varsayilan"))
        _sources(lay, tweak)


def _cautions(tweak, availability):
    """Onay pencerelerinde gösterilen dikkat maddeleri (notlar + bu bilgisayara özel uyarılar)."""
    items = list(tweak.get("notlar") or [])
    if availability:
        items += [t(k, **p) for k, p in availability.warnings]
    restart = tweak.get("yeniden_baslatma_kodu")
    if restart and restart not in ("yok", "ses_servisi"):
        items.append(t(f"yeniden.{restart}"))
    return items


class InfoDialog(_Dialog):
    """(i) düğmesi."""

    def __init__(self, parent, tweak, availability=None, detected=False):
        super().__init__(parent, tweak["ad"], height=600)
        self.heading(display_name(tweak))
        lay = self.scroll_body()
        fill_tweak_details(lay, tweak)
        self.outer.addWidget(w.hbox(None, w.button(t("ui.kapat"), self.accept, width=120)))


class _CheckedDialog(_Dialog):
    """"Okudum, anladım" işaretlenmeden ilerleme düğmesi açılmaz."""

    def add_buttons(self, ok_text, warn=True, check_text=None):
        self.check = QCheckBox(check_text or t("ui.okudum_anladim"))
        self.outer.addWidget(self.check)
        self.ok = w.button(ok_text, self.accept, warn=warn, primary=not warn)
        self.ok.setEnabled(False)
        self.check.toggled.connect(self.ok.setEnabled)
        self.outer.addWidget(w.hbox(None, w.button(t("ui.vazgec"), self.reject), self.ok))


class ConfirmCarefulDialog(_CheckedDialog):
    """Dikkatli (veya bu bilgisayar için uyarılı) ayar açılmadan önce: tek onay."""

    def __init__(self, parent, tweak, availability=None, anti_cheat=""):
        super().__init__(parent, t("ui.onay_baslik"), height=640)
        self.heading(t("ui.onay_giris", ad=display_name(tweak)), size=16)
        lay = self.scroll_body()
        _section(lay, t("ui.ne_ise_yarar"), tweak["ne_ise_yarar"])
        _pros_cons(lay, tweak)
        _section(lay, t("ui.dikkat"), items=_cautions(tweak, availability), tone="uyari")
        if tweak.get("dokunmamali"):
            _section(lay, t("ui.dokunmamali"), items=tweak["dokunmamali"], tone="uyari")
        if anti_cheat:
            _section(lay, t("ui.anti_cheat_baslik"), anti_cheat)
        self.add_buttons(t("ui.onayla_ac"))


class RiskStepOneDialog(_CheckedDialog):
    """Riskli ayar, 1. ekran: ne yapar, açılırsa/kapatılırsa ne olur, dikkat, kimler dokunmamalı."""

    def __init__(self, parent, tweak, availability=None, enabling=True, anti_cheat=""):
        super().__init__(parent, t("ui.risk1_baslik"), height=680)
        self.heading(t("ui.risk1_giris_ac" if enabling else "ui.risk1_giris_kapat", ad=display_name(tweak)), size=16)
        lay = self.scroll_body()
        _section(lay, t("ui.ne_ise_yarar"), tweak["ne_ise_yarar"])
        if enabling:
            _section(lay, t("ui.risk1_acilirsa"), items=tweak["eksiler"], tone="sorun")
            _section(lay, t("ui.risk1_kazanc"), items=tweak["artilar"])
        else:
            _section(lay, t("ui.risk1_kapatilirsa"),
                     items=[t("ui.risk1_varsayilana_doner", varsayilan=tweak.get("varsayilan") or "—")]
                     + [t("ui.risk1_kaybedilen", madde=a) for a in tweak["artilar"]], tone="uyari")
        _section(lay, t("ui.dikkat"), items=_cautions(tweak, availability), tone="uyari")
        if tweak.get("dokunmamali"):
            _section(lay, t("ui.dokunmamali"), items=tweak["dokunmamali"], tone="sorun")
        if anti_cheat:
            _section(lay, t("ui.anti_cheat_baslik"), anti_cheat)
        self.add_buttons(t("ui.devam"))


class RiskStepTwoDialog(_Dialog):
    """Riskli ayar, 2. ekran: son onay."""

    def __init__(self, parent, tweak, enabling=True):
        super().__init__(parent, t("ui.risk2_baslik"), width=520, height=260)
        stripe = QFrame()
        stripe.setProperty("stripe", "sorun")
        stripe.setFixedHeight(5)
        self.outer.addWidget(stripe)
        self.heading(t("ui.risk2_baslik"), size=17)
        self.outer.addWidget(w.label(t("ui.risk2_metin", ad=display_name(tweak))))
        self.outer.addStretch(1)
        ok = w.button(t("ui.risk2_uygula" if enabling else "ui.risk2_kapat"), self.accept, warn=True)
        cancel = w.button(t("ui.vazgec"), self.reject, primary=True)
        cancel.setDefault(True)  # Enter yanlışlıkla onaylamasın
        self.outer.addWidget(w.hbox(None, cancel, ok))


class PartialStateDialog(_Dialog):
    """Ayar kısmen uygulanmışsa: tamamen uygula mı, tamamen kapat mı?"""

    def __init__(self, parent, tweak):
        super().__init__(parent, t("ui.kismen_baslik"), width=520, height=230)
        self.heading(display_name(tweak), size=16)
        self.outer.addWidget(w.label(t("ui.kismen_metin")))
        self.outer.addStretch(1)
        self.choice = None
        self.outer.addWidget(w.hbox(None, w.button(t("ui.vazgec"), self.reject),
                                    w.button(t("ui.kismen_kapat"), lambda: self._pick(False)),
                                    w.button(t("ui.kismen_uygula"), lambda: self._pick(True), primary=True)))

    def _pick(self, value):
        self.choice = value
        self.accept()


class ConsentDialog(_CheckedDialog):
    """İlk açılış / sürüm değişikliği: sorumluluk uyarısı. Kabul edilmezse uygulama kapanır."""

    def __init__(self, text):
        super().__init__(None, t("ui.onay_ekrani_baslik"), width=560, height=380)
        self.heading(t("ui.onay_ekrani_baslik"), size=18)
        lay = self.scroll_body()
        lay.addWidget(w.label(text))
        self.check = QCheckBox(t("ui.onay_ekrani_kutu"))
        self.outer.addWidget(self.check)
        self.ok = w.button(t("ui.onay_ekrani_kabul"), self.accept, primary=True)
        self.ok.setEnabled(False)
        self.check.toggled.connect(self.ok.setEnabled)
        self.outer.addWidget(w.hbox(None, w.button(t("ui.onay_ekrani_ret"), self.reject), self.ok))


class LanguageDialog(_Dialog):
    """İlk açılışta, başlangıç onayından önce: arayüz dili seçimi. Diller lang klasöründen okunur."""

    def __init__(self, languages, selected):
        super().__init__(None, t("ui.dil.baslik"), width=420, height=320)
        self.heading(t("ui.dil.baslik"), size=18)
        self.outer.addWidget(w.label(t("ui.dil.aciklama"), muted=True))
        self.group = QButtonGroup(self)
        lay = self.scroll_body()
        for item in languages:
            radio = QRadioButton(item["yerel_ad"] if item["yerel_ad"] == item["ad"]
                                 else f"{item['yerel_ad']} ({item['ad']})")
            radio.setProperty("kod", item["kod"])
            radio.setChecked(item["kod"] == selected)
            self.group.addButton(radio)
            lay.addWidget(radio)
        self.outer.addWidget(w.hbox(None, w.button(t("ui.dil.devam"), self.accept, primary=True)))

    def choice(self):
        button = self.group.checkedButton()
        return button.property("kod") if button else None


def ask_language(languages, selected):
    """Seçilen dil kodu; pencere kapatılırsa None."""
    dialog = LanguageDialog(languages, selected)
    return dialog.choice() if _accepted(dialog) else None


class MessageDialog(_Dialog):
    def __init__(self, parent, title, text, yes_no=False, yes_text=None, no_text=None, kind="bilgi", on_no=None):
        super().__init__(parent, title, width=540, height=280)
        stripe = QFrame()
        stripe.setProperty("stripe", kind)
        stripe.setFixedHeight(5)
        self.outer.addWidget(stripe)
        self.outer.addWidget(w.label(title, bold=True, size=16))
        lay = self.scroll_body()
        self.body_label = w.label(text, selectable=True, plain=True)  # metinde program/görev adı olabilir: HTML sayılmaz
        lay.addWidget(self.body_label)
        if yes_no:
            row = w.hbox(None, w.button(no_text or t("ui.hayir"), on_no or self.reject),
                         w.button(yes_text or t("ui.evet"), self.accept, primary=True))
        else:
            row = w.hbox(None, w.button(t("ui.tamam"), self.accept, primary=True))
        self.outer.addWidget(row)


class RestorePointAskDialog(MessageDialog):
    """Oturumdaki ilk değişiklikten önce: geri yükleme noktası oluşturulsun mu? (+ "bir daha sorma")."""

    def __init__(self, parent):
        self.skip = False
        super().__init__(parent, t("ui.rp_baslik"), t("ui.rp_sor"), yes_no=True, yes_text=t("ui.rp_olustur"),
                         no_text=t("ui.rp_atla"), kind="bilgi", on_no=self._skip)
        self.remember = QCheckBox(t("ui.rp_bir_daha_sorma"))
        self.outer.insertWidget(self.outer.count() - 1, self.remember)

    def _skip(self):
        self.skip = True
        self.accept()


def ask_restore_point(parent):
    """("olustur" | "atla" | None, hatırla mı). Esc / pencereyi kapatma = None: değişiklik yapılmaz."""
    dialog = RestorePointAskDialog(parent)
    if not _accepted(dialog):
        return None, False
    return ("atla" if dialog.skip else "olustur"), dialog.remember.isChecked()


def _accepted(dialog):
    return dialog.exec() == QDialog.DialogCode.Accepted


def show_message(parent, title, text, kind="bilgi"):
    MessageDialog(parent, title, text, kind=kind).exec()


class KeepDisplayDialog(MessageDialog):
    """Ekran ayarı değişince: "Kalsın / Geri dön"; süre dolarsa geri döner (Windows'taki gibi)."""

    def __init__(self, parent, seconds):
        super().__init__(parent, t("ui.mon.kalsin_mi_baslik"), t("ui.mon.kalsin_mi", sn=seconds), yes_no=True,
                         yes_text=t("ui.mon.kalsin"), no_text=t("ui.mon.geri_don"), kind="bilgi")
        self.remaining = seconds
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(1000)

    def _tick(self):
        self.remaining -= 1
        if self.remaining <= 0:
            self.timer.stop()
            self.reject()
            return
        self.body_label.setText(t("ui.mon.kalsin_mi", sn=self.remaining))


def ask_keep_display(parent, seconds=15):
    return _accepted(KeepDisplayDialog(parent, seconds))


def ask_yes_no(parent, title, text, yes_text=None, no_text=None, kind="uyari"):
    return _accepted(MessageDialog(parent, title, text, yes_no=True, yes_text=yes_text, no_text=no_text, kind=kind))


class BulkPreviewDialog(_Dialog):
    """Toplu uygulamadan önce: neyin değişeceğini tek tek listeler; işaretli olanlar onaydan sonra uygulanır."""

    def __init__(self, parent, tweaks):
        super().__init__(parent, t("ui.toplu.pencere"), width=640, height=600)
        self.heading(t("ui.toplu.baslik", n=len(tweaks)), size=16)
        self.outer.addWidget(w.label(t("ui.toplu.aciklama"), muted=True))
        lay = self.scroll_body()
        self.checks = []
        for tweak in tweaks:
            row = w.Card(layout="h", spacing=12, margins=(16, 12, 16, 12))
            check = QCheckBox()
            check.setChecked(True)
            check.toggled.connect(self._count)
            self.checks.append((tweak["id"], check))
            text = QVBoxLayout()
            text.setSpacing(4)
            text.addWidget(w.label(display_name(tweak), bold=True))
            badges = [w.label(t("ui.toplu.kapali_acik"), muted=True, size=12, wrap=False),
                      w.impact_badge(tweak["performans_etkisi"]["seviye"])]
            if tweak["risk"] != "güvenli":
                badges.append(w.risk_badge(tweak["risk"]))
            text.addWidget(w.hbox(*badges, None))
            row.lay.addWidget(check, 0, Qt.AlignmentFlag.AlignTop)
            row.lay.addLayout(text, 1)
            lay.addWidget(row)
        if any(tw["risk"] != "güvenli" for tw in tweaks):
            self.outer.addWidget(w.label(t("ui.toplu.dikkatli_not"), muted=True, size=12))
        self.apply_button = w.button("", self.accept, primary=True)
        self.outer.addWidget(w.hbox(None, w.button(t("ui.vazgec"), self.reject), self.apply_button))
        self._count()

    def _count(self):
        self.apply_button.setText(t("ui.toplu.uygula", n=len(self.chosen())))

    def chosen(self):
        return [tweak_id for tweak_id, check in self.checks if check.isChecked()]


def choose_bulk(parent, tweaks):
    """İşaretli ayar kimlikleri; vazgeçildiyse ya da hiçbiri işaretli değilse boş liste."""
    dialog = BulkPreviewDialog(parent, tweaks)
    return dialog.chosen() if _accepted(dialog) else []


def confirm_careful(parent, tweak, availability=None, anti_cheat=""):
    return _accepted(ConfirmCarefulDialog(parent, tweak, availability, anti_cheat))


def confirm_risky(parent, tweak, availability=None, enabling=True, anti_cheat=""):
    """Riskli ayar: iki ayrı onay ekranı. İkisi de kabul edilirse True."""
    return (_accepted(RiskStepOneDialog(parent, tweak, availability, enabling, anti_cheat))
            and _accepted(RiskStepTwoDialog(parent, tweak, enabling)))


def choose_partial(parent, tweak):
    """True: tamamen uygula, False: tamamen kapat, None: vazgeç."""
    dialog = PartialStateDialog(parent, tweak)
    return dialog.choice if _accepted(dialog) else None


def ask_consent(text):
    return _accepted(ConsentDialog(text))


class BusyDialog(_Dialog):
    """Uzun işlemlerde bekleme penceresi; iş bitene kadar kapatılamaz."""

    def __init__(self, parent, title, text):
        super().__init__(parent, title, width=460, height=150)
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
        self.outer.addWidget(w.label(text))
        bar = QProgressBar()
        bar.setRange(0, 0)  # belirsiz ilerleme
        self.outer.addWidget(bar)
        self._closing = False

    def finish(self):
        self._closing = True
        self.accept()

    def reject(self):  # Esc ile kapatılmasın
        if self._closing:
            super().reject()

    def closeEvent(self, event):
        if self._closing:
            super().closeEvent(event)
        else:
            event.ignore()


def busy(parent, title, text):
    dialog = BusyDialog(parent, title, text)
    dialog.open()  # pencere modlu ama bloklamaz; arka plan işi sürerken arayüz akıcı kalır
    return dialog
