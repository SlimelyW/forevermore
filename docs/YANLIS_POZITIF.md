# Antivirüs yanlış pozitifi ve SmartScreen (Faz 1.4, 31 Ekim 2026)

Durum: iki arkadaşta Defender ML tespiti ("…!ml") .exe'yi sildi, SmartScreen engelledi. Kullanıcıya antivirüsü
kapatmasını ÖNERMEYİN. Sitede "Neden uyarı veriyor?" metni site promptunda; burada yok.

## 1. Kod imzalama seçenekleri (Kubilay karar verecek, satın alma/başvuru yapılmadı)
Kaynak: araştırma ajanının birincil kaynak taraması (Microsoft Learn, satıcı sayfaları); "doğrulanamadı" yazanlara güvenmeyin.

| Seçenek | Türkiye'den bireysel | Maliyet | SmartScreen | Not |
|---|---|---|---|---|
| Microsoft Artifact Signing (eski adı Trusted Signing) | **Hayır**: bireyler yalnızca ABD/Kanada; kurum listesinde Türkiye yok | ~$9.99/ay (fiyat sayfasında doğrulanamadı) | Anında itibar yok, zamanla birikir | [quickstart](https://learn.microsoft.com/en-us/azure/artifact-signing/quickstart) |
| Certum Standard Code Signing (SimplySign bulut) | Muhtemelen evet: yasaklı ülke listesinde (RU, BY, KP, CU, SY) Türkiye yok; **resmî teyit yok** | certum.store "from $249"; bayilerde ~$99–180/yıl (doğrulanamadı) | Anında itibar yok | USB token gerekmez (bulut HSM) |
| SSL.com IV (bireysel) | Doğrulanamadı | Doğrulanamadı | Anında itibar yok | SSL.com'da OV kurumlar içindir, bireye IV |
| EV sertifika | Şirket gerekir | $400+/yıl | **Artık anında itibar vermiyor** (Microsoft, 2024) | [smartscreen-reputation](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation) |

- 1 Haziran 2023'ten beri özel anahtar donanım modülünde olmak zorunda (FIPS 140-2 L2 / CC EAL4+); bulut HSM kabul edilir.
- Öneri (benim görüşüm): Certum bireysel bulut sertifikası en ucuz ve Türkiye'den uygulanabilir görünen yol; başvurmadan önce
  Certum'a Türkiye'den bireysel başvuru ve kimlik doğrulama yöntemini e-postayla sorun. İmza tek başına ML tespitini
  kaldırmayabilir; ama aynı imzayla yayımlanan sürümler itibar biriktirir.
- Zaman damgası: DigiCert `http://timestamp.digicert.com` (bu bilgisayarda denendi, çalıştı), Microsoft `http://timestamp.acs.microsoft.com`
  (Artifact Signing ile). Certum `http://time.certum.pl` (resmî belgede doğrulanamadı).

### Altyapı (hazır)
- `tools/authenticode_imzala.ps1`: `signtool sign /fd SHA256 /tr <zaman damgası> /td SHA256`; sertifika deposu (parmak izi),
  Artifact Signing (`/dlib` + `/dmdf metadata.json`) veya yerel sınama `.pfx`. İmzadan sonra `Get-AuthenticodeSignature` ile
  durum ve zaman damgası geri okunur; damga yoksa hata verir.
- `tools/derle.ps1`: `FOREVERMORE_IMZA_PARMAKIZI` (ya da `FOREVERMORE_IMZA_METADATA` + `FOREVERMORE_IMZA_DLIB`) tanımlıysa
  .exe'yi PyInstaller'dan hemen sonra, paket özetinden (`tools/imzala.py`) ÖNCE imzalar; tanımlı değilse sarı uyarı.
- Denendi: openssl ile scratchpad'de üretilen kendinden imzalı sınama sertifikasıyla PyInstaller önyükleyicisinin kopyası
  imzalandı, DigiCert zaman damgası eklendi, durum `UnknownError` (sınama kökü güvenilir değil; beklenen). Gerçek sertifikayla
  ve gerçek `Forevermore.exe` ile DENENMEDİ.

## 2. Tetikleyicileri azaltma
| Konu | Durum |
|---|---|
| Paketleyici/gizleyici (UPX, VMProtect, Themida, crypter) | Kullanılmıyor; kullanılmayacak (AV riskini artırır). |
| `-ExecutionPolicy Bypass` | **Kaldırıldı** (`-Command` için etkisiz olduğu ölçüldü). Güncelleme betiği `RemoteSigned`. |
| `-EncodedCommand`, Base64, `iex` | Yok (test: `tests/test_gizlilik.py` TestAntivirusTriggers). |
| Gizli pencere | Alt süreçler `CREATE_NO_WINDOW` ile; `-WindowStyle Hidden` güncelleme betiğinden kaldırıldı. Kalan tek yer: Store geri yükleme (`wsreset -i`, kullanıcı başlatır). |
| PowerShell süreç sayısı | Açılışta 35 → 29 (eşzamanlı aynı sorgular tek süreç). Kalanlar: tarama (8), ayar durumları (~20). Sonraki adım: durum okumalarını tek PowerShell oturumunda toplamak veya kayıt defteri/WMI ile yerel okumak (BACKLOG'a). |
| Dosya indirip çalıştırma | Yalnızca uygulama güncellemesi: varsayılan KAPALI, yalnızca GitHub, imza doğrulamalı (`app/core/guncelleme.py`). Gerekçeli; kalır. |
| Kendini değiştirme | Aynı güncelleme: imzalı yeni klasörle değiştirme. Gerekçeli. |
| Kayıt defteriyle kalıcılık | Yok. "Windows'la başlat" isteğe bağlı zamanlanmış görev (`app/core/autostart.py`); varsayılan kapalı. |
| Defender ayarları | SYS-017 gerçek zamanlı koruma anahtarı (kullanıcı isteğiyle eklendi, CLAUDE.md). **En güçlü ML tetikleyicisi adayı** (`Set-MpPreference -DisableRealtimeMonitoring` metni pakette). Kaldırmak/rehber kartına çevirmek Kubilay'ın kararı. |
| Sürüm bilgisi + manifest | `build/surum_bilgisi.txt` ve `build/forevermore.spec` var; bu oturumda `build/` okuma izni olmadığı için **denetlenemedi**. |
| Tekrarlanabilir derleme | `PYTHONHASHSEED=0` + `SOURCE_DATE_EPOCH` (son commit) `derle.ps1`'de; paket sürümleri `==` ile sabit. Aynı çıktı DENENMEDİ (iki derleme karşılaştırılmadı). |

### Kurulum paketi değerlendirmesi (uygulanmadı)
- **Inno Setup (önerilen):** ücretsiz, onedir klasörünü olduğu gibi kurar (Qt LGPL düzeni bozulmaz), Program Files + kaldırma kaydı;
  kurulum dosyası da imzalanmalı. Program Files'a kurulunca güncelleme değişimi yönetici ister (uygulama zaten yönetici çalışıyor).
- **MSIX: uygun değil.** Paketli uygulamaların HKCU ve dosya yazmaları sanallaştırılır; ayarlar gerçek kayıt defterine yazılmaz.
  İmzasız kurulamaz. (Belgeden değil, bilgiye dayalı; denenmedi.)
- **NSIS:** ücretsiz; kötü amaçlı yükleyicilerde sık görüldüğü için ML tespitine daha açık olduğu söylenir (anekdot, doğrulanmadı).
- Karar: sertifika alınınca Inno Setup ile imzalı kurulum + imzalı .exe. Zip de kalabilir.

## 3. Yerelde ölçüm (temiz sanal makine)
1. Güncel Windows 10 22H2 ve 11 sanal makinesi; Defender varsayılan (gerçek zamanlı + bulut koruması + otomatik örnek gönderimi açık).
   Gerçek kullanıcıya benzesin diye zip'i tarayıcıyla indirin (Mark of the Web).
2. Yönetici PowerShell: `powershell -NoProfile -File tools\defender_tara.ps1 -Yol <zip veya klasör> -ImzaGuncelleme`
   (Start-MpScan + Get-MpThreatDetection; tespit adını ve Defender imza sürümünü `<yol>.defender.json`'a yazar).
3. Zip'i açıp `Forevermore.exe`'yi çalıştırın (ML çoğu zaman çalıştırma anında karar verir); `Get-MpThreatDetection` ile tekrar bakın.
4. Her değişiklikten (imza, kurulum paketi, Defender anahtarının kaldırılması…) sonra aynı adımlar; tabloya yazın.
- Bu oturumda YAPILMADI: sanal makine yok, `dist/` erişimi yok, geliştirici bilgisayarında karantina riski var. Betik yalnızca
  sözdizimi denetiminden geçti.

## 4. Microsoft'a yanlış pozitif gönderimi
1. https://www.microsoft.com/en-us/wdsi/filesubmission → **Software developer** seçin (Microsoft hesabıyla oturum isteğe bağlı,
   ama durum takibi ve iletişim için önerilir).
2. Ürün: Microsoft Defender Antivirus (Windows); dosya ≤ 50 MB: zip 39.8 MB sınırın altında, değilse yalnızca `Forevermore.exe`.
3. Tespit adı (ör. `Trojan:Win32/Wacatac.B!ml`), tespit tarihi, Defender imza sürümü (`defender_tara.ps1` çıktısı).
4. Açıklama (İngilizce, ≤ 1900 karakter): ne olduğu (Windows ayar aracı, PyInstaller + Python, kapalı kaynak), neden PowerShell/
   kayıt defteri kullandığı, resmî indirme adresi, SHA256, imza durumu, iletişim e-postası.
5. Sonuç birkaç gün içinde gelir (öncelik "Medium" için süre garanti değil). "Incorrectly detected" sonucu gelirse tanım
   güncellemesini bekleyin; her yeni derleme yeni hash demektir, gerekirse yeniden gönderin.
6. Geliştirici SSS: https://learn.microsoft.com/en-us/defender-xdr/developer-faq

## 5. Sürüm başına kontrol listesi
Her yayın için bir satır ekleyin (derle.ps1 sonunda SHA256 yazılır; `.exe` SHA256'sı `Get-FileHash dist\Forevermore\Forevermore.exe`).

| Sürüm | Tarih | Zip SHA256 | Forevermore.exe SHA256 | Authenticode | Defender VM (W10 / W11) | VirusTotal | MS gönderim no / sonuç |
|---|---|---|---|---|---|---|---|
| 2.1.2 | 30.10.2026 | 53F2075F…454D (HANDOFF) | — | yok | denenmedi | 0/67 | — |
| | | | | | | | |

Kutular: ☐ Authenticode + zaman damgası geçerli (`Get-AuthenticodeSignature` = Valid) ☐ paket imzası "orijinal" (`--kontrol`)
☐ W10 VM taraması ☐ W11 VM taraması ☐ çalıştırma anında tespit yok ☐ VirusTotal (dış servise yükleme: Kubilay onayıyla)
☐ tespit varsa MS gönderimi yapıldı ve numarası yazıldı.
