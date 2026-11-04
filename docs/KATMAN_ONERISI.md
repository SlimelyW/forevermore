# Ücretsiz / Pro katman önerisi (BACKLOG E1b) — UYGULANDI (sınır 20 yerine 15)

Tarih: 2026-10-28. **Uygulandı:** sınır 15, Önce/Sonra ücretsiz (aşağıdaki "Şu an" bölümü UYGULAMADAN ÖNCEKİ durumu anlatır). Fiyat: ₺150 / ay.

## Uygulamadan önceki durum (kod: `app/core/licensing.py:46-47`)
- Ücretsiz: tarama, tüm ayar sayfaları, aynı anda **en fazla 5** uygulama değişikliği (`FREE_LIMIT = 5`).
- Pro: sınırsız değişiklik + kilitli sayfalar `PRO_PAGES = ("profiller", "oyunlar", "olcum")` (Profiller, Oyunlar, Önce/Sonra).
- Boost sayfası, Monitör yöneticisi, Ekran yerleşimi ve donanıma özel öneri (D1) ücretsiz tarafta (sayfa kilidi yok).
- Katman ayarları zaten tek yerde (`licensing.py`); ayrı bir yapılandırma dosyası gerekmiyor.

## Öneri (cömert ücretsiz katman, CLAUDE.md kararına uygun)
| Özellik | Ücretsiz | Pro | Neden |
|---|---|---|---|
| Tarama, bulgular, bilgi kartları | evet | evet | Güven kazandırır, ayarı seçtiren kısım. |
| Geri yükleme noktası, geri alma, yedek | evet | evet | Güvenlik özelliği paywall arkasında olmamalı. |
| Değişiklik sınırı | **20** (şimdi 5) | sınırsız | 5 çok az, ilk izlenimi bozar; 20 çoğu kullanıcıya yeter, güçlü kullanıcı Pro'ya geçer. |
| Önce / Sonra ölçümü | **evet** (şimdi Pro) | evet | "Dürüst etki" ürünün ayırt edici yanı; ücretsiz olması güveni artırır. |
| Boost (RAM/süreç kapatma) | evet | evet | Sayfa zaten açık; değişiklik yok. |
| Monitör yöneticisi, ekran yerleşimi | evet | evet | Zaten açık; Pro'ya taşımak mevcut kullanıcıdan özellik almak olur. |
| Profiller (hazır paketler) | hayır | evet | Pro değeri: tek tıkla çok ayar. |
| Oyunlar (oyun başına ayar, otomatik Boost) | hayır | evet | Pro değeri. |
| Donanıma özel öneri (D1) | ilk 3 öneri | tamamı | Ücretsizde tat, Pro'da tam liste. **Kodda henüz bu ayrım yok; eklenecekse ayrı iş.** |
| Otomatik güncellenen ayar veritabanı | — | — | Uygulamada henüz yok (güncelleme mekanizması yok, bkz. SECURITY.md 8); vaat edilmemeli. |
| Destek | — | öncelikli | Süreç tanımlı değil; yalnızca vaat edecekseniz. |

## Kod değişikliği (onaylanırsa, küçük)
1. `FREE_LIMIT = 5` → `20`; `PRO_PAGES` içinden `"olcum"` çıkar (`licensing.py`).
2. Lisans sayfası ve site metinlerinde "5 değişiklik" / "Önce-Sonra Pro" geçen yerleri güncelle (`site/`, `lang/*.json`,
   `docs/LISANS_SISTEMI.md`); ilgili testler (`tests/test_lisans.py`) yeni sınıra göre.
3. D1'de ücretsiz/Pro ayrımı istenirse ayrı iş olarak planlanır.

## Karar bekleyenler
- Değişiklik sınırı: 20 mi, başka bir sayı mı, yoksa hiç sınır olmasın mı?
- Önce / Sonra ücretsiz olsun mu?
- D1 donanım önerisinde ücretsiz/Pro ayrımı yapılsın mı, hepsi ücretsiz mi?
- "Destek" ve "otomatik güncellenen veritabanı" Pro vaadi olarak yazılsın mı (şu an karşılığı yok)?
