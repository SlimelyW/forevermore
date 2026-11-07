"""'Windows varsayılanına döndür' (app/engine/varsayilan.py). Sahte kayıt defteri; gerçek bilgisayara DOKUNMAZ."""

import json
import unittest

from app.engine import fixes, varsayilan
from tests.test_motor import BY_ID, ROOT, EngineTestBase

PERF = varsayilan.CSRSS_PERF


class TestRestoreDefault(EngineTestBase):
    def plant(self):
        """Başka bir programın yaptığı gibi: csrss.exe gerçek zamanlı öncelik."""
        self.sys.write_reg("HKLM", PERF, "CpuPriorityClass", 4, "REG_DWORD")
        self.sys.write_reg("HKLM", PERF, "IoPriority", 3, "REG_DWORD")

    def run_plan(self, admin=True):
        plan = varsayilan.plan(self.sys, "PLC-018")
        engine = self.engine if admin else self.new_engine(admin=False)
        if not admin:
            engine.prepare()
        return engine.apply_custom(varsayilan.change_id("PLC-018"), "PLC-018", plan["adimlar"], plan["degerler"],
                                   related="PLC-018")

    def test_restores_default_then_undo_brings_values_back(self):
        self.plant()
        before = self.sys.state_copy()
        plan = varsayilan.plan(self.sys, "PLC-018")
        self.assertEqual(plan["onizleme"][1]["degerler"].lower(), "cpupriorityclass = 4, iopriority = 3")
        self.assertTrue(self.run_plan().ok)
        self.assertFalse(self.sys.get_key_exists("HKLM", PERF))
        self.assertTrue(self.sys.get_key_exists("HKLM", PERF.rpartition("\\")[0]))  # csrss.exe anahtarına dokunulmaz
        self.assertIsNone(varsayilan.plan(self.sys, "PLC-018"))  # artık düzeltilecek bir şey yok
        self.assertTrue(self.engine.store.has("VARSAYILAN-PLC-018"))  # Değişiklikler'de görünür
        self.assertTrue(self.engine.revert("VARSAYILAN-PLC-018").ok)
        self.assertEqual(self.sys.state_copy(), before)

    def test_needs_admin_and_changes_nothing_without_it(self):
        self.plant()
        before = self.sys.state_copy()
        result = self.run_plan(admin=False)
        self.assertEqual(result.key, "hata.yonetici_gerekli")
        self.assertEqual(self.sys.state_copy(), before)

    def test_no_button_when_default_not_certain(self):
        self.assertIsNone(varsayilan.plan(self.sys, "PLC-018"))  # anahtar yok: zaten varsayılan
        self.plant()
        for tid in ("PLC-008", "PLC-020", "PLC-021", "PLC-007"):  # wuauserv burada Devre dışı değil
            self.assertIsNone(varsayilan.plan(self.sys, tid), tid)
        self.sys.write_reg("HKLM", PERF, "Bilinmeyen", 1, "REG_DWORD")  # yedek geri getiremez: dokunma
        self.assertIsNone(varsayilan.plan(self.sys, "PLC-018"))

    def test_unexpected_subkey_or_type_blocks(self):
        self.plant()
        self.sys.create_reg_key("HKLM", PERF + r"\Alt")
        self.assertIsNone(varsayilan.plan(self.sys, "PLC-018"))
        self.sys.delete_reg_tree("HKLM", PERF + r"\Alt")
        self.sys.write_reg("HKLM", PERF, "PagePriority", b"\x01", "REG_BINARY")
        self.assertIsNone(varsayilan.plan(self.sys, "PLC-018"))

    def test_plan_never_touches_services_or_other_keys(self):
        self.plant()
        plan = varsayilan.plan(self.sys, "PLC-018")
        self.assertTrue(all(s["tur"] in ("registry", "registry_anahtar") and s["yol"] == PERF for s in plan["adimlar"]))
        self.assertEqual(plan["degerler"][-1], "kapali")
        self.assertTrue(all(v is None for v in plan["degerler"][:-1]))  # değerler yalnızca yedeklenir


class TestUpdateService(EngineTestBase):
    def test_disabled_update_service_goes_back_to_manual_and_undo(self):
        self.sys.services["wuauserv"] = {"baslangic": "Disabled", "calisiyor": False}
        before = self.sys.state_copy()
        plan = varsayilan.plan(self.sys, "PLC-021")
        self.assertEqual([s["ad"] for s in plan["adimlar"]], ["wuauserv"])  # başka servis/ilke yok
        self.assertTrue(self.engine.apply_custom("VARSAYILAN-PLC-021", "x", plan["adimlar"], plan["degerler"]).ok)
        self.assertEqual(self.sys.services["wuauserv"], {"baslangic": "Manual", "calisiyor": False})  # başlatılmadı
        self.assertIsNone(varsayilan.plan(self.sys, "PLC-021"))
        self.assertTrue(self.engine.revert("VARSAYILAN-PLC-021").ok)
        self.assertEqual(self.sys.state_copy(), before)

    def test_only_from_disabled(self):
        for start in ("Manual", "Automatic", "AutomaticDelayed"):
            self.sys.services["wuauserv"] = {"baslangic": start, "calisiyor": False}
            self.assertIsNone(varsayilan.plan(self.sys, "PLC-021"), start)


class TestFixesAndTexts(unittest.TestCase):
    def finding(self, tid):
        return {"kod": "tespit", "ilgili": [tid], "params": {}, "seviye": "sorun"}

    def test_summary_fix_types(self):
        for tid in varsayilan.SUPPORTED:
            self.assertEqual(fixes.fix_for(self.finding(tid), BY_ID), {"tur": "varsayilan", "id": tid})
        self.assertEqual(fixes.fix_for(self.finding("PLC-007"), BY_ID)["tur"], "kapat")
        for tid in varsayilan.MANUAL:  # belirsiz varsayılan / ayrı kart: düğme yok
            self.assertIsNone(fixes.fix_for(self.finding(tid), BY_ID), tid)

    def test_supported_and_manual_are_detected_info_items(self):
        for tid in varsayilan.SUPPORTED + varsayilan.MANUAL:
            self.assertEqual(BY_ID[tid]["sinif"], "BILGI", tid)
            self.assertTrue(BY_ID[tid].get("tespit"), tid)
        self.assertEqual(BY_ID["PLC-020"]["ilgili"], "SYS-017")  # Defender kartına git

    def test_manual_lines_exist_in_every_language(self):
        for path in (ROOT / "lang").glob("*.json"):
            texts = json.loads(path.read_text(encoding="utf-8"))
            for tid in varsayilan.MANUAL:
                self.assertIn(f"ui.varsayilan.elle.{tid}", texts, path.name)


if __name__ == "__main__":
    unittest.main()
