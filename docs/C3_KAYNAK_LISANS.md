# C3 — Kaynak lisans ve bağlantı değerlendirmesi

Tarih: 2026-10-27. Hukuki tavsiye değildir; **Kubilay hukuki olarak teyit etsin.**
Erişim notu: sitelerin kullanım koşulları sayfaları tek tek okunmadı; bilgiler ana sayfa/altbilgi ve GitHub API'sinden alındı.

| Kaynak | Lisans durumu | Bağlantı yeterli mi | Erişim |
|---|---|---|---|
| beforeiplay.com | CC BY-SA 4.0 (altbilgide yazıyor, "aksi belirtilmedikçe"); Miraheze barındırıyor | Evet; alıntı/uyarlama için atıf + aynı lisans gerekir, bağlantı serbest | Tam |
| BoringBoredom/PC-Optimization-Hub | Lisans dosyası yok (GitHub API license=null, LICENSE raw adresi 404) = varsayılan olarak tüm hakları saklı | Yalnızca bağlantı + kendi özetimiz; kopya yok | Tam |
| howmanyfps.com | Lisans/koşullar okunamadı (Cloudflare 403 engeli); yalnızca arama özetinden tanım görüldü | Bağlantı güvenli; koşullar doğrulanmadı | Kısmi (403) |
| framesynclabs.com | "Copyright 2026 FrameSync Labs. All rights reserved." | Yalnızca bağlantı; ücretli hizmet, rakip/reklam algısı riski | Tam (Kullanım Koşulları okunmadı) |

## 1. beforeiplay.com
- Lisans: altbilgi CC BY-SA 4.0 diyor (HTML'de de doğrulandı). Ticari kullanıma izin verir ama atıf ve aynı lisansla paylaşım ister; kodumuza/metnimize kopyalarsak türev lisans sorunu doğar. Bağlantı + kendi cümlelerimiz sorunsuz.
- ÖNEMLİ: Site bir PC optimizasyon wiki'si DEĞİL; "oynamadan önce bilmen gerekenler" türünde (spoiler gizleyen) oyun bilgi wiki'si. Backlog'daki beklentiyle uyuşmuyor; Kubilay başka bir site/ad kastetmiş olabilir. Bu kaynağın ayar listemize katkısı yok.
- İçerik: oyun sayfaları, spoiler biçimlendirme rehberi. Güvenilirlik: topluluk/editör içeriği, ölçüm değil.
- Önerilen metin (TR): "Oyuna başlamadan önce bilinmesi gerekenler için topluluk wiki'si (Before I Play)." — yalnızca oyun sayfasında anlamlıysa.

## 2. BoringBoredom/PC-Optimization-Hub
- Lisans: bulunamadı (depo API'si null). Açık izin olmadığı için kopyalama yapılmaz; bağlantı ve özgün özet sorun çıkarmaz (olgular/fikirler telif konusu değil, metin öyle).
- Kapsam: gecikme ve yenileme hızı gerekçeleri; FrameView/PresentMon ile ölçüm; kablolama, USB denetleyici yerleşimi, topraklama/EMI; fare (kablolu/kablosuz, DPI, polling); monitör (VRR/V-Sync/FPS sınırı, görüntü işleme gecikmesi); BIOS/saat/sıcaklık; Windows sadeleştirme, özel ISO; donanım öneri listeleri.
- Güvenilirlik: ölçüm odaklı yöntem, ama sayfada özgün veri yok; üçüncü taraf test/çalışmalara atıf veriyor. Yöntem iyi, bireysel iddialar tek tek doğrulanmalı. Depo 2026-10-09'da güncellenmiş, ~1285 yıldız.
- Bizde karşılığı olmayan (kaba arama, ayar adlarına bakıldı, tam eşleme yapılmadı) konular: (1) fiziksel kurulum/USB denetleyici-port yerleşimi rehberi, (2) XMP/EXPO ve BIOS RAM ayarı yönlendirmesi, (3) kare sınırlama + VRR + V-Sync birlikte kurulum rehberi, (4) PresentMon/FrameView ile önce-sonra ölçüm yönlendirmesi, (5) kablosuz fare/polling önerisi.
- Önerilen metin (TR): "Gecikme ve kare süresi ölçümüne dayalı kapsamlı bir topluluk rehberi (BoringBoredom PC-Optimization-Hub)."

## 3. howmanyfps.com
- Lisans: bulunamadı/okunamadı (siteye doğrudan erişimde 403). Arama özeti: makine öğrenmesi + gerçek benchmark verisiyle "bu PC kaç FPS verir" tahmini; ücretsiz masaüstü uygulaması ile kare kare FPS/CPU/GPU/sıcaklık kaydı; FPS ve darboğaz hesaplayıcı, PC kurucu, topluluk benchmark'ları, donanım mağazası, istek üzerine geliştirici API'si.
- Güvenilirlik: kullanıcı verisine dayalı ama tahminler model çıktısı; doğrulanmadı. Tercih "sonuçlar mantıklıysa" koşulu karşılanmadı (denenmedi).
- Bizde karşılığı olmayan: darboğaz (CPU/GPU) analizi, oyun bazlı FPS tahmini. (Kendi telemetri yasağımız nedeniyle veri paylaşımı/API entegrasyonu yapılmaz; yalnızca bağlantı.)
- Önerilen metin (TR): "Donanımına göre oyun FPS tahmini ve darboğaz hesaplama için harici site (howmanyfps.com)."

## 4. framesynclabs.com
- Lisans: tüm hakları saklı. Uzaktan, elle yapılan ücretli optimizasyon hizmeti (€5-€179 planlar, TeamViewer oturumu, %19-72 FPS artışı iddiası). Sonuçlar kendi pazarlama iddiası, bağımsız doğrulanmamış.
- Kapsam: BIOS, Windows, ağ, giriş/kare ritmi ayarı, 26+ rekabetçi oyun, anticheat uyumu iddiası.
- Öneri: uygulamada yer vermemek veya yalnızca tarafsız "ücretli harici hizmet" notuyla anmak; ticari rakip/yönlendirme algısı ve doğrulanmamış iddia riski var. Kopya yok.
- Önerilen metin (TR, kullanılacaksa): "Ücretli, uzaktan elle optimizasyon hizmeti veren harici bir firma (doğrulanmamış iddialar içerir)."

## Doğrulanmamış noktalar
- Hiçbir sitenin ayrı Kullanım Koşulları sayfası okunmadı.
- howmanyfps içerik/lisansı doğrudan görülmedi.
- "Bizde yok" listesi data/tweaks_app.json üzerinde anahtar kelime sayımıyla çıkarıldı (dosya yapısı 5 üst anahtarlı; tam id eşlemesi yapılmadı).
- **Kubilay hukuki olarak teyit etsin.**
