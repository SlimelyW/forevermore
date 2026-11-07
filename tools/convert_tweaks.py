"""tweaks.json + data/islemler.json  ->  data/tweaks_app.json + tools/donusum_raporu.md

Çalıştırma (proje klasöründe):
    py -3.12 tools\\convert_tweaks.py

Bu betik sistemde HİÇBİR ayarı değiştirmez; yalnızca dosya okur ve yazar.

Ne yapar:
  1. Her ayarı SWITCH / REHBER / BİLGİ olarak sınıflandırır.
  2. SWITCH ayarlarının kesin işlemlerini data/islemler.json'dan alır.
  3. tweaks.json'daki serbest metinden komutları otomatik çıkarıp elle yazılmış
     işlemlerle karşılaştırır (yazım hatası yakalamak için).
  4. Windows sürümü ve donanım metinlerini filtrelenebilir alanlara çevirir.
  5. Sonucu doğrular; otomatik dönüştürülemeyen veya belirsiz kalan ayarları
     rapora yazar.
"""

import datetime
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.engine.resolvers import find_placeholders  # noqa: E402
from app.engine.schema import FORBIDDEN_IDS, validate_tweak  # noqa: E402

SOURCE = ROOT / "tweaks.json"
CURATED = ROOT / "data" / "islemler.json"
OUTPUT = ROOT / "data" / "tweaks_app.json"
REPORT = ROOT / "tools" / "donusum_raporu.md"

# Uygulamanın otomatik okuyup değiştirebileceği türler.
AUTOMATABLE_TYPES = {"registry", "powercfg", "servis", "komut", "bcdedit"}


WIN10_BUILDS = {"1703": 15063, "1709": 16299, "1803": 17134, "1903": 18362, "2004": 19041}
WIN11_BUILDS = {"22H2": 22621, "23H2": 22631, "24H2": 26100, "25H2": 26200}

POWERCFG_ALIASES = {
    "SUB_PROCESSOR": "54533251-82be-4824-96c1-47b60b740d00",
    "CPMINCORES": "0cc5b647-c1df-4637-891a-dec35c318583",
    "PROCTHROTTLEMIN": "893dee8e-2bef-41e0-89c6-b55d0929964c",
    "PERFBOOSTMODE": "be337238-0d82-4146-a960-4f3749d470c7",
    "SYSCOOLPOL": "94d3a615-a899-4ac5-ae2b-e4d8f634367f",
    "SUB_DISK": "0012ee47-9041-4b5d-9b77-535fba8b1442",
    "DISKIDLE": "6738e2c4-e8a5-4a42-b16a-e040e769756e",
}

