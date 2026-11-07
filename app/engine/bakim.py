"""Bakım araçları: Windows'un KENDİ araçlarını çalıştırır; hiçbir ayar yazmaz, hiçbir araç indirmez/gömmez.

- sistem_onar: `sfc /scannow`, sonra `DISM /Online /Cleanup-Image /RestoreHealth` (yönetici ister, 10-30 dk).
- optimize: SSD'de `Optimize-Volume -ReTrim` (TRIM), HDD'de `-Defrag` (birleştirme).

GÜVENLİK: komutlar bu dosyada sabittir; arayüz yalnızca sürücü HARFİ gönderir, harf her seferinde yeniden okunan
sabit sürücü listesinde yoksa çalıştırılmaz. Kabuk kullanılmaz (liste olarak Popen), araçlar System32'den tam yolla çağrılır.
Metin sonuçları Windows diline bağlıdır: tanınmazsa "belirsiz" denir, ham çıktı her zaman kullanıcıya gösterilir.
Ayrıntı: docs/GUVENLIK.md "Bakım araçları".
"""

import os
import re
import subprocess
import threading

from app.core import admin, log, powershell
from app.scan import storage

_log = log.get("bakim")

CREATE_NO_WINDOW = 0x08000000
MAX_CIKTI = 200_000  # karakter; fazlası baştan kırpılır (sondaki sonuç satırları kalır)
_YUZDE = re.compile(r"(\d{1,3})(?:[.,]\d)?\s*%|%\s*(\d{1,3})")

# Sonuç metni tanıma (küçük harfe çevrilmiş). Yalnızca İngilizce ve Türkçe Windows; başka dilde "belirsiz" çıkar.
_SFC_ONARILAMADI = ("unable to fix", "could not perform", "onaramad", "düzeltemedi", "gerçekleştiremedi")
_SFC_ONARILDI = ("successfully repaired", "başarıyla onard")
_SFC_TEMIZ = ("did not find any integrity violations", "bütünlük ihlali bulamad")

# Sürücü türü -> (Optimize-Volume anahtarı, sonuçta kullanılan ad). Türü bilinmeyen sürücü çalıştırılmaz.
_ISLEM = {"SSD": ("-ReTrim", "trim"), "HDD": ("-Defrag", "birlestir")}

_SURUCU_PS = (
    "$pd=@{}; Get-PhysicalDisk | ForEach-Object { $pd[[string]$_.DeviceId]=[string]$_.MediaType };"
    "$fix=@(Get-Volume | Where-Object { $_.DriveLetter -and [string]$_.DriveType -eq 'Fixed' } "
    "| ForEach-Object { [string]$_.DriveLetter });"
    "Get-Partition | Where-Object { $_.DriveLetter -and $fix -contains [string]$_.DriveLetter } "
    "| ForEach-Object { [pscustomobject]@{ harf=[string]$_.DriveLetter; tur=$pd[[string]$_.DiskNumber] } }"
)


