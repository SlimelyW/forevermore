# Anti-cheat ve oyun başına çekirdek/öncelik ayarı: araştırma raporu (Revizyon Faz 5)

**Soru:** Anti-cheat (Vanguard, Easy Anti-Cheat, BattlEye) çalışırken oyun sürecinin
çekirdeklerini kısıtlamak veya önceliğini değiştirmek, anti-cheat'in işlemci tüketimini veya
FPS'i etkiler mi? (Örnek: League of Legends / Vanguard.)

**Kısa cevap:** Ölçülmüş, güvenilir bir kanıt bulamadım. Bulduklarım anekdot düzeyinde ve
birbiriyle çelişiyor. Riot'un veya anti-cheat üreticilerinin bu konuda resmi bir açıklamasını
bulamadım.

## Bulgular

1. **FPS'e etkisi: kanıt yok, yalnızca anekdot.**
   - Bir forum kullanıcısı, Process Lasso ile **vgc'nin** (Vanguard servisi) çekirdeklerini yarıya
     indirince FPS düşüşlerinin azaldığını yazıyor. Ölçüm yöntemi yok.
     ([vlr.gg](https://www.vlr.gg/207286/boosting-fps))
   - Guru3D'de League of Legends'ı tek bir CCD'ye kısıtlayan bir kullanıcı belirgin bir fark
     görmediğini yazıyor; League'in tek çekirdek performansına bağlı olduğu belirtiliyor.
     ([Guru3D](https://forums.guru3d.com/threads/league-of-legends-fps-drops-over-time-rtx-4070-ti-super-ryzen-9-3950x.460820/))

2. **Anti-cheat'in kendisine dokunmak önerilmiyor.**
   - Bir sorun giderme rehberi, oyun oynarken vgc.exe'nin önceliğini düşürmemeyi ve çekirdeklerini
     kısıtlamamayı söylüyor; Riot'un bunları çözüm olarak belgelemediğini belirtiyor.
     ([uGetFix](https://ugetfix.com/fix/how-to-fix-vanguard-user-mode-service-high-cpu-usage-in-windows/))
   - Bazı rehberler ise bunun tersini öneriyor, ama Riot'a veya ölçüme dayanmıyorlar.
     ([MakeUseOf](https://www.makeuseof.com/vanguard-user-mode-service-high-cpu/),
     [MiniTool](https://www.minitool.com/news/vanguard-user-mode-service-high-cpu-usage.html))
   - Riot'un bu konuda resmi destek makalesini bulamadım.

3. **Korumalı oyunlarda "Erişim reddedildi" en yaygın sonuç; ban kanıtı bulunamadı.**
   - Easy Anti-Cheat'li oyunlarda çekirdek veya öncelik değiştirirken "Access Denied" hatası
     bildiriliyor.
     ([Steam rehberi](https://steamcommunity.com/sharedfiles/filedetails/?id=3042130454),
     [Fatshark forumu](https://forums.fatsharkgames.com/t/allow-custom-cpu-affinity-easy-anti-cheat-blocks-it/32039))
   - BattlEye'li ArmA 3'te 2015'te Process Lasso kurallarının uygulanmadığı, BattlEye
     kapatılınca uygulandığı bildirilmiş; çok eski bir kayıt.
     ([Bitsum forumu](https://community.bitsum.com/forum/index.php?topic=4925.0))
   - Yalnızca öncelik veya çekirdek değiştirdiği için ban yiyen birine dair bir kayıt bulamadım.
     Bu, ban olmadığını kanıtlamaz.
   - BattlEye'in süreç ve tanıtıcı (handle) taramasına dair akademik çalışma:
     ([ACM](https://dl.acm.org/doi/10.1145/3733817.3762701))

4. **IFEO PerfOptions belgelenmemiş.** Kalıcı öncelik için kullanılan
   `Image File Execution Options\<exe>\PerfOptions\CpuPriorityClass` değeri Microsoft tarafından
   resmi olarak belgelenmemiş. Değer eşleşmesi (Yüksek=3, Normalin üstünde=6) bir topluluk
   cevabından alındı. ([Microsoft Q&A](https://learn.microsoft.com/en-us/answers/questions/4362251/how-to-permanently-set-priority-processes-using-re))
   I/O önceliği için IFEO'da güvenilir bir değer bulamadım; bu yüzden **I/O önceliği eklenmedi**.

5. **CPU Sets belgelenmiş.** Çekirdek seçimi için Microsoft'un "yumuşak" bir kısıtlama olarak
   tanımladığı, güç yönetimiyle uyumlu CPU Sets API'si kullanılıyor (`SetProcessDefaultCpuSets`).
   ([Microsoft Learn](https://learn.microsoft.com/en-us/windows/win32/procthread/cpu-sets))

## Uygulamaya yansıması

- Ayarlar **yalnızca oyunun kendi sürecine** uygulanır. vgc, vgk, BEService, EasyAntiCheat,
  FACEIT gibi süreçler ve başlatıcılar listeden eklenemez ve izleyici onları hiç açmaz
  (`app/games/profiles.py: PROTECTED_EXES`).
- Windows veya anti-cheat erişimi reddederse o ayar **atlanır** ve durum satırında söylenir.
  Tekrar denenmez.
- "Gerçek zamanlı" öncelik sunulmaz. "Yüksek" seçilince ayrıca onay istenir.
- **Öneri:** Rekabetçi ve anti-cheat'li oyunlarda (Valorant, League of Legends) çekirdek ayarını
  açmadan önce aynı sahnede önce/sonra ölçümü yapın (Faz 7). Tek ölçüm kanıt değildir.

**Emin olmadığım:** Vanguard'lı oyunlarda IFEO önceliğinin uygulanıp uygulanmadığı ve
anti-cheat'in bunu nasıl karşıladığı test edilmedi. Önce sanal makinede değil, gerçek bilgisayarda
ve ana hesap yerine mümkünse ikinci bir hesapla denenmelidir.
