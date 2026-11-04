"""Site demosunun verisini uygulamanın kendi dosyalarından üretir (geliştirme aracı).

    py -3.12 tools\\site_veri.py

- site/veri.js: tahmin oyunu, örnek tarama, geri alma, ayar künyesi, oyun listesi ve Steam appid'leri (TR + EN).
- site/index.html, site/en.html: <!--n:ad-->...<!--/n--> sayaçları ve <!--v:yol-->...<!--/v--> metinleri (ör. olcum.aciklama) yeniden yazılır.
Kaynaklar: data/tweaks_app.json, data/ceviriler/en.json, lang/tr.json, lang/en.json. Metinleri elle değiştirmeyin.
"""

import html
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"

SLUG = {"gerçek": "gercek", "kısmen gerçek": "kismen", "durumsal": "durumsal",
        "tartışmalı": "tartisma", "placebo": "placebo", "zararlı": "zararli"}
ORDER = ["gerçek", "kısmen gerçek", "durumsal", "tartışmalı", "placebo", "zararlı"]
QUIZ_IDS = ["PLC-001", "DISP-001", "PLC-003", "SYS-006", "SYS-004", "PLC-008", "PERF-002", "SYS-005"]
CHANGE_IDS = ["DISP-001", "SYS-006", "PERF-002"]
KUNYE_IDS = ["DISP-001", "SYS-007", "DISP-005", "DISP-004", "SYS-004", "PLC-002"]   # her etiketten bir örnek
# Örnek bilgisayar (uydurma): tarama demosunda kullanılan değerler
SAMPLE = {"monitor": "Monitör 1", "hz": 60, "max_hz": 144, "adet": 14, "hiz": 2133}
FINDINGS = ["ekran_hz_dusuk", "ram_tek_kanal", "baslangic_cok", "ram_xmp"]


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def fill(text, values):
    return re.sub(r"\{(\w+)\}", lambda m: str(values.get(m.group(1), m.group(0))), text)


def build():
    catalog = load("data/tweaks_app.json")["ayarlar"]
    en_catalog = load("data/ceviriler/en.json")["ayarlar"]
    langs = {"tr": load("lang/tr.json"), "en": load("lang/en.json")}
    anti_cheat = {"tr": load("data/tweaks_app.json")["meta"]["anti_cheat_uyarisi"],
                  "en": load("data/ceviriler/en.json")["genel"]["meta.anti_cheat_uyarisi"]}
    by_id = {t["id"]: t for t in catalog}
    counts = Counter(t["gerceklik"]["durum"] for t in catalog)
    games = [g["ad"] for g in load("data/oyun_rehberi.json")["oyunlar"]]
    out = {}
    for code, lang in langs.items():
        def name(t):
            return t["ad"] if code == "tr" else en_catalog[t["id"]]["ad"]

        def reason(t):
            return t["gerceklik"]["aciklama"] if code == "tr" else en_catalog[t["id"]]["gerceklik.aciklama"]

        label = {SLUG[d]: lang[f"deger.gerceklik.{d}"] for d in ORDER}
        impact = lambda t: lang[f"deger.etki.{t['performans_etkisi']['seviye']}"]
        risk = lambda t: lang.get(f"deger.risk.{t['risk']}", t["risk"])
        out[code] = {
            "n": {"toplam": len(catalog), **{SLUG[d]: counts[d] for d in ORDER}},
            "etiket": label,
            "tahmin": [{"id": i, "ad": name(by_id[i]), "durum": SLUG[by_id[i]["gerceklik"]["durum"]],
                        "neden": reason(by_id[i])} for i in QUIZ_IDS],
            "tarama": {
                "bulgular": [{"baslik": lang[f"bulgu.{k}.baslik"], "aciklama": fill(lang[f"bulgu.{k}.aciklama"], SAMPLE)}
                             for k in FINDINGS],
                "okunur": lang["ui.tarama_salt_okunur"],
            },
            "degisiklik": [{"id": i, "ad": name(by_id[i])} for i in CHANGE_IDS],
            "kunye": [{"id": i, "ad": name(by_id[i]), "durum": SLUG[by_id[i]["gerceklik"]["durum"]],
                       "etki": impact(by_id[i]), "risk": risk(by_id[i]), "neden": reason(by_id[i])} for i in KUNYE_IDS],
            "oyunlar": games,
            "steam": {g: STEAM_APPID[g] for g in games if g in STEAM_APPID},
            "kapak": {g: OTHER_COVER[g] for g in games if g in OTHER_COVER},
            "olcum": {"aciklama": lang["olcum.aciklama"], "durustluk": lang["olcum.durustluk"]},
            "sinir": {"uac": lang["ui.uac.not"], "wu": lang["ui.wu.not"], "anticheat": anti_cheat[code]},
        }
    return out


