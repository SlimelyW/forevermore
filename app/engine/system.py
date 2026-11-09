"""Windows'a dokunan tek katman.

Ayar motoru sisteme yalnızca bu sınıf üzerinden erişir. Testlerde aynı
arayüze sahip sahte bir sınıf (tests/fake_system.py) kullanılır; böylece
uygula/geri al mantığı gerçek bilgisayara dokunmadan denenebilir.

Okuma metotları `get_` / `read_` / `list_` ile başlar. Değişiklik yapan
metotlar `set_`, `write_`, `delete_`, `create_` ile başlar ve hepsi log'a yazılır.
ReadOnlySystem sarmalayıcısı değişiklik yapan metotları engeller.
"""

import ctypes
import json
import os
import re
import subprocess
import sys
import time
import uuid
import winreg
from ctypes import wintypes

from app.core import log, paths, powershell, registry
from app.engine import managers

_log = log.get("system")

WRITE = winreg.KEY_WRITE | winreg.KEY_READ | winreg.KEY_WOW64_64KEY
SET_VALUE = winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE | winreg.KEY_WOW64_64KEY
SERVICE_START = {2: "Automatic", 3: "Manual", 4: "Disabled", 0: "Boot", 1: "System"}
SC_START = {"Automatic": "auto", "Manual": "demand", "Disabled": "disabled", "AutomaticDelayed": "delayed-auto"}


class SystemError_(Exception):
    """Sistem işlemi başarısız oldu (ayrıntı log'da)."""


# ---------------------------------------------------------------------------
# ctypes yapıları
# ---------------------------------------------------------------------------

class GUID(ctypes.Structure):
    _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]

    @classmethod
    def from_string(cls, text):
        return cls.from_buffer_copy(uuid.UUID(text).bytes_le)

    def __str__(self):
        return str(uuid.UUID(bytes_le=bytes(self)))


class _ServiceStatus(ctypes.Structure):
    _fields_ = [("dwServiceType", wintypes.DWORD), ("dwCurrentState", wintypes.DWORD),
                ("dwControlsAccepted", wintypes.DWORD), ("dwWin32ExitCode", wintypes.DWORD),
                ("dwServiceSpecificExitCode", wintypes.DWORD), ("dwCheckPoint", wintypes.DWORD),
                ("dwWaitHint", wintypes.DWORD)]


SPI_SETMOUSE, SPI_SETMOUSESPEED = 0x0004, 0x0071
SPI_SETKEYBOARDSPEED, SPI_SETKEYBOARDDELAY = 0x000B, 0x0017
SPIF_UPDATE = 0x01 | 0x02  # SPIF_UPDATEINIFILE | SPIF_SENDCHANGE


