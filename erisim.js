/* Okunabilir yazı düğmesi (Aa). Demo ve tablo betiği: demo.js. */
(function () {
  var root = document.documentElement;
  var KEY = "forevermore-okunabilir";
  function stored() { try { return localStorage.getItem(KEY) === "1"; } catch (e) { return false; } }
  function save(on) { try { localStorage.setItem(KEY, on ? "1" : "0"); } catch (e) { /* özel pencere: kalıcı olmaz */ } }
  function apply(on, button) {
    if (on) root.setAttribute("data-okunabilir", ""); else root.removeAttribute("data-okunabilir");
    if (button) button.setAttribute("aria-pressed", on ? "true" : "false");
  }
  var button = document.querySelector("[data-a11y]");
  if (!button) return;
  apply(stored(), button);
  button.addEventListener("click", function () {
    var on = !root.hasAttribute("data-okunabilir");
    apply(on, button);
    save(on);
  });
})();
