/* Demo penceresi (tarama, künye, geri alma, tahmin), oyun denetimi ve fiyat süresi.
   Veri: veri.js (tools/site_veri.py, uygulamanın kendi dosyalarından). Betik yoksa fiyatlar düz okunur. */
(function () {
  var lang = document.documentElement.lang === "en" ? "en" : "tr";
  var V = window.FM_VERI && window.FM_VERI[lang];
  var cfg = window.FOREVERMORE || {};
  var reduce = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  var U = {
    tr: {
      step: "{k} / {n}", real: "Doğru.", wrong: "Forevermore'da etiketi:", next: "Sonraki", last: "Sonucu gör",
      score: "{n} / {t} doğru", scoreNote: "Etiketlerin anlamı aşağıda; her ayarın gerekçesi uygulamada.", table: "Etiketlere bak", again: "Tekrar oyna",
      scan: "Taramayı başlat", scanning: "Taranıyor…", rescan: "Yeniden tara", fix: "Çöz", fixed: "Çözüldü (örnek)",
      steps: ["Donanım okunuyor", "Ekran ve RAM okunuyor", "Başlangıç uygulamaları sayılıyor", "Bulgular sıralanıyor"],
      done: "{n} bulgu", machine: ["İşlemci", "Bellek", "Ekran kartı", "Monitör"],
      undoAll: "Hepsini geri al", redo: "Yeniden uygula", backup: "Yedek alındı", restore: "Geri yükleme noktası", reverted: "Geri alındı",
      changed: { "DISP-001": ["60 Hz", "144 Hz"], "SYS-006": ["14 uygulama", "6 uygulama"], "PERF-002": ["Kayıt açık", "Kayıt kapalı"] },
      kEtki: "Performans etkisi", kRisk: "Risk", kNeden: "Gerekçe", kGeri: "Geri alma",
      kGeriMetin: "Değiştirilmeden önce yedeklenir; Değişiklikler sayfasından tek tıkla eski hâline döner.",
      kKaynak: "Kaynaklar ve ölçüm notları uygulamada, ayarın (i) penceresinde.",
      oBos: "Bir oyun adı yaz ya da listeden seç.",
      oVar: "{ad} için oyun içi ayar rehberi var. Sistem ayarları da geçerli.",
      oYok: "{ad} listede yok. Sistem ayarları bu oyunda da geçerli; oyun bir mağazadan kuruluysa Oyunlar sayfası bulur. Oyun içi rehber yalnızca listedeki oyunlar için var."
    },
    en: {
      step: "{k} / {n}", real: "Correct.", wrong: "Forevermore labels it:", next: "Next", last: "See result",
      score: "{n} / {t} correct", scoreNote: "The labels are explained below; each setting's reason is in the app.", table: "See the labels", again: "Play again",
      scan: "Start scan", scanning: "Scanning…", rescan: "Scan again", fix: "Fix", fixed: "Fixed (sample)",
      steps: ["Reading hardware", "Reading display and RAM", "Counting startup apps", "Sorting findings"],
      done: "{n} findings", machine: ["CPU", "Memory", "Graphics", "Monitor"],
      undoAll: "Undo all", redo: "Apply again", backup: "Backup taken", restore: "Restore point", reverted: "Reverted",
      changed: { "DISP-001": ["60 Hz", "144 Hz"], "SYS-006": ["14 apps", "6 apps"], "PERF-002": ["Recording on", "Recording off"] },
      kEtki: "Performance impact", kRisk: "Risk", kNeden: "Reason", kGeri: "Undo",
      kGeriMetin: "Backed up before it changes; one click on the Changes page restores the original.",
      kKaynak: "Sources and measurement notes are in the setting's (i) window in the app.",
      oBos: "Type a game name or pick one from the list.",
      oVar: "There is an in-game setting guide for {ad}. System settings apply too.",
      oYok: "{ad} is not on the list. System settings apply in this game as well; if it is installed through a store, the Games page finds it. In-game guides exist only for the listed games."
    }
  }[lang];
  function fill(s, o) { return s.replace(/\{(\w+)\}/g, function (m, k) { return o[k] != null ? o[k] : m; }); }
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function badge(slug) { return el("span", "rozet r-" + slug, V.etiket[slug]); }
  function wait(fn, ms) { if (reduce) fn(); else setTimeout(fn, ms); }

  /* ------------------------------------------------------------ sekmeler */
  var tabs = Array.prototype.slice.call(document.querySelectorAll('[role="tab"]'));
  function select(tab, focus) {
    tabs.forEach(function (t) {
      var on = t === tab;
      t.setAttribute("aria-selected", on ? "true" : "false");
      t.tabIndex = on ? 0 : -1;
      document.getElementById(t.getAttribute("aria-controls")).hidden = !on;
    });
    if (focus) tab.focus();
  }
  tabs.forEach(function (t, i) {
    t.addEventListener("click", function () { select(t); });
    t.addEventListener("keydown", function (e) {
      var d = { ArrowDown: 1, ArrowRight: 1, ArrowUp: -1, ArrowLeft: -1 }[e.key];
      if (d) { e.preventDefault(); select(tabs[(i + d + tabs.length) % tabs.length], true); }
    });
  });

  if (!V) return;

  /* ------------------------------------------------------------ tahmin oyunu */
  var quiz = document.querySelector("[data-quiz]");
  if (quiz) (function () {
    var items = V.tahmin.slice().sort(function () { return Math.random() - 0.5; });
    var order = ["gercek", "placebo", "zararli"];
    var index = 0, score = 0, marks = [];
    var live = el("div"); live.setAttribute("aria-live", "polite"); quiz.appendChild(live);

    function bar() {
      var b = el("div", "ilerleme");
      items.forEach(function (_, i) { b.appendChild(el("i", marks[i] || "")); });
      return b;
    }
    function show() {
      live.innerHTML = "";
      var box = el("div", "giris");
      live.appendChild(box);
      if (index >= items.length) {
        box.appendChild(el("p", "skor", fill(U.score, { n: score, t: items.length })));
        box.appendChild(el("p", "alt", U.scoreNote));
        var row = el("div", "secenekler");
        var go = el("a", "btn primary", U.table); go.href = "#etiketler";
        var again = el("button", "btn", U.again); again.type = "button";
        again.onclick = function () { items.sort(function () { return Math.random() - 0.5; }); index = 0; score = 0; marks = []; show(); };
        row.appendChild(go); row.appendChild(again); box.appendChild(row);
        return;
      }
      var item = items[index];
      box.appendChild(bar());
      box.appendChild(el("p", "alt", fill(U.step, { k: index + 1, n: items.length })));
      box.appendChild(el("p", "iddia", item.ad));
      var choices = el("div", "secenekler");
      order.forEach(function (slug) {
        var b = el("button", "btn", V.etiket[slug]); b.type = "button";
        b.onclick = function () { answer(slug, choices, box, item); };
        choices.appendChild(b);
      });
      box.appendChild(choices);
    }
    function answer(slug, choices, box, item) {
      var right = slug === item.durum;
      if (right) score++;
      marks[index] = right ? "tamam" : "yanlis";
      Array.prototype.forEach.call(choices.children, function (b) { b.disabled = true; });
      var res = el("div", "sonuc");
      var head = el("div");
      head.appendChild(el("span", right ? "dogru" : "yanlis", (right ? U.real : U.wrong) + " "));
      head.appendChild(badge(item.durum));
      res.appendChild(head);
      res.appendChild(el("p", null, item.neden));
      box.appendChild(res);
      var next = el("button", "btn primary sonuc-eylem", index + 1 >= items.length ? U.last : U.next); next.type = "button";
      next.onclick = function () { index++; show(); };
      box.appendChild(next);
      box.querySelector(".ilerleme").replaceWith(bar());
      next.focus();
    }
    show();
  })();

  /* ------------------------------------------------------------ örnek tarama */
  var scan = document.querySelector("[data-tarama]");
  if (scan) (function () {
    var btn = scan.querySelector("button.start"), bar = scan.querySelector(".cubuk i"), line = scan.querySelector(".durum-satir"),
        list = scan.querySelector(".bulgular");
    function run() {
      btn.disabled = true; btn.textContent = U.scanning; list.innerHTML = ""; bar.style.width = "0";
      var n = U.steps.length, i = 0;
      (function tick() {
        if (i < n) {
          line.textContent = U.steps[i] + "…"; bar.style.width = ((i + 1) / (n + 1) * 100) + "%"; i++; wait(tick, 520);
          return;
        }
        bar.style.width = "100%"; line.textContent = fill(U.done, { n: V.tarama.bulgular.length });
        V.tarama.bulgular.forEach(function (f, k) {
          wait(function () {
            var li = el("li", "bulgu giris");
            li.appendChild(el("h3", null, f.baslik)); li.appendChild(el("p", null, f.aciklama));
            var fix = el("button", "btn small", U.fix); fix.type = "button";
            fix.onclick = function () { li.classList.add("cozuldu"); fix.textContent = U.fixed; fix.disabled = true; };
            li.appendChild(fix); list.appendChild(li);
          }, k * 380);
        });
        wait(function () { btn.disabled = false; btn.textContent = U.rescan; }, V.tarama.bulgular.length * 380);
      })();
    }
    btn.addEventListener("click", run);
  })();

  /* ------------------------------------------------------------ geri alma */
  var undo = document.querySelector("[data-geri]");
  if (undo) (function () {
    var list = undo.querySelector(".degisiklikler"), btn = undo.querySelector("button.toggle"), chips = undo.querySelector(".zincir"),
        live = undo.querySelector("[data-live]");
    var applied = true;
    function render() {
      list.innerHTML = "";
      V.degisiklik.forEach(function (c) {
        var v = U.changed[c.id], li = el("li", applied ? "" : "geri");
        li.appendChild(el("span", "ad", c.ad));
        var val = el("span", "deger");
        if (applied) { val.appendChild(el("span", "eski", v[0])); val.appendChild(el("span", "yeni", v[1])); }
        else { val.appendChild(el("span", "yeni", v[0])); }
        li.appendChild(val); list.appendChild(li);
      });
      chips.innerHTML = "";
      [U.backup, U.restore].forEach(function (t) { chips.appendChild(el("span", "chip acik", "✓ " + t)); });
      if (!applied) chips.appendChild(el("span", "chip", U.reverted));
      btn.textContent = applied ? U.undoAll : U.redo;
    }
    btn.addEventListener("click", function () {
      applied = !applied; render(); live.textContent = applied ? "" : U.reverted;
    });
    render();
  })();

  /* ------------------------------------------------------------ ayar künyesi */
  var kunye = document.querySelector("[data-kunye]");
  if (kunye) (function () {
    var chips = el("div", "zincir"), card = el("div", "kunye-kart");
    chips.setAttribute("role", "group");
    kunye.appendChild(chips); kunye.appendChild(card);
    function row(k, v) { var r = el("div", "kunye-satir"); r.appendChild(el("b", null, k)); r.appendChild(el("span", null, v)); return r; }
    function show(item, btn) {
      Array.prototype.forEach.call(chips.children, function (c) { c.setAttribute("aria-pressed", c === btn ? "true" : "false"); });
      card.className = "kunye-kart giris r-" + item.durum;
      card.innerHTML = "";
      var head = el("div", "kunye-bas");
      head.appendChild(el("h3", null, item.ad)); head.appendChild(el("code", null, item.id)); head.appendChild(badge(item.durum));
      card.appendChild(head);
      card.appendChild(row(U.kEtki, item.etki)); card.appendChild(row(U.kRisk, item.risk));
      card.appendChild(row(U.kNeden, item.neden)); card.appendChild(row(U.kGeri, U.kGeriMetin));
      card.appendChild(el("p", "kunye-not", U.kKaynak));
    }
    V.kunye.forEach(function (item, i) {
      var b = el("button", "chip filtre", item.ad.length > 34 ? item.ad.slice(0, 32).trim() + "…" : item.ad); b.type = "button";
      b.style.setProperty("--rc", "var(--v-" + item.durum + ")");
      b.addEventListener("click", function () { show(item, b); });
      chips.appendChild(b);
      if (i === 0) show(item, b);
    });
  })();

  /* ------------------------------------------------------------ oyun denetimi */
  var oyun = document.querySelector("[data-oyun]");
  if (oyun) (function () {
    var input = oyun.querySelector("input"), chips = oyun.querySelector(".oyun-chipler"), out = oyun.querySelector(".oyun-sonuc");
    function norm(x) { return x.toLowerCase().replace(/[^a-z0-9ğüşıöç]+/g, ""); }
    function check() {
      var raw = input.value.trim();
      if (!raw) { out.textContent = U.oBos; out.className = "oyun-sonuc"; return; }
      var hit = V.oyunlar.filter(function (g) { return norm(g).indexOf(norm(raw)) >= 0 || norm(raw).indexOf(norm(g)) >= 0; })[0];
      out.textContent = fill(hit ? U.oVar : U.oYok, { ad: hit || raw });
      out.className = "oyun-sonuc " + (hit ? "var" : "yok");
    }
    V.oyunlar.forEach(function (g) {
      var b = el("button", "chip filtre", g); b.type = "button";
      b.addEventListener("click", function () { input.value = g; check(); });
      chips.appendChild(b);
    });
    input.addEventListener("input", check); check();
  })();

  /* ------------------------------------------------------------ fiyat süresi */
  var plan = document.querySelector("[data-sure]");
  if (plan) {
    // Düğme metinlerine hiç dokunulmaz (eski hata: [data-per] seçicisi ilk düğmeyi yakalayıp "1 ay" yazısını eziyordu).
    var buttons = Array.prototype.slice.call(plan.querySelectorAll("button[data-ay]")), price = document.querySelector("[data-aylik]"),
        bill = document.querySelector("[data-fatura]"), save = document.querySelector("[data-tasarruf]");
    var months = { 1: "fiyat1", 3: "fiyat3", 12: "fiyat12" }, locale = lang === "en" ? "en-US" : "tr-TR";
    // "$16 (~₺800)" -> { usd: 16, tl: 800 }
    function parse(raw) { var m = /^\$(\d+(?:\.\d+)?)\s*\(~₺([\d.]+)\)$/.exec(raw || ""); return m ? { usd: +m[1], tl: +m[2].replace(/\./g, "") } : null; }
    function money(n) { var d = n % 1 ? 2 : 0; return "$" + n.toLocaleString(locale, { minimumFractionDigits: d, maximumFractionDigits: d }); }
    var base = parse(cfg.fiyat1);
    function set(btn) {
      buttons.forEach(function (b) { b.setAttribute("aria-pressed", b === btn ? "true" : "false"); });
      var ay = +btn.dataset.ay, p = parse(cfg[months[ay]]);
      var amount = document.querySelectorAll("[data-al-tutar]");
      if (!p) {   // biçim tutmadı: eski tutar düğmede kalmasın
        price.textContent = lang === "en" ? "soon" : "yakında"; bill.textContent = ""; save.hidden = true;
        Array.prototype.forEach.call(amount, function (el) { el.textContent = ""; });
        return;
      }
      var monthly = Math.round(p.usd / ay * 100) / 100, pct = base ? Math.round((1 - p.usd / ay / base.usd) * 100) : 0;
      price.textContent = money(monthly);
      var total = money(p.usd) + " (~₺" + p.tl.toLocaleString(locale) + ")";
      bill.textContent = lang === "en"
        ? (ay === 1 ? "1 month" : ay + " months") + ", paid once: " + total + ". No auto-renewal."
        : ay + " ay için tek seferde " + total + " ödenir. Otomatik yenilenmez.";
      save.hidden = pct <= 0;
      save.textContent = lang === "en" ? "Save " + pct + "% vs monthly" : "1 aylığa göre %" + pct + " tasarruf";
      // Buy Me a Coffee'de tutar elle girilir: düğme seçilen toplamı gösterir
      Array.prototype.forEach.call(amount, function (el) { el.textContent = "(" + money(p.usd) + ")"; });
      save.classList.remove("yeni"); void save.offsetWidth; save.classList.add("yeni");
    }
    buttons.forEach(function (b) { b.addEventListener("click", function () { set(b); }); });
    set(buttons[0]);
  }
})();
