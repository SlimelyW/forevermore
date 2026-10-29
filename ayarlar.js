// Sitenin tek ayar dosyası. Mağaza ve indirme bağlantıları hazır olunca yalnızca burayı doldurun.
// Boş bırakılan düğmeler "Yakında" olarak görünür ve tıklanamaz.
window.FOREVERMORE = {
  // GitHub Releases'taki zip (sürüm yükseltilse de değişmeyen bağlantı):
  // "https://github.com/KULLANICI_ADI/forevermore/releases/latest/download/Forevermore.zip"
  indir: "https://github.com/SlimelyW/forevermore/releases/latest/download/Forevermore.zip",
  // Satın alma sayfası (Buy Me a Coffee): ödeme burada yapılır, kod Discord ticket ile teslim edilir.
  satinal: "https://buymeacoffee.com/forevermore",
  // Discord sunucusu davet bağlantısı (kod teslimi için ticket): "https://discord.gg/..." Boşsa "Yakında".
  discord: "https://discord.gg/eyQBGyQkVG",
  // Tüm sürümler ve sürüm notları (GitHub Releases)
  github: "https://github.com/SlimelyW/forevermore/releases",
  // Bağış sayfası
  bagis: "https://buymeacoffee.com/forevermore",
  // Pro kodu fiyatları. Biçim TAM OLARAK "$<USD> (~₺<TL>)", ör. "$16 (~₺800)": site aylık fiyatı, toplamı, tasarrufu ve
  // düğmedeki tutarı bundan hesaplar; başka biçim sitede "yakında" görünür (tests/test_site_fiyat.py denetler).
  // Kod otomatik yenilenmez; süre dolunca yeni kod alınır.
  fiyat1: "$2 (~₺100)",
  fiyat3: "$5 (~₺250)",
  fiyat12: "$16 (~₺800)",
  // Paket doğrulama bilgileri (derle.bat çıktısı)
  sha256: "E710845C4CB7121AEEBDEFA6CE45E6C133C83A47FC13F34C2D4A4783816AD742",
  parmakIzi: "5FE5-D786-0B89-A56E",
};

document.addEventListener("DOMContentLoaded", () => {
  const cfg = window.FOREVERMORE;
  const isEn = document.documentElement.lang === "en";
  document.querySelectorAll("[data-link]").forEach((el) => {
    const url = cfg[el.dataset.link];
    if (url) {
      el.href = url;
    } else {
      el.setAttribute("aria-disabled", "true");
      el.removeAttribute("href");
      el.textContent = isEn ? "Coming soon" : "Yakında";
    }
  });
  document.querySelectorAll("[data-value]").forEach((el) => {
    const value = cfg[el.dataset.value];
    el.textContent = value || (isEn ? "coming soon" : "yakında");
  });
  document.querySelectorAll("[data-year]").forEach((el) => { el.textContent = "2026"; });
  // Kapalı bir SSS kutusuna giden bağlantı (ör. #antivirus) kutuyu açar
  const openTarget = (hash) => {
    const target = hash && document.getElementById(hash.slice(1));
    if (target && target.tagName === "DETAILS") target.open = true;
  };
  document.querySelectorAll('a[href^="#"]').forEach((a) => {
    a.addEventListener("click", () => openTarget(a.getAttribute("href")));
  });
  openTarget(location.hash);
  // VirusTotal raporu: güncel zip'in SHA-256 değerinden kurulur (yeni sürümde kendiliğinden güncellenir)
  document.querySelectorAll("[data-vt]").forEach((el) => {
    if (cfg.sha256) {
      el.href = "https://www.virustotal.com/gui/file/" + cfg.sha256.toLowerCase();
    } else {
      el.removeAttribute("href");
    }
  });
});
