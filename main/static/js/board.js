/* ==========================================================================
   WhoIsMyCrush — board behaviour
   Small, dependency-free, mobile-first. Everything degrades gracefully:
   the secret desk is a plain server-rendered form, this only adds polish.
   ========================================================================== */

(function () {
  "use strict";

  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function onReady(fn) {
    if (document.readyState !== "loading") fn();
    else document.addEventListener("DOMContentLoaded", fn);
  }

  function $(sel, root) {
    return (root || document).querySelector(sel);
  }

  function $$(sel, root) {
    return Array.prototype.slice.call((root || document).querySelectorAll(sel));
  }

  /* ---- Mobile navigation ------------------------------------------------ */

  function mobileNav() {
    var toggle = $("[data-nav-toggle]");
    var links = $("#nav-links");
    if (!toggle || !links) return;

    function setOpen(open) {
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
      links.classList.toggle("is-open", open);
    }

    toggle.addEventListener("click", function () {
      setOpen(toggle.getAttribute("aria-expanded") !== "true");
    });

    document.addEventListener("click", function (event) {
      if (toggle.getAttribute("aria-expanded") !== "true") return;
      if (links.contains(event.target) || toggle.contains(event.target)) return;
      setOpen(false);
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") setOpen(false);
    });

    window.addEventListener("resize", function () {
      if (window.innerWidth >= 760) setOpen(false);
    });
  }

  /* ---- Toasts ----------------------------------------------------------- */

  function toasts() {
    var items = $$(".toast");
    if (!items.length) return;
    var life = reduceMotion ? 2600 : 5200;
    items.forEach(function (toast) {
      setTimeout(function () {
        toast.style.transition = "opacity 200ms, transform 200ms";
        toast.style.opacity = "0";
        toast.style.transform = "translateY(-6px)";
        setTimeout(function () {
          if (toast.parentNode) toast.parentNode.removeChild(toast);
        }, 220);
      }, life);
    });
  }

  /* ---- Destructive action guard ---------------------------------------- */

  function confirms() {
    $$("[data-confirm]").forEach(function (el) {
      el.addEventListener("click", function (event) {
        if (!window.confirm(el.getAttribute("data-confirm"))) event.preventDefault();
      });
    });
  }

  /* ---- Campus search: submit on the go --------------------------------- */

  function instantSearch() {
    var form = $(".picker-search");
    if (!form) return;
    var input = form.querySelector("input[type='text'], input[name='q']");
    if (!input) return;

    var timer = null;
    input.addEventListener("input", function () {
      clearTimeout(timer);
      timer = setTimeout(function () {
        form.submit();
      }, 650);
    });
    input.form.addEventListener("submit", function () {
      clearTimeout(timer);
    });
  }

  /* ---- Mutual reveal: WAIT. ... IT'S MUTUAL. --------------------------- */

  function revealDramaticPause() {
    var stage = $("[data-reveal]");
    if (!stage || reduceMotion) {
      $$("[data-reveal-final]").forEach(function (el) {
        el.hidden = false;
      });
      if (stage) {
        $$("[data-reveal-first], [data-reveal-second]").forEach(function (el) {
          el.hidden = false;
        });
      }
      return;
    }

    var first = $("[data-reveal-first]", stage);
    var second = $("[data-reveal-second]", stage);
    var finalBlock = $("[data-reveal-final]");
    var hold = parseInt(stage.getAttribute("data-countdown"), 10) || 1600;

    if (first) first.hidden = false;
    if (second) second.hidden = true;

    setTimeout(function () {
      if (first) first.hidden = true;
      if (second) {
        second.hidden = false;
        second.style.animation = "pop 600ms cubic-bezier(0.2,0.7,0.3,1) both";
      }
    }, hold);

    setTimeout(function () {
      stage.hidden = true;
      $$("[data-reveal-final]").forEach(function (el) {
        el.hidden = false;
      });
    }, hold + 1100);
  }

  /* ---- Slot selection feedback ---------------------------------------- */

  function stampSlots() {
    $$(".slot.is-empty").forEach(function (slot) {
      slot.addEventListener("click", function (event) {
        if (event.target.closest("a, button, input")) return;
        slot.style.transform = "rotate(-1deg) scale(0.99)";
        setTimeout(function () {
          slot.style.transform = "";
        }, 220);
      });
    });
  }

  onReady(function () {
    mobileNav();
    toasts();
    confirms();
    instantSearch();
    revealDramaticPause();
    stampSlots();
  });
})();