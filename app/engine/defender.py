"""Windows Defender gerçek zamanlı koruması: kullanıcı isteğiyle eklenen, varsayılan olarak kapalı anahtar.

Yalnızca gerçek zamanlı koruma kapatılır (Set-MpPreference -DisableRealtimeMonitoring); Defender servisleri,
ilkeleri ve tanım güncellemeleri olduğu gibi kalır. Kurcalama koruması (Tamper Protection) açıkken Windows
bu komutu hatasız kabul edip yok sayar; bu yüzden durum yazdıktan sonra yeniden okunur ve değişmediyse
kullanıcıya Kurcalama korumasını Windows Güvenliği'nden kendisinin kapatması söylenir (uygulama kapatmaz).
Windows korumayı bir süre sonra veya yeniden başlatınca kendiliğinden geri açabilir.
"""

CHANGE_ID = "DEFENDER-GZK"
SECURITY_PAGE = {"tur": "uri", "hedef": "windowsdefender://threatsettings"}


def step():
    return {"tur": "yerlesik", "eylem": "defender_gercek_zamanli", "parametreler": {}, "acik": False, "kapali": True}
