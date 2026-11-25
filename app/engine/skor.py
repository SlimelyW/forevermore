"""Özet sayfasındaki iki halkanın hesabı (tek yer). Yalnızca sayı sayar; kazanç tahmini DEĞİLDİR.

Optimizasyon = bu bilgisayara uygun ayarlardan açık olanların oranı.
Oyun = "oyun" hazır profilinin işaretli ayarlarından, bu bilgisayarda uygun olanlar içinde açık olanların oranı.
Bulgular için skor YOKTUR: sorunsuz geçen kontroller bulgu üretmediğinden oran yanıltıcı olurdu (düz sayı gösterilir).
"""

from app.engine import profiles


def skor(acik, uygun):
    """(yüzde, açık, uygun) ya da hesaplanamıyorsa None. Yüzde AŞAĞI yuvarlanır: yalnızca hepsi açıksa 100 görünür."""
    if uygun <= 0:
        return None
    return acik * 100 // uygun, acik, uygun


def oyun_kimlikleri(profil_listesi):
    """"oyun" profilinin (temel profiliyle) işaretli gelen ayar kimlikleri."""
    return {i["id"] for i in profiles.expand(profil_listesi, "oyun") if i.get("secili")}
