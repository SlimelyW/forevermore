"""Taramayı komut satırından çalıştırır (arayüz gelene kadar test için).

    py -3.12 -m app.scan            -> raporu ekrana yazar
    py -3.12 -m app.scan --kaydet   -> ayrıca %LOCALAPPDATA%\\Forevermore\\reports altına kaydeder

Hiçbir ayarı değiştirmez.
"""

import argparse
import sys

from app.core import log, privacy
from app.core.i18n import t
from app.scan import report, run_scan


def main():
    parser = argparse.ArgumentParser(description="Forevermore sistem taraması (salt okunur)")
    parser.add_argument("--kaydet", action="store_true", help="Raporu dosyaya kaydet")
    args = parser.parse_args()

    sys.stdout.reconfigure(encoding="utf-8")
    log.setup()

    def progress(done, total, name):
        print(t("tarama.ilerleme", bolum=t(f"bolum.{name}"), sira=done, toplam=total), file=sys.stderr)

    result = run_scan(progress=progress)
    # Ekrana da kaydedilecek raporla aynı, kişisel bilgiden arındırılmış metin yazılır.
    print(privacy.scrub_text(report.build_text(privacy.scrub(result, export=True))))
    print(t("tarama.bitti", sure=result["toplam_sure"]), file=sys.stderr)
    if args.kaydet:
        txt_path, json_path = report.save(result)
        print(f"Rapor: {txt_path}", file=sys.stderr)
        print(f"JSON:  {json_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
