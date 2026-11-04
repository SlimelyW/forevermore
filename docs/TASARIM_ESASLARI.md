# Forevermore tasarım esasları (uygulama + site ortak temeli)

Karar (29 Ekim 2026, Kubilay): gerçek cam efekti (DWM Mica/Acrylic, bulanıklık) YOK. "Saydamımsı" görünüm, katmanlı düz
renk tonlarıyla yapılır; böylece performans maliyeti sıfırdır. Uygulama ve site aynı jetonları kullanır, birebir aynı değildir.

Hedef kullanıcı: DEHB, disleksi ve düzen/denge hassasiyeti olanlar dahil herkes. İlk bakışta tutmalı, çaba az olmalı.

## 1. Renk (yeşil ana, mor yalnızca vurgu)

| Rol | Koyu | Açık | Kullanım |
|---|---|---|---|
| Zemin | `#0F1420` | `#F4F6F9` | sayfa |
| Yan menü | `#0B101A` | `#E9EDF3` | menü |
| Kart | `#171E2E` | `#FFFFFF` | satır, kart |
| Kart (üstte) | `#1D2638` | `#F3F6FA` | hover, açılır liste |
| Yeşil ton | `#133A33` | `#DCF3EA` | yeşil yıkama: iyi durum, seçili satır |
| Mor ton | `#211F45` | `#E8E5FB` | mor yıkama: öneri, Pro, odak halkası |
| Çizgi | `#263046` | `#DDE3EC` | kart kenarı |
| Üst ışık | `#FFFFFF` %6 | `#FFFFFF` %70 | kartın üst kenarında 1 px (saydamımsı his) |
| Yeşil (ana) | `#2FD3A1` | `#0B7A5A` | ana düğme, açık anahtar, iyi |
| Mor (vurgu) | `#8B7CFF` | `#6A5AF0` | odak halkası, "Öneri" rozeti, Pro |
| Kehribar | `#F2B84B` | `#B7791F` | dikkat |
| Kırmızı | `#F0605D` | `#C93C3A` | sorun |

Kurallar: bir ekranda tek ana renk (yeşil); mor en fazla 2 yerde; durum rengi asla tek başına anlam taşımaz (renk + simge + metin).
Düz metin tam mürekkep renginde (`#E9EEF8` / `#141A26`), saf beyaz/siyah yok (göz yorgunluğu).

## 2. Saydamımsı yüzey (performanslı)

- Bulanıklık, gerçek saydamlık, DWM efekti, gölge yok.
- Katman = zeminden bir ton açık düz renk + kartın üst kenarında 1 px `Üst ışık` çizgisi + çok hafif yeşil/mor yıkama (kahraman kart).
- Qt'de yalnızca stil dosyası (`theme.py`); özel çizim yok. Hover ve seçili durumlar da düz renk geçişi.

## 3. Yazı ve okunabilirlik (disleksi dahil)

- Varsayılan: Segoe UI Variable; gövde 13 px, satır aralığı rahat, sola hizalı, satır uzunluğu en çok ~70 karakter.
- Boyut basamakları: 12 · 13 · 15 · 18 · 26 · 34 px (altı basamak, daha fazlası yok). Büyük sayı 34 px, hero başlığı 26 px.
- Yasak: italik gövde, tamamı büyük harf etiket, iki yana yaslı metin, uzun kalın paragraf.
- **Okunabilir yazı** modu (Ayarlar): Verdana, +1 px, harf aralığı +0,3 px, satır aralığı 1,5. Sistem yazı tipi; font gömülmez.
- Site: aynı mod bir düğmeyle (`data-okunabilir`), `prefers-reduced-motion` ve `prefers-contrast` desteklenir.

## 4. Izgara, hizalama, denge (OKB dostu)

- 8 px ızgara: aralıklar yalnızca 4 · 8 · 12 · 16 · 24 · 32 px.
- Kart iç boşluğu 24 × 20 px; kartlar arası 12 px; sayfa kenarı sol ve sağda eşit.
- Aynı türdeki öğeler aynı yükseklik: ayar satırı 64 px, menü satırı 36 px, düğme 36 px.
- Sütunlar hizalı: anahtar her satırda aynı sağ kenarda.

## 5. Simgeler

