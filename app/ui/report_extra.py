"""Raporun "uygulama etkinliği" bölümleri: yapılan değişiklikler, geri alınamaz işlemler,
oyun profilleri ve son ölçüm karşılaştırması.

Dosya yolları rapora YAZILMAZ (oyunların .exe yolu gibi); yalnızca adlar ve değerler.
Metin, raporun geri kalanı gibi gizlilik filtresinden geçer.
"""

import os

from app.core.i18n import fmt_date, t
from app.measure import MeasurementStore, compare

IRREVERSIBLE = ("eylem", "npi")


def irreversible_records(store, limit=20):
    return [r for r in store.read_history(None, limit=500) if r.get("islem") in IRREVERSIBLE][:limit]


def _name(controller, record_id):
    tweak = controller.by_id.get(record_id)
    if tweak:
        return tweak["ad"]
    entry = controller.engine.store.get(record_id) or {}
    return entry.get("ad", record_id)


def _game_line(game):
    p = game["profil"]
    parts = [t("rapor_ek.oncelik", deger=t(f"ui.oncelik.{p['oncelik']}")),
             t("rapor_ek.gpu", deger=t(f"ui.gpu_tercihi.{p['gpu_tercihi']}"))]
    if p.get("fso_kapali"):
        parts.append(t("rapor_ek.fso"))
    exe = os.path.basename(game.get("exe") or "") or "—"
    return f"- {game['ad']} ({exe}): " + "; ".join(parts)


def _change_line(controller, change_id, name, when):
    """Güncel ayar adıyla; etkisi bir süreçle görülen sürücü ayarında (NVIDIA bindirmesi) sürecin ŞU ANKİ durumu da yazılır:
    raporda yalnızca "uygulandı" görünürken süreçler çalışmaya devam ediyordu (2.5)."""
    from app.ui.dialogs import display_name  # noqa: WPS433
    from app.ui.managers_ui import SETTING_PROCESS, running_count  # noqa: WPS433
    tweak = controller.by_id.get(change_id)
    line = f"- {display_name(tweak) if tweak else name} ({when})"
    setting = ((tweak or {}).get("nvidia") or {}).get("ayar")
    exe = SETTING_PROCESS.get(int(setting, 16)) if setting else None
    if exe:
        count = running_count(exe)
        line += "\n    " + (t("ui.nvidia_bindirme_suruyor", adet=count) if count else t("ui.nvidia_bindirme_kapali"))
    return line


def sections(controller, game_store=None, measure_store=None):
    """[(başlık, [satırlar])]"""
    result = []
    changes = controller.changed()
    lines = [_change_line(controller, change_id, name, when) for change_id, name, when in changes] or [t("rapor_ek.yok")]
    result.append((t("rapor_ek.degisiklikler", adet=len(changes)), lines))

    records = irreversible_records(controller.engine.store)
    lines = [f"- {_name(controller, r['id'])} — {t('ui.basarili') if r['basarili'] else t('ui.basarisiz')} "
             f"({r['zaman'].replace('T', ' ')})" for r in records] or [t("rapor_ek.yok")]
    result.append((t("rapor_ek.geri_alinamaz"), lines))

    if game_store is not None:
        lines = [_game_line(g) for g in game_store.games] or [t("rapor_ek.yok")]
        result.append((t("rapor_ek.oyunlar", adet=len(game_store.games)), lines))

    measure_store = measure_store or MeasurementStore()
    lines = []
    for kind in ("sistem", "oyun"):
        after = next((m for m in measure_store.items if m["tur"] == kind and m["etiket"] == "sonra"), None)
        before = next((m for m in measure_store.items if m["tur"] == kind and m["etiket"] == "once"
                       and (after is None or m["zaman"] < after["zaman"])), None)
        if not (before and after):
            continue
        lines.append(t("rapor_ek.olcum_cifti", tur=t(f"olcum.tur.{kind}"), once=fmt_date(before["zaman"]),
                       sonra=fmt_date(after["zaman"])))
        for metric, a, b, _diff, pct, _better in compare(before, after):
            change = "" if pct is None else f" ({pct:+.1f}%)"
            lines.append(f"    {t(f'olcum.metrik.{metric}')}: {a:g} -> {b:g}{change}")
    if lines:
        lines.append(t("olcum.durustluk"))
    result.append((t("rapor_ek.olcumler"), lines or [t("rapor_ek.yok")]))
    return result
