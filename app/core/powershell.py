"""PowerShell komutlarını çalıştırıp sonucu Python verisine çeviren yardımcı.

Tarama ve yer tutucu çözümleyicileri bu modülü kullanır. Komutlar pencere
açmadan çalışır; çıktı JSON olarak alınır, böylece Windows dili (Türkçe,
İngilizce...) sonucu etkilemez.
"""

import ctypes
import json
import os
import subprocess
import threading

CREATE_NO_WINDOW = 0x08000000
# Aynı anda en fazla bu kadar PowerShell süreci: tarama (6) ve durum okuma (8) iş parçacıkları birlikte
# 14-15 powershell.exe açıyordu (her biri ~80 MB). Fazlası sırayla bekler; komutlar bitince süreçler kapanır.
# Ölçüm (29 Eki 2026): sınırsız 9,3 sn, 6 ile 10,2 sn, 3 ile 13 sn "tüm durumlar hazır"; 6 seçildi.
MAX_PARALLEL = 6
_slots = threading.BoundedSemaphore(MAX_PARALLEL)

# PowerShell tek tırnak olarak ASCII ' yanında tipografik tırnakları da kabul eder; quote() hepsini ikiler.
_QUOTES = "'\u2018\u2019\u201a\u201b"


def _system_dir():
    """System32. Ortam değişkeninden okunmaz: HKCU\\Environment yönetici olmayan süreçlerce yazılabilir."""
    buffer = ctypes.create_unicode_buffer(260)
    return buffer.value if ctypes.windll.kernel32.GetSystemDirectoryW(buffer, 260) else r"C:\Windows\System32"


SYSTEM32 = _system_dir()
# Yükseltilmiş süreç, kullanıcının yazabildiği modül klasörünü (Belgeler\WindowsPowerShell\Modules) yüklemesin.
_MODULE_PATH = os.path.join(SYSTEM32, "WindowsPowerShell", "v1.0", "Modules")


def clean_env():
    return {**os.environ, "PSModulePath": _MODULE_PATH}


# Çıktının UTF-8 gelmesi için her komutun başına eklenir.
_PREFIX = (
    "$ErrorActionPreference='Stop';"
    "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8;"
)


class PowerShellError(Exception):
    """Komut başarısız olduğunda veya zaman aşımına uğradığında fırlatılır."""


def quote(value):
    """Bir metni PowerShell tek tırnaklı dizgesi olarak güvenle yazar."""
    return "'" + "".join(c * 2 if c in _QUOTES else c for c in str(value)) + "'"


def features_query(names):
    """Get-WindowsOptionalFeature birden çok ad için. -FeatureName tek metin alır: 'a','b' her zaman
    "Cannot convert 'System.Object[]'" hatası verir (PERF-004 bu yüzden hiçbir bilgisayarda görünmüyordu)."""
    listed = ",".join(quote(n) for n in names)
    return f"@({listed}) | ForEach-Object {{ Get-WindowsOptionalFeature -Online -FeatureName $_ -ErrorAction SilentlyContinue }}"


def run(command, timeout=30):
    """Komutu çalıştırır ve standart çıktıyı metin olarak döndürür."""
    with _slots:
        return _run(command, timeout)


def _run(command, timeout):
    try:
        proc = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                # -ExecutionPolicy yok: yalnızca betik dosyalarını etkiler, -Command'ı değil (Restricted/AllSigned/
                # bayraksız çalıştırma aynı sonucu verdi, docs/faz-notlari.md 1.4); Bypass bayrağı antivirüs sezgisellerini tetikler.
                "-Command",
                _PREFIX + command,
            ],
            capture_output=True,
            timeout=timeout,
            creationflags=CREATE_NO_WINDOW,
            env=clean_env(),
        )
    except subprocess.TimeoutExpired as exc:
        raise PowerShellError(f"Zaman aşımı ({timeout} sn)") from exc
    except OSError as exc:
        raise PowerShellError(f"PowerShell başlatılamadı: {exc}") from exc

    stdout = proc.stdout.decode("utf-8", errors="replace").strip()
    if proc.returncode != 0:
        stderr = proc.stderr.decode("utf-8", errors="replace").strip()
        raise PowerShellError(stderr or f"Çıkış kodu {proc.returncode}")
    return stdout


def run_object(script, timeout=60):
    """Tek bir nesne (sözlük) döndüren betiği çalıştırır.

    Betik `[pscustomobject]@{...}` üretmelidir. Boş çıktıda boş sözlük döner.
    """
    text = run(f"& {{ {script} }} | ConvertTo-Json -Compress -Depth 5", timeout)
    if not text:
        return {}
    data = json.loads(text)
    return data if isinstance(data, dict) else {}


def as_list(value):
    """PowerShell JSON'unda tek eleman liste yerine nesne gelebilir; düzeltir."""
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def run_json(command, timeout=30):
    """Komutun çıktısını `ConvertTo-Json` ile alır ve her zaman liste döndürür.

    PowerShell tek bir nesne döndüğünde liste yerine nesne verir; burada bu
    fark ortadan kaldırılır. Boş çıktı boş liste demektir.
    """
    text = run(f"@({command}) | ConvertTo-Json -Compress -Depth 4", timeout)
    if not text:
        return []
    data = json.loads(text)
    if isinstance(data, list):
        return data
    return [data]
