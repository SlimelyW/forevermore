"""Kanıt döngüsünün sonuç hesabı (app/measure/dongu.py): fark gürültüyle kıyaslanır, tek ölçüm sonuç sayılmaz."""

import unittest

from app.measure import dongu, system_measure


def fps(*values):
    return [{"fps_ort": v} for v in values]


class TestKarsilastir(unittest.TestCase):
    def test_single_pair_is_never_a_result(self):
        result = dongu.karsilastir(fps(60), fps(120), "oyun")  # iki katı FPS olsa da tek çift: karar yok
        self.assertEqual(result["karar"], "yetersiz")
        self.assertEqual(result["tekrar"], (1, 1))

    def test_difference_inside_spread_is_no_difference(self):
        result = dongu.karsilastir(fps(100, 110, 105), fps(108, 112, 104), "oyun")  # yayılım 10, fark 3
        self.assertEqual(result["karar"], "fark_yok")
        self.assertIsNone(result["satirlar"][0][4])

    def test_small_and_clear_difference(self):
        self.assertEqual(dongu.karsilastir(fps(100, 102, 104), fps(106, 108, 107), "oyun")["karar"], "kucuk")  # fark 5, gürültü 4
        clear = dongu.karsilastir(fps(100, 102, 104), fps(120, 122, 121), "oyun")
        self.assertEqual(clear["karar"], "belirgin")
        self.assertTrue(clear["satirlar"][0][4])  # FPS arttı: iyi
        worse = dongu.karsilastir(fps(120, 122, 121), fps(100, 102, 104), "oyun")
        self.assertEqual(worse["karar"], "belirgin")
        self.assertFalse(worse["satirlar"][0][4])

    def test_two_repeats_need_a_bigger_difference(self):
        """Denetim YAYIN K2: bir tekrar düşünce (2'ye 2) gürültü iki katı sayılır; 3'e 3'te "küçük" olan fark burada sayılmaz."""
        self.assertEqual(dongu.karsilastir(fps(100, 102, 101), fps(105, 106, 105.5), "oyun")["karar"], "kucuk")
        self.assertEqual(dongu.karsilastir(fps(100, 102), fps(105, 106), "oyun")["karar"], "fark_yok")
        self.assertEqual(dongu.karsilastir(fps(100, 102), fps(120, 121), "oyun")["karar"], "belirgin")  # büyük fark yine görünür

    def test_metric_seen_once_is_not_a_result(self):
        """Denetim YAYIN K9: 3 tekrarın yalnızca birinde okunan ölçüm tek değerle "belirgin" kararı veremez."""
        before = [{"fps_ort": 100, "fps_1": 60}, {"fps_ort": 100}, {"fps_ort": 101}]
        after = [{"fps_ort": 100, "fps_1": 66}, {"fps_ort": 100}, {"fps_ort": 101}]
        result = dongu.karsilastir(before, after, "oyun")
        self.assertEqual(result["karar"], "fark_yok")
        self.assertEqual([r[0] for r in result["satirlar"]], ["fps_ort"])

    def test_process_count_uses_absolute_floor(self):
        """Denetim YAYIN K10: Boost 5 program kapatınca (210 -> 205) %3 tabanı yüzünden "fark yok" denmez; 1-2 süreç yine gürültü."""
        before = [{"surec_sayisi": n} for n in (210, 211, 210)]
        result = dongu.karsilastir(before, [{"surec_sayisi": n} for n in (205, 205, 206)], "sistem")
        self.assertEqual((result["karar"], result["satirlar"][0][4]), ("kucuk", True))
        self.assertEqual(dongu.karsilastir(before, [{"surec_sayisi": n} for n in (209, 208, 209)], "sistem")["karar"], "fark_yok")

    def test_identical_repeats_still_need_three_percent(self):
        self.assertEqual(dongu.karsilastir(fps(100, 100, 100), fps(102, 102, 102), "oyun")["karar"], "fark_yok")

    def test_mixed_when_metrics_disagree(self):
        before = [{"fps_ort": 100, "fps_1": 60}, {"fps_ort": 101, "fps_1": 61}]
        after = [{"fps_ort": 120, "fps_1": 40}, {"fps_ort": 121, "fps_1": 41}]
        self.assertEqual(dongu.karsilastir(before, after, "oyun")["karar"], "karisik")

    def test_system_near_zero_values_use_absolute_floor(self):
        before = [{"bosta_cpu": 0.0, "surec_sayisi": 200}] * 3
        after = [{"bosta_cpu": 0.5, "surec_sayisi": 201}] * 3  # yarım puan işlemci, 1 süreç: gürültü
        self.assertEqual(dongu.karsilastir(before, after, "sistem")["karar"], "fark_yok")
        fewer = [{"bosta_cpu": 0.0, "surec_sayisi": 170}] * 3
        result = dongu.karsilastir(before, fewer, "sistem")
        self.assertEqual(result["karar"], "belirgin")
        self.assertEqual([r[0] for r in result["satirlar"] if r[4]], ["surec_sayisi"])  # daha az süreç: iyi

    def test_mean(self):
        self.assertEqual(dongu.ortalama([{"fps_ort": 100, "fps_1": 50}, {"fps_ort": 110}]), {"fps_ort": 105, "fps_1": 50})


