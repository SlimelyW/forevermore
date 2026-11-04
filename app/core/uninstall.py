"""Kaldırmadan önce temizlik.

Uygulama silinmeden önce bilgisayarda bıraktığı izleri kaldırır:
1. "Windows'la başlat" zamanlanmış görevi (uygulamanın Windows'a eklediği tek kalıcı kayıt).
2. Yarım kalmış oyun oturumu (oyun sırasında durdurulan servisler, güç planı, bildirimler).
3. İstenirse: uygulamanın yaptığı TÜM değişiklikler eski haline getirilir.
4. İstenirse: uygulama verileri (%LOCALAPPDATA%\\Forevermore) silinir. Değişiklikler geri
   alınmadan veriler silinemez; aksi hâlde geri alma için gereken yedekler kaybolur.

Kurulum programı kaldırırken `Forevermore.exe --kaldir` çalıştırmalıdır
(`--tumunu-geri-al` eklenirse değişiklikler de geri alınır).
"""

import logging
import shutil

from app.core import autostart, log, paths

_log = log.get("uninstall")


def cleanup(engine, revert_changes=False, delete_data=False, session=None):
    """Sonuç: {'gorev', 'oyun_oturumu', 'geri_alinan', 'geri_alinamayan', 'veri_silindi'}."""
    report = {"gorev": False, "oyun_oturumu": False, "geri_alinan": 0, "geri_alinamayan": [], "veri_silindi": False}
    try:
        if autostart.is_enabled():
            autostart.disable()
            report["gorev"] = True
    except Exception as exc:
        _log.warning("Başlangıç görevi silinemedi: %s", exc)
    try:
        if session is None:
            from app.games.runtime import GameSession, ProcessOps  # noqa: WPS433
            session = GameSession(engine.system, ProcessOps())
        report["oyun_oturumu"] = session.recover()
    except Exception as exc:
        _log.warning("Oyun oturumu geri alınamadı: %s", exc)
    if revert_changes:
        for change_id, result in engine.revert_all():
            if result.ok:
                report["geri_alinan"] += 1
            else:
                report["geri_alinamayan"].append(change_id)
    _log.info("Kaldırma temizliği: %s", report)
    if delete_data:
        if engine.changed_ids():
            _log.warning("Geri alınmamış değişiklik var; uygulama verileri silinmedi")
        else:
            logging.shutdown()  # log dosyası açıkken klasör silinemez
            shutil.rmtree(paths.user_data_dir(), ignore_errors=True)
            shutil.rmtree(paths.legacy_data_dir(), ignore_errors=True)  # eski adın (PC Optimizer) kopyası
            report["veri_silindi"] = True
    return report
