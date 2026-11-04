# Zamanlayıcı çözünürlüğü ve bekleme listesi (Revizyon 2 Faz 5)

## Zamanlayıcı çözünürlüğü (Performans menüsü)

**Yöntem:** Uygulamanın kendi kodu (`app/engine/timer_resolution.py`); ISLC veya başka araç gömülmez.
`ntdll` içindeki `NtQueryTimerResolution` / `NtSetTimerResolution` çağrıları. Bu çağrılar belgelenmemiş
ama uzun süredir Windows'ta duruyor. Seçenekler: Windows'a bırak / 1 ms / 0,5 ms.

- Windows 10 2004'ten beri istek yalnızca isteyen süreci etkiler. Windows 11'de diğer programları
  (oyunları) da etkilemesi için `GlobalTimerResolutionRequests` değeri gerekir (İşlemci > CPU-009).
- İstek yalnızca uygulama açıkken geçerlidir; kapanınca Windows kendiliğinden bırakır. Kalıcı bir
  sistem değişikliği yoktur; bu yüzden yedek ve UAC gerekmez.
- Etki etiketi **belirsiz**: kare süresi tutarlılığına küçük etki bildirilir, geniş ölçüm yoktur.

**Bu bilgisayarda (23.10.2026):** Okuma çalışıyor: en kaba 15,625 ms, en ince 0,5 ms. Şu anki değer
başka bir program istediği için zaten 0,5 ms'ydi. 0,5 ms isteme ve bırakma hatasız çalıştı. Oyun
üzerindeki etkisi denenmedi.

## Önce / Sonra: Sleep(1) süresi

Sistem ölçümüne "Sleep(1) süresi" eklendi: `Sleep(1)` 200 kez çağrılır, gerçekte kaç ms sürdüğünün
ortalaması (ve p99'u) kaydedilir. Ölçüm **ayrı bir süreçte** yapılır (`--uyku-testi`), böylece
uygulamanın kendi isteği sonucu değiştirmez; çözünürlük istemeyen bir oyunun gördüğü değer ölçülür.
Bu bilgisayarda ortalama yaklaşık 1,14 ms, p99 yaklaşık 1,9 ms ölçüldü.

## Bekleme listesini (standby list) temizleme: eklenmedi

Araştırma sonucu (PLC-001'in kaynakları): Windows 10 1803 civarında bekleme listesinin boşaltılmaması
kaynaklı bir takılma hatası vardı ve o dönemde ISLC bazı sistemlerde gerçekten fayda sağladı. Güncel
Windows sürümlerinde bu sorun için tutarlı bir kanıt bulunamadı; Windows önbelleği gerektiğinde zaten
anında serbest bırakır. Bu yüzden sistem genelinde "bekleme listesini temizle" ayarı **eklenmedi**.

Not: Oyunlar menüsündeki "oyun başlarken bekleme belleğini temizle" seçeneği önceki revizyondan kalmadır,
varsayılan kapalıdır ve "durumsal, kullanmadan önce ölçün" etiketiyle durur. Faz 7'de (Oyunlar) yeniden
değerlendirilecek.
