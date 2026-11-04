"""Durum tanılama raporu: her switch ayarı için okunan HAM değeri ve bunun nasıl yorumlandığını yazar.

Bir ayar gerçekte açıkken kapalı görünüyorsa (ya da tersi) bu rapor hangi okumanın yanlış olduğunu gösterir.
Salt okunurdur (ReadOnlySystem); DNS adresleri gibi kişisel alanlar rapora yazılmaz.
"""

import tempfile
from pathlib import Path

from app.engine import catalog, handlers
from app.engine.backup import BackupStore
from app.engine.engine import Engine
from app.engine.system import ReadOnlySystem, WindowsSystem

PRIVATE_KEYS = {"dns", "ham", "ozel"}
MAX_RAW = 240


def _raw(snap):
    clean = {k: v for k, v in snap.items() if k not in PRIVATE_KEYS} if isinstance(snap, dict) else snap
    text = repr(clean)
    return text if len(text) <= MAX_RAW else text[:MAX_RAW] + "…"


def rapor(profile=None):
    """Raporun metnini döndürür."""
    guarded = ReadOnlySystem(WindowsSystem())
    with tempfile.TemporaryDirectory() as tmp:
        engine = Engine(system=guarded, store=BackupStore(Path(tmp)), profile=profile)
        prof = engine.profile
        lines = [f"Windows {prof.windows_version} build {prof.build}, {prof.form}, GPU {prof.gpu_vendors}", ""]
        for tweak in catalog.tweaks():
            if tweak.get("islem", {}).get("kontrol") != "switch":
                continue
            avail = engine.availability(tweak)
            if not avail.visible:
                lines.append(f"{tweak['id']:<9} gizli ({avail.reasons[0][0]})")
                continue
            try:
                steps = engine._steps(tweak)  # noqa: SLF001 - aynı paket
                parts = []
                for step in steps:
                    snap = handlers.snapshot(guarded, step)
                    parts.append(f"{handlers.state(step, snap)} <- {step.get('eylem') or step.get('tur')} {_raw(snap)}")
                state = engine.read_state(tweak).status
            except Exception as exc:  # tek ayarın hatası raporu durdurmasın
                lines.append(f"{tweak['id']:<9} HATA {type(exc).__name__}: {exc}")
                continue
            lines.append(f"{tweak['id']:<9} {state:<8} {tweak['ad'][:50]}")
            lines.extend(f"{'':11}{p}" for p in parts)
    return "\n".join(lines) + "\n"
