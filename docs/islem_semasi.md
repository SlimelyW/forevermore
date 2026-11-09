# `islem` şeması (ADIM 1)

Bu belge `data/islemler.json` dosyasında bir ayarın nasıl tanımlandığını anlatır.
Yeni bir ayar eklemek veya bir değeri düzeltmek istediğinde buraya bak.

## Dosyalar nasıl birbirine bağlı

```
tweaks.json  ─┐   (senin araştırma veritabanın: açıklamalar, artılar, eksiler...)
              ├─► tools/convert_tweaks.py ─► data/tweaks_app.json  (uygulama BUNU okur)
islemler.json ┘   (elle yazılan kesin işlemler)        └─► tools/donusum_raporu.md
```

- `tweaks.json` veya `islemler.json` değişince dönüştürücüyü yeniden çalıştır.
- `tweaks_app.json`'u elle düzenleme; her çalıştırmada yeniden yazılır.

## Üç sınıf

| Sınıf | Anlamı | Nasıl belirlenir |
|---|---|---|
| **SWITCH** | Uygulama okur, açar/kapatır | `islemler.json`'da `islem` tanımı varsa (riskli, placebo ve zararlı dahil) — yasaklı beş ayar hariç |
| **REHBER** | Kullanıcı elle yapar; adımlar + "Ayarı aç" düğmesi | NVIDIA/AMD paneli, BIOS, Ayarlar menüsü, üçüncü parti araç veya kesin işlemi tanımlanmamış her ayar |
| **BİLGİ** | Yalnızca açıklama + neden yapılamadığı (`bilgi.yapilamaz_nedeni`) | Yasaklı beş ayar, `islem` tanımı olmayan riskli/placebo/zararlı ayarlar (ör. ayrı program türleri) |

**Yasaklı beş ayar** (`schema.FORBIDDEN_IDS`, motor da engeller): Defender'ı kapatma,
Windows Update'i kalıcı kapatma, sayfa dosyasını kapatma, Realtime öncelik, agresif debloat.

**Onay seviyesi** (`onay_seviyesi`, dönüştürücü risk alanından üretir):

| Seviye | Risk | Arayüz |
|---|---|---|
| 0 | güvenli | onaysız |
| 1 | dikkatli | açarken tek onay penceresi |
| 2 | riskli | açarken **ve** kapatırken / eski haline getirirken iki ayrı uyarı ekranı |

`liste_yoneticisi`: `baslangic` / `msi` / `cihaz_guc` — ayar tek bir switch değil, uygulamanın
kendi listesinden öğe öğe yapılır (yöneticiler `Engine.apply_custom` ile yedekler). Kaynak
veritabanındaki `yonetici` alanı (yönetici izni gerekir) ile karıştırılmamalıdır.

`nvidia`: `{ayar, secenekler, onerilen}` — `liste_yoneticisi: "nvidia"` olan ayarın NVAPI seçenekleri.

`powercfg` adımında `kaynak: "dc"` pilde değerini yazar; laptopta arayüz bunu otomatik üretir.

`yalnizca_kapat: true`: veritabanı hedef değer vermediği veya ayar zararlı olduğu için
uygulama ayarı yalnızca kapatabilir (açıksa geri alır), açamaz.

`kontrol: "eylem"`: tek seferlik, geri alınamaz işlem (`eylemler: [{id, etiket, eylem}]`;
şimdilik `gecici_dosyalari_temizle`, `prefetch_temizle`). Değişiklik listesine değil işlem
geçmişine yazılır.

## "Açık" ne demek?

Switch **açık** = optimizasyon **uygulanmış**. Örneğin "Fare ivmesini kapat" switch'i
açıksa ivme kapalıdır. Ayar motoru:

1. Uygulamadan önce mevcut değeri **yedekler**.
2. Kapatırken önce **yedekteki** eski değeri geri yazar.
3. Yedek yoksa (ayar uygulama kurulmadan önce zaten uygulanmışsa) `kapali` değerini kullanır.

## Adım türleri

Bir switch'in `adimlar` listesindeki **tüm** adımlar birlikte uygulanır. Hepsi "açık"
durumdaysa switch açık görünür; bir kısmı açıksa "kısmen uygulanmış" görünür.

### `registry` — tek bir registry değeri

```json
{"tur": "registry", "kok": "HKCU", "yol": "Control Panel\\Mouse", "ad": "MouseSpeed",
 "veri_turu": "REG_SZ", "acik": "0", "kapali": "1", "yoksa": "1"}
```

