# Kurulum ve çalıştırma (kod bilmeden)

Bu adımlar geliştirme sürecinde senin bilgisayarında taramayı denemen içindir.
Arkadaşların bunlara gerek duymayacak; onlara ADIM 5'te tek bir `.exe` vereceğiz.

## 1. Python 3.12'yi kur (bir kez)

Bilgisayarında Python 3.15 zaten var; 3.12'yi **yanına** kuruyoruz, ikisi birbirini bozmaz.

**Yol A — tek komut (önerilen):**

1. Başlat menüsüne `Terminal` yaz, aç.
2. Şunu yapıştırıp Enter'a bas:

   ```
   winget install --id Python.Python.3.12 -e
   ```

3. Bitince Terminal'i kapatıp yeniden aç.

**Yol B — elle:** python.org > Downloads > Windows > "Python 3.12.x — Windows installer (64-bit)"
indir, çalıştır, "Install Now" de. ("Add python.exe to PATH" kutusu gerekmez.)

**Kontrol:** Terminal'de şunu yaz, `Python 3.12.x` görmelisin:

```
py -3.12 --version
```

## 2. Terminal'i proje klasöründe aç

1. Dosya Gezgini'nde `Belgeler\pcoptimizer` klasörünü aç.
2. Üstteki adres çubuğuna tıkla, `powershell` yaz, Enter'a bas.
   Açılan pencere doğrudan bu klasörde çalışır.

## 2b. Arayüz kütüphanesini kur (bir kez)

```
py -3.12 -m pip install -r requirements.txt
```

## 2c. Uygulamayı aç

**Önce önizleme modunda dene** (yönetici izni istemez, HİÇBİR ayarı değiştirmez; düğmeler gri görünür):

```
py -3.12 -m app --onizleme
```

**Normal açılış** (ayarları değiştirebilmek için yönetici izni ister). Bunu yalnızca sanal makinede
veya geri yükleme noktası aldıktan sonra kendi bilgisayarında dene:

```
py -3.12 -m app
```

UAC penceresinde "Hayır" dersen uygulama salt okunur modda açılır.

## 2d. İsteğe bağlı araçlar (`tools` klasörü)

Uygulama bu araçları gömmez; istersen sen indirip proje klasöründeki (derlenmiş sürümde
programın yanındaki) `tools` klasörüne koyarsın:

| Dosya | Ne için | Lisans | Nereden |
|---|---|---|---|
| `PresentMon-...-x64.exe` (konsol sürümü) | Önce/Sonra sayfasında oyun FPS ölçümü | MIT (Intel) | github.com/GameTechDev/PresentMon > Releases |
| `nvidiaProfileInspector.exe` | Yalnızca NVAPI'ye erişilemezse NVIDIA ayarları için yedek yöntem | MIT | github.com/Orbmu2k/nvidiaProfileInspector > Releases |

`derle.bat` çalışırken `tools\PresentMon*.exe` varsa programın yanına kopyalanır.

Diğer komut satırı seçenekleri: `--kaldir` (kaldırmadan önce temizlik; `--tumunu-geri-al` ile
tüm değişiklikleri de geri alır), `--tepside` (pencere açmadan tepside başlar; "Windows'la başlat"
bunu kullanır), `--kontrol` (pencere açmadan paket kontrolü).

## 3. Kontrol testlerini çalıştır (ayar değiştirmez)

```
py -3.12 -m unittest tests.test_veri tests.test_gizlilik tests.test_tarama tests.test_motor tests.test_metinler tests.test_arayuz
```

Arayüz testleri. Ekranda hiçbir pencere açılmaz; ayarlar yalnızca bellekteki sahte bir Windows'a yazılır. İkinci komut her sayfanın görüntüsünü PNG olarak bir klasöre çizer ve klasörün yerini yazar:

```
py -3.12 -m unittest tests.test_arayuz
py -3.12 -m tests.arayuz_goruntu
```

Ayarların bu bilgisayardaki durumunu **salt okunur** görmek için (yazma girişimleri engellenir):

```
py -3.12 -m tests.durum_okuma
```

Sonda `OK` yazmalı. `FAILED` yazarsa çıktının tamamını bana gönder.

## 4. Sistem taramasını çalıştır (ayar değiştirmez)

```
py -3.12 -m app.scan --kaydet
```

- Rapor ekrana yazılır ve ayrıca dosyaya kaydedilir.
- Raporların klasörünü açmak için:

  ```
  explorer $env:LOCALAPPDATA\Forevermore\reports
  ```

**Tam tarama için yönetici olarak:** Başlat'a sağ tıkla > "Terminal (Yönetici)". Sonra:

```
cd $HOME\Documents\pcoptimizer
py -3.12 -m app.scan --kaydet
```

Yönetici izniyle disk sağlığı ayrıntıları (sıcaklık, aşınma), önyükleme ayarları ve bellek
sıkıştırma durumu da okunur. Bu yine **yalnızca okuma**dır.

## Bir şey ters giderse

- Log dosyası: `%LOCALAPPDATA%\Forevermore\logs\forevermore.log`
- Bu dosyada kişisel bilgi bulunmaz (kullanıcı adı, IP vb. otomatik temizlenir); bana gönderebilirsin.
