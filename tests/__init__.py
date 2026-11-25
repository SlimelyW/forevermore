import os

os.environ.setdefault("PCOPT_HAREKET", "azalt")  # testlerde animasyon yok; hareket testi bunu kendi içinde açar
os.environ.setdefault("PCOPT_BEKCI", "kapali")  # arayüz bekçisi (app/ui/worker.StallWatch) test pencerelerinde gürültü yapar