| Alan | Açıklama |
|---|---|
| `kok` | `HKCU` (kullanıcı) veya `HKLM` (bilgisayar, yönetici gerekir) |
| `yol` | Kök olmadan yol. JSON'da `\` iki kez yazılır: `\\` |
| `veri_turu` | `REG_DWORD` (sayı) veya `REG_SZ` (metin) |
| `acik` | Açıkken yazılacak değer |
| `kapali` | Kapatınca yazılacak değer. `null` = değeri **sil** |
| `yoksa` | Değer hiç yoksa Windows'un varsaydığı değer (okurken kullanılır). Bilinmiyorsa `null` |

### `registry_bayrak` — "Ad=Değer;" listesindeki tek parça

`DirectXUserGlobalSettings` gibi değerler `VRROptimizeEnable=1;SwapEffectUpgradeEnable=1;`
biçimindedir. Bu tür yalnızca `anahtar` ile verilen parçayı değiştirir, diğerlerine dokunmaz.

### `registry_bit` — sayının tek bir biti

Yapışkan tuşlar gibi değerlerde birçok seçenek tek sayıda bit olarak saklanır. `maske`
hangi bitin değişeceğini söyler; diğer bitler korunur.

### `registry_anahtar` — anahtarın varlığı

Klasik sağ tık menüsü gibi, değerin değil anahtarın var olması önemliyse. `silinecek_yol`
kapatırken silinecek üst anahtardır; güvenlik için çok üst seviyedeki yollar reddedilir.

### `servis`

```json
{"tur": "servis", "ad": "SysMain",
 "acik":   {"baslangic": "Disabled",  "calisiyor": false},
 "kapali": {"baslangic": "Automatic", "calisiyor": true}}
```

### `powercfg` — etkin güç planındaki bir ayar (prizdeyken / AC)

`alt_grup` ve `ayar` GUID'dir (bu bilgisayarda `powercfg /aliases` ve `powercfg /qh` ile
doğrulandı). `kapali: "plan_varsayilani"` = planın kendi varsayılanına dön.

### `guc_plani` — etkin güç planını değiştir

### `yerlesik` — kod içinde tanımlı güvenli eylemler

Veri dosyasından **keyfi komut çalıştırılamaz**. Komut gerektiren işler kodda önceden yazılmış
eylemlerle yapılır ve veri dosyası yalnızca eylemin adını ve parametresini verir:

| Eylem | Ne yapar |
|---|---|
| `hazirda_bekletme` | `powercfg /hibernate on/off` |
| `bellek_sikistirma` | `Enable/Disable-MMAgent -MemoryCompression` |
| `windows_ozelligi` | Windows isteğe bağlı özelliklerini aç/kapat (yalnızca sistemde var olanlar) |
| `ag_gelismis_ozellik` | Ağ kartı gelişmiş özelliği (`Set-NetAdapterAdvancedProperty`) |
| `bcdedit` | Önyükleme ayarı `{eleman}`; `null`/`"*"` = sil (yönetici gerekir) |
| `tcp_otomatik_ayar` | TCP alma penceresi otomatik ayarı (`netsh int tcp set global autotuninglevel`) |
| `zamanlanmis_gorev` | Zamanlanmış görevi etkinleştir/devre dışı bırak (`{yol, ad}`) |
| `pnp_cihaz` | Aygıtı etkinleştir/devre dışı bırak (`{donanim_kimligi}`) |
| `nihai_performans_plani` | Nihai Performans planı: varsa onu, yoksa kopyasını oluşturup etkinleştirir; geri alırken önceki plana döner ve yalnızca kendi oluşturduğu kopyayı siler |
| `dns` | Ağ kartının DNS sunucuları (`{bagdastirici}`; seçim için) |
| `gorsel_efekt` | Performans Seçenekleri'ndeki bir görsel efekt (`{ad}`; SystemParametersInfo). `acik: false` = efekt kapalı |
| `guc_modu` | Windows 11 güç modu (`{kaynak}`: `ac`/`dc`; belgelenmemiş PowerSetActiveOverlayScheme) |
| `nvidia_drs` | NVIDIA genel profil ayarı (`{ayar}`: onaltılık kimlik, ör. `0x00CE2691`); değer `null` = sürücü varsayılanı |
| `ses_bicimi` | Ses çıkış cihazının varsayılan biçimi (yalnızca yöneticiden; değer `"48000/24"`) |
| `ekran_yenileme` | Monitörün yenileme hızı (`{aygit}`); `acik: "en_yuksek"` = bu çözünürlükte desteklenen en yüksek Hz. `kapali: null`: kapalı hedefi yoktur, yalnızca yedekten geri alınır |

