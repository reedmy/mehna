/* مهنة — progressive enhancement only. Nothing here is required to read a page. */

(function () {
  "use strict";

  // ── HTMX: send the CSRF token with every non-GET request ──
  document.body.addEventListener("htmx:configRequest", function (event) {
    var meta = document.querySelector('meta[name="csrf-token"]');
    if (meta && event.detail.verb !== "get") {
      event.detail.headers["X-CSRFToken"] = meta.getAttribute("content");
    }
  });

  // ── Dropdowns ────────────────────────────────────────────
  document.addEventListener("click", function (event) {
    var toggle = event.target.closest("[data-dropdown-toggle]");
    var panel = event.target.closest("[data-dropdown-panel]");

    document.querySelectorAll("[data-dropdown-panel].is-open").forEach(function (open) {
      if (!panel || open !== panel) open.classList.remove("is-open");
    });

    if (toggle) {
      var target = toggle.parentElement.querySelector("[data-dropdown-panel]");
      if (target) {
        var willOpen = !target.classList.contains("is-open");
        target.classList.toggle("is-open", willOpen);
        toggle.setAttribute("aria-expanded", String(willOpen));
      }
    }
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") {
      document.querySelectorAll("[data-dropdown-panel].is-open").forEach(function (p) {
        p.classList.remove("is-open");
      });
      var filters = document.getElementById("filters");
      if (filters) filters.classList.remove("is-open");
    }
  });

  // ── Flash messages: auto-dismiss after 6s ────────────────
  document.querySelectorAll("#flash-stack .flash").forEach(function (node) {
    setTimeout(function () {
      node.style.transition = "opacity .3s, transform .3s";
      node.style.opacity = "0";
      node.style.transform = "translateY(-6px)";
      setTimeout(function () { node.remove(); }, 320);
    }, 6000);
  });

  // ── Password visibility toggle ───────────────────────────
  document.querySelectorAll("[data-password-toggle]").forEach(function (button) {
    button.addEventListener("click", function () {
      var input = document.getElementById(button.getAttribute("data-password-toggle"));
      if (!input) return;
      input.type = input.type === "password" ? "text" : "password";
      button.textContent = input.type === "password" ? "إظهار" : "إخفاء";
    });
  });

  // ── Submit buttons: prevent double submit ────────────────
  document.querySelectorAll("form").forEach(function (form) {
    form.addEventListener("submit", function () {
      var button = form.querySelector('button[type="submit"]');
      if (!button) return;
      setTimeout(function () {
        button.disabled = true;
        button.dataset.label = button.textContent;
        button.textContent = "جارٍ…";
      }, 0);
    });
  });

  // ── Re-enable buttons when the page is restored from bfcache ──
  window.addEventListener("pageshow", function () {
    document.querySelectorAll('button[type="submit"][disabled]').forEach(function (button) {
      button.disabled = false;
      if (button.dataset.label) button.textContent = button.dataset.label;
    });
  });
})();