class WindowsSystem:
    """Gerçek Windows erişimi."""

    # ------------------------------------------------------------------ registry
    def read_reg(self, root, path, name):
        """(değer, tür) veya değer yoksa None. Erişim reddi PermissionError fırlatır."""
        return registry.read_typed(root, path, name)

    def get_key_exists(self, root, path):
        return registry.key_exists(root, path)

    def write_reg(self, root, path, name, value, reg_type):
        _log.info("Registry yaz: %s\\%s [%s] = %r (%s)", root, path, name, value, reg_type)
        # Yalnızca "değer yaz" izni istenir. KEY_WRITE "alt anahtar oluştur"u da
        # içerir; ses cihazı (FxProperties) gibi anahtarlarda Yöneticiler'e bu
        # izin verilmediği için "Erişim reddedildi" hatası alınıyordu.
        try:
            key = winreg.OpenKey(registry.ROOTS[root], path, 0, SET_VALUE)
        except FileNotFoundError:
            key = winreg.CreateKeyEx(registry.ROOTS[root], path, 0, SET_VALUE)
        with key:
            winreg.SetValueEx(key, name, 0, registry.TYPE_CODES[reg_type], value)

    def delete_reg_value(self, root, path, name):
        _log.info("Registry sil: %s\\%s [%s]", root, path, name)
        try:
            with winreg.OpenKey(registry.ROOTS[root], path, 0, SET_VALUE) as key:
                winreg.DeleteValue(key, name)
        except FileNotFoundError:
            pass  # zaten yok

    def create_reg_key(self, root, path, default_value=None):
        _log.info("Registry anahtar oluştur: %s\\%s", root, path)
        with winreg.CreateKeyEx(registry.ROOTS[root], path, 0, WRITE) as key:
            if default_value is not None:
                winreg.SetValueEx(key, "", 0, winreg.REG_SZ, default_value)

    def delete_reg_tree(self, root, path):
        _log.info("Registry anahtar sil (alt anahtarlarla): %s\\%s", root, path)

        def remove(handle_root, sub):
            try:
                with winreg.OpenKey(handle_root, sub, 0, WRITE) as key:
                    while True:
                        try:
                            child = winreg.EnumKey(key, 0)
                        except OSError:
                            break
                        remove(handle_root, sub + "\\" + child)
                winreg.DeleteKeyEx(handle_root, sub, winreg.KEY_WOW64_64KEY, 0)
            except FileNotFoundError:
                pass

        remove(registry.ROOTS[root], path)

    def delete_empty_keys(self, root, path, stop_at):
        """`path`ten başlayıp `stop_at`e kadar (hariç) boş anahtarları siler.
        İçinde değer veya alt anahtar olan bir anahtarda durur."""
        current = path
        while current and len(current) > len(stop_at) and current.lower().startswith(stop_at.lower()):
            try:
                with winreg.OpenKey(registry.ROOTS[root], current, 0, registry.READ) as key:
                    sub_count, value_count, _ = winreg.QueryInfoKey(key)
                if sub_count or value_count:
                    return
                _log.info("Boş anahtar siliniyor: %s\\%s", root, current)
                winreg.DeleteKeyEx(registry.ROOTS[root], current, winreg.KEY_WOW64_64KEY, 0)
            except FileNotFoundError:
                pass
            current = current.rpartition("\\")[0]

    def list_reg(self, root, path):
        """(değer adları, alt anahtar adları); yalnızca okur."""
        return list(registry.values(root, path)), registry.subkeys(root, path)

    def export_reg_key(self, root, path, file_path):
        """Anahtarı .reg dosyasına yedekler (elle geri yükleme için). Başarısızsa False."""
        try:
            proc = subprocess.run(["reg", "export", f"{root}\\{path}", str(file_path), "/y"],
                                  capture_output=True, timeout=30, creationflags=powershell.CREATE_NO_WINDOW)
            return proc.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return False

    # ------------------------------------------------------------------ servisler
    def get_service(self, name):
        """{'baslangic': 'Automatic'|'AutomaticDelayed'|'Manual'|'Disabled', 'calisiyor': bool} veya None."""
        key = rf"SYSTEM\CurrentControlSet\Services\{name}"
        start = registry.read("HKLM", key, "Start")
        if start is None:
            return None
        kind = SERVICE_START.get(start, str(start))
        if kind == "Automatic" and registry.read("HKLM", key, "DelayedAutostart") == 1:
            kind = "AutomaticDelayed"
        return {"baslangic": kind, "calisiyor": self._service_running(name)}

    @staticmethod
    def _service_running(name):
        advapi = ctypes.WinDLL("advapi32", use_last_error=True)
        advapi.OpenSCManagerW.restype = ctypes.c_void_p
        advapi.OpenServiceW.restype = ctypes.c_void_p
        advapi.OpenServiceW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR, wintypes.DWORD]
        advapi.QueryServiceStatus.argtypes = [ctypes.c_void_p, ctypes.POINTER(_ServiceStatus)]
        advapi.CloseServiceHandle.argtypes = [ctypes.c_void_p]
        manager = advapi.OpenSCManagerW(None, None, 0x0001)  # SC_MANAGER_CONNECT
        if not manager:
            return None
        try:
            service = advapi.OpenServiceW(manager, name, 0x0004)  # SERVICE_QUERY_STATUS
            if not service:
                return None
            try:
                status = _ServiceStatus()
                if not advapi.QueryServiceStatus(service, ctypes.byref(status)):
                    return None
                return status.dwCurrentState == 4  # SERVICE_RUNNING
            finally:
                advapi.CloseServiceHandle(service)
        finally:
            advapi.CloseServiceHandle(manager)

    def set_service(self, name, start_type, running):
        _log.info("Servis ayarla: %s başlangıç=%s çalışsın=%s", name, start_type, running)
        proc = subprocess.run(["sc.exe", "config", name, "start=", SC_START[start_type]],
                              capture_output=True, timeout=30, creationflags=powershell.CREATE_NO_WINDOW)
        if proc.returncode != 0:
            raise SystemError_(f"sc config {name} başarısız (kod {proc.returncode})")
        if running is True:
            powershell.run(f"Start-Service -Name {powershell.quote(name)}", timeout=60)
        elif running is False:
            powershell.run(f"Stop-Service -Name {powershell.quote(name)} -Force", timeout=60)

    # ------------------------------------------------------------------ güç planı
    @staticmethod
    def _powrprof():
        return ctypes.WinDLL("powrprof")

    def get_active_scheme(self):
        ptr = ctypes.POINTER(GUID)()
        result = self._powrprof().PowerGetActiveScheme(None, ctypes.byref(ptr))
        if result != 0:
            raise SystemError_(f"PowerGetActiveScheme hata {result}")
        try:
            return str(ptr.contents)
        finally:
            ctypes.windll.kernel32.LocalFree(ptr)

    def set_active_scheme(self, scheme):
        _log.info("Güç planı etkinleştir: %s", scheme)
        result = self._powrprof().PowerSetActiveScheme(None, ctypes.byref(GUID.from_string(scheme)))
        if result != 0:
            raise SystemError_(f"PowerSetActiveScheme hata {result}")

    def read_power_ac(self, scheme, subgroup, setting, source="ac"):
        """Planın prizde (ac) veya pilde (dc) değeri."""
        value = wintypes.DWORD()
        func = "PowerReadACValueIndex" if source == "ac" else "PowerReadDCValueIndex"
        result = getattr(self._powrprof(), func)(
            None, ctypes.byref(GUID.from_string(scheme)), ctypes.byref(GUID.from_string(subgroup)),
            ctypes.byref(GUID.from_string(setting)), ctypes.byref(value))
        if result != 0:
            raise SystemError_(f"{func} hata {result}")
        return value.value

    def read_power_ac_default(self, scheme, subgroup, setting, source="ac"):
        """Planın fabrika değeri. Yalnızca Windows'un hazır planları için bilinir; yoksa None.

        Emin değilim: PowerReadACDefaultIndex'in ikinci parametresi planın
        'kişiliği'dir; hazır planlarda plan GUID'iyle aynıdır. Özel planlarda
        None döndürülür ve motor kullanıcıya açıklama gösterir.
        """
        if scheme not in ("381b4222-f694-41f0-9685-ff5bb260df2e", "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c",
                          "a1841308-3541-4fab-bc81-f71556f20b4a"):
            return None
        value = wintypes.DWORD()
        func = "PowerReadACDefaultIndex" if source == "ac" else "PowerReadDCDefaultIndex"
        result = getattr(self._powrprof(), func)(
            None, ctypes.byref(GUID.from_string(scheme)), ctypes.byref(GUID.from_string(subgroup)),
            ctypes.byref(GUID.from_string(setting)), ctypes.byref(value))
        return value.value if result == 0 else None

    def write_power_ac(self, scheme, subgroup, setting, value, source="ac"):
        _log.info("Güç ayarı yaz (%s): plan=%s ayar=%s değer=%s", source, scheme, setting, value)
        func = "PowerWriteACValueIndex" if source == "ac" else "PowerWriteDCValueIndex"
        result = getattr(self._powrprof(), func)(
            None, ctypes.byref(GUID.from_string(scheme)), ctypes.byref(GUID.from_string(subgroup)),
            ctypes.byref(GUID.from_string(setting)), wintypes.DWORD(value))
        if result != 0:
            raise SystemError_(f"{func} hata {result}")
        # Etkin planı yeniden uygula ki değişiklik hemen geçerli olsun.
        if scheme == self.get_active_scheme():
            self.set_active_scheme(scheme)

    # ------------------------------------------------------------------ yerleşik eylemler
    def get_hibernate(self):
        value = registry.read("HKLM", r"SYSTEM\CurrentControlSet\Control\Power", "HibernateEnabled")
        return None if value is None else value == 1

    def set_hibernate(self, enabled):
        _log.info("Hazırda bekletme: %s", enabled)
        proc = subprocess.run(["powercfg", "/hibernate", "on" if enabled else "off"], capture_output=True,
                              timeout=60, creationflags=powershell.CREATE_NO_WINDOW)
        if proc.returncode != 0:
            raise SystemError_(f"powercfg /hibernate başarısız (kod {proc.returncode})")

    def get_memory_compression(self):
        rows = powershell.run_json("Get-MMAgent | Select-Object MemoryCompression", timeout=60)
        return bool(rows[0]["MemoryCompression"]) if rows else None

    def set_memory_compression(self, enabled):
        _log.info("Bellek sıkıştırma: %s", enabled)
        verb = "Enable" if enabled else "Disable"
        powershell.run(f"{verb}-MMAgent -MemoryCompression", timeout=60)

    def get_defender_status(self):
        """Windows Defender: gerçek zamanlı koruma, Kurcalama koruması ve çalışma modu (salt okunur)."""
        rows = powershell.run_json("Get-MpComputerStatus | Select-Object RealTimeProtectionEnabled, "
                                   "IsTamperProtected, AMRunningMode", timeout=60)
        if not rows:
            return None
        row = rows[0]
        return {"gercek_zamanli": row.get("RealTimeProtectionEnabled"), "kurcalama": row.get("IsTamperProtected"),
                "mod": row.get("AMRunningMode")}

    def set_defender_realtime(self, enabled):
        """Kurcalama koruması açıkken Windows komutu hatasız kabul edip yok sayar. Son okunan durumu döndürür
        (çağıran yeniden okumasın: her okuma bir PowerShell, Denetim A O6)."""
        _log.info("Defender gerçek zamanlı koruma: %s", enabled)
        powershell.run(f"Set-MpPreference -DisableRealtimeMonitoring {'$false' if enabled else '$true'}", timeout=60)
        status = None
        for attempt in range(5):  # durum birkaç saniye gecikmeli güncellenebilir
            status = self.get_defender_status()
            if status and bool(status["gercek_zamanli"]) == bool(enabled):
                break
            if attempt < 4:
                time.sleep(1)
        return status

    def get_features(self, names):
        """{özellik: 'Enabled'|'Disabled'} (yalnızca sistemde bulunanlar)."""
        rows = powershell.run_json(
            f"{powershell.features_query(names)} | "
            "Select-Object FeatureName, @{n='State';e={[string]$_.State}}", timeout=180)
        return {r["FeatureName"]: ("Enabled" if r["State"] in ("Enabled", "EnablePending") else "Disabled")
                for r in rows}

    def set_feature(self, name, enabled):
        _log.info("Windows özelliği %s: %s", name, enabled)
        if enabled:
            cmd = f"Enable-WindowsOptionalFeature -Online -FeatureName {powershell.quote(name)} -All -NoRestart"
        else:
            cmd = f"Disable-WindowsOptionalFeature -Online -FeatureName {powershell.quote(name)} -NoRestart"
        powershell.run(cmd + " | Out-Null", timeout=900)

    def get_nic_property(self, adapter, keyword):
        from app.engine import resolvers  # döngüsel içe aktarmayı önlemek için burada
        return resolvers.nic_property(adapter, keyword)

    def set_nic_property(self, adapter, keyword, value):
        _log.info("Ağ kartı özelliği: %s %s = %s", adapter, keyword, value)
        powershell.run(f"Set-NetAdapterAdvancedProperty -Name {powershell.quote(adapter)} "
                       f"-RegistryKeyword {powershell.quote(keyword)} -RegistryValue {powershell.quote(value)}",
                       timeout=90)

    # ------------------------------------------------------------------ önyükleme (bcdedit)
    def get_bcd(self):
        """Etkin önyükleme girdisinin öğeleri: {öğe_adı: değer}. Yönetici izni gerekir.

        bcdedit'in başlık satırları Windows diline göre çevrilir ama öğe adları
        (hypervisorlaunchtype, useplatformclock...) ve değerleri İngilizce kalır.
        """
        proc = subprocess.run(["bcdedit", "/enum", "{current}"], capture_output=True, timeout=30,
                              creationflags=powershell.CREATE_NO_WINDOW)
        if proc.returncode != 0:
            raise PermissionError("bcdedit okunamadı (yönetici izni gerekir)")
        elements = {}
        for line in proc.stdout.decode("mbcs", errors="replace").splitlines():
            match = re.match(r"^([a-z]+)\s+(.+?)\s*$", line)
            if match:
                elements[match.group(1)] = match.group(2)
        return elements

    def export_bcd(self, file_path):
        """Önyükleme yapılandırmasının tamamını yedekler (bcdedit /export). Geri yükleme: bcdedit /import <dosya>."""
        proc = subprocess.run(["bcdedit", "/export", str(file_path)], capture_output=True, timeout=30,
                              creationflags=powershell.CREATE_NO_WINDOW)
        if proc.returncode != 0:
            raise SystemError_(f"bcdedit /export başarısız (kod {proc.returncode})")

    def set_bcd(self, element, value):
        """value None ise öğe silinir (Windows varsayılanına döner)."""
        _log.info("bcdedit: %s = %s", element, value)
        if value is None:
            if element not in self.get_bcd():
                return
            args = ["bcdedit", "/deletevalue", "{current}", element]
        else:
            args = ["bcdedit", "/set", "{current}", element, str(value)]
        proc = subprocess.run(args, capture_output=True, timeout=30, creationflags=powershell.CREATE_NO_WINDOW)
        if proc.returncode != 0:
            raise SystemError_(f"bcdedit başarısız (kod {proc.returncode})")

    # ------------------------------------------------------------------ TCP alma penceresi otomatik ayarı
    def get_tcp_autotuning(self):
        rows = powershell.run_json("Get-NetTCPSetting -SettingName Internet | "
                                   "Select-Object @{n='v';e={[string]$_.AutoTuningLevelLocal}}")
        return rows[0]["v"].lower() if rows and rows[0].get("v") else None

    def set_tcp_autotuning(self, level):
        _log.info("TCP otomatik ayar: %s", level)
        proc = subprocess.run(["netsh", "int", "tcp", "set", "global", f"autotuninglevel={level}"],
                              capture_output=True, timeout=30, creationflags=powershell.CREATE_NO_WINDOW)
        if proc.returncode != 0:
            raise SystemError_(f"netsh başarısız (kod {proc.returncode})")

    # ------------------------------------------------------------------ WLAN otomatik yapılandırma (Wi-Fi taraması)
    def _wlan(self):
        """wlanapi.dll: (dll, tutamaç, [(guid_metni, GUID)]). Wi-Fi hizmeti/kartı yoksa boş liste."""
        dll = ctypes.WinDLL("wlanapi")
        dll.WlanOpenHandle.argtypes = [wintypes.DWORD, ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD),
                                       ctypes.POINTER(wintypes.HANDLE)]
        dll.WlanEnumInterfaces.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
        dll.WlanQueryInterface.argtypes = [wintypes.HANDLE, ctypes.POINTER(GUID), ctypes.c_int, ctypes.c_void_p,
                                           ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(ctypes.c_void_p),
                                           ctypes.c_void_p]
        dll.WlanSetInterface.argtypes = [wintypes.HANDLE, ctypes.POINTER(GUID), ctypes.c_int, wintypes.DWORD,
                                         ctypes.c_void_p, ctypes.c_void_p]
        dll.WlanFreeMemory.argtypes = [ctypes.c_void_p]
        dll.WlanCloseHandle.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
        version, handle = wintypes.DWORD(), wintypes.HANDLE()
        if dll.WlanOpenHandle(2, None, ctypes.byref(version), ctypes.byref(handle)) != 0:
            return dll, None, []
        listing = ctypes.c_void_p()
        interfaces = []
        if dll.WlanEnumInterfaces(handle, None, ctypes.byref(listing)) == 0 and listing.value:
            count = ctypes.cast(listing, ctypes.POINTER(wintypes.DWORD))[0]
            # WLAN_INTERFACE_INFO_LIST: 8 bayt başlık, sonra 532 baytlık kayıtlar (GUID + 256 WCHAR + durum)
            for i in range(count):
                guid = GUID.from_buffer_copy(ctypes.string_at(listing.value + 8 + i * 532, 16))
                interfaces.append((str(uuid.UUID(bytes_le=bytes(guid))).upper(), guid))
            dll.WlanFreeMemory(listing)
        return dll, handle, interfaces

    def get_wlan_autoconfig(self):
        """{arabirim GUID: 'Enabled'|'Disabled'} (wlan_intf_opcode_autoconf_enabled). Wi-Fi yoksa boş."""
        dll, handle, interfaces = self._wlan()
        result = {}
        try:
            for name, guid in interfaces:
                size, data = wintypes.DWORD(), ctypes.c_void_p()
                if dll.WlanQueryInterface(handle, ctypes.byref(guid), 1, None, ctypes.byref(size),
                                          ctypes.byref(data), None) == 0 and data.value:
                    result[name] = "Enabled" if ctypes.cast(data, ctypes.POINTER(wintypes.BOOL))[0] else "Disabled"
                    dll.WlanFreeMemory(data)
        finally:
            if handle:
                dll.WlanCloseHandle(handle, None)
        return result

    def set_wlan_autoconfig(self, name, enabled):
        _log.info("WLAN otomatik yapılandırma %s: %s", name, enabled)
        dll, handle, interfaces = self._wlan()
        try:
            guid = next((g for n, g in interfaces if n == name), None)
            if guid is None:
                raise SystemError_(f"Wi-Fi arabirimi bulunamadı: {name}")
            flag = wintypes.BOOL(bool(enabled))
            status = dll.WlanSetInterface(handle, ctypes.byref(guid), 1, ctypes.sizeof(flag), ctypes.byref(flag), None)
            if status != 0:
                raise SystemError_(f"WlanSetInterface başarısız (kod {status})")
        finally:
            if handle:
                dll.WlanCloseHandle(handle, None)

    # ------------------------------------------------------------------ zamanlanmış görevler
    def get_task_state(self, path, name):
        """'Enabled' / 'Disabled' veya görev yoksa None."""
        rows = powershell.run_json(
            f"Get-ScheduledTask -TaskPath {powershell.quote(path)} -TaskName {powershell.quote(name)} "
            "-ErrorAction SilentlyContinue | Select-Object @{n='s';e={[string]$_.State}}")
        if not rows:
            return None
        return "Disabled" if rows[0]["s"] == "Disabled" else "Enabled"

    def set_task_enabled(self, path, name, enabled):
        _log.info("Zamanlanmış görev %s%s: %s", path, name, enabled)
        verb = "Enable" if enabled else "Disable"
        powershell.run(f"{verb}-ScheduledTask -TaskPath {powershell.quote(path)} -TaskName {powershell.quote(name)}"
                       " | Out-Null", timeout=60)

    # ------------------------------------------------------------------ aygıtlar (Aygıt Yöneticisi)
    def get_pnp_devices(self, hardware_id):
        """Donanım kimliği eşleşen aygıtlar: [{'id': örnek_kimliği, 'kapali': bool}]."""
        rows = powershell.run_json(
            "Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue | "
            f"Where-Object {{ $_.HardwareID -contains {powershell.quote(hardware_id)} }} | "
            "Select-Object InstanceId, @{n='p';e={[int]$_.Problem}}", timeout=60)
        return [{"id": r["InstanceId"], "kapali": r.get("p") == 22} for r in rows]  # 22 = devre dışı

    def set_pnp_enabled(self, instance_id, enabled):
        _log.info("Aygıt %s: %s", instance_id, "etkin" if enabled else "devre dışı")
        verb = "Enable" if enabled else "Disable"
        powershell.run(f"{verb}-PnpDevice -InstanceId {powershell.quote(instance_id)} -Confirm:$false", timeout=60)

    # ------------------------------------------------------------------ Nihai Performans planı
    ULTIMATE_TEMPLATE = "e9a42b02-d5df-448d-aa00-03f14749eb61"

    def list_ultimate_schemes(self):
        """Nihai Performans planının kopyaları (şablon hariç). Windows bu planları
        adındaki sabit kaynak numarasıyla (powrprof.dll,-19) işaretler."""
        key = r"SYSTEM\CurrentControlSet\Control\Power\User\PowerSchemes"
        found = []
        for guid in registry.subkeys("HKLM", key):
            name = registry.read("HKLM", f"{key}\\{guid}", "FriendlyName") or ""
            if "powrprof.dll,-19," in name and guid.lower() != self.ULTIMATE_TEMPLATE:
                found.append(guid.lower())
        return found

    def is_ultimate_scheme(self, guid):
        """Etkin plan Nihai Performans mı? Yalnızca DURUM okumasında kullanılır (silme için list_ultimate_schemes).
        Şablonun kendisi doğrudan etkinleştirilmiş olabilir (powercfg -setactive e9a42b02-...) ya da kopya, Windows'un
        sürümüne/dil paketine göre kaynak numarası yerine düz adla ("Ultimate Performance", "Nihai Performans") kayıtlı olabilir."""
        guid = guid.lower()
        if guid == self.ULTIMATE_TEMPLATE:
            return True
        key = rf"SYSTEM\CurrentControlSet\Control\Power\User\PowerSchemes\{guid}"
        name = registry.read("HKLM", key, "FriendlyName") or ""
        return "powrprof.dll,-19," in name or bool(re.search(r"ultimate|nihai", name, re.IGNORECASE))

    def create_ultimate_scheme(self):
        _log.info("Nihai Performans planı oluşturuluyor")
        proc = subprocess.run(["powercfg", "-duplicatescheme", self.ULTIMATE_TEMPLATE], capture_output=True,
                              timeout=30, creationflags=powershell.CREATE_NO_WINDOW)
        found = re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
                          proc.stdout.decode("mbcs", errors="replace"), re.IGNORECASE)
        if proc.returncode != 0 or not found:
            raise SystemError_("Nihai Performans planı oluşturulamadı")
        return found.group(0).lower()

    def delete_scheme(self, guid):
        _log.info("Güç planı siliniyor: %s", guid)
        subprocess.run(["powercfg", "-delete", guid], capture_output=True, timeout=30,
                       creationflags=powershell.CREATE_NO_WINDOW)

    # ------------------------------------------------------------------ DNS
    def get_dns(self, adapter):
        """{'otomatik': bool, 'sunucular': [...]}. Adresler yalnızca geri alma yedeği
        için okunur; rapora ve log'a yazılmaz."""
        rows = powershell.run_json(
            f"Get-DnsClientServerAddress -InterfaceAlias {powershell.quote(adapter)} -AddressFamily IPv4 "
            "-ErrorAction SilentlyContinue | Select-Object InterfaceIndex, ServerAddresses")
        servers = powershell.as_list(rows[0].get("ServerAddresses")) if rows else []
        guid = next((a.get("InterfaceGuid") for a in self._adapters() if a.get("Name") == adapter), None)
        static = registry.read("HKLM", rf"SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces\{guid}",
                               "NameServer") if guid else ""
        return {"otomatik": not (static or "").strip(), "sunucular": servers}

    @staticmethod
    def _adapters():
        from app.engine import resolvers  # döngüsel içe aktarmayı önlemek için burada
        return resolvers.physical_net_adapters() or ()

    def set_dns(self, adapter, servers):
        """servers None ise otomatik (modem/DHCP) DNS'e döner."""
        _log.info("DNS değiştiriliyor: %s (%s)", adapter, "otomatik" if not servers else f"{len(servers)} sunucu")
        if not servers:
            cmd = f"Set-DnsClientServerAddress -InterfaceAlias {powershell.quote(adapter)} -ResetServerAddresses"
        else:
            addresses = ",".join(powershell.quote(s) for s in servers)
            cmd = f"Set-DnsClientServerAddress -InterfaceAlias {powershell.quote(adapter)} -ServerAddresses {addresses}"
        powershell.run(cmd, timeout=60)

    # ------------------------------------------------------------------ bellek ve dosyalar
    def get_total_ram_kb(self):
        from app.scan.hardware import memory_status  # noqa: WPS433
        return int(memory_status()["toplam_gb"] * 1024 * 1024)

    # ------------------------------------------------------------------ yöneticiler (bkz. managers.py)
    def list_startup_items(self):
        return managers.list_startup_items()

    def list_logon_tasks(self):
        return managers.list_logon_tasks()

    def list_services(self):
        return managers.list_services()

    def list_pci_devices(self):
        return managers.list_pci_devices()

    def list_power_managed_devices(self):
        return managers.list_power_managed_devices()

    def get_startup_approved(self, root, path, name):
        return managers.get_startup_approved(root, path, name)

    def set_startup_approved(self, root, path, name, enabled):
        _log.info("Başlangıç öğesi %s: %s", "etkin" if enabled else "devre dışı", name)
        managers.set_startup_approved(root, path, name, enabled)

    def set_startup_approved_raw(self, root, path, name, hex_value):
        managers.write_startup_approved_raw(root, path, name, hex_value)

    def get_device_power(self, instance):
        return managers.get_device_power(instance)

    def set_device_power(self, instance, enabled):
        _log.info("Aygıt güç yönetimi %s: %s", instance, enabled)
        managers.set_device_power(instance, enabled)

    def list_audio_pnp_devices(self):
        return managers.list_audio_pnp_devices()

    def get_device_enabled(self, instance):
        return managers.get_device_enabled(instance)

    def set_device_enabled(self, instance, enabled):
        _log.info("Aygıt %s: %s", "etkinleştiriliyor" if enabled else "devre dışı bırakılıyor", instance)
        managers.set_device_enabled(instance, enabled)

    def get_ui_effect(self, name):
        return managers.get_ui_effect(name)

    def set_ui_effect(self, name, enabled):
        _log.info("Görsel efekt %s: %s", name, enabled)
        managers.set_ui_effect(name, enabled)

    def get_power_overlay(self, source):
        return managers.get_power_overlay(source)

    def set_power_overlay(self, source, guid):
        _log.info("Güç modu (%s): %s", source, guid)
        managers.set_power_overlay(source, guid)

    # ------------------------------------------------------------------ NVIDIA (NVAPI) ve ses biçimi
    def nvidia_available(self):
        from app.engine import nvidia  # noqa: WPS433
        return nvidia.available()

    def get_nvidia_settings(self, setting_ids):
        from app.engine import nvidia  # noqa: WPS433
        return nvidia.get_settings(setting_ids)

    def set_nvidia_setting(self, setting_id, value):
        from app.engine import nvidia  # noqa: WPS433
        nvidia.set_setting(setting_id, value)

    def npi_available(self):
        from app.engine import nvidia  # noqa: WPS433
        return nvidia.npi_path() is not None

    def npi_check(self):
        """NPI exe'sinin SHA-256 + imza özeti (driver_tools.verify); araç yoksa None."""
        from app.engine import driver_tools, nvidia  # noqa: WPS433
        path = nvidia.npi_path()
        return driver_tools.verify(str(path)) if path else None

    def run_npi_import(self, settings, sha256=None):
        from app.engine import nvidia  # noqa: WPS433
        nvidia.npi_import(settings, sha256)

    # ------------------------------------------------------------------ AMD (ADLX) ve ekran ölçeklemesi
    def get_amd_settings(self):
        from app.engine import amd  # noqa: WPS433
        return amd.read_settings()

    def set_amd_feature(self, gpu, feature, enabled):
        from app.engine import amd  # noqa: WPS433
        _log.info("AMD %s (%s): %s", feature, gpu, enabled)
        amd.set_feature(gpu, feature, enabled)

    def _amd_display(self, device):
        """Windows ekranına (DISPLAYn) karşılık gelen ADLX ekranı. ADLX, Windows ekran adını vermediği için
        önce EDID adıyla, o tutmazsa "AMD kartında tek ekran" durumuyla eşleştirilir; emin olunamazsa None."""
        from app.engine import amd  # noqa: WPS433
        from app.scan.displays import monitors  # noqa: WPS433
        from app.scan.hardware import collect_displays  # noqa: WPS433
        displays = amd.read_scaling()
        if not displays:
            return None
        on_amd = [d["aygit"].lower() for d in collect_displays()
                  if any(word in (d.get("ekran_karti") or "").upper() for word in ("AMD", "RADEON"))]
        if device.lower() not in on_amd:
            return None
        edid = {m["aygit"].lower(): m.get("edid_ad") for m in monitors()}.get(device.lower())
        named = [d for d in displays if edid and d["ad"] == edid]
        if len(named) == 1:
            return named[0]
        return displays[0] if len(displays) == 1 and len(on_amd) == 1 else None

    def get_display_scaling(self, device):
        """{'surucu': 'nvidia'|'amd', 'deger': 'nvidia:7'} — ölçeklemeyi kim yapıyor; okunamazsa None.
        Sürücü, ekranı süren kartla (EnumDisplayDevices) aynı olmalı: hibritte NVIDIA, dahili kartın ekranını
        "kendisinde" gösterirse monitör kartı ile Bilgisayar sayfası çelişirdi (2.8)."""
        from app.engine import nvidia  # noqa: WPS433
        from app.scan.hardware import collect_displays  # noqa: WPS433
        card = next((d.get("ekran_karti") or "" for d in collect_displays() if d["aygit"].lower() == device.lower()), "")
        on_nvidia = "NVIDIA" in card.upper() or not card  # kart okunamazsa eski davranış
        value = nvidia.get_scaling(device) if on_nvidia and self.nvidia_available() else None
        if value is not None:
            return {"surucu": "nvidia", "deger": f"nvidia:{value}"}
        target = self._amd_display(device)
        if target is not None and target["deger"] is not None:
            return {"surucu": "amd", "deger": f"amd:{target['deger']}"}
        return None

    def set_display_scaling(self, device, value):
        from app.engine import amd, nvidia  # noqa: WPS433
        driver, _sep, number = str(value).partition(":")
        _log.info("Ekran ölçeklemesi (%s): %s", device, value)
        if driver == "nvidia":
            nvidia.set_scaling(device, int(number))
            return
        target = self._amd_display(device) if driver == "amd" else None
        if target is None:
            raise SystemError_(f"ölçekleme değiştirilemedi: {value}")
        amd.set_scaling(target["kimlik"], int(number))

    # ------------------------------------------------------------------ sürücü araçları ve güvenli mod
    def restart_computer(self, seconds=10):
        """Windows'u verilen saniye sonra yeniden başlatır (shutdown /r)."""
        _log.info("Bilgisayar %s sn sonra yeniden başlatılıyor", seconds)
        subprocess.run(["shutdown", "/r", "/t", str(int(seconds))], capture_output=True, timeout=30,
                       creationflags=powershell.CREATE_NO_WINDOW, check=True)

    def open_path(self, target):
        """Kullanıcının tools klasörüne koyduğu programı veya resmi indirme sayfasını açar."""
        _log.info("Açılıyor: %s", target)
        os.startfile(str(target))  # noqa: S606 - hedef sabit listeden (sürücü araçları)

    def get_audio_format(self, device):
        from app.engine import audio  # noqa: WPS433
        return audio.device_formats(device)

    def set_audio_format(self, device, value=None, raw_hex=None):
        from app.engine import audio  # noqa: WPS433
        audio.set_device_format(device, value, raw_hex)

    def get_sleep_precision(self):
        """Sleep(1) gerçekte kaç ms sürüyor: ayrı bir süreçte ölçülür (bu sürecin kendi zamanlayıcı
        isteği sonucu değiştirmesin; çözünürlük istemeyen bir oyunun gördüğü değer)."""
        if getattr(sys, "frozen", False):
            command = [sys.executable, "--uyku-testi"]
        else:
            command = [sys.executable, "-m", "app", "--uyku-testi"]
        proc = subprocess.run(command, capture_output=True, timeout=60, cwd=str(paths.app_dir()),
                              creationflags=powershell.CREATE_NO_WINDOW)
        return json.loads(proc.stdout.decode("utf-8", errors="replace").strip().splitlines()[-1])

    def get_boot_info(self):
        from app.measure.system_measure import read_boot_info  # noqa: WPS433
        return read_boot_info()

    def get_display_refresh(self, device):
        from app.scan.hardware import display_refresh  # noqa: WPS433
        return display_refresh(device)

    def list_monitors(self):
        """Monitör kartı için: ad (EDID), bağlantı, süren kart, modlar, ölçek, ölçekleme."""
        from app.scan.displays import label, monitors  # noqa: WPS433
        from app.scan.hardware import collect_displays, display_layout, display_modes  # noqa: WPS433
        details = {m["aygit"].lower(): m for m in monitors()}
        layouts = {i["aygit"].lower(): i for i in display_layout()}
        result = []
        for index, d in enumerate(collect_displays(), 1):
            m = details.get(d["aygit"].lower(), {})
            try:
                scaling = self.get_display_scaling(d["aygit"])
            except Exception as exc:  # sürücü okuması kartı bozmasın
                _log.info("Ölçekleme okunamadı (%s): %s", d["aygit"], exc)
                scaling = None
            result.append({"aygit": d["aygit"], "ad": label(d, index), "monitor_yolu": m.get("monitor_yolu", ""),
                           "baglanti": d.get("baglanti"), "dahili": d.get("dahili"), "birincil": d["birincil"],
                           "gpu": d["ekran_karti"], "mod": display_modes(d["aygit"]), "olcek": m.get("olcek"),
                           "surucu_olcekleme": scaling, "yerlesim": layouts.get(d["aygit"].lower())})
        return result

    def find_display(self, monitor_path, fallback):
        from app.scan.displays import find_device  # noqa: WPS433
        return find_device(monitor_path, fallback)

    def get_display_mode(self, device):
        from app.scan.hardware import display_modes  # noqa: WPS433
        return display_modes(device)

    def set_display_mode(self, device, width, height, hz):
        from app.scan.hardware import set_display_mode  # noqa: WPS433
        _log.info("Ekran modu: %s %sx%s@%s", device, width, height, hz)
        set_display_mode(device, width, height, hz)

    def get_display_layout(self, device):
        from app.scan.hardware import display_layout  # noqa: WPS433
        return next((i for i in display_layout() if i["aygit"].lower() == device.lower()), None)

    def set_display_layout(self, device, x, y, orientation):
        from app.scan.hardware import set_display_layout  # noqa: WPS433
        _log.info("Ekran yerleşimi: %s (%s,%s) %s", device, x, y, orientation)
        set_display_layout(device, x, y, orientation)

    def get_display_scale(self, device):
        from app.scan.displays import monitors  # noqa: WPS433
        return next((m["olcek"] for m in monitors() if m["aygit"].lower() == device.lower()), None)

    def set_display_scale(self, device, percent):
        from app.scan.displays import set_scale  # noqa: WPS433
        _log.info("Ekran ölçeği: %s %%%s", device, percent)
        set_scale(device, percent)

    def set_display_refresh(self, device, hz):
        from app.scan.hardware import set_display_refresh  # noqa: WPS433
        _log.info("Yenileme hızı değiştiriliyor: %s -> %s Hz", device, hz)
        set_display_refresh(device, int(hz))

    def delete_temp_files(self, folder):
        """Klasördeki silinebilen dosyaları siler (kullanımdakiler atlanır). (adet, bayt) döner.
        Bu işlem GERİ ALINAMAZ; yalnızca kullanıcının açık onayıyla çağrılır."""
        _log.info("Geçici dosyalar temizleniyor: %s", folder)
        count = size = 0
        base = os.path.normcase(os.path.realpath(folder))
        for root, dirs, files in os.walk(folder, topdown=False):
            real = os.path.normcase(os.path.realpath(root))
            if real != base and not real.startswith(base + os.sep):
                continue  # os.walk bağlantı klasörüne (junction) girer: klasör dışını gösteren yerin içi silinmez
            for name in files:
                path = os.path.join(root, name)
                try:
                    length = os.path.getsize(path)
                    os.remove(path)
                    count += 1
                    size += length
                except OSError:
                    continue  # kullanımdaki dosya
            for name in dirs:
                try:
                    os.rmdir(os.path.join(root, name))
                except OSError:
                    continue
        return count, size

    # ------------------------------------------------------------------ anında uygulama
    def set_audio_service_restart(self):
        """Windows Ses servisini yeniden başlatır (ses geliştirmeleri değişikliği için)."""
        _log.info("Windows Ses servisi yeniden başlatılıyor")
        powershell.run("Restart-Service -Name Audiosrv -Force", timeout=60)

    def refresh_mouse(self):
        """Fare değerlerini registry'den alıp Windows'a hemen uygular (oturum kapatmadan)."""
        values = registry.values("HKCU", r"Control Panel\Mouse")
        params = (ctypes.c_int * 3)(int(values.get("MouseThreshold1", "6")),
                                    int(values.get("MouseThreshold2", "10")),
                                    int(values.get("MouseSpeed", "1")))
        user32 = ctypes.windll.user32
        user32.SystemParametersInfoW(SPI_SETMOUSE, 0, params, SPIF_UPDATE)
        user32.SystemParametersInfoW(SPI_SETMOUSESPEED, 0,
                                     ctypes.c_void_p(int(values.get("MouseSensitivity", "10"))), SPIF_UPDATE)

    def refresh_keyboard(self):
        values = registry.values("HKCU", r"Control Panel\Keyboard")
        user32 = ctypes.windll.user32
        user32.SystemParametersInfoW(SPI_SETKEYBOARDDELAY, int(values.get("KeyboardDelay", "1")), None, SPIF_UPDATE)
        user32.SystemParametersInfoW(SPI_SETKEYBOARDSPEED, int(values.get("KeyboardSpeed", "31")), None, SPIF_UPDATE)

    # ------------------------------------------------------------------ geri yükleme noktası
    def list_restore_points(self):
        """[{'aciklama', 'zaman' (ISO)}]. Yönetici izni gerekir; okunamazsa None."""
        try:
            return powershell.run_json(
                "Get-ComputerRestorePoint -ErrorAction Stop | Select-Object Description, "
                "@{n='Zaman';e={([Management.ManagementDateTimeConverter]::ToDateTime($_.CreationTime)).ToString('s')}}",
                timeout=60)
        except powershell.PowerShellError:
            return None

    def create_restore_point(self, description):
        _log.info("Geri yükleme noktası oluşturuluyor: %s", description)
        powershell.run(f"Checkpoint-Computer -Description {powershell.quote(description)} "
                       "-RestorePointType MODIFY_SETTINGS", timeout=300)


class ReadOnlySystem:
    """Değişiklik yapan her metodu engelleyen sarmalayıcı (önizleme ve testler için)."""

    WRITE_PREFIXES = ("set_", "write_", "delete_", "create_", "refresh_", "export_", "run_", "restart_")

    def __init__(self, inner):
        self._inner = inner
        self.blocked = []

    def __getattr__(self, name):
        attr = getattr(self._inner, name)
        if name.startswith(self.WRITE_PREFIXES):
            def blocked(*args, **kwargs):
                self.blocked.append((name, args))
                raise PermissionError(f"Salt okunur modda engellendi: {name}")
            return blocked
        return attr
