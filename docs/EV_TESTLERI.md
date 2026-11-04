# Evde yapılan yazma testleri — doğrulama kaydı

Kural: güvenlik/sistem ayarlarını (UAC, Defender, HVCI, kayıt defteri) kullanıcı uygulamadan kendisi
değiştirir; Claude yalnızca SALT OKUYARAK doğrular (`tests.durum_okuma`, kayıt defteri ve
`Get-MpComputerStatus` okuması, uygulamanın işlem geçmişi). Önce geri yükleme noktası alınır.

## 2026-10-23

Kullanıcı geri yükleme noktası aldı ve testleri yaptığını, sonucun iyi olduğunu bildirdi.

Okuyarak bulunanlar (testlerden sonra):

| Kontrol | Testten önce | Testten sonra |
|---|---|---|
| Tüm SWITCH ayarlarının durumu (`tests.durum_okuma`, 153 satır) | kayıt alındı | birebir aynı (fark yok) |
| UAC: ConsentPromptBehaviorAdmin / PromptOnSecureDesktop / EnableLUA | 5 / 1 / 1 | 5 / 1 / 1 |
| Defender: gerçek zamanlı koruma / Kurcalama koruması | Açık / Açık | Açık / Açık |

- Her şey testten önceki hâlinde: uygulanan değişiklikler geri alınmış görünüyor ya da hiç uygulanmamış.
- **Açık nokta:** `%LOCALAPPDATA%\Forevermore\backups\islem_gecmisi.jsonl` dosyasında bugüne ait kayıt yok
  (son kayıt 2026-10-22) ve `logs\forevermore.log` 08:16'dan beri boş. Uygulama bu Windows hesabıyla
  çalıştırılıp değişiklik yapsaydı burada iz kalırdı. Yani yazma/geri alma işlemlerinin uygulama üzerinden
  yapıldığı bu kayıtlarla **doğrulanamadı**. Testler başka bir hesapla (yönetici olarak başka kullanıcı)
  yapıldıysa kayıtlar o hesabın `%LOCALAPPDATA%` klasöründedir.
- Kullanıcı (aynı gün, sonradan): testleri bu Windows hesabıyla, uygulamayı yönetici olarak açıp ayarları
  aç/kapa yaparak yaptığını bildirdi. Yeniden bakıldı: bu hesabın `%LOCALAPPDATA%\Forevermore` ve eski
  `%LOCALAPPDATA%\PCOptimizer` klasörlerinde son normal açılış 2026-10-22 23:43; bugüne ait işlem kaydı yok.
  Bilgisayarda başka kullanıcı hesabı yok. Bu çelişki çözülmedi; ayarlar ise test öncesiyle aynı.
- Kesin doğrulama için bir sonraki denemede: ayarı uygulamadan aç → Claude okusun → "Eski haline getir"
  → Claude tekrar okusun.
