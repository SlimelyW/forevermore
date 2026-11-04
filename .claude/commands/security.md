---
description: Release öncesi kısa güvenlik kontrolü (docs/SECURITY.md'nin hızlı sürümü); hiçbir şeyi değiştirmez
---

Yalnızca OKU ve raporla; kod, ayar veya belge değiştirme. Her satır için EVET/HAYIR/DOĞRULANMADI + kanıt (komut çıktısı veya dosya:satır) yaz.

1. **Secret:** `git grep -nIiE "(api[_-]?key|secret|token|passwd|password|bearer)\s*[:=]\s*['\"][A-Za-z0-9_\-]{12,}" -- . ':!*.md'` ve `git grep -nI "BEGIN .*PRIVATE KEY"` boş olmalı. `git ls-files | grep -iE "\.(env|pem|pfx|key)$|kodlar|secret"` boş olmalı.
2. **Ağ:** `git grep -nE "urllib|requests\.|http\.client|socket\." -- app` yalnızca `app/core/licensing.py` göstermeli. `tests.test_gizlilik` geçmeli.
3. **Komut enjeksiyonu:** `git grep -nE "shell\s*=\s*True|os\.system" -- app` boş olmalı. PowerShell'e giren her dış değer `powershell.quote()` ile geçmeli (yeni `powershell.run(f"` satırlarına bak).
4. **Debug / geliştirici anahtarları:** `licensing.dev_override` `frozen` iken kapalı olmalı; `app/core/log.py` düzeyi INFO kalmalı.
5. **Üçüncü parti araçlar:** `tools\` içinden çalıştırılan her exe (NPI, DDU, NVCleanstall, PresentMon) çalıştırmadan önce `driver_tools.verify` + özet yeniden denetiminden geçmeli; yeni bir araç eklendiyse aynısı yapılmış mı?
6. **Yedek:** `app/engine/backup.py` imza (HMAC) ve `engine.revert` içindeki `validate_stored_step` yerinde mi? `tests.test_yedek_butunluk` geçmeli.
7. **Testler:** `QT_QPA_PLATFORM=offscreen python -m unittest discover -s tests -t .` tamamı geçmeli; `python -m app --kontrol` hata vermemeli.
8. **Bağımlılık:** `requirements*.txt` sürümleri hâlâ sabit mi? Değiştiyse `pip-audit` yeniden çalıştırılmalı (geçici venv'de, `--no-deps`; onay iste).
9. **Paket:** `dist\Forevermore.zip` varsa `derle.ps1` çıktısında "denetim: orijinal" görünmeli; "İMZASIZ" ise dağıtma. Özel imza anahtarı (`%USERPROFILE%\.forevermore-imza`) depoda/pakette olmamalı.
10. **Açık maddeler:** `docs/SECURITY.md` özet tablosunda `~~`/"Düzeltildi" olmayan satırları listele; bunların hâlâ geçerli olduğunu söyle.

Sonda: en fazla 8 satır özet (kaç EVET / HAYIR / DOĞRULANMADI), HAYIR çıkanların listesi ve "yayınlanabilir mi?" önerisi.
