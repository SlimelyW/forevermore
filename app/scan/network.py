"""Ağ ayarları: bağlantı türü/hızı, TCP ayarları, DNS türü, Nagle.

Gizlilik: IP adresi, MAC adresi ve Wi-Fi ağ adı (SSID) toplanmaz. DNS sunucu
adresleri yalnızca bellekte sınıflandırılır ("Cloudflare", "modem" gibi) ve
adresin kendisi hiçbir yere yazılmaz.
"""

import ipaddress
import re

from app.core import powershell, registry
from app.core.i18n import t
from app.engine import resolvers

PUBLIC_DNS = {
    "1.1.1.1": "Cloudflare", "1.0.0.1": "Cloudflare",
    "8.8.8.8": "Google", "8.8.4.4": "Google",
    "9.9.9.9": "Quad9", "149.112.112.112": "Quad9",
    "208.67.222.222": "OpenDNS", "208.67.220.220": "OpenDNS",
    "94.140.14.14": "AdGuard", "94.140.15.15": "AdGuard",
}
TCPIP_INTERFACES = r"SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces"

_NETWORK_PS = r"""
$tcp = $null; $dns = @(); $rss = @()
try { $tcp = Get-NetTCPSetting -SettingName Internet -ErrorAction Stop | Select-Object @{n='AutoTuning';e={[string]$_.AutoTuningLevelLocal}}, @{n='Congestion';e={[string]$_.CongestionProvider}} } catch {}
try { $dns = @(Get-DnsClientServerAddress -AddressFamily IPv4 -ErrorAction Stop | Select-Object InterfaceAlias, ServerAddresses) } catch {}
try { $rss = @(Get-NetAdapterRss -ErrorAction Stop | Select-Object Name, Enabled) } catch {}
[pscustomobject]@{tcp=$tcp; dns=$dns; rss=$rss}
"""


def _link_mbps(adapter):
    """Bağlantı hızı (Mbps). Sayısal Speed (bit/sn) değeri kullanılır; LinkSpeed metni
    ("1 Gbps") Windows diline göre farklı yazılabildiği için yalnızca yedektir."""
    bits = adapter.get("HizBit")
    if isinstance(bits, (int, float)) and 0 < bits < 2 ** 63:
        return bits / 1e6
    text = adapter.get("LinkSpeed")
    match = re.match(r"([\d.]+)\s*([GMK])bps", text or "")
    if not match:
        return None
    factor = {"G": 1000, "M": 1, "K": 0.001}[match.group(2)]
    return float(match.group(1)) * factor


def _classify_dns(addresses):
    """DNS adreslerini kişisel bilgi içermeyen bir etikete çevirir."""
    labels = set()
    for addr in addresses:
        if addr in PUBLIC_DNS:
            labels.add(PUBLIC_DNS[addr])
            continue
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if ip.is_loopback:
            labels.add("yerel_proxy")  # bu bilgisayarda çalışan DNS aracı (ör. DNSCrypt)
        else:
            labels.add("yerel_ag" if ip.is_private else "diger_genel")
    return sorted(labels)


def collect_network():
    adapters = resolvers.physical_net_adapters() or ()
    extra = powershell.run_object(_NETWORK_PS, timeout=60)
    dns_by_alias = {d.get("InterfaceAlias"): powershell.as_list(d.get("ServerAddresses"))
                    for d in powershell.as_list(extra.get("dns"))}
    rss_by_name = {r.get("Name"): r.get("Enabled") for r in powershell.as_list(extra.get("rss"))}

    rows = []
    for a in adapters:
        guid = a.get("InterfaceGuid") or ""
        iface_key = f"{TCPIP_INTERFACES}\\{guid}"
        static_dns = registry.read("HKLM", iface_key, "NameServer") or ""
        connected = a.get("Durum") == "Up"
        rows.append({
            "ad": a.get("InterfaceDescription"),
            "_yerel_baglanti_adi": a.get("Name"),
            "tur": "wifi" if a.get("NdisPhysicalMedium") == resolvers.NDIS_MEDIUM_WIFI else "kablolu",
            "bagli": connected,
            "hiz_mbps": _link_mbps(a) if connected else None,
            "dns": {
                "elle_ayarli": bool(static_dns.strip()),
                "saglayici": _classify_dns(dns_by_alias.get(a.get("Name"), [])) if connected else [],
            },
            "nagle_kapali": (registry.read("HKLM", iface_key, "TcpAckFrequency") == 1
                             and registry.read("HKLM", iface_key, "TCPNoDelay") == 1),
            "rss": rss_by_name.get(a.get("Name")),
        })
    tcp = extra.get("tcp") or {}
    return {
        "bagdastiricilar": rows,
        "tcp": {"otomatik_ayar": tcp.get("AutoTuning"), "tikaniklik_algoritmasi": tcp.get("Congestion")},
        "teslim_iyilestirme_ilkesi": registry.read(
            "HKLM", r"SOFTWARE\Policies\Microsoft\Windows\DeliveryOptimization", "DODownloadMode"),
        "ipv6_kapatma_degeri": registry.read(
            "HKLM", r"SYSTEM\CurrentControlSet\Services\Tcpip6\Parameters", "DisabledComponents"),
        "not": t("tarama.not.wifi"),
    }