- Tek aile (Segoe Fluent Icons), tek boyut: 20 px, 36 px'lik kutuda ortalı.
- Simge kutuları arasında en az 12 px; bir satırda en çok 1 simge kutusu + 1 eylem simgesi.
- Renk: soluk gri; seçili/etkin olanda yeşil. Süs için çok renkli simge yok.

## 6. Hareket (akıcı ve hızlı)

- Hover/basma: 120 ms, sayfa geçişi: 160 ms solma, ease-out. 200 ms'yi aşan hareket yok.
- Yalnızca opaklık ve konum; aynı anda en çok 3 öğe hareket eder.
- Onay anı (ayar uygulandı): tek bir yeşil işaret + sayı, 400 ms; başka kutlama yok.
- "Hareketi azalt" açıkken (ve pencere etkin değilken) tüm süreler 0.

## 7. Performans bütçesi (uygulama asla yavaşlamamalı)

- Sayfa geçişi ≤ 20 ms (ekran dışı ölçüm `tests.arayuz_goruntu` çıktısı; bugün 8–16 ms).
- Yeni özel çizim yok (yalnızca mevcut canlı grafikler); arka planda ek zamanlayıcı yok.
- Animasyonlar yalnızca kullanıcı eylemi sırasında çalışır, boşta CPU 0.

## 8. Toplu "Önerilenleri aç" akışı (DEHB: az çaba)

1. Düğmeye basınca doğrudan uygulanmaz: **önizleme penceresi** açılır.
2. Pencere, her ayar için şunu listeler: ad, `Kapalı → Açık` (ya da tersi), etki ve risk rozeti. Gruplar: "Açılacaklar", "Kapatılacaklar", "Değişmeyecekler (zaten böyle)".
3. Kullanıcı tek tek onay kutusunu kaldırabilir; "Uygula" ve "Vazgeç" düğmeleri vardır.
4. Onaylanınca yalnızca işaretli ayarlar, her zamanki yoldan (geri yükleme noktası, yedek, geri alma) uygulanır; bitince "N ayar uygulandı, Değişiklikler sayfasından geri alınabilir".
5. Riskli/anti-cheat uyarılı ayarlar toplu pakete girmez, listede ayrı "Elle seç" notuyla görünür.

## 9. Site ile ilişki

- Aynı jeton adları ve değerler `site/style.css`'te CSS değişkeni olur. Site: cam/bulanıklık yok, aynı katmanlı düz renk tekniği.
- Fark: sitede büyük tipografi, tek "canlı şey" (bir ayarı aç/kapat deneyip placebo mu gerçek mi gören mini kart), geniş boşluk.
- Uygulamada: yoğun, işlevsel, hızlı.

## 10. Erişilebilirlik tabanı

