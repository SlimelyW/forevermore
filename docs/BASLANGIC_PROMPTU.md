# Claude Code ilk prompt (proje klasöründe `claude` açınca yapıştır)

```
Forevermore projesinde devam ediyoruz. Önce SADECE CLAUDE.md, HANDOFF.md ve docs/BACKLOG.md dosyalarını oku (docs/TEST_KONTROL_LISTESI.md ve tweaks.json çok büyük, okuma).

Sonra:
1. docs/BACKLOG.md'deki Faz A ve B maddelerini mevcut koda göre kontrol et: her madde için ilgili dosya/fonksiyonu grep ile bul; zaten yapılmışsa maddeyi `[x]` yapıp "zaten vardı: dosya" yaz, eksikse (dosya:satır) notu düş. Kod DEĞİŞTİRME.
2. Bana en fazla 10 satırlık özet ver: hangi maddeler zaten bitmiş, hangileri eksik, önerdiğin sıra, belirsiz kalanlar.
3. Dur. Ben "/next" yazınca her seferinde tek madde yapacaksın; bitince commit at, kısa özet ver, /clear öner.

Kurallar: CLAUDE.md'deki tüm kurallar geçerli (özellikle ayar yazma/izin kuralları ve token tasarrufu bölümü). Araştırma için researcher subagent'ını kullan. Benim kodlama geçmişim yok, sade anlat.
```

## Gece otonom çalıştırma

```
docs/BACKLOG.md'de FAZ A'dan başlayarak sırayla maddeleri yap. Her madde: mevcut durumu kontrol et, uygula, ilgili testleri çalıştır, BACKLOG'u güncelle, küçük commit at. Karar gerektiren, belirsiz, E-fazı veya sistem ayarı yazmayı gerektiren maddelerde DUR, docs/SABAH.md'ye "karar bekliyor: ..." yaz, sonrakine geç. Sistem ayarı değiştirme, silme, force push yapma. Sabah için docs/SABAH.md'ye 10 satırı geçmeyen özet yaz.
```