# ------------------------------------------------------------------ süreç çalıştırma
def decode(data):
    """sfc çıktısı borulandığında UTF-16 gelir (NUL'lu); PowerShell UTF-8 yazar."""
    if data.count(b"\x00") > len(data) // 4:
        return data[:len(data) // 2 * 2].decode("utf-16-le", "replace").lstrip("﻿")
    return data.decode("utf-8", "replace")


def yuzde(text):
    """Çıktının SON ilerleme yüzdesi (0-100) ya da None."""
    found = None
    for match in _YUZDE.finditer(text[-600:]):
        found = int(match.group(1) or match.group(2))
    return found if found is None or 0 <= found <= 100 else None


def temizle(text):
    """Ham çıktıyı okunur yapar: \\r ilerleme satırlarının yalnızca sonuncusu kalır, boş satırlar atılır, uzunluk sınırlanır."""
    lines = []
    for line in re.split(r"[\r\n]+", text):
        line = line.rstrip()
        if not line.strip():
            continue
        if lines and _YUZDE.search(line) and _YUZDE.search(lines[-1]):
            lines[-1] = line
        else:
            lines.append(line)
    return "\n".join(lines)[-MAX_CIKTI:]


def calistir(komut, iptal, ilerleme=None):
    """Komutu pencere açmadan çalıştırır. (çıkış kodu, ham bayt) döner; iptal olursa süreç sonlandırılır (kod None).
    ilerleme(yüzde|None) çıktı geldikçe çağrılır (çalıştıran iş parçacığından DEĞİL, okuyucu iş parçacığından)."""
    proc = subprocess.Popen(komut, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            creationflags=CREATE_NO_WINDOW, env=powershell.clean_env())
    buffer = bytearray()

    def read():
        while True:
            chunk = proc.stdout.read1(512)
            if not chunk:
                return
            buffer.extend(chunk)
            if ilerleme:
                ilerleme(yuzde(decode(bytes(buffer[-1200:]))))

    reader = threading.Thread(target=read, name="bakim_okuyucu", daemon=True)
    reader.start()
    cancelled = False
    while True:
        try:
            proc.wait(0.5)
            break
        except subprocess.TimeoutExpired:
            if iptal.is_set():
                cancelled = True
                proc.terminate()
                try:
                    proc.wait(10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                break
    reader.join(5)
    proc.stdout.close()
    return (None if cancelled else proc.returncode), bytes(buffer)


# ------------------------------------------------------------------ sistem dosyalarını onar
def _komutlar():
    system = powershell.SYSTEM32
    return (("sfc", [os.path.join(system, "sfc.exe"), "/scannow"]),
            ("dism", [os.path.join(system, "Dism.exe"), "/Online", "/Cleanup-Image", "/RestoreHealth"]))


def sfc_sonucu(text):
    low = text.casefold()
    if any(k in low for k in _SFC_ONARILAMADI):
        return "onarilamadi"
    if any(k in low for k in _SFC_ONARILDI):
        return "onarildi"
    if any(k in low for k in _SFC_TEMIZ):
        return "temiz"
    return "belirsiz"


def birlestir(sfc, dism):
    """İki adımın sonucundan tek sonuç. DISM çıkış kodu dilden bağımsızdır (0 = başarılı)."""
    if dism != "tamam":
        return "onarilamadi"
    return {"temiz": "temiz", "onarildi": "onarildi", "onarilamadi": "tekrar"}.get(sfc, "belirsiz")


def sistem_onar(iptal, ilerleme=None, calis=calistir, yonetici=admin.is_admin):
    """sfc ardından DISM. ilerleme(adım, toplam, yüzde|None). Dönen sözlük:
    sonuc: temiz | onarildi | tekrar | onarilamadi | belirsiz | iptal | yetki | baslatilamadi; cikti: ham metin."""
    if not yonetici():
        return {"sonuc": "yetki", "cikti": ""}
    steps = _komutlar()
    parts, results = [], {}
    for index, (name, command) in enumerate(steps, 1):
        if iptal.is_set():
            return {"sonuc": "iptal", "cikti": "\n\n".join(parts)}
        if ilerleme:
            ilerleme(index, len(steps), None)
        try:
            code, data = calis(command, iptal, (lambda p, i=index: ilerleme(i, len(steps), p)) if ilerleme else None)
        except OSError as exc:
            _log.error("%s başlatılamadı: %s", name, exc)
            return {"sonuc": "baslatilamadi", "cikti": "\n\n".join(parts + [f"{name}: {exc}"])}
        text = temizle(decode(data))
        parts.append(f"> {os.path.basename(command[0])} {' '.join(command[1:])}\n{text}\n(çıkış kodu: {code})")
        if code is None:
            return {"sonuc": "iptal", "cikti": "\n\n".join(parts)}
        results[name] = sfc_sonucu(text) if name == "sfc" else ("tamam" if code == 0 else "hata")
    final = birlestir(results["sfc"], results["dism"])
    _log.info("Sistem dosyası onarımı bitti: sfc=%s dism=%s", results["sfc"], results["dism"])
    return {"sonuc": final, "cikti": "\n\n".join(parts)}


# ------------------------------------------------------------------ sürücü optimizasyonu
def suruculer():
    """Sabit sürücüler: [{'harf': 'C', 'tur': 'SSD' | 'HDD' | 'bilinmiyor'}]. Yalnızca okur."""
    result = []
    for row in powershell.run_json(_SURUCU_PS, timeout=60):
        letter = str(row.get("harf") or "")
        if re.fullmatch(r"[A-Za-z]", letter):
            result.append({"harf": letter.upper(), "tur": storage.MEDIA_TUR.get(str(row.get("tur")), "bilinmiyor")})
    return sorted(result, key=lambda d: d["harf"])


def _optimize_komut(letter, flag):
    script = ("$ErrorActionPreference='Stop';[Console]::OutputEncoding=[System.Text.Encoding]::UTF8;"
              f"Optimize-Volume -DriveLetter {letter} {flag} -Verbose *>&1")
    exe = os.path.join(powershell.SYSTEM32, "WindowsPowerShell", "v1.0", "powershell.exe")
    return [exe, "-NoProfile", "-NonInteractive", "-Command", script]


def optimize(harfler, iptal, ilerleme=None, calis=calistir, liste=suruculer, yonetici=admin.is_admin):
    """Seçilen sürücülerde sırayla optimize eder. ilerleme(sıra, toplam, harf). Dönen sözlük:
    sonuc: tamam | kismen | hata | iptal | yetki | yok; suruculer: [{harf, tur, islem, tamam}]; cikti: ham metin."""
    if not yonetici():
        return {"sonuc": "yetki", "suruculer": [], "cikti": ""}
    known = {d["harf"]: d for d in liste()}
    chosen = [known[h] for h in dict.fromkeys(str(h).upper() for h in harfler)
              if h in known and known[h]["tur"] in _ISLEM]  # listede olmayan / türü bilinmeyen sürücü çalışmaz
    if not chosen:
        return {"sonuc": "yok", "suruculer": [], "cikti": ""}
    done, parts = [], []
    for index, drive in enumerate(chosen, 1):
        if iptal.is_set():
            return {"sonuc": "iptal", "suruculer": done, "cikti": "\n\n".join(parts)}
        flag, operation = _ISLEM[drive["tur"]]
        if ilerleme:
            ilerleme(index, len(chosen), drive["harf"])
        try:
            code, data = calis(_optimize_komut(drive["harf"], flag), iptal, None)
        except OSError as exc:
            code, data = 1, str(exc).encode()
        parts.append(f"> Optimize-Volume {drive['harf']}: {flag}\n{temizle(decode(data))}\n(çıkış kodu: {code})")
        if code is None:
            return {"sonuc": "iptal", "suruculer": done, "cikti": "\n\n".join(parts)}
        done.append({"harf": drive["harf"], "tur": drive["tur"], "islem": operation, "tamam": code == 0})
    ok = sum(d["tamam"] for d in done)
    return {"sonuc": "tamam" if ok == len(done) else "kismen" if ok else "hata", "suruculer": done,
            "cikti": "\n\n".join(parts)}