- Odak halkası her etkileşimli öğede görünür (mor, 2 px).
- Metin/zemin karşıtlığı en az AA (4.5:1). Hesaplandı (29 Ekim): koyu temada soluk metin/kart 5,75, metin/kart 14,3, mor/kart 5,1, kırmızı/kart 5,2, kehribar/kart 9,3, koyu yazı/yeşil düğme 8,2; açık temada yeşil/beyaz 5,3 (ilk seçilen `#0E8F6A` 4,07 ile AA'yı geçemediği için koyulaştırıldı).
- Her anlam (iyi/dikkat/sorun) simge + metin içerir.
- Klavyeyle her şey erişilebilir; Ctrl+K arama zaten var.

## 11. Metin: slogan ve tekrar yasağı (29 Ekim 2026)
Kaynak: "her menüye tagline", "aynı şeyi dört kez göster" şikâyetleri. Uygulama ve site metni için geçerli.
- Başlığın altına alt yazı YALNIZCA başlıkta olmayan bir bilgi taşıyorsa konur (sayı, sınır, koşul, ne yapacağı). "Hakkında", "Tara ve açıkla" gibi başlığı tekrarlayan ya da duygu yaratmaya çalışan satır silinir.
- Aynı bilgi sayfada bir kez yazılır; başka yerde gerekiyorsa o yere bağlantı verilir. Aynı cümlenin kopyası olmaz.
- Soyut vaat yok ("kendi dünyan", "her şey yolunda", "tam kontrol"); her cümle bir ad, sayı, eylem veya sınır içerir.
- Başlıklar eylemi veya konuyu söyler ("Geri alma", "Fiyat"); ruh hali söylemez.
- Boş durum ve hata metninde ne olduğunu ve ne yapılacağını yaz; teselli cümlesi yazma.
- Yeni metin eklerken kontrol: başlığı ve alt yazıyı yan yana oku; ikisi aynı şeyi diyorsa alt yazıyı sil.

## 12. Yoğunluk: "sade liste" (yön A, 30 Ekim 2026)
Geri bildirim: "çok boş ve aynı anda dolu". Sebep: her ayar ayrı çerçeveli kart (içi boş, toplamı kalabalık), Özet'te aynı ağırlıkta 10 büyük rakam, menüde her satırda "3 / 15" rozeti.
- Ayar satırları tek kartta (`widgets.RowList`, QSS `#List`), aralarında 1 px çizgi (`#Divider`); satırın kendi çerçevesi yok (`#Card[inlist]`).
- Özet: kahraman kart tek odak; dört istatistik tek sıra küçük çip (`#StatNum` 20 px, tıklanır); "N uyarı var" tekrarı kaldırıldı; canlı kutular alçak (değer + grafik yan yana, `#LiveNum` 22 px).
- Kenar menü rozeti yalnızca o kategoride önerilen ama açık olmayan ayar sayısı.
- Renk, yazı ve hareket jetonları değişmedi (theme.py, motion.py).

## 13. Hız öncelikli his, tek jeton seti (30 Ekim 2026; C bölümü yeniden yazıldı)
- **Eylem önce, animasyon sonra:** hiçbir animasyon işi bekletmez. Toggle iyimser: tıklanan durum anında görünür
  ("uygulanıyor", soluklaşmaz, tıklanmaz), onay reddedilir veya işlem başarısız olursa gerçek durum okununca geri döner.
  Onay penceresi açan yönetici kartları (ses aygıtı, MSI, AMD) "önce onay" düzenini korur: pencere zaten anında geri bildirimdir.
- **Hareket jetonları (`motion.py`):** basma 90, hover 120 (çıkış 90), toggle 160 (hafif yay, OutBack 0.9), bölüm açılması
  160 / kapanması 100, sayfa 180 ms; hepsi < 300 ms, çıkış girişten kısa. Giriş eğrisi OutCubic; doğrusal ve sert ease-in yok.
- **Yalnızca opaklık ve çizim konumu canlandırılır:** yükseklik animasyonu kaldırıldı (bölüm anında yerleşir, içerik solarak gelir);
  opaklık efekti iş bitince kaldırılır. Sayfa solması 0,35'ten başlar (geçişte boş ekran anı yok).
- **Mikro etkileşim:** düğmeler basılıyken %97 ölçekle çizilir (`widgets.PressButton`, yerleşim değişmez); basma/hover/odak/
  devre dışı durumları QSS'te düğme, açılır liste ve metin kutusunda tanımlı; toggle'da klavye odağı mor halka.
- **Ölçü sistemi (`theme.py`):** `SPACE` 4'ün katları, `RADIUS` sm 6 / md 8 / lg 12 (kontroller md, kart/şerit lg, rozet sm);
  kalan sabit yarıçaplar geometrik (yuvarlak düğme, ince çubuk). Değişen rakamlar tabular (`theme.tabular`, tnum).
- **Yükleniyor:** ilk açılışta (önbellek yok) Özet iskeleti (`widgets.skeleton`, parıltı döngüsü yok); uzun kaldırıcı listesi
  40 satırlık parçalarla, aşağı kaydırdıkça çizilir. Arka planda/küçültülünce animasyon yok; Windows "Animasyon efektleri" kapalıysa da.
- **Ölçüm (ekran dışı, önizleme, sıralı; önce → sonra):** açılış 0,47 → 0,40 sn; RAM 177 → 165 MB; boşta CPU %0,25 → %0,26
  (gürültü); tüm durumlar hazır 10,7 → 9,8 sn; toggle görsel tepkisi 7,8 → 0,6 ms (sahte sistem; gerçekte eski sürüm yazma
  bitene kadar bekliyordu); sayfa geçişleri: Özet 17 → 10, Sistem 32 → 20, Ekran Kartı 50 → 24, Oyunlar 55 → 23,
  Önce/Sonra 60 → 29, Kaldırıcı 56 → 19, Değişiklikler 39 → 17, Profiller 28 → 16 ms. Yeni bağımlılık yok; paket yeniden derlenmedi.
