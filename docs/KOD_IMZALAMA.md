# Kod imzalama seçenekleri (araştırma, 4 Kasım 2026)

Başvuru yapılmadı. Kaynaklar değişebilir; başvurudan önce güncel sayfaya bakın.

| Seçenek | Uygun mu? | Not |
|---|---|---|
| SignPath Foundation (ücretsiz, açık kaynak) | Olası | OSI lisansı (MIT uygun), kapalı kod/ticari çift lisans yok, public repo, doğrulanabilir CI derlemesi, tüm ekipte MFA, ana sayfada imzalama politikası metni, her sürümde elle onay, "etkin bakım" + "doğrulanabilir itibar". Sayısal yıldız eşiği yok. Sertifika SignPath Foundation adınadır: yayıncı adı olarak o görünür. Kaynak: signpath.org/terms |
| Azure Artifact Signing (eski Trusted Signing) | **Türkiye'den hayır** | Bireyler yalnızca ABD/Kanada; kurumlar ABD, Kanada, AB, BK ve listedeki ülkeler. Basic ~$9.99/ay. Ücretsiz katman yok. Kaynak: learn.microsoft.com/azure/artifact-signing/quickstart |
| Certum Open Source Code Signing | Olası (yedek) | Bireysel, açık kaynak için; fiyat kaynaklara göre €49–69 (güncel sayfadan bakın); Türkiye'ye satış ve bulut/CI desteği doğrulanmadı. Kaynak: shop.certum.eu |
| OV/EV sertifika | Pahalı | ~$150–300/yıl, donanım anahtarı zorunlu |

## Başvuruda gerekenler
- Public depo + OSI lisansı (var: MIT), bağımlılık lisansları temiz (`THIRD-PARTY-NOTICES.txt`).
- **GitHub Actions ile tekrarlanabilir derleme** (şu an `tools/derle.ps1` yerel; CI işi yazılmalı). SignPath için şart.
- README/ana sayfada imzalama politikası metni; GitHub hesabında MFA.
- Yayınlanmış sürüm geçmişi ve kullanıcı/itibar kanıtı (indirme, issue, tanıtım).
- Certum için ayrıca kimlik belgesi.

Sıra önerisi: SignPath → reddedilirse Certum.
