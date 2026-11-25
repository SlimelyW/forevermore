"""Otomatik çevrilen bir dilde ANLAM TAŞIYAN metinleri (uyarı, hata, risk, geri alma, onay) İngilizceyle yan yana döker:
ikinci kontrol geçişi (insan okuması) için. Çıktıdaki sayı "kontrol edilecek" metin sayısıdır; kalanı kontrol EDİLMEZ.

    py -3.12 tools/ceviri_ikinci_gecis.py es > dosya.txt
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# arayüz anahtarı önekleri: hata/uyarı/onay/risk/geri alma/güvenlik metinleri
UI_PREFIXES = (
    "hata.", "ui.risk1_", "ui.risk2_", "ui.defender.", "ui.uac.", "ui.guvenli.", "koruma.", "ui.msi_guvenli_mod", "ui.kaldir.",
    "ui.tumunu_geri_al", "ui.eylem_onay", "ui.npi_onay", "ui.oncelik_yuksek_onay", "ui.temizlik.soru_liste", "ui.rp_", "uyari.",
    "ui.yedek_", "ui.anti_cheat_", "ui.surucu_arac.imza_yok", "ui.surucu_arac.klasor_uyari", "ui.boost.toplu_zorla_soru",
    "ui.boost.zorla_soru", "ui.kaldirici.kaldir_soru", "ui.kaldirici.yedegi_sil_soru", "ui.kaldirici.geri_yukle_soru",
    "ui.kaldirici.baslamadi_kullanici", "ui.bakim.onar_soru", "ui.bakim.ag_sifirla_onizleme", "ui.bakim.wu_onar_sert_onizleme",
    "ui.bakim.ayrilmis_kapat_onizleme", "ui.bakim.bilesen_temizle_onizleme", "ui.bakim.geri_alinamaz", "ui.bakim.bak_birakilan",
    "ui.varsayilan.onizleme", "ui.nvprofil.aciklama", "ui.mon.kalsin_mi", "ui.ayar.windows_ile_baslat_profil",
    "ui.guncelleme.hata.", "ui.guncelleme.var", "ui.kismen_metin", "rp.", "store_geri.uyari.", "store_geri.neden.",
    "ui.wu.dikkat.", "ui.wu.eksi.", "ui.wu.dokunmamali.", "ui.wu.not",
)
# riskli/dikkatli ayarlarda: uyarı, kimlere göre değil, geri alma ve tespit metinleri
LAYER_FIELDS = ("eksiler", "dokunmamali", "notlar", "rehber.geri_alma", "tespit.mesaj", "bilgi.yapilamaz_nedeni")


def main():
    language = sys.argv[1]
    sys.stdout.reconfigure(encoding="utf-8")
    load = lambda p: json.loads(p.read_text(encoding="utf-8"))
    en, own = load(ROOT / "lang/en.json"), load(ROOT / f"lang/{language}.json")
    items = [(k, en[k], own[k]) for k in en if k != "_meta" and k.startswith(UI_PREFIXES)]
    tweaks = load(ROOT / "data/tweaks_app.json")["ayarlar"]
    risky = [t["id"] for t in tweaks if t.get("risk") in ("riskli", "dikkatli")]
    en_l, own_l = (load(ROOT / f"data/ceviriler/{c}.json")["ayarlar"] for c in ("en", language))
    for tid in risky:
        for field in LAYER_FIELDS:
            if field in en_l[tid]:
                a, b = en_l[tid][field], own_l[tid][field]
                items.append((f"{tid}.{field}", " | ".join(a) if isinstance(a, list) else a,
                              " | ".join(b) if isinstance(b, list) else b))
    for key, a, b in items:
        print(f"{key}\nEN {a}\nES {b}\n".replace("\nES ", f"\n{language.upper()} "))
    total = len(json.loads((ROOT / "lang/en.json").read_text(encoding="utf-8"))) - 1
    print(f"# kontrol edilecek metin: {len(items)} (arayüz anahtarı toplamı {total}, ayar çevirisi {len(en_l)} ayar)", file=sys.stderr)


if __name__ == "__main__":
    main()
