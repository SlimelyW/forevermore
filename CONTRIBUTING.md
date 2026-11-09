# Katkı rehberi / Contributing

Katkı vermek istediğiniz için teşekkürler. Forevermore Windows ayarlarını değiştirdiği için bazı kurallar sıkıdır;
amaç kullanıcının bilgisayarını korumaktır. Bu bir hobi projesidir; geri dönüş süresi garanti edilmez.

## Başlamadan önce

- Hata ya da öneri için bir **konu (issue)** açın. Büyük bir değişiklik yapacaksanız önce konuşalım.
- **Güvenlik açığını herkese açık konu olarak açmayın**; bkz. [SECURITY.md](SECURITY.md).
- Katkınız [MIT lisansı](LICENSE) altında yayımlanır; bunu kabul etmiş olursunuz.

## Geliştirme ortamı

Python 3.12, Windows 10/11.

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
$env:QT_QPA_PLATFORM = "offscreen"
.venv\Scripts\python -m unittest discover -s tests -t .      # tüm testler (pencere açmaz, gerçek ayar yazmaz)
.venv\Scripts\python -m app --onizleme                        # uygulamayı hiçbir ayarı değiştirmeden dene
```

PR göndermeden önce testlerin geçtiğinden emin olun. Arayüz değişikliğinde pencere göstermeden çizen aracı kullanın:
`py -3.12 -m tests.arayuz_goruntu <klasör>` (bkz. dosyanın başındaki açıklama).

## Kurallar (kısaca)

1. **Her sistem değişikliği motordan geçer** (`apply_custom` / `set_enabled`): yedek, doğrulama ve geri alma olmadan
   doğrudan kayıt defterine/hizmete/diske yazan kod eklemeyin. Motorun güvenlik katmanı: [docs/GUVENLIK.md](docs/GUVENLIK.md).
2. **Testler gerçek sisteme yazmaz.** Sahte sistem kullanın (`tests/fake_system.py`). Test etmediğiniz şeyi "test edildi"
   diye yazmayın; doğrulanamayanı PR açıklamasında söyleyin.
3. **Yeni ayar eklerken kanıt gerekir:** ayarın ne yaptığı, artısı/eksisi, riski ve **birincil kaynak** (Microsoft/üretici
   belgesi ya da ölçüm). Forum düzeyindeki iddialar yalnızca "tartışmalı/placebo" olarak etiketlenebilir. Katalog
   `data/islemler.json` içindedir; `tools/convert_tweaks.py` ile `data/tweaks_app.json` üretilir
   ([docs/islem_semasi.md](docs/islem_semasi.md)).
4. **Telemetri, kişisel veri toplama ve yeni ağ bağlantısı yok.** Uygulama yalnızca kullanıcının bir kez sorulan soruda "evet" dediği güncelleme
   denetiminde (GitHub) internete bağlanır; `tests/test_gizlilik.py` bunu denetler.
5. **Yasaklı işlemler:** Windows Defender'ı tamamen kapatmak, anti-cheat süreçlerine dokunmak, "bellek temizleyici" gibi
   placebo/zararlı işlemler, gerçek zamanlı öncelik. Bunları eklemeyin.
6. **Telifli içerik eklemeyin:** oyun kapak görselleri, mağaza görselleri, marka logoları, indirilmiş üçüncü taraf
   simgeler ve başkasının metni depoya girmez; gerekirse çalışma anında alınır. Yeni üçüncü taraf bileşenin lisansını
   kontrol edin ve [THIRD-PARTY-NOTICES.txt](THIRD-PARTY-NOTICES.txt) dosyasına ekleyin.
7. **Metinler iki dilli:** `lang/tr.json` ve `lang/en.json` aynı anahtarlara sahip olmalı. Anahtar eklemek/silmek için
   `tools/dil_anahtar.py` kullanın ([docs/DIL_EKLEME.md](docs/DIL_EKLEME.md)). Ekrandaki metinler `t()` ile çevrilir.
8. **Küçük ve odaklı değişiklik:** bir PR bir konuyu çözsün; ilgisiz yeniden biçimlendirme yapmayın. Kodun çevresindeki
   üsluba (Türkçe iç kimlikler, kısa yorumlar) uyun.
9. Kullanıcıya görünen davranışı değiştiriyorsanız ilgili belgeyi (README, docs/) güncelleyin.

## Çekme isteği (PR) kontrol listesi

- [ ] Testler geçiyor (`unittest discover`), `python -m app --kontrol` temiz.
- [ ] Yeni/değişen davranış için test eklendi.
- [ ] Sistem değişikliği yedek + geri alma yolundan geçiyor.
- [ ] Yeni metinler tr ve en'de var.
- [ ] Telifli içerik, gizli anahtar ya da kişisel veri eklenmedi.
- [ ] Doğrulanamayan noktalar açıklamada yazıldı.

---

## English (short)

Open an issue first for anything big. Do not report vulnerabilities publicly (see [SECURITY.md](SECURITY.md)). Python 3.12 on
Windows; run `unittest discover -s tests -t .` with `QT_QPA_PLATFORM=offscreen` (tests never write real system settings).
Every system change must go through the engine (backup, verification, undo). New tweaks need an evidence label and a
primary source. No telemetry, no new network access, no copyrighted assets (game covers, store art, brand logos). Keep
`lang/tr.json` and `lang/en.json` in sync (`tools/dil_anahtar.py`). By contributing you agree to the MIT license.
