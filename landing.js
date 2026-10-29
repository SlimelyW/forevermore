/* Ana sayfa hareketi: hero kare süresi grafiği ve önce/sonra ayırıcısı, sayaçlar, başlık ve bölüm açılışı, şeritler, Önce/Sonra.
   İmleç konumuna göre kendiliğinden hareket eden hiçbir şey yok; ayırıcı yalnızca sürüklenince veya ok tuşlarıyla kayar.
   Bağımlılık yok (Web Animations API); yalnızca transform ve opacity canlandırılır.
   Hareket azaltılmışsa veya Okuma modu açıksa animasyon yok, son hâl hemen görünür. Betik yoksa sayfa tam ve durağandır. */
(function () {
  var root = document.documentElement;
  var lang = root.lang === "en" ? "en" : "tr";
  var locale = lang === "en" ? "en-US" : "tr-TR";
  var V = window.FM_VERI && window.FM_VERI[lang];
  var mq = window.matchMedia ? matchMedia("(prefers-reduced-motion: reduce)") : { matches: false };
  function calm() { return mq.matches || root.hasAttribute("data-okunabilir"); }
  var EASE = "cubic-bezier(.16, 1, .3, 1)";
  function each(sel, fn, scope) { Array.prototype.forEach.call((scope || document).querySelectorAll(sel), fn); }
  if (!calm()) root.classList.add("js");   // CSS çizgi, kutu süzülmesi ve Pro çerçevesi bu sınıfla başlar

  function fmt(n, d) { return n.toLocaleString(locale, { minimumFractionDigits: d, maximumFractionDigits: d }); }
  function onView(el, fn, margin) {
    if (!("IntersectionObserver" in window)) { fn(); return; }
    var io = new IntersectionObserver(function (es) {
      es.forEach(function (e) { if (e.isIntersecting) { io.disconnect(); fn(); } });
    }, { rootMargin: margin || "0px 0px -10% 0px" });
    io.observe(el);
  }
  function reveal(el, delay, from) {
    el.animate([{ opacity: 0, transform: from || "translateY(28px)" }, { opacity: 1, transform: "none" }],
               { duration: 800, delay: delay, easing: EASE, fill: "backwards" });
  }

  /* ------------------------------------------------ 25 oyun: sayı ve ad şeridi veri.js'ten (kaynaklı rehberi olan oyunlar) */
  var gameList = V && V.oyunlar;
  // Steam'in kendi görsel türleri, sırayla denenir (appid veri.js'te, Steam API'siyle doğrulanmış; tahmin yok)
  var COVERS = ["header.jpg", "capsule_616x353.jpg", "library_hero.jpg", "capsule_231x87.jpg"];
  var GAMEPAD = '<svg class="ikon" viewBox="0 0 24 24" aria-hidden="true"><path d="M7.5 8h9a4.5 4.5 0 0 1 4.4 5.5l-.7 3a2.6 2.6 0 0 1-4.5 1.1L14 15.5h-4l-1.7 2.1a2.6 2.6 0 0 1-4.5-1.1l-.7-3A4.5 4.5 0 0 1 7.5 8z"/><path d="M8 10.5v3M6.5 12h3M15.5 11.5h.01M17.5 13h.01"/></svg>';
  each("[data-oyun-sayi]", function (el) { if (gameList) el.textContent = String(gameList.length); });
  each("[data-oyun-serit]", function (iz) {
    if (!gameList) return;
    [0, 1].forEach(function (copy) {
      var ul = document.createElement("ul");
      if (copy) ul.setAttribute("aria-hidden", "true");
      gameList.forEach(function (g) {
        // her kart önce simge + adla dolu çizilir; görsel yüklenince üstüne solarak gelir, yüklenmezse kart böyle kalır
        var li = document.createElement("li"), id = V.steam && V.steam[g], other = V.kapak && V.kapak[g];
        var box = document.createElement("span"), name = document.createElement("span");
        box.className = "kapak-yer"; box.innerHTML = GAMEPAD; name.className = "ad"; name.textContent = g;
        // Steam: görsel türleri sırayla; Steam dışı: yayıncının/mağazanın tek resmî adresi (veri.js)
        var urls = id ? COVERS.map(function (f) { return "https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/" + id + "/" + f; }) : other ? [other] : [];
        li.className = urls.length ? "kapak" : "yazili"; li.appendChild(box); li.appendChild(name);
        if (urls.length) {
          var img = new Image(184, 86), n = 0;
          img.loading = "lazy"; img.decoding = "async"; img.alt = "";
          img.addEventListener("load", function () { li.classList.add("yuklendi"); });
          img.addEventListener("error", function () { if (++n < urls.length) img.src = urls[n]; else img.remove(); });
          img.src = urls[0];
          box.appendChild(img);
        }
        ul.appendChild(li);
      });
      iz.appendChild(ul);
    });
  });
  // şerit üzerine gelince ya da içine odaklanınca yavaşlar
  each(".serit", function (s) {
    var iz = s.querySelector(".serit-iz");
    function rate(r) { if (iz && iz.getAnimations) iz.getAnimations().forEach(function (a) { a.playbackRate = r; }); }
    s.addEventListener("pointerenter", function () { rate(0.2); });
    s.addEventListener("pointerleave", function () { rate(1); });
    s.addEventListener("focusin", function () { rate(0); });
    s.addEventListener("focusout", function () { rate(1); });
  });

  /* ------------------------------------------------ kare süresi izi (hero, önce/sonra, kapanış ortak) */
  var R = new Float32Array(2048), SP = new Float32Array(2048), seed = 7;
  for (var i = 0; i < R.length; i++) {
    seed = (seed * 16807) % 2147483647; R[i] = seed / 2147483647 - 0.5;
    seed = (seed * 16807) % 2147483647; SP[i] = seed / 2147483647 > 0.955 ? 0.6 + (seed % 1000) / 1000 : 0;
  }
  // kesirli zamanda iki örnek arası doğrusal geçiş (kesirli dizi indeksi NaN verip çizgiyi siliyordu)
  function sample(k) { var f = Math.floor(k), j = ((f % 2048) + 2048) % 2048, q = k - f, a = R[j], b = R[(j + 1) % 2048], c = R[(j + 2) % 2048];
    return a + b + (c - a) * q; }
  // ms değeri: önce = 60 Hz bütçesi + takılma tepeleri, sonra = 144 Hz bütçesi + küçük gürültü
  function frame(k, mix) {
    var j = ((Math.floor(k) % 2048) + 2048) % 2048;
    var before = 16.7 + 1.6 * sample(k) + SP[j] * 26 + SP[(j + 1) % 2048] * 12;
    var after = 6.9 + 0.55 * sample(k + 300);
    return before + (after - before) * mix;
  }
  function smooth(a, b, x) { var t = Math.min(1, Math.max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t); }

  function Trace(canvas, opts) {
    var ctx = canvas.getContext("2d"), w = 0, h = 0, dpr = Math.min(window.devicePixelRatio || 1, 1.5), col = {};
    function size() {
      var r = canvas.getBoundingClientRect(), cs = getComputedStyle(canvas);
      w = r.width; h = r.height;
      canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr); ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      // renkler temadan: açık ve koyu zeminde okunur kalsın
      ["--border", "--muted", "--green", "--stutter"].forEach(function (k) { col[k] = cs.getPropertyValue(k).trim(); });
    }
    size();
    var top = opts.top || 0.1, bottom = opts.bottom || 0.9, maxMs = 46;
    function y(ms) { return h * bottom - (ms / maxMs) * h * (bottom - top); }
    function line(t, split, mix, step, amp, alpha, width) {
      var n = Math.ceil(w / step) + 1;
      ctx.beginPath();
      for (var p = 0; p < n; p++) {
        var x = p * step, m = split == null ? mix : smooth(split - 40, split + 40, x);
        var v = frame(p + t, m) * amp;
        if (p === 0) ctx.moveTo(x, y(v)); else ctx.lineTo(x, y(v));
      }
      ctx.globalAlpha = alpha; ctx.lineWidth = width; ctx.stroke();
    }
    function guide(ms, label) {
      var yy = Math.round(y(ms)) + 0.5;
      ctx.globalAlpha = 0.9; ctx.strokeStyle = col["--border"]; ctx.lineWidth = 1; ctx.setLineDash([4, 6]);
      ctx.beginPath(); ctx.moveTo(0, yy); ctx.lineTo(w, yy); ctx.stroke(); ctx.setLineDash([]);
      if (label) { ctx.globalAlpha = 1; ctx.fillStyle = col["--muted"]; ctx.font = "12px Segoe UI, system-ui, sans-serif"; ctx.textAlign = "right"; ctx.fillText(label, w - 14, yy - 6); }
    }
    return {
      resize: size,
      draw: function (t, split, mix) {
        ctx.clearRect(0, 0, w, h); ctx.globalAlpha = 1;
        guide(16.7, opts.labels && opts.labels[0]); guide(6.9, opts.labels && opts.labels[1]);
        var red = col["--stutter"], green = col["--green"], stroke = ctx.createLinearGradient(0, 0, w, 0);
        if (split == null) {
          var c = mix < 0.5 ? red : green; stroke.addColorStop(0, c); stroke.addColorStop(1, c);
        } else {
          var s = Math.min(Math.max((split - 40) / w, 0), 1), e = Math.min(Math.max((split + 40) / w, 0), 1);
          stroke.addColorStop(0, red); stroke.addColorStop(s, red); stroke.addColorStop(e, green); stroke.addColorStop(1, green);
        }
        ctx.strokeStyle = stroke; ctx.lineJoin = "round";
        if (opts.depth) { line(t * 0.6 + 700, split, mix, 9, 1.25, 0.14, 1.5); line(t * 0.8 + 1300, split, mix, 7, 0.82, 0.22, 1.5); }
        line(t, split, mix, opts.step || 5, 1, 0.16, 9);
        line(t, split, mix, opts.step || 5, 1, 1, 2);
        if (split != null) {
          ctx.fillStyle = green;
          ctx.globalAlpha = 0.06; ctx.fillRect(split - 60, 0, 60, h);
          ctx.globalAlpha = 0.08; ctx.fillRect(split - 24, 0, 24, h);
          ctx.globalAlpha = 1; ctx.fillRect(Math.round(split), 0, 2, h);
        }
        ctx.globalAlpha = 1;
      }
    };
  }

  // Görünürken ve sekme açıkken çalışan döngüler; ekran dışında, gizli sekmede ve okuma modunda durur
  var loops = [], finishers = [];   // finishers: okuma modu açılınca bekleyen açılışları son hâle getirir
  function loop(el, tick) {
    var on = false, raf = 0, last = 0, visible = true;
    function run(now) { if (calm()) { stop(); return; } tick(now, last ? Math.min(now - last, 50) : 16); last = now; raf = requestAnimationFrame(run); }
    function start() { if (!on && visible && !document.hidden && !calm()) { on = true; last = 0; raf = requestAnimationFrame(run); } }
    function stop() { on = false; cancelAnimationFrame(raf); }
    if ("IntersectionObserver" in window) {
      new IntersectionObserver(function (es) { visible = es[0].isIntersecting; if (visible) start(); else stop(); }).observe(el);
    }
    document.addEventListener("visibilitychange", function () { if (document.hidden) stop(); else start(); });
    var l = { stop: stop, start: start }; loops.push(l); start();
    return l;
  }
  // erisim.js okuma modunu değiştirince haber verir
  document.addEventListener("forevermore:okuma", function () {
    if (calm()) { root.classList.remove("js"); loops.forEach(function (l) { l.stop(); }); finishers.forEach(function (f) { f(); }); }
    else { if (!mq.matches) root.classList.add("js"); loops.forEach(function (l) { l.start(); }); }
  });
  if (mq.addEventListener) mq.addEventListener("change", function () { document.dispatchEvent(new Event("forevermore:okuma")); });

  /* ------------------------------------------------ hero */
  var hero = document.querySelector(".hero2");
  var heroCanvas = hero && hero.querySelector("canvas");
  if (heroCanvas && heroCanvas.getContext) {
    var labels = lang === "en" ? ["16.7 ms: 60 Hz frame budget", "6.9 ms: 144 Hz frame budget"] : ["16,7 ms: 60 Hz kare bütçesi", "6,9 ms: 144 Hz kare bütçesi"];
    var tr = Trace(heroCanvas, { top: 0.42, bottom: 0.9, depth: true, labels: labels, step: 6 });
    // önce/sonra ayırıcısı: fareyle veya dokunarak sürüklenir, ok tuşlarıyla kayar; imleci kendiliğinden izlemez
    var t = 0, pct = 60, hint = null, knob = hero.querySelector(".ayirici");
    var say = lang === "en" ? function (p) { return p + "%: before on the left, after on the right"; } : function (p) { return "%" + p + ": solda önce, sağda sonra"; };
    function splitX() { return heroCanvas.clientWidth * (hint ? Math.max(lo, Math.min(hi, hint.value)) : pct) / 100; }
    function place() { if (knob) knob.style.transform = "translate3d(" + splitX().toFixed(1) + "px, -50%, 0)"; }
    function redraw() { place(); tr.draw(t, splitX(), 0); }
    var SEEN = "forevermore-ipucu";
    var tipped = false;   // sürüklerken her adımda depoya yazmasın: yalnızca ilk çağrıda
    function tipDone() { if (tipped) return; tipped = true; if (knob) knob.classList.remove("ipucu"); try { localStorage.setItem(SEEN, "1"); } catch (e) { /* özel pencere */ } }
    // aralık: "Önce" ve "Sonra" etiketleri ekranın içinde kalsın (dar ekranda uçlarda kesiliyordu)
    var lo = 5, hi = 95;
    function bounds() {
      var w = heroCanvas.clientWidth, a = knob && knob.querySelector(".yan.once"), b = knob && knob.querySelector(".yan.sonra");
      if (!w || !a || !b) return;
      lo = Math.ceil((a.offsetWidth + 22 + 8 + 8) / w * 100); hi = Math.floor(100 - (b.offsetWidth + 22 + 8 + 8) / w * 100);
      knob.setAttribute("aria-valuemin", String(lo)); knob.setAttribute("aria-valuemax", String(hi));
      if (pct < lo || pct > hi) pct = Math.max(lo, Math.min(hi, pct));
    }
    function setPct(p) {
      hint = null; pct = Math.max(lo, Math.min(hi, Math.round(p)));
      if (knob) { knob.setAttribute("aria-valuenow", String(pct)); knob.setAttribute("aria-valuetext", say(pct)); }
      redraw(); tipDone();
    }
    loop(hero, function (now, dt) {
      t += dt * 0.012;
      if (hint) { var k = (now - hint.start) / 2200; if (k >= 1) hint = null; else if (k > 0) hint.value = 60 - 18 * Math.sin(k * Math.PI * 2) * (1 - k); }
      redraw();
    });
    if (knob) {
      knob.hidden = false; knob.setAttribute("aria-valuetext", say(pct));
      var drag = false;
      knob.addEventListener("pointerdown", function (e) { drag = true; knob.setPointerCapture(e.pointerId); knob.classList.add("tutuldu"); e.preventDefault(); });
      knob.addEventListener("pointermove", function (e) {
        if (!drag) return;
        var r = heroCanvas.getBoundingClientRect(); setPct((e.clientX - r.left) / r.width * 100);
      });
      var release = function () { drag = false; knob.classList.remove("tutuldu"); };
      knob.addEventListener("pointerup", release); knob.addEventListener("pointercancel", release); knob.addEventListener("lostpointercapture", release);
      knob.addEventListener("keydown", function (e) {
        var step = { ArrowLeft: -5, ArrowDown: -5, ArrowRight: 5, ArrowUp: 5, PageDown: -20, PageUp: 20 }[e.key];
        if (e.key === "Home") setPct(lo); else if (e.key === "End") setPct(hi); else if (step) setPct(pct + step); else return;
        e.preventDefault();
      });
      // ilk girişte bir kez ipucu: yazı görünür, hareket açıksa tutamaç bir kez sağa sola kayar
      var seen = false; try { seen = localStorage.getItem(SEEN) === "1"; } catch (e) { /* özel pencere */ }
      if (!seen) {
        knob.classList.add("ipucu");
        // arka plan sekmesinde başlamaz (orada kare çizilmez, ipucu görülmeden "görüldü" sayılırdı); sekme açılınca başlar
        var startTip = function () {
          if (document.hidden || tipped) return;
          document.removeEventListener("visibilitychange", startTip);
          if (!calm()) hint = { start: performance.now() + 1400, value: 60 };
          setTimeout(tipDone, 6500);
        };
        document.addEventListener("visibilitychange", startTip); startTip();
      }
    }
    bounds(); redraw();
    if (document.fonts) document.fonts.ready.then(function () { bounds(); redraw(); });   // etiket genişliği yazı tipiyle değişir
    window.addEventListener("resize", function () { tr.resize(); bounds(); redraw(); });
    document.addEventListener("forevermore:okuma", function () { if (calm()) hint = null; tr.resize(); bounds(); redraw(); });

    // açılış: başlık satırları, metin, düğmeler; içerik baştan görünür (fill: backwards yalnızca gecikme süresince)
    if (!calm() && hero.animate) {
      each("h1 .satir, .lead, .actions, .not, .hud, .sayaclar, .hero-etiket", function (el, k) { reveal(el, 80 + k * 90); }, hero);
    }
  }

  /* ------------------------------------------------ sayaçlar (0'dan sayar) */
  each("[data-say]", function (el) {
    var end = parseFloat(String(el.textContent).replace(",", ".")), d = +(el.dataset.ondalik || 0);
    if (isNaN(end) || calm()) return;
    el.textContent = fmt(0, d);
    finishers.push(function () { el.textContent = fmt(end, d); });
    onView(el, function () {
      var t0 = performance.now(), dur = 1400;
      (function step(now) {
        var p = Math.min(1, (now - t0) / dur), e = 1 - Math.pow(2, -10 * p);
        el.textContent = fmt(p >= 1 ? end : end * e, d);
        if (p < 1) requestAnimationFrame(step);
      })(t0);
    }, "0px");
  });

  /* ------------------------------------------------ etiket dağılımı büyür */
  each(".dagilim", function (bar) {
    if (calm() || !bar.animate) return;
    onView(bar, function () {
      Array.prototype.forEach.call(bar.children, function (seg, k) {
        seg.animate([{ transform: "scaleX(0)", opacity: 0 }, { transform: "none", opacity: 1 }], { duration: 700, delay: 500 + k * 110, easing: EASE, fill: "backwards" });
      });
    }, "0px");
  });

  /* ------------------------------------------------ başlıklar kelime kelime (erişilebilir ad bölünmez) */
  each("[data-kelime]", function (h) {
    if (calm() || !h.animate || h.children.length) return;
    var text = h.textContent.trim(), words = text.split(/\s+/);
    h.textContent = "";
    var sr = document.createElement("span"); sr.className = "sr"; sr.textContent = text; h.appendChild(sr);
    var vis = document.createElement("span"); vis.setAttribute("aria-hidden", "true"); h.appendChild(vis);
    var spans = words.map(function (wd, k) {
      var s = document.createElement("span"); s.className = "kelime"; s.textContent = wd; vis.appendChild(s);
      if (k < words.length - 1) vis.appendChild(document.createTextNode(" "));
      return s;
    });
    spans.forEach(function (s) { s.style.opacity = "0"; });
    finishers.push(function () { spans.forEach(function (s) { s.style.opacity = ""; }); });
    onView(h, function () {
      spans.forEach(function (s, k) { s.style.opacity = ""; reveal(s, k * 55, "translateY(.5em) rotate(2deg)"); });
    });
  });

  /* ------------------------------------------------ bölümler kademeli açılır (başlıktan sonra içerik, kart kart) */
  if (!calm()) {
    each("main section > .wrap, .demo", function (wrap) {
      var items = [];
      Array.prototype.forEach.call(wrap.children, function (el) {
        if (el.matches("h2") || el.querySelector("[data-kelime]") || el.matches(".kisaca")) return;
        if (el.matches(".iki, .uclu, .plans2, .olculer, .indir, .sira")) items.push.apply(items, el.children); else items.push(el);
      });
      items.forEach(function (el) { el.style.opacity = "0"; });
      finishers.push(function () { items.forEach(function (el) { el.style.opacity = ""; }); });
      onView(wrap, function () {
        items.forEach(function (el, k) { el.style.opacity = ""; reveal(el, 120 + Math.min(k, 8) * 80); });
      }, "0px 0px -15% 0px");
    });
  }

  /* ------------------------------------------------ önce / sonra */
  var fark = document.querySelector(".fark");
  if (fark) {
    var fc = fark.querySelector("canvas"), buttons = fark.querySelectorAll("[data-ab]"), tiles = fark.querySelectorAll("[data-once]");
    var ft = fc && fc.getContext ? Trace(fc, { top: 0.12, bottom: 0.92, step: 5 }) : null;
    var mix = 1, mixGoal = 1, ftime = 0, touched = false;
    function show(state, animate) {
      fark.dataset.durum = state; mixGoal = state === "sonra" ? 1 : 0;
      Array.prototype.forEach.call(buttons, function (b) { b.setAttribute("aria-pressed", b.dataset.ab === state ? "true" : "false"); });
      Array.prototype.forEach.call(tiles, function (tile) {
        var b = tile.querySelector("b .v"), from = tile.dataset[state === "sonra" ? "once" : "sonra"], to = tile.dataset[state];
        var a = parseFloat(from.replace(",", ".")), z = parseFloat(to.replace(",", ".")), d = (to.split(/[.,]/)[1] || "").length;
        if (!animate || calm() || isNaN(a) || isNaN(z)) { b.textContent = to; return; }
        var t0 = performance.now();
        (function step(now) {
          var p = Math.min(1, (now - t0) / 900), e = 1 - Math.pow(2, -10 * p);
          b.textContent = p >= 1 ? to : fmt(a + (z - a) * e, d);
          if (p < 1) requestAnimationFrame(step);
        })(t0);
      });
      if (ft && calm()) { mix = mixGoal; ft.draw(ftime, null, mix); }
    }
    Array.prototype.forEach.call(buttons, function (b) { b.addEventListener("click", function () { touched = true; show(b.dataset.ab, true); }); });
    if (ft) {
      ft.draw(0, null, 1);
      loop(fc, function (now, dt) { ftime += dt * 0.01; mix += (mixGoal - mix) * Math.min(1, dt / 220); ft.draw(ftime, null, mix); });
      window.addEventListener("resize", function () { ft.resize(); ft.draw(ftime, null, mix); });
      document.addEventListener("forevermore:okuma", function () { ft.resize(); ft.draw(ftime, null, mix); });
    }
    // görününce önce "Önce" gösterilir, kısa süre sonra kendiliğinden "Sonra"ya geçer (kullanıcı dokunduysa geçmez)
    if (!calm()) {
      show("once", false); mix = 0;
      onView(fark.querySelector(".grafik"), function () { setTimeout(function () { if (!touched && !calm()) show("sonra", true); }, 1100); }, "0px 0px -25% 0px");
    }
  }

  /* ------------------------------------------------ kapanış izi */
  var son = document.querySelector(".son canvas");
  if (son && son.getContext) {
    var st = Trace(son, { top: 0.3, bottom: 0.96, step: 7 }), stime = 0;
    function sonSplit(now) { return son.clientWidth * (0.5 + 0.18 * Math.sin(now / 3200)); }
    st.draw(0, sonSplit(0), 0);
    loop(son, function (now, dt) { stime += dt * 0.008; st.draw(stime, sonSplit(now), 0); });
    window.addEventListener("resize", function () { st.resize(); st.draw(stime, sonSplit(performance.now()), 0); });
  }
})();
