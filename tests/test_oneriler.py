"""Bu bilgisayar için öneriler: sıralama ve eleme kuralları (sahte ayar verisiyle)."""

import unittest
from types import SimpleNamespace as NS

from app.engine import recommend


def tweak(tid, impact="orta", reality="gerçek", risk="güvenli", gpu=None, form=None, **extra):
    data = {"id": tid, "sinif": "SWITCH", "kategori": "Performans", "risk": risk, "islem": {},
            "performans_etkisi": {"seviye": impact}, "gerceklik": {"durum": reality},
            "uyumluluk": {"gpu": gpu, "form": form or {"masaustu": "goster", "laptop": "goster"}}}
    data.update(extra)
    return data


def run(tweaks, off=None, hidden=(), gpus=("NVIDIA",), form="laptop", **kwargs):
    states = {t["id"]: NS(status="kapali") for t in tweaks}
    states.update(off or {})
    availability = {h: NS(visible=False) for h in hidden}
    return recommend.recommend(tweaks, availability, states, list(gpus), form, **kwargs)


class TestRecommend(unittest.TestCase):
    def test_hardware_specific_first_then_impact(self):
        tweaks = [tweak("A", "düşük"), tweak("B", "düşük", gpu=["NVIDIA"]),
                  tweak("C", "düşük", form={"masaustu": "goster", "laptop": "gizle"})]
        result = run(tweaks)
        self.assertEqual([r["id"] for r in result], ["B", "A", "C"])  # aynı etkide donanıma özel olan önde
        self.assertEqual((result[0]["neden"], result[0]["deger"]), ("gpu", "NVIDIA"))
        self.assertEqual(result[1]["neden"], "genel")

    def test_high_impact_still_beats_low_impact_hardware_match(self):
        result = run([tweak("hw", "düşük", gpu=["NVIDIA"]), tweak("yuksek", "yüksek")])
        self.assertEqual([r["id"] for r in result], ["yuksek", "hw"])

    def test_laptop_only_setting_is_form_match_on_laptop(self):
        laptop_only = tweak("L", "düşük", form={"masaustu": "gizle", "laptop": "goster"})
        self.assertEqual(run([laptop_only], form="laptop")[0]["neden"], "form")
        self.assertEqual(run([laptop_only], form="laptop")[0]["deger"], "laptop")

    def test_excluded(self):
        tweaks = [tweak("placebo", reality="placebo"), tweak("zarar", reality="zararlı"), tweak("yok", impact="yok"),
                  tweak("riskli", risk="riskli"), tweak("kapat", islem={"yalnizca_kapat": True}),
                  tweak("elle", liste_yoneticisi="msi"), tweak("gizli"), tweak("acik"), tweak("plc", kategori="Placebo"),
                  tweak("rehber", sinif="REHBER"), tweak("tamam")]
        result = run(tweaks, off={"acik": NS(status="acik")}, hidden=["gizli"])
        self.assertEqual([r["id"] for r in result], ["tamam"])

    def test_other_vendor_gpu_setting_gets_no_bonus(self):
        result = run([tweak("amd", "düşük", gpu=["AMD"]), tweak("genel", "düşük")], gpus=("NVIDIA",))
        self.assertEqual({r["id"]: r["neden"] for r in result}, {"amd": "genel", "genel": "genel"})

    def test_limit_and_stable_order(self):
        tweaks = [tweak(f"T{i}") for i in range(10)]
        result = run(tweaks, limit=3)
        self.assertEqual([r["id"] for r in result], ["T0", "T1", "T2"])


if __name__ == "__main__":
    unittest.main()
