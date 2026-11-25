"""Bakım araçları (ikinci küme): ağ sıfırlama, Windows Update onarma, disk taraması, bileşen deposu temizliği,
ayrılmış depolama. Windows'un KENDİ araçlarını Microsoft'un belgeli adımlarıyla çalıştırır; hiçbir araç indirmez/gömmez.

GÜVENLİK (bakim.py ile aynı kurallar, ayrıntı docs/GUVENLIK.md "Bakım araçları"):
- Komutlar bu dosyada sabittir. Arayüz yalnızca araç kimliği ve (disk taramasında) sürücü HARFİ gönderir; harf her
  seferinde yeniden okunan NTFS sabit sürücü listesinde yoksa çalıştırılmaz. Kabuk kullanılmaz (liste olarak Popen).
- Araçlar System32'den tam yolla çağrılır; dosya yolları ortam değişkeninden değil Windows'tan okunur.
- Uzun işler arayüzden iş parçacığında çağrılır (calistir_arac); iptal edilirse çalışan süreç sonlandırılır.
- Windows Update onarmada hizmetler (bits, wuauserv, cryptsvc) iptal ya da hata olsa da yeniden başlatılır.
- Microsoft'un belgesinde olmayan adım YOK: ilke anahtarlarına, güvenlik şablonuna, GroupPolicy klasörlerine dokunulmaz;
  `sc sdset` ve `regsvr32` adımları (belgede "yalnızca başka çözüm kalmadıysa") uygulanmaz; DISM `/ResetBase` ASLA.
"""

import datetime
import glob
import os
import threading

from app.core import admin, guvenli_klasor, log, paths, powershell
from app.engine import bakim

_log = log.get("bakim")

HIZMETLER = ("bits", "wuauserv", "cryptsvc")  # Microsoft'un sırası
NET_TAMAM = (0, 2)       # net.exe: 2 = hizmet zaten durmuş / çalışıyor (NET çıkış kodları ayrıntı vermez)
DISM_TAMAM = (0, 3010)   # 3010 = işlem tamam, yeniden başlatma gerekir
AG_ANAHTARLARI = (("Tcpip", r"HKLM\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters"),
                  ("DHCP", r"HKLM\SYSTEM\CurrentControlSet\Services\DHCP\Parameters"))

# yonetici: yönetici izni ister · geri_alinamaz: arayüz açık uyarı gösterir · geri_yukleme: işten önce geri yükleme
# noktası önerilir · yeniden_baslat: başarıda yeniden başlatma ister.
ARACLAR = {
    "ag_sifirla": {"yonetici": True, "geri_alinamaz": True, "geri_yukleme": True, "yeniden_baslat": True},
    "wu_onar": {"yonetici": True, "geri_alinamaz": False, "geri_yukleme": True, "yeniden_baslat": False},
    "wu_onar_sert": {"yonetici": True, "geri_alinamaz": False, "geri_yukleme": True, "yeniden_baslat": False},
    "disk_tara": {"yonetici": True, "geri_alinamaz": False, "geri_yukleme": False, "yeniden_baslat": False},
    "bilesen_temizle": {"yonetici": True, "geri_alinamaz": True, "geri_yukleme": True, "yeniden_baslat": False},
    "ayrilmis_kapat": {"yonetici": True, "geri_alinamaz": False, "geri_yukleme": True, "yeniden_baslat": False},
    "ayrilmis_ac": {"yonetici": True, "geri_alinamaz": False, "geri_yukleme": True, "yeniden_baslat": False},
}

# Windows'un kendi Denetim Masası panelleri (kanıt gerekmez); hepsi schema.ALLOWED_PROGRAMS beyaz listesinde.
PANELLER = (("ag", "ncpa.cpl"), ("guc", "powercfg.cpl"), ("programlar", "appwiz.cpl"), ("sistem", "sysdm.cpl"),
            ("guvenlik_duvari", "firewall.cpl"), ("internet", "inetcpl.cpl"), ("saat", "timedate.cpl"))


def _exe(name):
    return os.path.join(powershell.SYSTEM32, name)


def _goster(argv):
    return " ".join([os.path.basename(argv[0])] + [str(a) for a in argv[1:]])


def _komut(ad, argv, tamam=(0,), **extra):
    return {"ad": ad, "komut": argv, "goster": _goster(argv), "tamam": tamam, **extra}


def _islev(ad, goster, islev, **extra):
    return {"ad": ad, "islev": islev, "goster": goster, "tamam": (0,), **extra}


# ------------------------------------------------------------------ dosya adımları (Python, kabuksuz)
def _klasor_hazirla(yol):
    def run(_iptal):
        os.makedirs(yol, exist_ok=True)
        return 0, str(yol)
    return run


