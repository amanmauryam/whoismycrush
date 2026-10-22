/* Pro Tips reading polish: progress bar, copy-link, active table of contents. */

(function () {
  "use strict";

  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function onReady(fn) {
    if (document.readyState !== "loading") fn();
    else document.addEventListener("DOMContentLoaded", fn);
  }

  function readingProgress() {
    var track = document.querySelector("[data-reading-progress]");
    var article = document.querySelector("[data-article-body]");
    if (!track || !article) return;
    var fill = track.querySelector("span");
    if (!fill) return;

    var ticking = false;

    function update() {
      var rect = article.getBoundingClientRect();
      var top = window.scrollY + rect.top;
      var height = Math.max(1, article.offsetHeight);
      var read = window.scrollY + window.innerHeight - top;
      var percent = Math.max(0, Math.min(1, read / height));
      fill.style.width = (percent * 100).toFixed(2) + "%";
      ticking = false;
    }

    function requestUpdate() {
      if (ticking) return;
      ticking = true;
      window.requestAnimationFrame(update);
    }

    update();
    window.addEventListener("scroll", requestUpdate, { passive: true });
    window.addEventListener("resize", requestUpdate);
  }

  function copyLink() {
    var buttons = Array.prototype.slice.call(
      document.querySelectorAll("[data-copy-link]")
    );
    if (!buttons.length) return;

    function legacyCopy(text) {
      var area = document.createElement("textarea");
      area.value = text;
      area.setAttribute("readonly", "");
      area.style.position = "fixed";
      area.style.top = "-9999px";
      document.body.appendChild(area);
      area.select();
      var copied = false;
      try {
        copied = document.execCommand("copy");
      } catch (error) {
        copied = false;
      }
      document.body.removeChild(area);
      return copied;
    }

    function flash(button, label) {
      var text = button.querySelector("span");
      if (!text) return;
      var original = text.textContent;
      text.textContent = label;
      window.setTimeout(function () {
        text.textContent = original;
      }, 2200);
    }

    buttons.forEach(function (button) {
      button.addEventListener("click", function () {
        var url = button.getAttribute("data-copy-url") || window.location.href;
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard
            .writeText(url)
            .then(function () {
              flash(button, "Copied ✓");
            })
            .catch(function () {
              flash(button, legacyCopy(url) ? "Copied ✓" : "Copy failed");
            });
        } else {
          flash(button, legacyCopy(url) ? "Copied ✓" : "Copy failed");
        }
      });
    });
  }

  function activeToc() {
    var body = document.querySelector("[data-article-body]");
    if (!body) return;
    var headings = Array.prototype.slice.call(
      body.querySelectorAll("h2[id], h3[id]")
    );
    if (!headings.length || !("IntersectionObserver" in window)) return;

    var links = {};
    Array.prototype.slice
      .call(document.querySelectorAll(".toc-link"))
      .forEach(function (link) {
        links[link.getAttribute("href").slice(1)] = link;
      });

    if (!Object.keys(links).length) return;

    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting) return;
          Object.keys(links).forEach(function (id) {
            links[id].classList.toggle("is-active", id === entry.target.id);
          });
        });
      },
      { rootMargin: "-18% 0px -68% 0px", threshold: 0 }
    );

    headings.forEach(function (heading) {
      observer.observe(heading);
    });
  }

  onReady(function () {
    readingProgress();
    copyLink();
    if (!reduceMotion) activeToc();
  });
})();
