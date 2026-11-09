# Yeni dil ekleme

Uygulamanın dili kodu değiştirmeden eklenir. Bir dil, üç dosyadan oluşur:

| Dosya | Ne içerir | Zorunlu mu |
|---|---|---|
| `lang/<kod>.json` | Arayüz metinleri (menüler, düğmeler, uyarılar, rapor) | Evet |
| `lang/baslangic_onayi.<kod>.txt` | İlk açılıştaki sorumluluk onayı | Evet (yoksa İngilizcesi gösterilir) |
| `data/ceviriler/<kod>.json` | Ayarların adları, açıklamaları, artı/eksileri, rehber adımları | Hayır (yoksa İngilizce, o da yoksa Türkçe) |

`<kod>` iki harfli dil kodudur (ISO 639-1): `de`, `fr`, `ar`, `ja`, `zh` gibi.

## 1. Arayüz metinleri: `lang/<kod>.json`

1. `lang/en.json` dosyasını kopyalayıp `lang/<kod>.json` olarak kaydet.
2. En üstteki `_meta` bölümünü doldur:

   | Alan | Anlamı | Örnek (Almanca) |
   |---|---|---|
   | `kod` | Dosya adındaki kodla aynı | `de` |
   | `ad` | Dilin İngilizce adı | `German` |
   | `yerel_ad` | Dilin kendi dilindeki adı (seçim listesinde görünür) | `Deutsch` |
   | `yon` | Yazı yönü: `ltr` (soldan sağa) veya `rtl` (Arapça, İbranice) | `ltr` |
   | `yerel` | Bölge kodu (bilgi amaçlı) | `de-DE` |
   | `ondalik` / `binlik` | Ondalık ve binlik ayracı | `,` / `.` |
   | `tarih` | Tarih biçimi: `{gun}`, `{ay}`, `{yil}` | `{gun}.{ay}.{yil}` |
   | `saat` | Saat biçimi: `{saat}`, `{dakika}` | `{saat}:{dakika}` |
   | `yuzde` | Yüzde biçimi: `{n}` sayıdır | `{n} %` |
   | `yazi_tipi` | Boş bırak; yalnızca Segoe UI'da olmayan yazılar için (ör. `Yu Gothic UI`, `Microsoft YaHei UI`) | `` |

3. Her değeri çevir. **Anahtarlara dokunma.** Süslü parantez içindeki yer tutucuları (`{ad}`, `{adet}`,
   `{sure}`) olduğu gibi bırak; yerleri cümle içinde değişebilir.
4. Boş metinler (`""`) bilerek boştur (ör. Türkçede çeviri notu yok); istersen doldurabilirsin.

Çevrilmemiş bir anahtar silinirse uygulama o metni İngilizce gösterir; bozulmaz.

## 2. Onay metni: `lang/baslangic_onayi.<kod>.txt`

`baslangic_onayi.en.txt` dosyasını kopyalayıp çevir. Son paragraftaki "asıl metin Türkçedir" notu
kalmalıdır. **Hukuki not:** Asıl (geçerli) metin Türkçedir; her çeviri yayından önce bir avukata
kontrol ettirilmelidir.

## 3. Ayar metinleri (isteğe bağlı): `data/ceviriler/<kod>.json`

Ayarların metinleri `data/islemler.json` → `data/tweaks_app.json` içinde Türkçe yazılıdır. Çeviri
katmanı yalnızca **ekranda görünen** alanları değiştirebilir; kimlikler, risk/etki seviyeleri,
registry yolları ve değerler değişmez (değiştirmeye çalışan satır yok sayılır ve log'a yazılır).

```json
{
  "ayarlar": {
    "SYS-001": {
      "ad": "Disable the Print Spooler service",
      "ne_ise_yarar": "…",
      "artilar": ["…", "…"],
      "nvidia.secenekler.0.etiket": "…"
    }
  },
  "genel": {
    "meta.anti_cheat_uyarisi": "…",
    "kategoriler.0.aciklama": "…"
  }
}
```

Çevrilebilen alanların tam listesi `app/engine/catalog.py` içindeki `TRANSLATABLE` ve
`TRANSLATABLE_GENERAL` sabitlerindedir. En kolay yol `data/ceviriler/en.json` dosyasını kopyalayıp
değerleri çevirmektir.

Türkçe bir ayar metni değişince o ayarın çevirisi eskir. `py -3.12 tools\ceviri_ozeti.py` eskiyen ve
eksik ayarları listeler; çeviriyi düzelttikten sonra `--yenile <kod>` ile özetleri yenile (test de
eskimiş çeviride düşer).

## 4. Kontrol

```
py -3.12 -m unittest tests.test_metinler tests.test_dil -v
py -3.12 -m app --kontrol
```

Test, her dil dosyasının Türkçeyle aynı anahtarlara, aynı sıraya ve aynı yer tutuculara sahip
olduğunu ve onay metninin bulunduğunu denetler. Sonra uygulamayı aç, Ayarlar > Dil'den yeni
dili seç ve tüm sayfaları gez: kesilen veya taşan metinleri not et.

## Notlar

- **Windows'un dili ile uygulamanın dili ayrıdır.** Uygulama Windows'tan okuduğu bilgileri dile bağlı
  olmayan yollarla okur (servis adı, GUID, olay numarası, sayısal değer). Windows'un kendi verdiği adlar
  (ör. güç planı adı "Dengeli/Balanced", aygıt adları) Windows dilinde görünür; bu normaldir.
- **Sağdan sola diller:** `yon: "rtl"` verilince uygulamanın düzeni aynalanır. Bu altyapı hazır ama
  gerçek bir RTL çeviriyle denenmedi.
- **İngilizce çeviri** geliştirici tarafından yapıldı; ana dili İngilizce olan bir uzmanın kontrol etmesi
  gerekir.