def _qmgr_sil(klasor):
    def run(_iptal):
        silinen = glob.glob(os.path.join(klasor, "qmgr*.dat"))
        for dosya in silinen:
            os.remove(dosya)
        return 0, f"{len(silinen)} dosya silindi"
    return run


def _bak_yap(yol, damga, birakilan):
    def run(_iptal):
        if not os.path.isdir(yol):
            return 0, f"{yol}: yok, atlandı"
        hedef = yol + ".bak"
        if os.path.exists(hedef):  # önceki .bak ezilmesin
            hedef = f"{yol}.bak.{damga}"
        os.rename(yol, hedef)
        birakilan.append(hedef)
        return 0, f"{yol} -> {hedef}"
    return run


# ------------------------------------------------------------------ plan (hem önizleme hem çalıştırma bunu kullanır)
def plan(arac, harfler=(), programdata=None, windir=None, yedek=None, damga=None):
    """Aracın adım listesi: [{ad, goster, komut | islev, tamam, kritik?, sonda?, rol?}]. Hiçbir şey çalıştırmaz.
    `goster` kullanıcıya önizlemede gösterilen gerçek komuttur. Klasör parametreleri yalnızca testler içindir."""
    if arac not in ARACLAR:
        raise KeyError(arac)
    damga = damga or datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    if arac == "ag_sifirla":
        yedek = yedek or paths.backups_dir() / "bakim"
        steps = [_islev("yedek_klasor", f"mkdir {yedek}", _klasor_hazirla(yedek), kritik=True, klasor=str(yedek))]
        for name, key in AG_ANAHTARLARI:
            file = os.path.join(yedek, f"ag_sifirla_{damga}_{name}.reg")
            steps.append(_komut("yedek_kayit", [_exe("reg.exe"), "export", key, file, "/y"], kritik=True))
        steps += [_komut("winsock", [_exe("netsh.exe"), "winsock", "reset"], sifirla=True),
                  _komut("ip", [_exe("netsh.exe"), "int", "ip", "reset", os.path.join(yedek, f"ag_sifirla_{damga}.log")],
                         sifirla=True)]
        return steps
    if arac in ("wu_onar", "wu_onar_sert"):
        programdata = programdata or guvenli_klasor.common_appdata()
        windir = windir or os.path.dirname(powershell.SYSTEM32)
        indirici = os.path.join(programdata, "Microsoft", "Network", "Downloader")
        steps = [_komut("hizmet_durdur", [_exe("net.exe"), "stop", name, "/y"], tamam=NET_TAMAM, hizmet=name,
                        beklenen=False) for name in HIZMETLER]
        steps.append(_islev("qmgr", f'Del "{os.path.join(indirici, "qmgr*.dat")}"', _qmgr_sil(indirici)))
        if arac == "wu_onar_sert":
            for yol in (os.path.join(windir, "SoftwareDistribution", "DataStore"),
                        os.path.join(windir, "SoftwareDistribution", "Download"),
                        os.path.join(windir, "System32", "catroot2")):
                birakilan = []  # adımın bıraktığı klasör; sonuçta kullanıcıya gösterilir (Denetim A2 O4)
                steps.append(_islev("bak", f"Ren {yol} {os.path.basename(yol)}.bak", _bak_yap(yol, damga, birakilan),
                                    birakilan=birakilan))
        steps += [_komut("hizmet_baslat", [_exe("net.exe"), "start", name], tamam=NET_TAMAM, sonda=True, hizmet=name,
                         beklenen=True) for name in HIZMETLER]
        return steps
    if arac == "disk_tara":
        return [_komut("tara", [_exe("chkdsk.exe"), f"{harf}:", "/scan"], tamam=(0, 1, 2, 3), rol="tarama", harf=harf)
                for harf in harfler]
    if arac == "bilesen_temizle":
        return [_komut("bilesen", [_exe("Dism.exe"), "/Online", "/Cleanup-Image", "/StartComponentCleanup"], tamam=DISM_TAMAM)]
    return [_komut("ayrilmis", [_exe("Dism.exe"), "/Online", "/Set-ReservedStorageState",
                                "/State:Disabled" if arac == "ayrilmis_kapat" else "/State:Enabled"], tamam=DISM_TAMAM)]


def onizleme(arac, harfler=()):
    """Arayüzün onay penceresinde göstereceği gerçek komutlar."""
    return [step["goster"] for step in plan(arac, harfler)]


# ------------------------------------------------------------------ çalıştırma
def _yurut(adim, iptal, ilerleme, calis):
    if "komut" in adim:
        code, data = calis(adim["komut"], iptal, ilerleme)
        return code, bakim.temizle(bakim.decode(data))
    return adim["islev"](iptal)