# Steam appid'leri (sitedeki oyun kapak görselleri için). Her biri 29 Ekim 2026'da Steam'in
# store.steampowered.com/api/appdetails yanıtındaki adla doğrulandı. Steam'de olmayan oyun (LoL, Valorant,
# TFT, Fortnite, Minecraft) bilerek yok: sitede görselsiz, yazılı etiket olarak kalır. Tahminle id eklemeyin.
STEAM_APPID = {
    "ARC Raiders": 1808500, "Counter-Strike 2": 730, "Destiny 2": 1085660, "Marvel Rivals": 2767030,
    "Once Human": 2139460, "Overwatch 2": 2357570, "PUBG: BATTLEGROUNDS": 578080, "Rocket League": 252950,
    "THE FINALS": 2073850, "The First Descendant": 2074920, "Tom Clancy's Rainbow Six Siege": 359550,
    "Warframe": 230410, "Apex Legends": 1172470, "Cyberpunk 2077": 1091500, "Grand Theft Auto V": 271590,
    "Call of Duty: Warzone": 1962663, "Dota 2": 570, "Rust": 252490, "Elden Ring": 1245620, "Deadlock": 1422450,
}

# Steam'de olmayan oyunların kapağı: yayıncının ya da resmî mağazanın kendi görsel sunucusu (30 Ekim 2026'da doğrulandı).
# Minecraft/Fortnite/Valorant: Microsoft displaycatalog API (9MVXMVT8ZKWC "Minecraft" Microsoft Studios,
# BT5P2X999VH2 "Fortnite" Epic Games Inc., 9N1NLJK9SKRN "VALORANT" Riot Games), TitledHeroArt 1920x1080, 368x207'ye küçültülmüş.
# TFT: Apple lookup id 1480616748 "TFT: Teamfight Tactics", satıcı Riot Games, mağaza ekran görüntüsü 1.
# League of Legends: mağaza kapağı yok; Riot Data Dragon'un belgeli şampiyon görseli (Ahri, ana görünüm).
# Adres değişirse sitede kart simge + adla kalır; tahminle adres eklemeyin.
OTHER_COVER = {
    "Minecraft": "https://store-images.s-microsoft.com/image/apps.964.13850085746326678.06e2dc5c-7997-46e9-a8e6-0e48b57cb13b.caac2a25-0ba1-480f-a6a3-87b84e4affcb?q=85&w=368&h=207",
    "Fortnite": "https://store-images.s-microsoft.com/image/apps.60143.70702278257994163.6d75301b-59c3-4a73-b70c-5901ae9cbb44.b4128829-0f4a-4974-8765-24aa73a79dc8?q=85&w=368&h=207",
    "Valorant": "https://store-images.s-microsoft.com/image/apps.46961.13898029070941789.b9070612-bb75-4081-8f05-4acaf8e47425.7e5dd477-7b17-4a3f-b59f-14c8d26413ca?q=85&w=368&h=207",
    "Teamfight Tactics": "https://is1-ssl.mzstatic.com/image/thumb/PurpleSource221/v4/50/85/e7/5085e741-2ff0-d8aa-0d1b-3b93407f31d8/TFT_ST1826_ASO_ScreenshotUpdates_01_2208x1242_UPDATED_v001_SCha.png/406x228bb.jpg",
    "League of Legends": "https://ddragon.leagueoflegends.com/cdn/img/champion/splash/Ahri_0.jpg",
}


def patch(path, data):
    counts = data["n"]
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"<!--n:(\w+)-->.*?<!--/n-->", lambda m: f"<!--n:{m.group(1)}-->{counts[m.group(1)]}<!--/n-->", text)
    def value(m):
        item = data
        for part in m.group(1).split("."):
            item = item[part]
        return f"<!--v:{m.group(1)}-->{html.escape(item)}<!--/v-->"

    text = re.sub(r"<!--v:([\w.]+)-->.*?<!--/v-->", value, text)
    path.write_text(text, encoding="utf-8")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    data = build()
    (SITE / "veri.js").write_text(
        "/* tools/site_veri.py üretir; elle değiştirmeyin. */\nwindow.FM_VERI = "
        + json.dumps(data, ensure_ascii=False, indent=1) + ";\n", encoding="utf-8")
    for code, page in (("tr", "index.html"), ("en", "en.html")):
        if (SITE / page).exists():
            patch(SITE / page, data[code])
    print("site/veri.js yazıldı;", data["tr"]["n"])


if __name__ == "__main__":
    main()
