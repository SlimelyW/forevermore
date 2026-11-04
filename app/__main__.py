"""Uygulamanın giriş noktası.

    py -3.12 -m app              -> normal açılış (yönetici izni ister)
    py -3.12 -m app --onizleme   -> önizleme: yönetici izni istemez, HİÇBİR ayar değiştirmez

Yönetici değilse uygulama kendini "Yönetici olarak" yeniden başlatır. Kullanıcı
UAC penceresinde "Hayır" derse uygulama salt okunur modda açılır (tarama ve
rehberler çalışır, ayarlar değiştirilemez).
"""

import argparse
import sys

from app.core import admin, i18n, log
from app.ui.controller import MODE_NORMAL, MODE_PREVIEW, MODE_READ_ONLY


def main():
    parser = argparse.ArgumentParser(description="Forevermore")
    parser.add_argument("--onizleme", action="store_true", help="Hiçbir ayarı değiştirmeyen deneme modu")
    parser.add_argument("--yukseltildi", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--tepside", action="store_true", help="Pencere açmadan tepside başlar (Windows'la başlatma)")
    parser.add_argument("--kaldir", action="store_true",
                        help="Kaldırmadan önce temizlik: Windows'la başlat görevini ve yarım oyun ayarlarını kaldırır")
    parser.add_argument("--tumunu-geri-al", action="store_true",
                        help="--kaldir ile birlikte: uygulamanın yaptığı tüm değişiklikleri de geri alır")
    parser.add_argument("--uyku-testi", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--kontrol", action="store_true",
                        help="Pencere açmadan paket kontrolü yapar (veri, metin, arayüz dosyaları) ve çıkar")
    args = parser.parse_args()
    if args.uyku_testi:  # Önce / Sonra ölçümü için ayrı süreçte Sleep(1) hassasiyeti
        import json  # noqa: WPS433
        from app.engine import timer_resolution  # noqa: WPS433
        print(json.dumps(timer_resolution.sleep_test()))
        return 0

    log.setup()
    from app.core import settings  # noqa: WPS433
    i18n.load(settings.get("dil") or i18n.suggest())
    _log = log.get("main")

    if args.kontrol:
        return self_check()

    if args.kaldir:
        if not admin.is_admin() and not args.yukseltildi and admin.relaunch_as_admin(["--yukseltildi"]):
            return 0
        from app.core import uninstall  # noqa: WPS433
        from app.engine.engine import Engine  # noqa: WPS433
        engine = Engine()
        engine.accept_without_restore_point()  # yalnızca geri alma yapılır; geri alma nokta gerektirmez
        report = uninstall.cleanup(engine, revert_changes=args.tumunu_geri_al)
        return 0 if not report["geri_alinamayan"] else 2

    if args.onizleme:
        mode = MODE_PREVIEW
    elif admin.is_admin():
        mode = MODE_NORMAL
    elif not args.yukseltildi and admin.relaunch_as_admin(["--yukseltildi"]):
        _log.info("Yönetici olarak yeniden başlatıldı")
        return 0
    else:
        _log.warning("Yönetici izni verilmedi; salt okunur mod")
        mode = MODE_READ_ONLY

    _log.info("Uygulama açıldı (mod: %s)", mode)
    from app.ui.app import run  # Tk yalnızca gerektiğinde yüklensin
    run(mode, in_tray=args.tepside)
    return 0


def self_check():
    """Derlenmiş .exe'nin dosyalarını bulabildiğini doğrular. Hiçbir pencere
    açmaz, hiçbir ayara dokunmaz. Sonuç logs\\kontrol.txt dosyasına yazılır."""
    import json

    from app import __version__
    from app.core import consent, paths
    from app.engine import catalog, profiles

    lines, ok = [f"Forevermore {__version__}"], True

    def check(name, func):
        nonlocal ok
        try:
            lines.append(f"OK    {name}: {func()}")
        except Exception as exc:  # her hatayı rapora yaz
            ok = False
            lines.append(f"HATA  {name}: {exc}")

    check("veri klasörü", lambda: paths.data_dir().name + (" (dışarıda)" if (paths.app_dir() / "data").is_dir()
                                                          else " (gömülü)"))
    check("ayarlar", lambda: f"{len(catalog.tweaks())} ayar yüklendi")
    check("profiller", lambda: f"{len(profiles.load(catalog.by_id()))} profil")
    check("diller", lambda: ", ".join(f"{item['kod']} ({len(json.loads((paths.lang_dir() / (item['kod'] + '.json')).read_text(encoding='utf-8'))) - 1} anahtar)"
                                      for item in i18n.available()))
    check("seçili dil", lambda: i18n.current())
    check("başlangıç onayı metinleri", lambda: ", ".join(
        f"{item['kod']}: {len(consent.text(item['kod']))} karakter" for item in i18n.available()))
    check("bilinen süreçler", lambda: (paths.data_dir() / "bilinen_surecler.json").stat().st_size and "var")

    def qt_check():
        import PySide6
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication(["kontrol", "-platform", "offscreen"])
        return f"PySide6 {PySide6.__version__}, {'hazır' if app else 'YOK'}"

    check("arayüz kütüphanesi", qt_check)
    (paths.logs_dir() / "kontrol.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