Registry adımında `acik: {"hesapla": "toplam_ram_kb"}` hesaplanan değer kullanır;
`acik_kosulu` (`"var"` veya `{"kucuk": n}`) yalnızca `yalnizca_kapat` ayarlarında "açık"
durumunu tanımlar. Servis adımında `calisiyor: null` = çalışma durumuna dokunma; servis
bu bilgisayarda yoksa adım atlanır ("yok").

`sonrasinda` listesiyle ayar uygulandıktan sonra çalışacak güvenli eylemler verilebilir:
`fare_ayarlarini_yenile`, `klavye_ayarlarini_yenile` (oturum kapatmadan anında uygular),
`ses_servisini_yeniden_baslat` (ses geliştirmeleri için), `gezgin_yeniden_baslat_oner`.

Bu, güvenlik açısından önemlidir: biri `tweaks_app.json`'u değiştirse bile uygulama yönetici
yetkisiyle rastgele komut çalıştırmaz.

## Seçim (`kontrol: "secim"`)

Aç/kapa yerine değer seçilen ayarlar (fare hızı, klavye tekrar gecikmesi). Her `alan`
ya `secenekler` listesi ya da `aralik` (min–max) içerir; `onerilen` önerilen değerdir.

## Yer tutucular ve çözümleyiciler

Bilgisayara göre değişen değerler `{{ad}}` biçiminde yazılır ve `cozumleyici` çalışma anında
gerçek değeri bulur (`app/engine/resolvers.py`):

| Çözümleyici | Bulduğu yer tutucular | Bulamazsa |
|---|---|---|
| `ekranlar` | `{{ekran_aygiti}}`, `{{ekran_adi}}` (masaüstüne bağlı her monitör) | ayar gizlenir |
| `ag_arabirimleri` | `{{ag_arabirim_guid}}`, `{{ag_bagdastirici}}` (bağlı fiziksel ağ kartları) | ayar gizlenir |
| `ag_ozellik_destekleyen` | `{{ag_bagdastirici}}`, `{{ag_ozellik}}` (özelliği destekleyen kartlar) | ayar gizlenir |
| `amd_gpu_anahtarlari` | `{{amd_gpu_anahtari}}` (ör. `0000`) | ayar gizlenir |
| `ses_cikis_cihazlari` | `{{ses_cihazi}}`, `{{ses_cihazi_adi}}` | ayar gizlenir |

Birden fazla sonuç varsa (ör. 3 ses cihazı) işlem her biri için tekrarlanır.

## Uyumluluk

```json
"uyumluluk": {
  "windows": {"surumler": ["10", "11"], "min_build": {"10": 17134, "11": null}},
  "form": {"masaustu": "goster", "laptop": "uyar"},
  "gpu": ["NVIDIA"],
  "kosullar": [{"ad": "hdd_var"}, {"ad": "x3d_cift_ccd", "degil": true}]
}
```

- `form`: `goster` / `uyar` (ek uyarıyla göster) / `gizle`
- `gpu`: `null` = tüm ekran kartları
- `kosullar`: hepsi doğru olmalı. Koşul doğrulanamazsa (ör. okuma hatası) ayar gizlenir.
  Mevcut koşullar: `hdd_var`, `wifi_var`, `coklu_monitor`, `hibrit_gpu`, `hibrit_cpu`,
  `cpu_saglayici`, `gpu_saglayici`, `x3d_cift_ccd`, `guc_plani_mevcut`, `windows_ozelligi_mevcut`.

## Rehber ("Ayarı aç" düğmesi)

```json
"rehber": {"ac": {"tur": "ms-settings", "hedef": "ms-settings:display-advanced"}}
```

`tur`: `ms-settings`, `uri` (yalnızca `windowsdefender://`), `program` veya `denetim_masasi`.
Program ve denetim masası öğeleri koddaki beyaz listede olmalı. Emin olmadığım bağlantılar
`"dogrulanmadi": true` ile işaretli ve test listesinde denenecek.

## Tespit (BİLGİ kartları için)

Zararlı bir "tweak" daha önce uygulanmışsa tarama bunu fark edip uyarır (ör. msconfig'de
işlemci sınırı, kapatılmış sayfa dosyası). Yalnızca okur, kendiliğinden düzeltmez.
