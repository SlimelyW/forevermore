"""İşlemci yapısı (salt okunur): mantıksal işlemciler, çekirdekler, P/E sınıfı, L3 grupları.

Windows'un belgelenmiş API'leri:
- GetSystemCpuSetInformation (CPU Set kimliği, çekirdek, son seviye önbellek, verim sınıfı)
- GetLogicalProcessorInformationEx(RelationCache) (L3 önbellek boyutu; X3D V-Cache CCD'sini bulmak için)

Oyun başına çekirdek seçimi CPU Set kimlikleriyle yapılır (SetProcessDefaultCpuSets).
"""

import ctypes
from ctypes import wintypes

RELATION_CACHE = 2


class _CpuSet(ctypes.Structure):
    _fields_ = [("Id", wintypes.DWORD), ("Group", wintypes.WORD), ("LogicalProcessorIndex", ctypes.c_ubyte),
                ("CoreIndex", ctypes.c_ubyte), ("LastLevelCacheIndex", ctypes.c_ubyte),
                ("NumaNodeIndex", ctypes.c_ubyte), ("EfficiencyClass", ctypes.c_ubyte),
                ("AllFlags", ctypes.c_ubyte), ("Reserved", wintypes.DWORD), ("AllocationTag", ctypes.c_uint64)]


class _CpuSetInfo(ctypes.Structure):
    _fields_ = [("Size", wintypes.DWORD), ("Type", wintypes.DWORD), ("CpuSet", _CpuSet)]


class _GroupAffinity(ctypes.Structure):
    _fields_ = [("Mask", ctypes.c_size_t), ("Group", wintypes.WORD), ("Reserved", wintypes.WORD * 3)]


class _CacheRelationship(ctypes.Structure):
    _fields_ = [("Level", ctypes.c_ubyte), ("Associativity", ctypes.c_ubyte), ("LineSize", wintypes.WORD),
                ("CacheSize", wintypes.DWORD), ("Type", wintypes.DWORD), ("Reserved", ctypes.c_ubyte * 18),
                ("GroupCount", wintypes.WORD), ("GroupMask", _GroupAffinity)]


def _cpu_sets():
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    needed = wintypes.ULONG()
    kernel.GetSystemCpuSetInformation(None, 0, ctypes.byref(needed), None, 0)
    buffer = (ctypes.c_byte * needed.value)()
    if not kernel.GetSystemCpuSetInformation(buffer, needed, ctypes.byref(needed), None, 0):
        raise OSError(f"GetSystemCpuSetInformation hata {ctypes.get_last_error()}")
    result, offset = [], 0
    while offset < needed.value:
        info = _CpuSetInfo.from_buffer(buffer, offset)
        if info.Type == 0:  # CpuSetInformation
            c = info.CpuSet
            result.append({"id": c.Id, "grup": c.Group, "mantiksal": c.LogicalProcessorIndex, "cekirdek": c.CoreIndex,
                           "l3": c.LastLevelCacheIndex, "sinif": c.EfficiencyClass})
        offset += info.Size or ctypes.sizeof(_CpuSetInfo)
    return result


def _l3_sizes():
    """{(grup, mantıksal işlemci): L3 boyutu (bayt)}."""
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    needed = wintypes.DWORD()
    kernel.GetLogicalProcessorInformationEx(RELATION_CACHE, None, ctypes.byref(needed))
    buffer = (ctypes.c_byte * needed.value)()
    if not kernel.GetLogicalProcessorInformationEx(RELATION_CACHE, buffer, ctypes.byref(needed)):
        return {}
    sizes, offset = {}, 0
    while offset < needed.value:
        relation, size = ctypes.cast(ctypes.byref(buffer, offset), ctypes.POINTER(wintypes.DWORD * 2))[0]
        if relation == RELATION_CACHE:
            cache = _CacheRelationship.from_buffer(buffer, offset + 8)
            if cache.Level == 3:
                mask = cache.GroupMask
                for bit in range(64):
                    if mask.Mask >> bit & 1:
                        sizes[(mask.Group, bit)] = cache.CacheSize
        offset += size or 1
    return sizes


def read():
    """İşlemci yapısı:
    {'cpular': [{'id', 'no', 'cekirdek', 'l3', 'sinif', 'p', 'ilk_is_parcacigi'}],
     'hibrit': bool, 'smt': bool, 'l3_gruplari': [{'indeks', 'boyut_mb', 'cpular'}], 'vcache_l3': indeks|None}
    """
    sets = _cpu_sets()
    sizes = _l3_sizes()
    classes = {s["sinif"] for s in sets}
    hybrid = len(classes) > 1
    top_class = max(classes) if classes else 0
    seen_cores = set()
    cpus = []
    for number, s in enumerate(sorted(sets, key=lambda x: (x["grup"], x["mantiksal"]))):
        core_key = (s["grup"], s["cekirdek"])
        first = core_key not in seen_cores
        seen_cores.add(core_key)
        cpus.append({"id": s["id"], "no": number, "cekirdek": s["cekirdek"], "l3": s["l3"], "sinif": s["sinif"],
                     "p": (s["sinif"] == top_class) if hybrid else True, "ilk_is_parcacigi": first,
                     "l3_boyut": sizes.get((s["grup"], s["mantiksal"]))})
    groups = {}
    for cpu in cpus:
        groups.setdefault(cpu["l3"], []).append(cpu)
    l3_groups = [{"indeks": index, "boyut_mb": round((members[0]["l3_boyut"] or 0) / 2 ** 20),
                  "cpular": [c["no"] for c in members]} for index, members in sorted(groups.items())]
    vcache = None
    if len(l3_groups) == 2 and not hybrid:
        a, b = l3_groups
        # X3D çift CCD: bir CCD'nin L3'ü diğerinin en az 2 katıysa V-Cache CCD odur.
        if a["boyut_mb"] and b["boyut_mb"] and max(a["boyut_mb"], b["boyut_mb"]) >= 2 * min(a["boyut_mb"], b["boyut_mb"]):
            vcache = a["indeks"] if a["boyut_mb"] > b["boyut_mb"] else b["indeks"]
    return {"cpular": cpus, "hibrit": hybrid, "smt": len(seen_cores) < len(cpus), "l3_gruplari": l3_groups,
            "vcache_l3": vcache}


def preset_ids(topology, preset):
    """Hazır seçimin CPU numaraları: tum / performans / fiziksel / vcache."""
    cpus = topology["cpular"]
    if preset == "performans":
        return [c["no"] for c in cpus if c["p"]]
    if preset == "fiziksel":
        return [c["no"] for c in cpus if c["ilk_is_parcacigi"]]
    if preset == "vcache" and topology["vcache_l3"] is not None:
        return [c["no"] for c in cpus if c["l3"] == topology["vcache_l3"]]
    return [c["no"] for c in cpus]
