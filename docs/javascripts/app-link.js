/*
 * When these pages are served by the NewSEGS app (under /documentation/), add a link
 * in the header that returns to the app launch page. On GitHub Pages there is no
 * app to return to, so nothing is added.
 */
(function () {
  var APP_DOCS_PREFIX = "/documentation/";
  if (window.location.pathname.indexOf(APP_DOCS_PREFIX) !== 0) {
    return;
  }

  function addLink() {
    var header = document.querySelector(".md-header__inner");
    if (!header || header.querySelector(".newsegs-app-link")) {
      return;
    }
    var link = document.createElement("a");
    link.className = "md-header__button newsegs-app-link";
    link.href = "/";
    link.title = "Return to the NewSEGS app";
    link.textContent = "Back to the app";
    link.style.cssText = "align-self:center;font-size:.7rem;font-weight:700;white-space:nowrap;color:inherit;";
    var search = header.querySelector(".md-search");
    header.insertBefore(link, search);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", addLink);
  } else {
    addLink();
  }
})();
