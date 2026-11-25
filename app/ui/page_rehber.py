"""Rehber: oyun içi grafik ayarlarında nelere bakılır ve oyuna göre dış rehber bağlantıları.

Yalnızca BİLGİ: uygulama oyun içi ayarı DEĞİŞTİREMEZ, bu yüzden bu içerik oyunun kendi sayfasında değil burada durur
(Araçlar paneli). Profesyonel oyuncu ayarı içeriği ve bağlantıları yoktur (9 Kasım 2026'da çıkarıldı). Bağlantılar
kullanıcının tarayıcısında açılır; uygulama bu sitelere kendisi bağlanmaz.
"""

import os

from PySide6.QtWidgets import QComboBox, QLabel, QVBoxLayout, QWidget

from app.core import i18n
from app.core.i18n import t
from app.games import guides
from app.ui import dialogs, widgets as w
from app.ui.page_settings import about_data


class GuidePage(w.Page):
    def __init__(self, app):
        super().__init__(app)
        self.game = None       # seçili oyun adı; None: genel (her oyunda aranacak maddeler)
        self.content = None

    def build(self):
        super().build()
        self.header.addWidget(w.title(t("ui.menu.rehber")))
        self.header.addWidget(w.label(t("ui.rehber.aciklama"), muted=True))
        self.body.addWidget(self._picker())
        self.content = QWidget()
        self.content_lay = QVBoxLayout(self.content)
        self.content_lay.setContentsMargins(0, 0, 0, 0)
        self.content_lay.setSpacing(12)
        self.body.addWidget(self.content)
        self._fill()

    def names(self):
        """Seçilebilir oyunlar: listemdekiler + rehber verisindekiler (aynı oyun bir kez; ad harf/rakama indirgenip karşılaştırılır)."""
        seen, names = set(), []
        for name in [g["ad"] for g in self.app.game_store.games] + guides.names():
            key = guides._key(name)
            if key and key not in seen:
                seen.add(key)
                names.append(name)
        return sorted(names, key=str.lower)

    def _picker(self):
        combo = QComboBox()
        combo.addItem(t("ui.rehber.genel"), None)
        for name in self.names():
            combo.addItem(name, name)
        combo.setCurrentIndex(max(0, combo.findData(self.game)))
        combo.setAccessibleName(t("ui.rehber.oyun_sec"))
        combo.currentIndexChanged.connect(lambda _i, c=combo: self._choose(c.currentData()))
        return w.hbox(w.label(t("ui.rehber.oyun_sec"), bold=True, wrap=False), combo, None, spacing=10)

    def _choose(self, name):
        self.game = name
        self._fill()

    def _fill(self):
        w.clear_layout(self.content_lay)
        if self.game:
            self.content_lay.addWidget(self._game_card(self.game))
        self.content_lay.addWidget(self._items_card())
        useful = about_data()["faydali"]
        if useful:
            self.content_lay.addWidget(self._useful_card(useful))

    def _game_card(self, name):
        """Seçili oyun: doğrulanmış Reflex desteği ve (varsa) sistem gereksinimi / FPS beklentisi bağlantıları."""
        card = w.Card(spacing=8)
        card.lay.addWidget(w.hbox((self._head(name), 1), w.info_button(
            lambda: dialogs.show_message(self.app, t("ui.oyun_rehber"), t("ui.oyun_bilgi.rehber"), "bilgi"))))
        support = guides.support(name)["reflex"]
        state = {True: "var", False: "yok", None: "bilinmiyor"}[support]
        card.lay.addWidget(w.hbox(w.label(t("ui.oyun_ici.reflex_destek"), bold=True, wrap=False),
                                  w.badge(t(f"ui.oyun_ici.destek.{state}"), "iyi" if support else "notr"), None))
        sources = guides.find(name)
        if not sources:
            card.lay.addWidget(w.label(t("ui.oyun_rehber.yok"), muted=True, size=12))
            return card
        buttons = []
        for source in sources:
            text = f"{source['site']}: {source['icerik']}"
            button = w.button(text if len(text) <= 56 else text[:55] + "…", lambda _=False, u=source["url"]: os.startfile(u))
            button.setToolTip(source["icerik"])
            buttons.append(button)
        card.lay.addWidget(w.flow(*buttons))
        card.lay.addWidget(w.label(t("ui.oyun_rehber.not"), muted=True, size=12))
        return card

    @staticmethod
    def _head(text):
        head = QLabel(text)
        head.setObjectName("CardTitle")
        return head

    def _items_card(self):
        """Her oyunda aranacak genel oyun içi ayar maddeleri, kanıt rozetiyle (oyuna özel sayı verilmez)."""
        card = w.Card(spacing=6)
        card.lay.addWidget(self._head(t("ui.oyun_ici.baslik")))
        card.lay.addWidget(w.label(t("ui.oyun_ici.aciklama"), muted=True, size=12))
        for item in guides.ingame_items(i18n.current()):
            card.lay.addWidget(w.hbox((w.label(item["baslik"], bold=True), 1),
                                      w.badge(t(f"ui.oyun_ici.kanit.{item['kanit']}"),
                                              "iyi" if item["kanit"] in ("belgeli", "olculmus") else "notr")))
            card.lay.addWidget(w.label(item["metin"], muted=True, size=12))
            if item["kaynak"]:
                card.lay.addWidget(w.label(t("ui.oyun_ici.kaynak", kaynak=item["kaynak"]), muted=True, size=11))
        return card

    def _useful_card(self, items):
        """Bilgi sayfasından taşınan faydalı dış bağlantılar (data/hakkinda.json 'faydali'); tarayıcıda açılır."""
        card = w.Card(spacing=6)
        card.lay.addWidget(self._head(t("ui.oyun_faydali.baslik")))
        card.lay.addWidget(w.label(t("ui.oyun_faydali.not"), muted=True, size=12))
        for item in items:
            parts = [(w.label(f"{item.get('etiket', '').removeprefix('Faydalı: ')}: {item.get('deger', '')}", selectable=True, wrap=False), 1)]
            if str(item.get("url", "")).startswith("https://"):
                parts.append(w.button(t("ui.bilgi.ac"), lambda _=False, u=item["url"]: os.startfile(u)))
            card.lay.addWidget(w.hbox(*parts))
        return card
