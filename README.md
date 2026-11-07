# Forevermore

Oyuncular için Windows 10/11 ayar uygulaması: bilgisayarınızı tarar, her ayarın ne yaptığını artıları ve eksileriyle
anlatır, işe yaramayan (placebo) ve zararlı ayarları ayırır, uyguladığınız her değişikliği yedekleyip tek tıkla geri
alınabilir yapar. **Ücretsiz ve açık kaynaktır (MIT); Pro, hesap, reklam ve telemetri yoktur.**

*English: a Windows 10/11 settings app for gamers. It scans your PC, explains every setting with evidence labels,
separates placebo from real tweaks, and backs up each change so it can be undone with one click. Free and open source
(MIT); no accounts, no telemetry. See the [English section](#english) below.*

<!-- Ekran görüntüsü: docs/img/ozet.png dosyasını ekleyip aşağıdaki satırı açın.
![Forevermore özet ekranı](docs/img/ozet.png)
-->
> **Ekran görüntüsü buraya gelecek.**

## Ne yapar

- **Tarama ve PC Detayları:** donanımı, sürücüleri, güç planını, ekranı, fare/klavyeyi ve Windows durumunu okur (salt okunur).
- **~150 ayar, her birinde kanıt etiketi:** gerçek, kısmen, duruma bağlı, tartışmalı, placebo ya da zararlı; kaynak ve
  ölçüm notlarıyla. Riskli ayarlar iki ayrı uyarıyla sorulur.
- **Her değişiklik geri alınabilir:** değişiklikten önce yedek ve (gerekirse) sistem geri yükleme noktası; Değişiklikler
  sayfasından tek tıkla geri alma.
- **Ekran kartı ayarları:** NVIDIA (NVAPI) ve AMD (ADLX) sürücü ayarları, ölçekleme, G-SYNC / FreeSync.
- **Oyunlar:** oyun başına işlemci önceliği ve çekirdek seçimi, oyun açılınca otomatik uygulama, kapanınca geri alma;
  oyun içi ayar rehberleri. Anti-cheat süreçlerine dokunulmaz.
- **Hazır profiller, tek tuş Boost, uygulama kaldırıcı, ekran yerleşimi, Önce / Sonra ölçümü** (PresentMon ile FPS ve kare süresi).
- Türkçe ve İngilizce arayüz.

Tüm özellikler herkese açıktır; kilitli bölüm yoktur.

## Önemli: sistem ayarlarını değiştirir

Forevermore **kayıt defterini, servisleri, önyükleme ayarlarını ve sürücü ayarlarını değiştirebilir**. Bunu yapmadan önce:

- İlk değişiklikte **sistem geri yükleme noktası** almayı dener (Windows'ta Sistem Koruması kapalıysa açmayı önerir) ve
  değiştirdiği her değeri **yedekler**; Değişiklikler sayfasından geri alabilirsiniz.
- Ayar değiştirmek için **yönetici izni** ister. Vermezseniz salt okunur modda açılır (tarama ve rehberler çalışır).
  `--onizleme` ile hiçbir şey değiştirmeden deneyebilirsiniz.
- Bazı ayarlar güvenliği azaltır (ör. Spectre/Meltdown azaltımları) ya da yeniden başlatma gerektirir; bunlar uygulamada
  açıkça uyarılır. Neyi onayladığınızı okuyun. Yazılım **garantisiz, "olduğu gibi"** sunulur (bkz. [LICENSE](LICENSE)).
- Windows Defender'ı tamamen kapatma, anti-cheat'e müdahale ve "bellek temizleyici" gibi zararlı/placebo işlemler yoktur.

## Kurulum

1. [Releases](https://github.com/SlimelyW/forevermore/releases/latest) sayfasından `Forevermore.zip` dosyasını indirin.
2. Bir klasöre açın (klasörü olduğu gibi tutun; `_internal` programın parçasıdır) ve **Forevermore.exe**'yi çalıştırın.
3. Kaldırmak için önce uygulamada Ekstra ayarlar > "Kaldırmaya hazırla" ile değişiklikleri geri alın, sonra klasörü silin.

**İndirdiğin dosyayı doğrula (iki adım):**
1. PowerShell'de zip'in olduğu klasörde şunu yaz: `Get-FileHash .\Forevermore.zip -Algorithm SHA256`
2. Çıkan değeri Releases sayfasında yazan SHA-256 ile karşılaştır. Aynıysa dosya değişmemiştir; farklıysa çalıştırma, yeniden indir.

Windows uyarı gösterirse bu normaldir, kod imzalama sertifikamız henüz yok; dosyanın SHA-256'sını doğrulayabilirsin.
Python + PyInstaller ile paketlenen programlar küçük antivirüslerde yanlış alarm verebilir; kod açık olduğu için isterseniz kendiniz derleyebilirsiniz.

## Kaynaktan çalıştırma ve derleme

Gereksinim: Windows 10/11, Python 3.12.

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt

.venv\Scripts\python -m app                 # çalıştır (ayar yazmak için yönetici izni ister)
.venv\Scripts\python -m app --onizleme      # hiçbir ayarı değiştirmeden dene
.venv\Scripts\python -m app --kontrol       # pencere açmadan paket öz denetimi
```

Testler (pencere açmaz, gerçek sistem ayarı yazmaz):

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
.venv\Scripts\python -m unittest discover -s tests -t .
```

Paket derleme (`dist\Forevermore\` klasörü ve `dist\Forevermore.zip`):

```powershell
.\derle.bat
```

`derle.bat` ayrı bir derleme ortamı kurar (`requirements-derleme.txt`: PyInstaller), veriyi yeniden üretir, testleri
çalıştırır, derler ve paket kontrolü yapar. `tools\PresentMon-*.exe` varsa pakete eklenir (Önce / Sonra ölçümü için).
Resmî paketin güncelleme imzası yapımcının özel anahtarıyla atılır ve anahtar depoda yoktur; kendi derlemeniz imzasız
olur ve resmî güncelleme kanalıyla karışmaz.

Klasör yapısı: `app/core` (ayarlar, yollar, dil), `app/engine` (motor, yedek, işleyiciler, katalog), `app/scan`
(salt okunur tarama), `app/ui` (Qt arayüzü), `app/games`, `app/measure`; `data/` (ayar kataloğu), `lang/` (çeviriler),
`tests/`, `tools/`, `site/` (tanıtım sitesi), `docs/`.

## Gizlilik

Telemetri, reklam, analiz yok. Tarama sonuçları, ayarlar, yedekler ve günlükler yalnızca bilgisayarınızda
(`%LOCALAPPDATA%\Forevermore`, yedekler `%ProgramData%\Forevermore`) kalır. İnternete tek bağlandığı yer güncelleme denetimidir: size bir kez
sorulur, "evet" derseniz günde en çok bir kez çalışır (yalnızca GitHub, veri göndermez, indirilen paketin imzası doğrulanır);
"hayır" derseniz kendiliğinden hiç bağlanmaz. Ayarlar > Sistem'den değiştirilir.

## Katkı, güvenlik, destek

- Katkı vermek için [CONTRIBUTING.md](CONTRIBUTING.md)
- Güvenlik açığı bildirmek için [SECURITY.md](SECURITY.md) (açığı herkese açık konu olarak açmayın)
- Üçüncü taraf bileşenler: [THIRD-PARTY-NOTICES.txt](THIRD-PARTY-NOTICES.txt)
- Beğendiyseniz gönüllü olarak [bir kahve ısmarlayabilirsiniz](https://buymeacoffee.com/forevermore); zorunlu değildir,
  uygulama hiçbir yerde sormaz.

## Lisans

[MIT](LICENSE) © 2026 Kubilay Paşa. Üçüncü taraf bileşenler kendi lisanslarına tabidir.

---

<a id="english"></a>

## English

Forevermore is a free, open-source (MIT) Windows 10/11 settings app for gamers. It scans your PC, explains what each
setting does with its pros and cons and an evidence label (real / partial / situational / debated / placebo / harmful),
and backs up every change so it can be undone with one click. There is no Pro tier, no account and no telemetry; the app
connects to the internet only for the update check it asks you about once (GitHub only, sends nothing;
answer "No" and it never connects on its own; change it in Settings > System).

**Warning: it changes system settings** (registry, services, boot options, GPU driver settings). It tries to create a
system restore point before the first change, backs up every value it writes, and asks for administrator rights only to
apply changes (without them it opens read-only; `--onizleme` tries everything without changing anything). Some settings
reduce security or need a restart and say so before you confirm. The software is provided "as is", without warranty.

- **Install:** download `Forevermore.zip` from [Releases](https://github.com/SlimelyW/forevermore/releases/latest), extract it, run `Forevermore.exe`.
- **Check your download (two steps):** (1) In PowerShell, in the folder with the zip, run `Get-FileHash .\Forevermore.zip -Algorithm SHA256`. (2) Compare the result with the SHA-256 on the Releases page; if it differs, do not run it, download again. If Windows shows a warning, that is normal: we do not have a code-signing certificate yet, and you can verify the file's SHA-256.
- **Run from source:** Python 3.12, `py -3.12 -m venv .venv`, `.venv\Scripts\python -m pip install -r requirements.txt`, `.venv\Scripts\python -m app`.
- **Tests:** `$env:QT_QPA_PLATFORM="offscreen"; .venv\Scripts\python -m unittest discover -s tests -t .`
- **Build a package:** `derle.bat` (PyInstaller; unsigned unless you hold the maintainer's update-signing key).
- **Contribute / report a vulnerability:** [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md).
- **Support (optional):** [buymeacoffee.com/forevermore](https://buymeacoffee.com/forevermore).
- **License:** [MIT](LICENSE); third-party components in [THIRD-PARTY-NOTICES.txt](THIRD-PARTY-NOTICES.txt).
