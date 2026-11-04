/* Okuma modu (disleksi / DEHB): aç/kapa, yazı tipi, yazı boyutu, okuma çizgisi, ilerleme çubuğu.
   Tercihler yalnızca bu tarayıcıda (localStorage). Kayıtlı tercihi ilk çizimden önce <head> içindeki küçük betik uygular. */
(function () {
  var root = document.documentElement, en = root.lang === "en";
  var K = { on: "forevermore-okunabilir", font: "forevermore-ok-font", size: "forevermore-ok-boyut", line: "forevermore-ok-cizgi" };
  function get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function put(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* özel pencere: kalıcı olmaz */ } }
  var SIZES = [18, 20, 22, 24, 26];
  // Lexend varsayılan: Atkinson Hyperlegible'da büyük İ ve ₺ yok (o harfler Verdana ile çizilir)
  var FONTS = [["lexend", "Lexend", "Lexend"], ["atkinson", "Atkinson Hyperlegible", "Atkinson Hyperlegible"], ["opendyslexic", "OpenDyslexic", "OpenDyslexic"]];
  var T = en
    ? { panel: "Reading settings", font: "Typeface", def: " (default)", size: "Text size", smaller: "Smaller text", bigger: "Larger text",
        line: "Reading line (a fixed band on screen; scroll the text through it)", close: "Close", settings: "Reading settings", note: {} }
    : { panel: "Okuma ayarları", font: "Yazı tipi", def: " (varsayılan)", size: "Yazı boyutu", smaller: "Yazıyı küçült", bigger: "Yazıyı büyüt",
        line: "Okuma çizgisi (ekranda sabit bir bant; metni kaydırarak içinden geçirin)", close: "Kapat", settings: "Okuma ayarları",
        note: { atkinson: "Büyük İ harfi bu yazı tipinde yok; o harf Verdana ile görünür." } };
  var size = +get(K.size);
  var state = { on: get(K.on) === "1", font: get(K.font) || "lexend", size: SIZES.indexOf(size) >= 0 ? size : 20, line: get(K.line) === "1" };
  if (!FONTS.some(function (f) { return f[0] === state.font; })) state.font = "lexend";

  function flag(name, on) { if (on) root.setAttribute(name, ""); else root.removeAttribute(name); }
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text) e.textContent = text; return e; }

  // ilerleme çubuğu ve okuma çizgisi (yalnızca okuma modunda görünür)
  var bar = el("div", "ok-ilerleme"), barFill = el("i"); bar.setAttribute("aria-hidden", "true"); bar.appendChild(barFill);
  var ruler = el("div", "ok-cizgi"); ruler.setAttribute("aria-hidden", "true");
  document.body.appendChild(bar); document.body.appendChild(ruler);
  var queued = false;
  function progress() {
    queued = false;
    var max = root.scrollHeight - innerHeight;
    barFill.style.transform = "scaleX(" + (max > 0 ? Math.min(1, scrollY / max) : 1) + ")";
  }
  addEventListener("scroll", function () { if (state.on && !queued) { queued = true; requestAnimationFrame(progress); } }, { passive: true });
  function moveRuler(y) { ruler.style.transform = "translateY(" + Math.round(y - ruler.offsetHeight / 2) + "px)"; }
  // okuma çizgisi ekranda sabit bir banttır (imleci izlemez); metin kaydırılarak içinden geçirilir
  addEventListener("resize", function () { if (state.on && state.line) moveRuler(innerHeight * 0.4); });

  var button = document.querySelector("[data-a11y]"), gear, panel, out, minus, plus;
  function apply(announce) {
    flag("data-okunabilir", state.on); flag("data-ok-cizgi", state.line);
    root.setAttribute("data-ok-font", state.font); root.setAttribute("data-ok-boyut", String(state.size));
    if (button) { button.setAttribute("aria-pressed", state.on ? "true" : "false"); gear.hidden = !state.on; }
    if (!state.on && panel) close(false);
    if (out) {
      out.textContent = state.size + " px";
      minus.disabled = state.size === SIZES[0]; plus.disabled = state.size === SIZES[SIZES.length - 1];
    }
    if (state.on) { progress(); if (state.line) moveRuler(innerHeight * 0.4); }
    if (announce) document.dispatchEvent(new Event("forevermore:okuma"));
  }
  if (!button) { apply(false); return; }

  /* ---------------------------------------------- başlıktaki düğmeler ve ayar paneli */
  var wrap = el("span", "okuma"); button.parentNode.insertBefore(wrap, button); wrap.appendChild(button);
  button.removeAttribute("title");
  button.insertAdjacentHTML("afterbegin", '<svg class="ikon" viewBox="0 0 24 24" aria-hidden="true"><path d="M3 5.5c3-1.3 6-1.3 9 .7 3-2 6-2 9-.7v13c-3-1.3-6-1.3-9 .7-3-2-6-2-9-.7z"/><path d="M12 6.2v13"/></svg>');
  gear = el("button", "a11y ok-ayar", "Aa"); gear.type = "button";
  gear.setAttribute("aria-label", T.settings); gear.setAttribute("aria-expanded", "false"); gear.setAttribute("aria-controls", "ok-panel");
  wrap.appendChild(gear);

  panel = el("div", "ok-panel"); panel.id = "ok-panel"; panel.hidden = true;
  panel.setAttribute("role", "group"); panel.setAttribute("aria-label", T.panel);
  var fs = el("fieldset"); fs.appendChild(el("legend", "", T.font));
  FONTS.forEach(function (f, k) {
    var lab = el("label", "ok-secenek"), input = el("input"), name = el("span", "", f[1] + (k === 0 ? T.def : ""));
    input.type = "radio"; input.name = "ok-font"; input.value = f[0]; input.checked = state.font === f[0];
    name.style.fontFamily = '"' + f[2] + '", Verdana, sans-serif';
    input.addEventListener("change", function () { state.font = f[0]; put(K.font, f[0]); apply(true); });
    lab.appendChild(input); lab.appendChild(name);
    if (T.note[f[0]]) { name.appendChild(document.createElement("br")); name.appendChild(el("small", "ok-not", T.note[f[0]])); }
    fs.appendChild(lab);
  });
  panel.appendChild(fs);
  var fs2 = el("fieldset"); fs2.appendChild(el("legend", "", T.size));
  var row = el("div", "ok-boyut");
  minus = el("button", "", "A−"); minus.type = "button"; minus.setAttribute("aria-label", T.smaller);
  plus = el("button", "", "A+"); plus.type = "button"; plus.setAttribute("aria-label", T.bigger);
  out = el("output"); out.setAttribute("aria-live", "polite");
  function step(d) { var i = SIZES.indexOf(state.size) + d; if (i < 0 || i >= SIZES.length) return; state.size = SIZES[i]; put(K.size, String(state.size)); apply(true); }
  minus.addEventListener("click", function () { step(-1); }); plus.addEventListener("click", function () { step(1); });
  row.appendChild(minus); row.appendChild(out); row.appendChild(plus); fs2.appendChild(row); panel.appendChild(fs2);
  var lineLab = el("label", "ok-secenek"), lineBox = el("input");
  lineBox.type = "checkbox"; lineBox.checked = state.line;
  lineBox.addEventListener("change", function () { state.line = lineBox.checked; put(K.line, state.line ? "1" : "0"); apply(true); });
  lineLab.appendChild(lineBox); lineLab.appendChild(el("span", "", T.line)); panel.appendChild(lineLab);
  var closeBtn = el("button", "btn ok-kapat", T.close); closeBtn.type = "button";
  closeBtn.style.marginTop = "12px"; closeBtn.addEventListener("click", function () { close(true); });
  panel.appendChild(closeBtn);
  wrap.appendChild(panel);

  function open() { panel.hidden = false; gear.setAttribute("aria-expanded", "true"); var c = panel.querySelector("input:checked"); if (c) c.focus(); }
  function close(focusBack) { panel.hidden = true; gear.setAttribute("aria-expanded", "false"); if (focusBack) gear.focus(); }
  gear.addEventListener("click", function () { if (panel.hidden) open(); else close(true); });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape" && !panel.hidden) close(true); });
  document.addEventListener("click", function (e) { if (!panel.hidden && !wrap.contains(e.target)) close(false); });

  button.addEventListener("click", function () {
    state.on = !state.on; put(K.on, state.on ? "1" : "0"); apply(true);
    if (state.on) open();   // ilk açılışta ayarlar görünsün
  });
  apply(false);
})();
