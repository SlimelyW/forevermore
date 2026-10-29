/* Demo penceresi (tahmin, tarama, geri alma), kanıt tablosu süzgeci ve fiyat süresi.
   Veri: veri.js (tools/site_veri.py, uygulamanın kendi dosyalarından). Betik yoksa tablo ve fiyatlar düz okunur. */
(function () {
  var lang = document.documentElement.lang === "en" ? "en" : "tr";
  var V = window.FM_VERI && window.FM_VERI[lang];
  var cfg = window.FOREVERMORE || {};
  var reduce = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  var U = {
    tr: {
      step: "{k} / {n}", real: "Doğru.", wrong: "Forevermore'da etiketi:", next: "Sonraki", last: "Sonucu gör",
      score: "{n} / {t} doğru", scoreNote: "Etiketlerin hepsi, gerekçeleriyle aşağıdaki tabloda.", table: "Tabloya git", again: "Tekrar oyna",
      scan: "Taramayı başlat", scanning: "Taranıyor…", rescan: "Yeniden tara", fix: "Çöz", fixed: "Çözüldü (örnek)",
      steps: ["Donanım okunuyor", "Ekran ve RAM okunuyor", "Başlangıç uygulamaları sayılıyor", "Bulgular sıralanıyor"],
      done: "{n} bulgu", machine: ["İşlemci", "Bellek", "Ekran kartı", "Monitör"],
      undoAll: "Hepsini geri al", redo: "Yeniden uygula", backup: "Yedek alındı", restore: "Geri yükleme noktası", reverted: "Geri alındı",
      changed: { "DISP-001": ["60 Hz", "144 Hz"], "SYS-006": ["14 uygulama", "6 uygulama"], "PERF-002": ["Kayıt açık", "Kayıt kapalı"] },
      shown: "{n} / {t} ayar"
    },
    en: {
      step: "{k} / {n}", real: "Correct.", wrong: "Forevermore labels it:", next: "Next", last: "See result",
      score: "{n} / {t} correct", scoreNote: "Every label, with its reason, is in the table below.", table: "Go to the table", again: "Play again",
      scan: "Start scan", scanning: "Scanning…", rescan: "Scan again", fix: "Fix", fixed: "Fixed (sample)",
      steps: ["Reading hardware", "Reading display and RAM", "Counting startup apps", "Sorting findings"],
      done: "{n} findings", machine: ["CPU", "Memory", "Graphics", "Monitor"],
      undoAll: "Undo all", redo: "Apply again", backup: "Backup taken", restore: "Restore point", reverted: "Reverted",
      changed: { "DISP-001": ["60 Hz", "144 Hz"], "SYS-006": ["14 apps", "6 apps"], "PERF-002": ["Recording on", "Recording off"] },
      shown: "{n} / {t} settings"
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
        var go = el("a", "btn primary", U.table); go.href = "#tablo";
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

  /* ------------------------------------------------------------ kanıt tablosu süzgeci */
  var table = document.querySelector("[data-tablo]");
  if (table) (function () {
    var rows = Array.prototype.slice.call(table.querySelectorAll("tbody tr")), q = table.querySelector("input[type=search]"),
        chips = Array.prototype.slice.call(table.querySelectorAll(".filtre")), out = table.querySelector("[data-say]"), f = "all";
    function apply() {
      var term = q.value.trim().toLowerCase(), n = 0;
      rows.forEach(function (r) {
        var ok = (f === "all" || r.dataset.d === f) && (!term || r.textContent.toLowerCase().indexOf(term) >= 0);
        r.hidden = !ok; if (ok) n++;
      });
      out.textContent = fill(U.shown, { n: n, t: rows.length });
    }
    chips.forEach(function (c) {
      c.addEventListener("click", function () {
        f = c.dataset.f; chips.forEach(function (o) { o.setAttribute("aria-pressed", o === c ? "true" : "false"); }); apply();
      });
    });
    q.addEventListener("input", apply); apply();
  })();

  /* ------------------------------------------------------------ fiyat süresi */
  var plan = document.querySelector("[data-sure]");
  if (plan) {
    var buttons = Array.prototype.slice.call(plan.querySelectorAll("button")), price = document.querySelector("[data-fiyat]"),
        tl = document.querySelector("[data-tl]"), per = document.querySelector("[data-per]");
    var months = { 1: "fiyat1", 3: "fiyat3", 12: "fiyat12" };
    function set(btn) {
      buttons.forEach(function (b) { b.setAttribute("aria-pressed", b === btn ? "true" : "false"); });
      var raw = cfg[months[btn.dataset.ay]] || "", m = raw.match(/^(\S+)\s*\((.*)\)$/);
      price.textContent = m ? m[1] : raw || (lang === "en" ? "soon" : "yakında");
      tl.textContent = m ? m[2] : "";
      per.textContent = btn.dataset.per;
    }
    buttons.forEach(function (b) { b.addEventListener("click", function () { set(b); }); });
    set(buttons[0]);
  }
})();
