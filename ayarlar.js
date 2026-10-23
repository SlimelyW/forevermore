// Sitenin tek ayar dosyası. Mağaza ve indirme bağlantıları hazır olunca yalnızca burayı doldurun.
// Boş bırakılan düğmeler "Yakında" olarak görünür ve tıklanamaz.
window.FOREVERMORE = {
  // GitHub Releases'taki zip (sürüm yükseltilse de değişmeyen bağlantı):
  // "https://github.com/KULLANICI_ADI/forevermore/releases/latest/download/Forevermore.zip"
  indir: "https://github.com/SlimelyW/forevermore/releases/latest/download/Forevermore.zip",
  // Lemon Squeezy satın alma bağlantısı: "https://MAGAZA.lemonsqueezy.com/buy/..."
  satinal: "",
  // Aboneliği yönet (müşteri portalı): "https://MAGAZA.lemonsqueezy.com/billing"
  portal: "https://forevermore.lemonsqueezy.com/billing",
  // Aylık fiyat, ekranda olduğu gibi yazılır (ör. "$4.99"). Boşsa "Yakında".
  fiyat: "₺250",
  // Paket doğrulama bilgileri (derle.bat çıktısı)
  sha256: "13D867C4394A4FC016ABFDA8DAF8BDD75EFBB9BBF1ED5D83DD26587E64BAB229",
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
});