def _tarama_sonucu(kodlar):
    """chkdsk /scan çıkış kodları (Microsoft): 0 hata yok, 1 hatalar bulundu ve düzeltildi, 2 temizlik yapıldı,
    3 denetlenemedi / hatalar düzeltilmedi. Başka kod = beklenmedik."""
    if not kodlar or any(k not in (0, 1, 2, 3) for k in kodlar):
        return "hata"
    return "sorun" if 3 in kodlar else "temiz" if all(k == 0 for k in kodlar) else "bilgi"


def _hizmet_calisiyor(ad):
    from app.engine.system import WindowsSystem  # noqa: WPS433 - yalnızca gerçek çalıştırmada
    return WindowsSystem._service_running(ad)


def calistir_arac(arac, iptal, ilerleme=None, calis=bakim.calistir, yonetici=admin.is_admin, harfler=(),
                  liste=bakim.suruculer, hizmet_calisiyor=_hizmet_calisiyor, **konum):
    """Aracı çalıştırır. ilerleme(adım_no, toplam, yüzde|None, adım_adı). Dönen sözlük:
    sonuc: tamam | temiz | bilgi | sorun | hata | yedeklenemedi | iptal | yetki | yok
    cikti: ham metin · yeniden_baslat: bool · yedek: yedek klasörü | None · suruculer: taranan harfler."""
    spec = ARACLAR[arac]
    bos = {"cikti": "", "yeniden_baslat": False, "yedek": None, "suruculer": [], "birakilan": []}
    if spec["yonetici"] and not yonetici():
        return {**bos, "sonuc": "yetki"}
    if arac == "ag_sifirla" and not konum.get("yedek") and not os.path.exists(paths.protected_path() / paths.PROTECTED_MARK):
        # taşıma bitmemişse yedek klasörü kullanıcının yazabildiği eski yer: yönetici oraya yazmaz (Denetim YAYIN D2)
        return {**bos, "sonuc": "yedeklenemedi"}
    if arac == "disk_tara":
        ntfs = {d["harf"] for d in liste() if d.get("fs") == "NTFS"}  # listede olmayan / NTFS olmayan sürücü çalışmaz
        harfler = [h for h in dict.fromkeys(str(h).upper() for h in harfler) if h in ntfs]
        if not harfler:
            return {**bos, "sonuc": "yok"}
    steps = plan(arac, harfler, **konum)
    serbest = threading.Event()  # son adımlar (hizmetleri yeniden başlat) iptal edilse de çalışır
    parts, codes, state, reboot, sifirlandi = [], [], None, False, False
    for index, step in enumerate(steps, 1):
        last = step.get("sonda")
        if not last:
            if state:
                continue
            if iptal.is_set():
                state = "iptal"
                continue
        if ilerleme:
            ilerleme(index, len(steps), None, step["ad"])
        report = (lambda p, i=index, a=step["ad"]: ilerleme(i, len(steps), p, a)) if ilerleme else None
        try:
            code, text = _yurut(step, serbest if last else iptal, report, calis)
        except OSError as exc:
            _log.error("%s başarısız: %s", step["goster"], exc)
            code, text = -1, str(exc)
        # net kodu 2 hem "zaten böyle" hem "olmadı" demek (Denetim A2 B5): sonucu hizmetin gerçek durumundan doğrula
        bozuk = False
        if step.get("hizmet") and code in step["tamam"] and hizmet_calisiyor(step["hizmet"]) not in (None, step["beklenen"]):
            bozuk = True
            text += f"\n{step['hizmet']}: hizmet " + ("başlamadı" if step["beklenen"] else "durmadı")
        parts.append(f"> {step['goster']}\n{text}\n(çıkış kodu: {code})")
        if code is None and not last:
            state = "iptal"
            continue
        if code == 3010:
            reboot = True
        sifirlandi = sifirlandi or bool(step.get("sifirla") and code in step["tamam"])
        if step.get("rol") == "tarama":
            codes.append(code)
        elif bozuk or code not in step["tamam"]:
            state = state or ("kritik" if step.get("kritik") else "hata")
    output = "\n\n".join(parts)
    if state == "iptal":
        result = "iptal"
    elif state == "kritik":
        result = "yedeklenemedi"
    elif state == "hata":  # ağ sıfırlamada biri yapıldıysa geri alınamaz: yeniden başlatma gerekir (Denetim A2 B6)
        result = "kismen" if sifirlandi else "hata"
    elif arac == "disk_tara":
        result = _tarama_sonucu(codes)
    else:
        result = "tamam"
    _log.info("Bakım aracı %s bitti: %s", arac, result)
    yedek = steps[0]["klasor"] if arac == "ag_sifirla" and result in ("tamam", "kismen", "hata") else None
    return {"sonuc": result, "cikti": output,
            "yeniden_baslat": (spec["yeniden_baslat"] and result in ("tamam", "kismen")) or reboot,
            "yedek": yedek, "suruculer": harfler if arac == "disk_tara" else [],
            "birakilan": [h for s in steps for h in s.get("birakilan", [])]}