TEXT_PLACEHOLDER_RE = re.compile(r"<[^<>]{2,40}>|\{endpoint-guid\}|'\.\.\.\\")
REG_SET_RE = re.compile(
    r"(?:Set|New)-ItemProperty\s+-Path\s+'(HKCU|HKLM):\\([^']+)'\s+-Name\s+'?([^'\s]+?)'?\s+"
    r"(?:-PropertyType\s+\w+\s+)?-Value\s+('[^']*'|[^\s;]+)",
    re.IGNORECASE,
)
REG_REMOVE_RE = re.compile(
    r"Remove-ItemProperty\s+-Path\s+'(HKCU|HKLM):\\([^']+)'\s+-Name\s+([^;\n]+)",
    re.IGNORECASE,
)
POWERCFG_RE = re.compile(r"setacvalueindex\s+SCHEME_CURRENT\s+(\S+)\s+(\S+)\s+(\d+)", re.IGNORECASE)
SERVICE_RE = re.compile(r"Set-Service\s+(?:-Name\s+)?([\w.]+)\s+-StartupType\s+(\w+)", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Metin yorumlama
# ---------------------------------------------------------------------------

def parse_windows(text):
    """'Windows 10 1803+, Windows 11' gibi metni filtrelenebilir yapıya çevirir."""
    if "bağımsız" in text or "Windows 7" in text:
        return {"surumler": ["10", "11"], "min_build": {"10": None, "11": None}}
    has10 = "Windows 10" in text
    has11 = "Windows 11" in text
    versions = []
    if has10 or not has11:
        versions.append("10")
    if has11 or not has10:
        versions.append("11")
    # Parantez içi notlar (ör. "Dev Drive: Windows 11 23H2+") ayarın kendisi
    # için alt sınır değildir; sürüm numarası yalnızca ana metinden okunur.
    main_text = re.sub(r"\([^)]*\)", "", text)
    m10 = re.search(r"Windows 10 (\d{4})\+", main_text)
    m11 = re.search(r"Windows 11 (\d{2}H\d)\+", main_text)
    return {
        "surumler": versions,
        "min_build": {
            "10": WIN10_BUILDS.get(m10.group(1)) if m10 else None,
            "11": WIN11_BUILDS.get(m11.group(1)) if m11 else None,
        },
    }


def parse_form(text):
    """Form faktörü metni. Yorumlanamazsa None döner."""
    t = text.strip().lower()
    if t == "hepsi" or t.startswith("hepsi "):
        return {"masaustu": "goster", "laptop": "goster"}
    if t == "laptop" or t.startswith("laptop ("):
        return {"masaustu": "gizle", "laptop": "goster"}
    if t == "masaüstü" or t.startswith("masaüstü ("):
        return {"masaustu": "goster", "laptop": "gizle"}
    return None


def parse_gpu(text):
    """GPU metni. (sonuç, anlaşıldı_mı) döner. Sonuç None = tüm GPU'lar."""
    t = text.strip().lower()
    if t.startswith("hepsi"):
        return None, True
    vendors = set()
    if "nvidia" in t:
        vendors.add("NVIDIA")
    if "amd" in t or "radeon" in t:
        vendors.add("AMD")
    if "intel" in t:
        vendors.add("Intel")
    if len(vendors) == 1:
        return sorted(vendors), True
    return None, False


def parse_restart(text):
    t = text.lower()
    if t.startswith("yok (gezgin") or "gezgin" in t:
        return "gezgin"
    if t.startswith("yok"):
        return "yok"
    if "audiosrv" in t or "servis yeniden" in t:
        return "ses_servisi"
    if "oturum" in t:
        return "oturum"
    if "uygulamayı" in t:
        return "uygulama"
    if "yeniden başlatma" in t:
        return "bilgisayar"
    return "durumsal"


_ABBREVIATIONS = ("ör.", "vb.", "bkz.", "vs.", "örn.")


def split_steps(text):
    """Uygulama metnini cümle cümle adımlara böler (ör. 'ör.' kısaltmasında bölmez)."""
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    steps = []
    for part in parts:
        if steps and steps[-1].lower().endswith(_ABBREVIATIONS):
            steps[-1] += " " + part
        else:
            steps.append(part)
    return [s for s in steps if s]


# ---------------------------------------------------------------------------
# Otomatik çıkarım (çapraz kontrol için)
# ---------------------------------------------------------------------------

def _norm_path(path):
    path = re.sub(r"<[^>]+>", "*", path)
    path = re.sub(r"\{\{[a-z_]+\}\}", "*", path)
    return path.lower()


def _norm_value(raw):
    raw = raw.strip()
    if raw.startswith("'") and raw.endswith("'"):
        return raw[1:-1]
    if raw.lower().startswith("0x"):
        return int(raw, 16)
    if raw.isdigit():
        return int(raw)
    return raw


def _same(a, b):
    return str(a) == str(b)


def auto_extract(text):
    """Serbest metindeki registry/powercfg/servis komutlarını çıkarır."""
    found = {"set": {}, "remove": set(), "powercfg": {}, "service": {}}
    for root, path, name, value in REG_SET_RE.findall(text):
        if path.startswith("..."):
            continue
        found["set"][(root, _norm_path(path), name.lower())] = _norm_value(value)
    for root, path, names in REG_REMOVE_RE.findall(text):
        for name in names.split(","):
            found["remove"].add((root, _norm_path(path), name.strip().strip("'").lower()))
    for sub, setting, value in POWERCFG_RE.findall(text):
        sub = POWERCFG_ALIASES.get(sub.upper(), sub).lower()
        setting = POWERCFG_ALIASES.get(setting.upper(), setting).lower()
        found["powercfg"][(sub, setting)] = int(value)
    for name, start in SERVICE_RE.findall(text):
        found["service"][name.lower()] = start
    return found


def cross_check(tweak, islem):
    """Elle yazılmış adımları metinden çıkarılanlarla karşılaştırır.

    Döndürür: [(adım açıklaması, durum, ayrıntı)]
    durum: 'eslesti' | 'farkli' | 'metinde_yok'
    """
    apply_ = auto_extract(tweak["uygulama"])
    undo = auto_extract(tweak["geri_alma"])
    results = []
    for step in islem.get("adimlar", []):
        kind = step["tur"]
        if kind == "registry":
            key = (step["kok"], _norm_path(step["yol"]), step["ad"].lower())
            label = f"{step['kok']}\\...\\{step['ad']}"
            if key in apply_["set"]:
                on_ok = _same(apply_["set"][key], step["acik"])
                if step["kapali"] is None:
                    off_ok = key in undo["remove"] or key not in undo["set"]
                    off_text = "silinir"
                else:
                    off_ok = key not in undo["set"] or _same(undo["set"][key], step["kapali"])
                    off_text = str(step["kapali"])
                if on_ok and off_ok:
                    results.append((label, "eslesti", ""))
                else:
                    results.append((label, "farkli",
                                    f"metin: uygula={apply_['set'][key]!r} geri_al={undo['set'].get(key, 'sil?')!r}; "
                                    f"tanım: acik={step['acik']!r} kapali={off_text}"))
            else:
                results.append((label, "metinde_yok", "Komut metinde PowerShell biçiminde yok (yalnızca açıklama var)"))
        elif kind == "powercfg":
            key = (step["alt_grup"].lower(), step["ayar"].lower())
            label = f"powercfg {step['ayar'][:8]}…"
            if key in apply_["powercfg"]:
                on_ok = apply_["powercfg"][key] == step["acik"]
                off_text = undo["powercfg"].get(key)
                off_ok = off_text is None or step["kapali"] == "plan_varsayilani" or off_text == step["kapali"]
                status = "eslesti" if on_ok and off_ok else "farkli"
                results.append((label, status, "" if status == "eslesti" else
                                f"metin: uygula={apply_['powercfg'][key]} geri_al={off_text}; tanım: {step['acik']}/{step['kapali']}"))
            else:
                results.append((label, "metinde_yok", "powercfg komutu metinde yok"))
        elif kind == "servis":
            name = step["ad"].lower()
            label = f"servis {step['ad']}"
            if name in apply_["service"]:
                on_ok = apply_["service"][name].lower() == step["acik"]["baslangic"].lower()
                off = undo["service"].get(name)
                off_ok = off is None or off.lower() == step["kapali"]["baslangic"].lower()
                status = "eslesti" if on_ok and off_ok else "farkli"
                results.append((label, status, "" if status == "eslesti" else
                                f"metin: {apply_['service'][name]}/{off}; tanım: {step['acik']['baslangic']}/{step['kapali']['baslangic']}"))
            else:
                results.append((label, "metinde_yok", "Set-Service komutu metinde yok"))
        else:
            results.append((f"{kind}", "metinde_yok", "Bu adım türü otomatik karşılaştırılmıyor"))
    return results


# ---------------------------------------------------------------------------
# Sınıflandırma
# ---------------------------------------------------------------------------

def classify(tweak, curated):
    """(sınıf, neden, belirsiz_mi) döndürür.

    Revizyon Faz 2 kuralları: riskli, placebo ve zararlı ayarlar da işlem
    tanımı varsa switch olur (riskli olanlar iki aşamalı onayla). Yalnızca
    yasaklı beş ayar ve uygulamanın yapamadığı ayarlar bilgi kartıdır.
    """
    if tweak["id"] in FORBIDDEN_IDS:
        return "BILGI", "Yasaklı liste: güvenlik nedeniyle hiçbir zaman uygulamadan yapılmaz.", False
    if curated.get("sinif"):
        # Elle verilmiş her sınıf kararı onay için rapora düşer.
        return curated["sinif"], curated.get("sinif_nedeni", ""), True
    if curated.get("islem"):
        return "SWITCH", "Kesin işlem tanımlı (data/islemler.json).", False
    durum = tweak["gerceklik"]["durum"]
    if tweak["risk"] == "riskli" or durum in ("placebo", "zararlı") or tweak["kategori"] == "Placebo":
        return "BILGI", curated.get("bilgi_nedeni") or "İşlem tanımı yok; bilgi kartı.", not curated.get("bilgi_nedeni")
    if tweak["tip"] in AUTOMATABLE_TYPES:
        return "REHBER", "Otomatik türde ama data/islemler.json'da kesin işlem tanımı yok.", True
    return "REHBER", f"'{tweak['tip']}' türü kullanıcının elle yapacağı bir ayar.", False


def bilgi_reason(tweak, placebo_reasons):
    return placebo_reasons.get(tweak["id"]) or tweak["gerceklik"].get("aciklama") or ""


# ---------------------------------------------------------------------------
# Ana dönüşüm
# ---------------------------------------------------------------------------

def apply_sade_adlar(tweaks, sade, report):
    """data/sade_adlar.json -> ayarın `sade_ad` alanı. Katalogda olmayan kimlik rapora HATA olarak yazılır."""
    for tweak in tweaks:
        if tweak["id"] in sade:
            tweak["sade_ad"] = sade[tweak["id"]]
    known = {t["id"] for t in tweaks}
    for tid in sade:
        if tid not in known:
            report["hata"].append(f"sade_adlar.json'da olmayan kimlik: {tid}")


def convert():
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    curated_all = json.loads(CURATED.read_text(encoding="utf-8"))["ayarlar"]

    category_ids = {c["ad"]: c["id"] for c in source["kategoriler"]}
    placebo_reasons = {}
    for key in ("liste", "diger_kategorilerde_placebo_veya_zararli"):
        for item in source["placebo_menusu"].get(key, []):
            placebo_reasons[item["id"]] = item.get("neden", "")

    source_ids = {t["id"] for t in source["ayarlar"]}
    unknown_curated = sorted(set(curated_all) - source_ids)

    out_tweaks = []
    report = defaultdict(list)

    for tweak in source["ayarlar"]:
        tid = tweak["id"]
        curated = curated_all.get(tid, {})
        sinif, reason, ambiguous = classify(tweak, curated)

        # --- uyumluluk
        windows = parse_windows(tweak["windows"])
        form = parse_form(tweak["donanim"]["form"])
        gpu, gpu_ok = parse_gpu(tweak["donanim"]["gpu"])
        cur_uyum = curated.get("uyumluluk", {})
        if form is None and "form" not in cur_uyum:
            report["donanim"].append((tid, "form", tweak["donanim"]["form"]))
            form = {"masaustu": "goster", "laptop": "goster"}
        if not gpu_ok and "gpu" not in cur_uyum:
            report["donanim"].append((tid, "gpu", tweak["donanim"]["gpu"]))
        uyumluluk = {
            "windows": cur_uyum.get("windows", windows),
            "form": cur_uyum.get("form", form),
            "gpu": cur_uyum.get("gpu", gpu),
            "kosullar": cur_uyum.get("kosullar", []),
            "kaynak_metin": {"windows": tweak["windows"], **tweak["donanim"]},
        }
        report["windows"].append((tid, tweak["windows"], uyumluluk["windows"]))

        out = {
            "id": tid,
            "kategori_id": category_ids.get(tweak["kategori"], tid.split("-")[0]),
            "kategori": tweak["kategori"],
            "ad": tweak["ad"],
            "sinif": sinif,
            "sinif_nedeni": reason,
            "risk": tweak["risk"],
            # 0: onaysız, 1: dikkatli (açarken tek onay), 2: riskli (açarken ve kapatırken iki aşama)
            "onay_seviyesi": {"dikkatli": 1, "riskli": 2}.get(tweak["risk"], 0),
            "onay_gerekli": tweak["risk"] in ("dikkatli", "riskli"),
            "performans_etkisi": tweak["performans_etkisi"],
            "gerceklik": tweak["gerceklik"],
            "ne_ise_yarar": tweak["ne_ise_yarar"],
            "artilar": tweak["artilar"],
            "eksiler": tweak["eksiler"],
            "dokunmamali": tweak["dokunmamali"],
            "notlar": curated.get("notlar", []),
            "varsayilan": tweak["varsayilan"],
            "yonetici": tweak["yonetici"],
            "yeniden_baslatma": tweak["yeniden_baslatma"],
            "yeniden_baslatma_kodu": parse_restart(tweak["yeniden_baslatma"]),
            "uyumluluk": uyumluluk,
            "kaynaklar": tweak["kaynaklar"],
            "kaynak_metin": {k: tweak[k] for k in ("tip", "okuma", "uygulama", "geri_alma")},
        }

        if isinstance(curated.get("rev"), int):
            out["rev"] = curated["rev"]  # ayarın adımları değişince artırılır; "Güncellendi" rozeti için

        if sinif == "SWITCH":
            out["islem"] = curated["islem"]
            for label, status, detail in cross_check(tweak, curated["islem"]):
                report["capraz"].append((tid, label, status, detail))
        if curated.get("nvidia"):
            out["nvidia"] = curated["nvidia"]  # NVAPI sürücü ayarı: kimlik ve seçenekler
        if curated.get("amd"):
            out["amd"] = curated["amd"]  # ADLX sürücü ayarı: hangi özellikler (anti_lag, chill, boost, enhanced_sync)
        if curated.get("liste_yoneticisi"):
            out["liste_yoneticisi"] = curated["liste_yoneticisi"]  # uygulamanın kendi listesiyle yapılır (başlangıç, MSI, aygıt gücü)
        if curated.get("kaynaklar_ek"):  # Revizyon 2: araştırmayla eklenen kaynaklar
            out["kaynaklar"] = list(out["kaynaklar"]) + [u for u in curated["kaynaklar_ek"] if u not in out["kaynaklar"]]
        if curated.get("geri_yukleme_zorunlu"):
            out["geri_yukleme_zorunlu"] = True  # geri yükleme noktası olmadan uygulanmaz (CPU-004)
        if curated.get("elle_nedeni"):
            out["elle_nedeni"] = curated["elle_nedeni"]  # uygulamanın yapamadığı ayar: neden (Elle yapılacaklar)
        if curated.get("ilgili"):
            out["ilgili"] = curated["ilgili"]  # aynı işi yapan başka ayar (ör. PLC-028 → NET-006)
        if sinif in ("SWITCH", "REHBER"):
            out["rehber"] = {
                "adimlar": curated.get("rehber", {}).get("adimlar") or split_steps(tweak["uygulama"]),
                "kontrol": tweak["okuma"],
                "geri_alma": tweak["geri_alma"],
                "ac": curated.get("rehber", {}).get("ac"),
            }
            opener = out["rehber"]["ac"]
            if opener and opener.get("dogrulanmadi"):
                report["dogrulanmamis_ac"].append((tid, opener["hedef"]))
        if sinif == "BILGI":
            out["bilgi"] = {"neden": bilgi_reason(tweak, placebo_reasons),
                            "yapilamaz_nedeni": curated.get("bilgi_nedeni", "")}
            if curated.get("rehber", {}).get("ac"):
                out["rehber"] = {"adimlar": [], "kontrol": tweak["okuma"],
                                 "geri_alma": tweak["geri_alma"], "ac": curated["rehber"]["ac"]}
        if curated.get("tespit"):
            out["tespit"] = curated["tespit"]
        if curated.get("islem") and sinif != "SWITCH":
            report["engellenen"].append((tid, reason))

        # --- yer tutucular
        text_ph = sorted(set(TEXT_PLACEHOLDER_RE.findall(
            " ".join(tweak[k] for k in ("okuma", "uygulama", "geri_alma")))))
        if text_ph:
            if sinif == "SWITCH":
                resolver = curated["islem"].get("cozumleyici", {}).get("ad")
                code_ph = sorted(find_placeholders(curated["islem"]))
                how = (f"Çalışma anında '{resolver}' çözümleyicisi bulur: {code_ph}. Bulunamazsa ayar gizlenir."
                       if resolver else "Switch işlemi yer tutucu gerektirmiyor (metindeki yer tutucu yalnızca açıklama/alternatif yol).")
            elif sinif == "REHBER":
                how = "Rehber metninde gösterilir; kullanıcı kendi değerini kullanır."
            else:
                how = "Bilgi kartı; uygulanmaz."
            report["yer_tutucu"].append((tid, sinif, ", ".join(text_ph), how))

        if ambiguous or curated.get("belirsizlik"):
            report["belirsiz"].append((tid, tweak["ad"], tweak["tip"], tweak["risk"], sinif,
                                       curated.get("belirsizlik") if sinif == "SWITCH" else reason))

        for err in validate_tweak(out):
            report["hata"].append(err)
        out_tweaks.append(out)

    sade = json.loads((ROOT / "data" / "sade_adlar.json").read_text(encoding="utf-8"))["ayarlar"]
    apply_sade_adlar(out_tweaks, sade, report)

    meta = dict(source["meta"])
    meta["anti_cheat_uyarisi"] = next(
        (w for w in meta.get("genel_uyarilar", []) if "anti-cheat" in w.lower()), "")
    meta["donusum"] = {
        "uretici": "tools/convert_tweaks.py",
        "tarih": datetime.date.today().isoformat(),
        "kaynak": "tweaks.json + data/islemler.json",
        "uyari": "Bu dosya otomatik üretilir. Elle düzenlemeyin; tweaks.json veya data/islemler.json'u değiştirip betiği yeniden çalıştırın.",
    }
    output = {
        "meta": meta,
        "kategoriler": source["kategoriler"],
        "arastirma_notlari": source["arastirma_notlari"],
        "placebo_menusu": source["placebo_menusu"],
        "ayarlar": out_tweaks,
    }
    for tid in unknown_curated:
        report["hata"].append(f"islemler.json'da tweaks.json'da olmayan kimlik: {tid}")
    return output, report


# ---------------------------------------------------------------------------
# Rapor
# ---------------------------------------------------------------------------

def _md_escape(text):
    return str(text).replace("|", "\\|").replace("\n", " ")


def write_report(output, report):
    tweaks = output["ayarlar"]
    lines = [
        "# Dönüşüm raporu",
        "",
        f"Üretim: `tools/convert_tweaks.py` — {datetime.date.today().isoformat()}. "
        "Bu dosya her çalıştırmada yeniden yazılır.",
        "",
        "## 1. Özet",
        "",
    ]
    by_class = Counter(t["sinif"] for t in tweaks)
    lines.append(f"Toplam {len(tweaks)} ayar: **SWITCH {by_class['SWITCH']}**, "
                 f"**REHBER {by_class['REHBER']}**, **BİLGİ {by_class['BILGI']}**.")
    careful = [t["id"] for t in tweaks if t["sinif"] == "SWITCH" and t["onay_seviyesi"] == 1]
    lines.append(f"SWITCH'lerin {len(careful)} tanesi 'dikkatli' (açarken tek onay): {', '.join(careful)}.")
    risky_switch = [t["id"] for t in tweaks if t["sinif"] == "SWITCH" and t["onay_seviyesi"] == 2]
    lines.append(f"Riskli switch ({len(risky_switch)}, açarken ve kapatırken iki aşamalı onay): {', '.join(risky_switch)}.")
    placebo_switch = [t["id"] for t in tweaks if t["sinif"] == "SWITCH"
                      and t["gerceklik"]["durum"] in ("placebo", "zararlı")]
    lines.append(f"Placebo/zararlı switch ({len(placebo_switch)}): {', '.join(placebo_switch)}.")
    forbidden = [t["id"] for t in tweaks if t["id"] in FORBIDDEN_IDS]
    lines.append(f"Yasaklı (hiçbir zaman switch olmaz): {', '.join(forbidden)}.")
    lines += ["", "| Kategori | SWITCH | REHBER | BİLGİ |", "|---|---|---|---|"]
    per_cat = defaultdict(Counter)
    for t in tweaks:
        per_cat[t["kategori"]][t["sinif"]] += 1
    for cat in output["kategoriler"]:
        c = per_cat[cat["ad"]]
        lines.append(f"| {cat['ad']} | {c['SWITCH']} | {c['REHBER']} | {c['BILGI']} |")

    lines += ["", "## 2. Doğrulama hataları", ""]
    if report["hata"]:
        lines += [f"- {e}" for e in report["hata"]]
    else:
        lines.append("Yok. Tüm ayarlar şema doğrulamasından geçti.")

    lines += [
        "", "## 3. Otomatik dönüştürülemeyen veya belirsiz kalan ayarlar (SENİN ONAYIN GEREKİYOR)", "",
        "Otomatik türde (registry/powercfg/servis/komut) olup switch yapılMAyanlar ve switch yapılan ama "
        "emin olmadığım noktası bulunanlar.", "",
        "| ID | Ad | Tür | Risk | Karar | Neden / belirsizlik |", "|---|---|---|---|---|---|",
    ]
    for tid, name, tip, risk, sinif, why in report["belirsiz"]:
        lines.append(f"| {tid} | {_md_escape(name)} | {tip} | {risk} | {sinif} | {_md_escape(why)} |")

    lines += ["", "## 4. Elle tanım ↔ metinden otomatik çıkarım karşılaştırması", ""]
    statuses = Counter(s for _, _, s, _ in report["capraz"])
    lines.append(f"Eşleşen: {statuses['eslesti']}, farklı: {statuses['farkli']}, "
                 f"metinde komut yok: {statuses['metinde_yok']}.")
    lines += ["", "| ID | Adım | Durum | Ayrıntı |", "|---|---|---|---|"]
    for tid, label, status, detail in report["capraz"]:
        if status != "eslesti":
            lines.append(f"| {tid} | {_md_escape(label)} | {status} | {_md_escape(detail)} |")

    lines += ["", "## 5. Yer tutucular", "",
              "| ID | Sınıf | Metindeki yer tutucu | Nasıl çözülüyor |", "|---|---|---|---|"]
    for tid, sinif, found, how in report["yer_tutucu"]:
        lines.append(f"| {tid} | {sinif} | `{_md_escape(found)}` | {_md_escape(how)} |")

    lines += ["", "## 6. Kurala takılıp switch olmaktan çıkarılanlar", ""]
    if report["engellenen"]:
        lines += [f"- {tid}: {why}" for tid, why in report["engellenen"]]
    else:
        lines.append("Yok.")

    lines += ["", "## 7. Yorumlanamayan donanım metinleri", ""]
    if report["donanim"]:
        lines += [f"- {tid} ({field}): \"{text}\" → tüm sistemlerde gösterilecek" for tid, field, text in report["donanim"]]
    else:
        lines.append("Yok (yorumlanamayanların hepsi islemler.json'da elle tanımlandı).")

    lines += ["", "## 8. Windows sürüm metinleri nasıl yorumlandı", "",
              "| Metin | Sürümler | En düşük build |", "|---|---|---|"]
    seen = set()
    for _tid, text, parsed in report["windows"]:
        key = (text, json.dumps(parsed, sort_keys=True))
        if key in seen:
            continue
        seen.add(key)
        builds = ", ".join(f"W{k}≥{v}" for k, v in parsed["min_build"].items() if v) or "—"
        lines.append(f"| {_md_escape(text)} | {', '.join(parsed['surumler'])} | {builds} |")

    lines += ["", "## 9. Doğrulanmamış 'Ayarı aç' bağlantıları (test listesinde denenecek)", ""]
    lines += [f"- {tid}: `{target}`" for tid, target in report["dogrulanmamis_ac"]] or ["Yok."]

    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    output, report = convert()
    OUTPUT.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_report(output, report)
    counts = Counter(t["sinif"] for t in output["ayarlar"])
    print(f"Yazıldı: {OUTPUT.relative_to(ROOT)} ({len(output['ayarlar'])} ayar: "
          f"SWITCH {counts['SWITCH']}, REHBER {counts['REHBER']}, BİLGİ {counts['BILGI']})")
    print(f"Rapor:   {REPORT.relative_to(ROOT)}")
    if report["hata"]:
        print(f"HATA: {len(report['hata'])} doğrulama hatası var, rapora bakın.")
        return 1
    print("Doğrulama hatası yok.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
