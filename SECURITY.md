# Güvenlik politikası / Security policy

Forevermore Windows ayarlarını (kayıt defteri, servisler, bcdedit, sürücü ayarları) değiştirdiği ve yönetici
izniyle çalıştığı için güvenlik açıkları ciddiye alınır.

## Açık bildirimi

**Açığı herkese açık bir konu (issue) olarak açmayın.** Bunun yerine:

1. GitHub'da bu deponun **Security > Report a vulnerability** (özel güvenlik bildirimi) bağlantısını kullanın:
   <https://github.com/SlimelyW/forevermore/security/advisories/new>
2. Ya da e-posta: **[kaldirildi]** (konu: `Forevermore güvenlik`).

Bildirimde şunları yazın: etkilenen sürüm, açığın ne olduğu, nasıl yeniden üretileceği (adımlar ya da küçük bir örnek),
etkisi (ör. yetki yükseltme, yedek/geri almanın atlatılması, imzasız güncellemenin kabulü) ve varsa önerdiğiniz düzeltme.
Gerçek kullanıcı verisi, anahtar ya da parola eklemeyin.

Bu bir hobi projesidir; bildirimi mümkün olan en kısa sürede değerlendirir, düzeltme yayımlanınca isterseniz adınızı
teşekkür olarak yazarım. Süre garantisi veremem.

## Kapsam

Kapsama giren örnekler:

- Motorun güvenlik katmanını aşmak: yedek/geri alma kaydının değiştirilip kayıt defteri ya da dosya sisteminde
  beklenmeyen bir yere yazdırılması, kök/yol doğrulamasının atlatılması (bkz. `docs/GUVENLIK.md`).
- Güncelleme: imzası doğrulanmamış ya da eski bir paketin kurulması (`app/core/guncelleme.py`, `app/core/integrity.py`).
- Yönetici olarak çalıştırılan dış araçların (`tools\` klasörü) doğrulamasız çalıştırılması.
- Uygulamanın kullanıcı verisini (tarama sonuçları, ayarlar, günlük) bilgisayarın dışına göndermesi. Uygulamanın
  telemetrisi yoktur; ağa yalnızca kullanıcının açtığı güncelleme denetiminde (GitHub) bağlanır.

Kapsama girmeyenler: bir ayarın tasarımı gereği güvenliği azaltması (ör. Spectre/Meltdown azaltımını kapatmak; bu
ayar onay penceresinde açıkça uyarılır), yönetici hesabı zaten ele geçirilmiş bir bilgisayarda yapılabilecek saldırılar,
üçüncü taraf bileşenlerin (Qt, PresentMon vb.) kendi açıkları (onlara bildirin; burada yalnızca sürüm güncellemesi yapılır).

## Desteklenen sürümler

Yalnızca en son yayımlanan sürüm düzeltme alır.
