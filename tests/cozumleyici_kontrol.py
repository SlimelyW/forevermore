"""Yer tutucu çözümleyicilerini bu bilgisayarda SALT OKUNUR çalıştırır.

Hiçbir ayarı değiştirmez. Gizlilik için ağ kartı adı, GUID, cihaz adı gibi
değerleri yazdırmaz; yalnızca kaç tane bulunduğunu ve ayarın görünüp
görünmeyeceğini gösterir.

Çalıştırma (proje klasöründe):
    py -3.12 -m tests.cozumleyici_kontrol
"""

import json
from pathlib import Path

from app.engine import resolvers

ROOT = Path(__file__).resolve().parent.parent


def main():
    data = json.loads((ROOT / "data" / "tweaks_app.json").read_text(encoding="utf-8"))

    print("Koşullar:")
    for name in sorted(resolvers.CONDITIONS):
        if name in ("guc_plani_mevcut", "gpu_saglayici", "cpu_saglayici", "windows_ozelligi_mevcut"):
            continue  # parametre ister; aşağıda ayar bazında denenir
        print(f"  {name:<24} {resolvers.check_condition({'ad': name})}")
    print(f"  GPU üreticileri          {resolvers.gpu_vendors()}")

    print("\nYer tutuculu / koşullu ayarlar:")
    for tweak in data["ayarlar"]:
        islem = tweak.get("islem")
        conds = tweak["uyumluluk"]["kosullar"]
        if not (conds or (islem and islem.get("cozumleyici"))):
            continue
        cond_results = [resolvers.check_condition(c) for c in conds]
        line = f"  {tweak['id']:<9} {tweak['sinif']:<7}"
        if cond_results:
            line += f" koşullar={cond_results}"
        if islem and islem.get("cozumleyici"):
            res = resolvers.resolve(islem)
            steps = resolvers.expand_steps(islem, res) if res.visible else []
            line += f" çözüm: görünür={res.visible} bağlam={len(res.contexts)} adım={len(steps)}"
            if not res.visible:
                line += f" ({res.reason})"
            leftover = resolvers.find_placeholders(steps)
            if leftover:
                line += f" HATA: çözülmemiş {leftover}"
        print(line)


if __name__ == "__main__":
    main()
