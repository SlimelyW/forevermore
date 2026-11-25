"""Denetim A2 S1: Windows araçları çıplak adla (cwd'de aranabilir) değil System32 tam yoluyla çağrılır.

Kaynakta subprocess.run/Popen/check_output/call'a verilen listenin ilk öğesi düz bir metin sabitiyse (ör. "reg") test düşer.
Çalıştırma: py -3.12 -m unittest tests.test_cagri_yolu -v
"""

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CALLS = {"run", "Popen", "check_output", "check_call", "call"}


def bare_calls():
    found = []
    for path in sorted((ROOT / "app").rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            # os.startfile("rstrui.exe") gibi yol/adres içermeyen sabit ad da çıplaktır (Denetim YAYIN D1)
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "startfile"
                    and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)
                    and not any(c in node.args[0].value for c in ":\\/")):
                found.append(f"{path.relative_to(ROOT)}:{node.lineno} {node.args[0].value}")
                continue
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in CALLS
                    and isinstance(node.func.value, ast.Name) and node.func.value.id == "subprocess" and node.args):
                continue
            arg = node.args[0]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):  # "reg export ..." (dize olarak verilmiş)
                found.append(f"{path.relative_to(ROOT)}:{node.lineno}")
            elif isinstance(arg, (ast.List, ast.Tuple)) and arg.elts and isinstance(arg.elts[0], ast.Constant) \
                    and isinstance(arg.elts[0].value, str):
                found.append(f"{path.relative_to(ROOT)}:{node.lineno} {arg.elts[0].value}")
    return found


class TestCagriYolu(unittest.TestCase):
    def test_cıplak_komut_adi_yok(self):
        self.assertEqual(bare_calls(), [])


if __name__ == "__main__":
    unittest.main()
