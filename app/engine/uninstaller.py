"""Uygulama kaldırıcı: kurulu programları listeler, programın kendi kaldırıcısını çalıştırır, sonra kalan klasör ve kayıt
defteri anahtarlarını bulur. Kalıntılar SİLİNMEZ: klasörler yedek klasörüne TAŞINIR, kayıt defteri anahtarları .reg olarak
dışa aktarılıp kaldırılır; her kaldırma geri yüklenebilir (restore) ve yedek yalnızca kullanıcının isteğiyle silinir.

Eşleşme bilerek dardır: yalnızca bilinen kök klasörlerin DOĞRUDAN alt klasörleri ve Software altındaki anahtarlar, adı programın
adıyla (ya da kurulum klasörünün adıyla) birebir aynıysa (boşluk/noktalama/harf boyutu yok sayılarak) kalıntı sayılır. Windows,
Microsoft ve sürücü gibi genel adlar ve sistem bileşenleri hiçbir zaman listelenmez.
"""

import ctypes
import datetime
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from app.core import admin, guvenli_klasor, log, paths, powershell, registry

_log = log.get("uninstaller")

UNINSTALL_KEYS = (("HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
                  ("HKLM", r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
                  ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Uninstall"))
SOFTWARE_ROOTS = (("HKCU", "Software"), ("HKLM", "SOFTWARE"), ("HKLM", r"SOFTWARE\WOW6432Node"))
FOLDER_ENV = ("ProgramFiles", "ProgramFiles(x86)", "ProgramData", "LOCALAPPDATA", "APPDATA")
# Sistem/sürücü bileşenleri: listede görünür ama kaldırılamaz (Windows ve oyunlar bunlara dayanır).
PROTECTED = re.compile(r"^(microsoft (visual c\+\+|\.net|edge|windows|update health)|windows |nvidia (graphics|physx|hd audio|"
                       r"container|frameview)|amd (software|chipset)|intel.*(driver|graphics|chipset|management)|realtek|forevermore)",
                       re.I)
GENERIC = {"microsoft", "windows", "common files", "packages", "programs", "temp", "google", "intel", "nvidia", "amd", "apps",
           "data", "cache", "logs", "software", "app", "setup", "installer", "microsoft shared", "windowsapps", "classes"}
UPDATE_TYPES = {"update", "hotfix", "security update", "critical update", "update rollup", "service pack"}


def _norm(text):
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def _clean_name(name):
    """Görünen addan sürüm ve mimari son ekini atar: "Foo 1.2.3 (x64)" -> "Foo"."""
    name = re.sub(r"\((?:x64|x86|64-bit|32-bit)\)|\b(?:x64|x86|64-bit|32-bit)\b", "", name or "", flags=re.I)
    name = re.sub(r"[\s\-_]+v?\d+(?:\.\d+)+\s*$", "", name.strip())
    return re.sub(r"[\s\-_]+$", "", name).strip()


SESSION_NAME = re.compile(r"\d{8}-\d{6}")
BACKUP_NAME = re.compile(r"k\d+|r\d+\.reg")  # remove_leftovers'ın ürettiği adlar


def is_protected(name):
    return bool(PROTECTED.match((name or "").strip()))


def list_programs(reg=registry):
    """Kurulu programlar (güncelleme ve sistem bileşenleri hariç), ada göre sıralı."""
    programs, seen = [], set()
    for root, key in UNINSTALL_KEYS:
        for sub in reg.subkeys(root, key):
            path = key + "\\" + sub
            get = lambda name: reg.read(root, path, name)  # noqa: E731
            name = (get("DisplayName") or "").strip()
            command = (get("UninstallString") or "").strip()
            if not name or not command or get("SystemComponent") == 1 or get("ParentKeyName") or \
                    str(get("ReleaseType") or "").lower() in UPDATE_TYPES:
                continue
            ident = (name.lower(), str(get("DisplayVersion") or ""))
            if ident in seen:
                continue
            seen.add(ident)
            size = get("EstimatedSize")
            programs.append({"ad": name, "surum": str(get("DisplayVersion") or ""), "yayinci": (get("Publisher") or "").strip(),
                             "konum": (get("InstallLocation") or "").strip().strip('"'), "komut": command,
                             "boyut_kb": size if isinstance(size, int) else 0, "kok": root, "anahtar": path,
                             "korumali": is_protected(name)})
    return sorted(programs, key=lambda p: p["ad"].lower())


def split_command(command):
    """Kaldırma komut satırını (çalıştırılabilir, bağımsız değişkenler) olarak ayırır; çıktı kabuk yorumlamaz."""
    command = command.strip()
    if command.startswith('"'):
        end = command.find('"', 1)
        return (command[1:end], command[end + 1:].strip()) if end > 0 else (command.strip('"'), "")
    match = re.search(r"\.(exe|bat|cmd|msi)\b", command, re.I)
    if match:
        return command[:match.end()], command[match.end():].strip()
    head, _, rest = command.partition(" ")
    return head, rest


def shell_execute(exe, args):
    """Windows'un kendi çalıştırma yolu (gerekirse UAC sorar); kaldırıcının bitmesini beklemez. True: başlatıldı."""
    return ctypes.windll.shell32.ShellExecuteW(None, "open", exe, args or None, None, 1) > 32


def start_uninstall(program, runner=shell_execute, user_runner=admin.run_unelevated):
    """Programın KENDİ kaldırıcısını başlatır. Korumalı programlar reddedilir. HKCU kaydını yönetici olmayan her program
    yazabilir: oradaki komut yönetici yetkisi almaz, başlatılamazsa da yönetici yetkisiyle denenmez."""
    if program.get("korumali"):
        return False
    exe, args = split_command(program["komut"])
    return bool(exe) and (user_runner if program["kok"] == "HKCU" else runner)(exe, args)


# --------------------------------------------------------------------------- kalıntı tarama
def _folder_roots(env):
    roots = [Path(env[name]) for name in FOLDER_ENV if env.get(name)]
    if env.get("LOCALAPPDATA"):
        roots.append(Path(env["LOCALAPPDATA"]) / "Programs")
    return roots


def _size(folder):
    total = 0
    for base, _dirs, files in os.walk(folder):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(base, name))
            except OSError:
                pass
    return total


def find_leftovers(program, env=None, reg=registry):
    """[{"tur": "klasor"|"kayit", "yol", "kok"?, "boyut"}]: programın adıyla birebir eşleşen klasör ve kayıt anahtarları."""
    env = os.environ if env is None else env
    names = {_clean_name(program["ad"])}
    location = os.path.normpath(program["konum"]) if program.get("konum") else ""
    if location:
        names.add(Path(location).name)
    norms = {_norm(n) for n in names if len(_norm(n)) >= 3} - {_norm(g) for g in GENERIC}
    publisher = _norm(program.get("yayinci"))
    result, seen = [], set()

    def add(item):
        key = (item["tur"], item["yol"].lower())
        if key not in seen:
            seen.add(key)
            result.append(item)

    roots = _folder_roots(env)
    for root in roots:
        try:
            children = [c for c in root.iterdir() if c.is_dir()]
        except OSError:
            continue
        for child in children:
            if _norm(child.name) in norms:
                add({"tur": "klasor", "yol": str(child), "boyut": _size(child)})
    # kurulum klasörü; köklerin atası (kullanıcı profili) ya da genel adlı (Common Files) değilse (Denetim A O2)
    if location and os.path.isdir(location) and Path(location) not in roots and len(Path(location).parts) >= 3 \
            and not any(Path(location) in root.parents for root in roots) \
            and _norm(Path(location).name) not in {_norm(g) for g in GENERIC}:
        windir = Path(os.path.dirname(powershell.SYSTEM32))  # ortam değişkeni HKCU'dan ezilebilir (Denetim A S1)
        # HKCU kaydını her program yazabilir: oradaki konum yalnızca bilinen program köklerinin altındaysa alınır
        trusted = program.get("kok") != "HKCU" or any(root in Path(location).parents for root in roots)
        if trusted and windir not in Path(location).parents and Path(location) != windir:
            add({"tur": "klasor", "yol": location, "boyut": _size(location)})
    for root, base in SOFTWARE_ROOTS:
        for sub in reg.subkeys(root, base):
            if _norm(sub) in norms:
                add({"tur": "kayit", "kok": root, "yol": base + "\\" + sub})
            elif publisher and _norm(sub) == publisher:   # Yayıncı\Program: yalnızca alt anahtar, yayıncının kendisi değil
                for child in reg.subkeys(root, base + "\\" + sub):
                    if _norm(child) in norms:
                        add({"tur": "kayit", "kok": root, "yol": base + "\\" + sub + "\\" + child})
    return sorted(result, key=lambda i: (i["tur"], i["yol"].lower()))


# --------------------------------------------------------------------------- yedekli kaldırma
class RegOps:
    """reg.exe ile dışa aktarma / silme / içe aktarma (testlerde sahtesi kullanılır)."""

    @staticmethod
    def _run(*args):
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        done = subprocess.run(["reg", *args], capture_output=True, creationflags=flags, timeout=60)
        return done.returncode == 0

    def export(self, root, path, file):
        return self._run("export", f"{root}\\{path}", str(file), "/y")

    def delete(self, root, path):
        return self._run("delete", f"{root}\\{path}", "/f")

    def import_file(self, file):
        return self._run("import", str(file))


def backup_dir():
    path = paths.uninstall_backups_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _reset_acl(path):
    """Klasör taşınınca eski izinleri de gelir: yedekte kullanıcı yazabilir kalır, geri yüklenince program klasörüne erişemez."""
    if not guvenli_klasor.reset_acl(path):
        _log.warning("İzinler tam sıfırlanamadı: %s", path)


def remove_leftovers(program_name, items, base=None, ops=None, now=None, tur=None):
    """Seçilen kalıntıları yedekleyip kaldırır. Klasör: yedek klasörüne taşınır; kayıt: .reg'e aktarılıp silinir.
    {"oturum", "kaldirilan": n, "basarisiz": [{"yol", "neden"}]} döner; yedek varsa manifest.json yazılır.
    tur: oturumun nereden geldiği (ör. "temizlik"; Temizlik sayfası yalnız kendi taşımalarını listeler); öğedeki
    "boyut" varsa taşınanların toplamı manifeste yazılır."""
    base, ops = Path(base) if base else backup_dir(), ops or RegOps()
    now = now or datetime.datetime.now()
    while (base / now.strftime("%Y%m%d-%H%M%S")).exists():  # aynı saniyede ikinci taşıma eski yedeğin manifestini ezmesin
        now += datetime.timedelta(seconds=1)
    session = base / now.strftime("%Y%m%d-%H%M%S")
    session.mkdir(parents=True, exist_ok=True)
    done, failed, moved_size = [], [], 0
    for number, item in enumerate(items, 1):
        try:
            if item["tur"] == "klasor":
                target = session / f"k{number}"
                shutil.move(item["yol"], str(target))
                _reset_acl(target)
                done.append({"tur": "klasor", "yol": item["yol"], "yedek": target.name})
                moved_size += item.get("boyut") or 0
            else:
                file = session / f"r{number}.reg"
                if not ops.export(item["kok"], item["yol"], file):
                    raise OSError("export")
                if not ops.delete(item["kok"], item["yol"]):
                    raise OSError("delete")   # silinemedi (ör. yönetici gerekir): .reg yedeği zararsız kalır
                done.append({"tur": "kayit", "kok": item["kok"], "yol": item["yol"], "yedek": file.name})
        except (OSError, shutil.Error) as exc:
            failed.append({"yol": item["yol"], "neden": str(exc)})
            if item["tur"] == "klasor" and target.exists():  # sürücüler arası taşıma yarıda: kopya listede kalsın (B5)
                _reset_acl(target)
                done.append({"tur": "klasor", "yol": item["yol"], "yedek": target.name, "kismen": True})
    manifest = {"program": program_name, "tarih": now.isoformat(timespec="seconds"), "ogeler": done}
    if tur:
        manifest.update(tur=tur, boyut=moved_size)
    if done:
        (session / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    else:
        shutil.rmtree(session, ignore_errors=True)
    return {"oturum": session.name if done else None, "kaldirilan": sum(not d.get("kismen") for d in done),
            "basarisiz": failed}


def list_sessions(base=None):
    """Geri yüklenebilir kaldırmalar, yeni olan önce: [{"oturum", "program", "tarih", "adet", "tur", "boyut"}]."""
    base = Path(base) if base else backup_dir()
    sessions = []
    for manifest in base.glob("*/manifest.json"):
        if not SESSION_NAME.fullmatch(manifest.parent.name):
            continue
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            sessions.append({"oturum": manifest.parent.name, "program": data["program"], "tarih": data["tarih"],
                             "adet": len(data["ogeler"]), "tur": data.get("tur", ""),
                             "boyut": data.get("boyut") or 0})
        except (OSError, ValueError, KeyError):
            continue
    return sorted(sessions, key=lambda s: s["oturum"], reverse=True)


def restore(session_name, base=None, ops=None):
    """Bir kaldırmayı geri yükler: klasörler yerine taşınır (yer doluysa atlanır), kayıt anahtarları içe aktarılır."""
    if not SESSION_NAME.fullmatch(session_name):
        raise ValueError(session_name)
    base, ops = Path(base) if base else backup_dir(), ops or RegOps()
    session = base / session_name
    data = json.loads((session / "manifest.json").read_text(encoding="utf-8"))
    restored, failed = 0, []
    for item in data["ogeler"]:
        try:
            if not BACKUP_NAME.fullmatch(item["yedek"]):  # eski oturumlar kullanıcı klasöründen geldi: yedek oturumun dışını gösteremez
                raise OSError("yedek yolu")
            source = session / item["yedek"]
            if item["tur"] == "klasor":
                if os.path.exists(item["yol"]):
                    raise OSError("yer dolu")
                Path(item["yol"]).parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(source), item["yol"])
                _reset_acl(item["yol"])
            elif not ops.import_file(source):
                raise OSError("import")
            restored += 1
        except (OSError, shutil.Error) as exc:
            failed.append({"yol": item["yol"], "neden": str(exc)})
    if not failed:
        shutil.rmtree(session, ignore_errors=True)
    return {"geri_yuklenen": restored, "basarisiz": failed}


def delete_session(session_name, base=None):
    """Yedeği kalıcı siler (yalnızca kullanıcı isterse). Oturum adı yol içeremez."""
    if not SESSION_NAME.fullmatch(session_name):
        raise ValueError(session_name)
    shutil.rmtree((Path(base) if base else backup_dir()) / session_name, ignore_errors=True)
