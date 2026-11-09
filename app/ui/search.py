"""Üst şeritteki arama kutusu: ayar (id, ad, açıklama) ve sayfa adı arar; sonuca tıklayınca oraya gider."""

from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtWidgets import QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from app.core.i18n import t

MAX_RESULTS = 8
_FOLD = str.maketrans("ıİşŞğĞüÜöÖçÇ", "iissgguuoocc")


def fold(text):
    """Küçük harf + Türkçe aksan farkı yok (ı/i, ş/s…)."""
    return (text or "").translate(_FOLD).casefold()


def search(tweaks, pages, query, limit=MAX_RESULTS):
    """[(tür, anahtar, başlık, alt metin)] en iyi eşleşme önce. tür: "page" | "tweak"."""
    words = fold(query).split()
    if not words:
        return []
    hits = []
    for key, label in pages:
        name = fold(label)
        if all(w in name for w in words):
            hits.append((0 if name.startswith(words[0]) else 1, "page", key, label, ""))
    for tw in tweaks:
        tid, name, desc = fold(tw["id"]), fold(f'{tw["ad"]} {tw.get("sade_ad", "")}'), fold(tw.get("ne_ise_yarar", ""))
        if not all(w in f"{tid} {name} {desc}" for w in words):
            continue
        first = words[0]
        if tid == first:
            rank = 0
        elif name.startswith(first):
            rank = 1
        elif all(w in name or w in tid for w in words):
            rank = 2
        else:
            rank = 3
        hits.append((rank, "tweak", tw["id"], tw.get("sade_ad") or tw["ad"], f"{tw['id']} · {t('kategori.' + tw['kategori_id'])}"))
    hits.sort(key=lambda h: h[0])
    return [h[1:] for h in hits[:limit]]


class SearchBox(QWidget):
    """Kutu + açılan sonuç listesi. `on_tweak(id)` / `on_page(key)` ile yönlendirir. `overlay` verilirse sonuç listesi
    o pencerenin üstünde, kutunun altında yüzer (şeridi aşağı itmez); verilmezse kutunun altında satır içi durur."""

    def __init__(self, tweaks, pages, on_tweak, on_page, overlay=None):
        super().__init__()
        self._tweaks, self._pages, self._on_tweak, self._on_page = tweaks, pages, on_tweak, on_page
        self._overlay = overlay
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText(t("ui.arama.yer_tutucu"))
        self.edit.setClearButtonEnabled(True)
        self.edit.textChanged.connect(self._refresh)
        self.edit.returnPressed.connect(self._open_current)
        self.edit.setAccessibleName(t("ui.arama.yer_tutucu"))
        self.edit.installEventFilter(self)  # Aşağı/Yukarı/Tab sonuç listesinde gezer, odak kutuda kalır
        lay.addWidget(self.edit)
        self.results = QListWidget(overlay)
        self.results.setObjectName("SearchResults")
        self.results.setAccessibleName(t("ui.arama.yer_tutucu"))
        self.results.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.results.setVisible(False)
        self.results.itemClicked.connect(self._open)
        if overlay is None:
            lay.addWidget(self.results)

    def focus(self):
        self.edit.setFocus()
        self.edit.selectAll()

    def _refresh(self, text):
        self.results.clear()
        hits = search(self._tweaks, self._pages, text)
        for kind, key, title, sub in hits:
            item = QListWidgetItem(f"{title}\n{sub}" if sub else title)
            item.setData(Qt.ItemDataRole.UserRole, (kind, key))
            self.results.addItem(item)
        if text.strip() and not hits:
            empty = QListWidgetItem(t("ui.arama.sonuc_yok"))
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            self.results.addItem(empty)
        self.results.setVisible(bool(text.strip()))
        if self.results.count():
            height = min(self.results.count(), MAX_RESULTS) * 44 + 6
            self.results.setFixedHeight(height)
            if self._overlay is not None:
                width = max(self.edit.width(), 340)
                corner = self.edit.mapTo(self._overlay, QPoint(self.edit.width() - width, self.edit.height() + 2))
                self.results.setGeometry(corner.x(), corner.y(), width, height)
                self.results.raise_()

    def eventFilter(self, obj, event):
        if obj is self.edit and event.type() == QEvent.Type.KeyPress and not self.results.isHidden():
            step = {Qt.Key.Key_Down: 1, Qt.Key.Key_Tab: 1, Qt.Key.Key_Up: -1, Qt.Key.Key_Backtab: -1}.get(event.key())
            if step and self.results.item(0) is not None and self.results.item(0).data(Qt.ItemDataRole.UserRole):
                row = min(max(self.results.currentRow() + step, 0), self.results.count() - 1)
                self.results.setCurrentRow(row)
                return True
        return super().eventFilter(obj, event)

    def _open_current(self):
        """Enter: seçili sonuç, yoksa ilki."""
        item = self.results.currentItem() or (self.results.item(0) if self.results.count() else None)
        if item is not None and item.data(Qt.ItemDataRole.UserRole):
            self._open(item)

    def _open(self, item):
        kind, key = item.data(Qt.ItemDataRole.UserRole)
        self.edit.clear()
        (self._on_tweak if kind == "tweak" else self._on_page)(key)