class FakeSampler:
    def sample(self):
        return {"cpu": 4.0, "ram_kullanilan": 8 * 2 ** 30, "surec_sayisi": 180, "disk": 2.0}

    def close(self):
        self.closed = True


class TestSampleIdle(unittest.TestCase):
    def test_sample_idle_reads_only_live_counters(self):
        seen = []
        values, details = system_measure.sample_idle(FakeSampler, 3, progress=lambda done, total: seen.append((done, total)),
                                                     sleep=lambda _s: None)
        self.assertEqual(values, {"bosta_cpu": 4.0, "bosta_ram_gb": 8.0, "surec_sayisi": 180, "disk_yuk": 2.0})
        self.assertEqual(details["ornek_sayisi"], 3)
        self.assertEqual(seen[-1], (3, 3))

    def test_sample_idle_stops_on_cancel(self):
        """Denetim YAYIN K8: "Durdur" 10 sn'lik tekrarın bitmesini beklemez."""
        slept = []
        system_measure.sample_idle(FakeSampler, 10, sleep=slept.append, cancel=lambda: len(slept) >= 2)
        self.assertEqual(len(slept), 2)


if __name__ == "__main__":
    unittest.main()


class TestAdim(unittest.TestCase):
    """Menü/yükleme -> oyun geçişi: kare hızı basamağı (app/measure/presentmon.adim_var_mi), sahte kare dizileriyle."""

    @staticmethod
    def kareler(*parcalar):
        """(saniye, fps) parçalarından kare süresi (ms) dizisi."""
        return [1000 / fps for saniye, fps in parcalar for _ in range(int(saniye * fps))]

    def test_menu_then_game_is_a_step(self):
        from app.measure import presentmon
        self.assertTrue(presentmon.adim_var_mi(self.kareler((8, 60), (12, 140))))

    def test_loading_screen_then_game_is_a_step(self):
        from app.measure import presentmon
        self.assertTrue(presentmon.adim_var_mi(self.kareler((6, 2), (14, 140))))

    def test_steady_game_is_not_a_step(self):
        from app.measure import presentmon
        self.assertFalse(presentmon.adim_var_mi(self.kareler((20, 140))))

    def test_fluctuating_play_is_not_a_step(self):
        from app.measure import presentmon
        fps = [120, 150, 95, 160, 110, 140, 100, 155, 125, 135, 105, 150, 115, 145, 98, 158, 128, 138, 108, 148]
        self.assertFalse(presentmon.adim_var_mi(self.kareler(*[(1, f) for f in fps])))

    def test_unchanging_menu_is_not_detected(self):
        """Bilinen sınır: hiç değişmeyen menü oyundan ayırt edilemez; bunu "Oyundayım, başla" düğmesi çözer."""
        from app.measure import presentmon
        self.assertFalse(presentmon.adim_var_mi(self.kareler((20, 60))))

    def test_short_capture_is_never_a_step(self):
        from app.measure import presentmon
        self.assertFalse(presentmon.adim_var_mi(self.kareler((3, 60), (4, 140))))
