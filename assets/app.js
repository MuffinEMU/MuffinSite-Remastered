/*!
 * MuffinEMU site — interaction layer.
 *
 * One rAF-throttled scroll loop drives everything scroll-linked (header
 * state, progress line, parallax, the pinned feature rail). Reveals use
 * IntersectionObserver. Pointer effects only run on fine pointers, and
 * nothing here runs its motion under prefers-reduced-motion.
 */
(function () {
  "use strict";

  var doc = document, root = doc.documentElement, body = doc.body;
  var T = window.MuffinThemes;
  var base = body.getAttribute("data-base") || "";
  var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var finePointer = window.matchMedia("(hover: hover) and (pointer: fine)").matches;
  root.classList.remove("no-js");

  function $(s, c) { return (c || doc).querySelector(s); }
  function $$(s, c) { return Array.prototype.slice.call((c || doc).querySelectorAll(s)); }

  /* ---------------------------------------------------------- toast */
  var toastEl, toastTimer;
  function toast(msg) {
    if (!toastEl) {
      toastEl = doc.createElement("div");
      toastEl.className = "toast";
      toastEl.setAttribute("role", "status");
      body.appendChild(toastEl);
    }
    toastEl.textContent = msg;
    toastEl.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { toastEl.classList.remove("show"); }, 2200);
  }

  /* ------------------------------------------- theme + mode switching */
  // A circular reveal from the point of interaction when View Transitions
  // exist; otherwise the registered colour properties cross-fade.
  function withReveal(evt, fn) {
    if (reduced || !doc.startViewTransition) { fn(); return; }
    var x = window.innerWidth / 2, y = 80;
    if (evt && evt.clientX) { x = evt.clientX; y = evt.clientY; }
    else if (evt && evt.currentTarget && evt.currentTarget.getBoundingClientRect) {
      var r = evt.currentTarget.getBoundingClientRect(); x = r.left + r.width / 2; y = r.top + r.height / 2;
    }
    var rr = Math.hypot(Math.max(x, window.innerWidth - x), Math.max(y, window.innerHeight - y));
    root.style.setProperty("--rx", x + "px");
    root.style.setProperty("--ry", y + "px");
    root.style.setProperty("--rr", rr + "px");
    root.classList.add("theme-reveal");
    var vt = doc.startViewTransition(fn);
    vt.finished.finally(function () { root.classList.remove("theme-reveal"); });
  }
  function setTheme(id, evt) {
    withReveal(evt, function () { T.setById(id, true); });
  }

  var modeBtn = $("[data-mode-cycle]");
  if (modeBtn) {
    var order = ["auto", "dark", "light"];
    function labelMode() { modeBtn.setAttribute("aria-label", "Colour mode: " + T.getMode() + ". Change"); }
    labelMode();
    modeBtn.addEventListener("click", function (e) {
      var next = order[(order.indexOf(T.getMode()) + 1) % order.length];
      withReveal(e, function () { T.setMode(next, true); });
      labelMode();
      toast("Mode: " + next);
    });
  }

  /* ---------------------------------------------------- mobile nav */
  var navToggle = $("[data-nav-toggle]");
  if (navToggle) {
    navToggle.addEventListener("click", function () {
      var open = body.classList.toggle("nav-open");
      navToggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }
  doc.addEventListener("click", function (e) {
    $$(".nav-dropdown[open]").forEach(function (d) { if (!d.contains(e.target)) d.removeAttribute("open"); });
    if (body.classList.contains("nav-open") && !e.target.closest(".site-header")) {
      body.classList.remove("nav-open");
      if (navToggle) navToggle.setAttribute("aria-expanded", "false");
    }
  });

  /* ----------------------------------------------------- scroll loop */
  var header = $(".site-header");
  var heroVisual = $(".hero-visual");
  var rail = $("[data-rail]");
  var railTrack = rail && $(".rail-track", rail);
  var railCount = rail && $("[data-rail-index]", rail);
  var railCards = railTrack ? $$(".card", railTrack) : [];
  var railActive = matchMedia("(min-width: 901px)");
  var railDistance = 0;

  function sizeRail() {
    if (!rail) return;
    if (reduced || !railActive.matches) { rail.style.height = ""; railDistance = 0; railTrack.style.removeProperty("--rail-x"); return; }
    railDistance = Math.max(0, railTrack.scrollWidth - window.innerWidth);
    rail.style.height = (window.innerHeight + railDistance) + "px";
  }

  var ticking = false;
  function onScroll() {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(function () {
      ticking = false;
      var sy = window.scrollY;
      var max = Math.max(1, root.scrollHeight - window.innerHeight);
      root.style.setProperty("--progress", (sy / max).toFixed(4));
      if (header) body.classList.toggle("scrolled", sy > 24);
      if (!reduced) root.style.setProperty("--sy", Math.min(sy, 2000).toFixed(1));
      if (rail && railDistance > 0) {
        var top = rail.getBoundingClientRect().top;
        var p = Math.min(1, Math.max(0, -top / railDistance));
        railTrack.style.setProperty("--rail-x", (-p * railDistance).toFixed(1) + "px");
        rail.style.setProperty("--rail", p.toFixed(4));
        if (railCount && railCards.length) {
          var n = Math.min(railCards.length, Math.round(p * (railCards.length - 1)) + 1);
          railCount.textContent = (n < 10 ? "0" : "") + n;
        }
      }
    });
  }
  sizeRail();
  onScroll();
  window.addEventListener("scroll", onScroll, { passive: true });
  window.addEventListener("resize", function () { sizeRail(); onScroll(); });
  railActive.addEventListener && railActive.addEventListener("change", function () { sizeRail(); onScroll(); });
  if (doc.fonts && doc.fonts.ready) doc.fonts.ready.then(function () { sizeRail(); onScroll(); });

  /* --------------------------------------------------------- reveals */
  var revealEls = $$("[data-reveal]");
  if (reduced || !("IntersectionObserver" in window)) {
    revealEls.forEach(function (el) { el.classList.add("in"); });
  } else {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) { en.target.classList.add("in"); io.unobserve(en.target); }
      });
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.12 });
    revealEls.forEach(function (el) { io.observe(el); });
  }
  // Stagger siblings that share a [data-stagger] parent.
  $$("[data-stagger]").forEach(function (p) {
    $$(":scope > [data-reveal]", p).forEach(function (el, i) { el.style.setProperty("--i", i); });
  });

  /* ------------------------------------------------ split wordmark */
  $$("[data-split]").forEach(function (el) {
    if (reduced) return;
    var i = 0;
    function walk(node) {
      Array.prototype.slice.call(node.childNodes).forEach(function (c) {
        if (c.nodeType === 3) {
          var frag = doc.createDocumentFragment();
          c.textContent.split("").forEach(function (ch) {
            var s = doc.createElement("span");
            s.className = "ch"; s.textContent = ch; s.style.setProperty("--i", i++);
            s.setAttribute("aria-hidden", "true");
            frag.appendChild(s);
          });
          node.replaceChild(frag, c);
        } else if (c.nodeType === 1) walk(c);
      });
    }
    el.setAttribute("aria-label", el.textContent);
    el.classList.add("split");
    walk(el);
    // Transformed letters can't share the parent's background-clip: text, so
    // each letter gets the gradient sized and offset to its parent's box...
    var chars = $$(".ch", el);
    chars.forEach(function (c) {
      var host = c.parentNode, hb = host.getBoundingClientRect(), cb = c.getBoundingClientRect();
      c.style.setProperty("--bw", hb.width + "px");
      c.style.setProperty("--bx", (hb.left - cb.left) + "px");
    });
    // ...and once the intro has played, the spans are unwrapped so the
    // original gradient (and its sheen animation) takes over seamlessly.
    var last = chars[chars.length - 1];
    if (last) last.addEventListener("animationend", function () {
      $$("*", el).concat([el]).forEach(function (n) { n.normalize && n.normalize(); });
      chars.forEach(function (c) { c.replaceWith(doc.createTextNode(c.textContent)); });
      el.normalize();
      el.classList.remove("split");
    });
  });

  /* ------------------------------------------------- pointer effects */
  if (finePointer && !reduced) {
    doc.addEventListener("pointermove", function (e) {
      var card = e.target.closest && e.target.closest(".card");
      if (card) {
        var r = card.getBoundingClientRect();
        card.style.setProperty("--x", (e.clientX - r.left) + "px");
        card.style.setProperty("--y", (e.clientY - r.top) + "px");
      }
    }, { passive: true });

    $$(".btn").forEach(function (b) {
      b.addEventListener("pointermove", function (e) {
        var r = b.getBoundingClientRect();
        b.style.setProperty("--mx", ((e.clientX - r.left - r.width / 2) * 0.18).toFixed(1) + "px");
        b.style.setProperty("--my", ((e.clientY - r.top - r.height / 2) * 0.28).toFixed(1) + "px");
      });
      b.addEventListener("pointerleave", function () { b.style.setProperty("--mx", "0px"); b.style.setProperty("--my", "0px"); });
    });

    if (heroVisual) {
      var icon = $(".hero-icon", heroVisual);
      heroVisual.addEventListener("pointermove", function (e) {
        var r = heroVisual.getBoundingClientRect();
        var px = (e.clientX - r.left) / r.width - 0.5, py = (e.clientY - r.top) / r.height - 0.5;
        icon.style.setProperty("--tiltY", (px * 22).toFixed(1) + "deg");
        icon.style.setProperty("--tiltX", (-py * 22).toFixed(1) + "deg");
      });
      heroVisual.addEventListener("pointerleave", function () {
        icon.style.setProperty("--tiltY", "0deg"); icon.style.setProperty("--tiltX", "0deg");
      });
    }
  }

  /* ------------------------------------------------------ count-up */
  $$("[data-count]").forEach(function (el) {
    var target = parseInt(el.getAttribute("data-count"), 10);
    var suffix = el.getAttribute("data-suffix") || "";
    if (reduced || !("IntersectionObserver" in window)) { el.textContent = target + suffix; return; }
    el.textContent = "0" + suffix;
    var o = new IntersectionObserver(function (en) {
      if (!en[0].isIntersecting) return;
      o.disconnect();
      var t0 = performance.now(), dur = 1400;
      (function step(now) {
        var k = Math.min(1, (now - t0) / dur);
        var eased = 1 - Math.pow(1 - k, 4);
        el.textContent = Math.round(target * eased) + suffix;
        if (k < 1) requestAnimationFrame(step);
      })(t0);
    }, { threshold: 0.6 });
    o.observe(el);
  });

  /* --------------------------------------------------- copy buttons */
  $$("[data-copy]").forEach(function (b) {
    b.addEventListener("click", function () {
      var text = b.getAttribute("data-copy");
      (navigator.clipboard ? navigator.clipboard.writeText(text) : Promise.reject())
        .then(function () { toast("Source URL copied"); })
        .catch(function () { toast(text); });
    });
  });

  /* ------------------------------------------------------ theme lab */
  function swatchOf(t) {
    if (t.stops) return "conic-gradient(" + t.stops.light.slice(0, 7).concat(t.stops.light[0]).join(", ") + ")";
    return "linear-gradient(135deg, " + t.top[0] + ", " + t.bottom[0] + ")";
  }
  // The app's real background for the current mode.
  function previewBg(t) { return T.backgroundOf(t, T.isLight()); }

  var orbs = $("[data-orbs]");
  var lab = $("[data-lab]");
  if (orbs) {
    T.THEMES.forEach(function (t) {
      var b = doc.createElement("button");
      b.type = "button";
      b.className = "orb-btn";
      b.style.setProperty("--sw", swatchOf(t));
      b.setAttribute("data-theme-option", t.id);
      b.setAttribute("aria-label", t.name + (t.pro ? " (Pro)" : ""));
      b.title = t.name;
      if (t.pro) { var s = doc.createElement("span"); s.className = "pro"; s.textContent = "PRO"; s.setAttribute("aria-hidden", "true"); b.appendChild(s); }
      b.addEventListener("click", function (e) { setTheme(t.id, e); });
      orbs.appendChild(b);
    });
  }

  /* -------------------------------------------- docs: themes grid */
  var themeGrid = $("#themeGrid");
  if (themeGrid) {
    T.THEMES.forEach(function (t) {
      var b = doc.createElement("button");
      b.type = "button"; b.className = "theme-swatch"; b.title = "Apply " + t.name;
      b.setAttribute("data-theme-option", t.id);
      var bg = doc.createElement("div"); bg.className = "swatch-bg";
      b._bg = bg; b._theme = t;
      var label = doc.createElement("div"); label.className = "swatch-label";
      var nm = doc.createElement("span"); nm.textContent = t.name; label.appendChild(nm);
      if (t.pro) { var p = doc.createElement("span"); p.className = "pro-badge"; p.textContent = "Pro"; label.appendChild(p); }
      b.appendChild(bg); b.appendChild(label);
      b.addEventListener("click", function (e) { setTheme(t.id, e); });
      themeGrid.appendChild(b);
    });
  }

  function syncTheme(t) {
    var k = T.isLight() ? 0 : 1;
    $$("[data-theme-option]").forEach(function (el) {
      el.setAttribute("aria-pressed", el.getAttribute("data-theme-option") === t.id ? "true" : "false");
      if (el._bg) el._bg.style.background = previewBg(el._theme);
    });
    $$("[data-theme-name]").forEach(function (el) { el.textContent = t.name; });
    var heroIcon = $(".hero-icon");
    if (heroIcon) swapImg(heroIcon, "hero-img", iconSrc(t), 512);
    if (lab) {
      // The preview is a small piece of the app in this theme: its background,
      // a card (cream, wrapper stroke, brown text) and a primary button
      // (muffinTopGradient with sparkleCream text).
      lab.style.setProperty("--lab-bg", previewBg(t));
      lab.style.setProperty("--lp-card", t.cream[k]);
      lab.style.setProperty("--lp-stroke", t.wrapper[k]);
      lab.style.setProperty("--lp-text", t.brownDarkest[k]);
      lab.style.setProperty("--lp-sub", t.brownMid[k]);
      lab.style.setProperty("--lp-b1", t.muffinTop[k]);
      lab.style.setProperty("--lp-b2", t.muffinDark[k]);
      lab.style.setProperty("--lp-on", T.buttonText(t, k));
      var sw = $$(".lp-swatches i", lab);
      [[t.top, "Background"], [t.muffinTop, "Buttons"], [t.cream, "Cards"], [t.pixel, "Accent"]].forEach(function (p, i) {
        if (sw[i]) { sw[i].style.background = p[0][k]; sw[i].title = p[1] + " " + p[0][k]; }
      });
      var stage = $(".lp-stage", lab), mini = $(".lp-mini", lab);
      if (stage) swapImg(stage, "lp-icon", iconSrc(t), 192);
      if (mini) mini.src = iconSrc(t);
      var nm = $(".lp-name", lab); if (nm) nm.textContent = t.name;
      var sub = $(".lp-sub", lab);
      if (sub) sub.textContent = (T.current() + 1) + " / " + T.THEMES.length + (t.pro ? " · Pro, unlocked with a code" : "");
    }
  }
  // Each theme has a matching app icon with the same id (Bakery is the main icon).
  function iconSrc(t) { return base + "assets/icons/" + t.id + ".png"; }
  var preloaded = {};
  function preload(t) { if (!preloaded[t.id]) { preloaded[t.id] = new Image(); preloaded[t.id].src = iconSrc(t); } }
  // Cross-fade an icon inside `box`: the new image animates in over the old one,
  // which animates out and is removed. Swaps only once the new image has
  // decoded, so it never flashes blank.
  function swapImg(box, cls, src, size) {
    var cur = $("img." + cls + ":not(.out)", box);
    if (cur && cur.getAttribute("src") === src) return;
    var img = doc.createElement("img");
    img.className = cls; img.alt = ""; img.width = size; img.height = size; img.src = src;
    function show() {
      box.appendChild(img);
      if (!cur) return;
      if (reduced) cur.remove();
      else { cur.classList.add("out"); cur.addEventListener("animationend", function () { cur.remove(); }); }
    }
    if (img.decode) img.decode().then(show, show); else show();
  }
  if (orbs) {
    $$(".orb-btn", orbs).forEach(function (b, i) {
      var t = T.THEMES[i];
      b.addEventListener("pointerenter", function () { preload(t); });
      b.addEventListener("focus", function () { preload(t); });
    });
  }

  T.onChange(syncTheme);
  syncTheme(T.THEMES[T.current()]);

  /* --------------------------------------------- docs: anchors + toc */
  $$(".docs-content :is(h2, h3)[id], .docs-content section[id] > h2").forEach(function (h) {
    var id = h.id || h.parentNode.id;
    var a = doc.createElement("a");
    a.className = "anchor"; a.href = "#" + id; a.textContent = "#";
    a.setAttribute("aria-label", "Link to this section");
    h.insertBefore(a, h.firstChild);
  });
  var tocLinks = $$(".docs-toc a[href^='#']");
  if (tocLinks.length && "IntersectionObserver" in window) {
    var map = {};
    tocLinks.forEach(function (a) { map[a.getAttribute("href").slice(1)] = a; });
    var targets = Object.keys(map).map(function (id) { return doc.getElementById(id); }).filter(Boolean);
    var tio = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) {
          tocLinks.forEach(function (a) { a.classList.remove("active"); });
          map[en.target.id].classList.add("active");
        }
      });
    }, { rootMargin: "-20% 0px -70% 0px" });
    targets.forEach(function (t) { tio.observe(t); });
  }

  /* -------------------------------------------------- command palette */
  var PAGES = [
    ["Home", "index.html", "Overview, install, status"],
    ["Installation", "docs/installation.html", "SideStore, AltStore, LiveContainer, TrollStore, JIT"],
    ["Documentation", "docs/index.html", "Every guide"],
    ["Features overview", "docs/features.html", "Library, importer, packs, DLC"],
    ["Screen Layout", "docs/screen-layout.html", "TV + GamePad screens, second display"],
    ["Save States", "docs/save-states.html", "4 slots per game"],
    ["Controls & GamePad", "docs/controls.html", "Measured pad, skins, Melo-Controller"],
    ["Themes & Icons", "docs/themes.html", "31 themes"],
    ["Troubleshooting", "docs/troubleshooting.html", "Launch, JIT, logs"],
    ["FAQ", "docs/faq.html", "Common questions"],
    ["Open-source licences", "docs/licenses.html", "Third-party licences"],
    ["GitHub", "https://github.com/kiddreads/MuffinEMU", "Source code"],
    ["Report an issue", "https://github.com/kiddreads/MuffinEMU/issues", "GitHub issues"]
  ];
  var ICON_PAGE = '<svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M6 3.5h8l4 4v13H6z"/><path d="M14 3.5v4h4"/></svg>';
  var ICON_HASH = '<svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"><path d="M9 4 7 20M17 4l-2 16M4 9h16M3 15h16"/></svg>';
  var ICON_BOLT = '<svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"><path d="M13 2.5 4.5 13.5H12l-1 8 8.5-11H12z"/></svg>';

  var dlg = $("[data-palette]");
  var openers = $$("[data-palette-open]");
  if (dlg && dlg.showModal) {
    var input = $("input", dlg), list = $(".palette-list", dlg);
    var items = [], sel = 0;

    function href(u) { return /^https?:/.test(u) ? u : base + u; }
    function buildItems() {
      var out = [];
      PAGES.forEach(function (p) { out.push({ group: "Pages", label: p[0], hint: p[2], icon: ICON_PAGE, run: function () { location.href = href(p[1]); } }); });
      $$("main h2[id], main section[id] > h2").forEach(function (h) {
        var id = h.id || h.parentNode.id, txt = h.textContent.replace(/^#/, "").trim();
        if (txt) out.push({ group: "On this page", label: txt, icon: ICON_HASH, run: function () { close(); location.hash = id; } });
      });
      out.push({ group: "Actions", label: "Cycle colour mode", hint: "auto / dark / light", icon: ICON_BOLT, run: function () { close(); modeBtn && modeBtn.click(); } });
      out.push({ group: "Actions", label: "Copy SideStore / AltStore source URL", icon: ICON_BOLT, run: function () { close(); var c = $("[data-copy]"); if (c) c.click(); else navigator.clipboard && navigator.clipboard.writeText("https://kiddreads.github.io/MuffinEMU/apps.json").then(function () { toast("Source URL copied"); }); } });
      out.push({ group: "Actions", label: "Random theme", icon: ICON_BOLT, run: function () { close(); var i; do { i = Math.floor(Math.random() * T.THEMES.length); } while (i === T.current()); setTheme(T.THEMES[i].id); } });
      T.THEMES.forEach(function (t) {
        out.push({ group: "Themes", label: t.name + (t.pro ? " · Pro" : ""), sw: swatchOf(t), hint: t.id === T.THEMES[T.current()].id ? "current" : "", run: function () { close(); setTheme(t.id); } });
      });
      return out;
    }
    function score(q, s) {
      s = s.toLowerCase();
      if (!q) return 1;
      if (s.indexOf(q) === 0) return 3;
      if (s.indexOf(q) > -1) return 2;
      var i = 0; for (var k = 0; k < s.length && i < q.length; k++) if (s[k] === q[i]) i++;
      return i === q.length ? 1 : 0;
    }
    function render() {
      var q = input.value.trim().toLowerCase();
      var mode = null;
      if (q.indexOf("theme ") === 0 || q === "theme") { mode = "Themes"; q = q.slice(6); }
      var all = buildItems().filter(function (it) { return !mode || it.group === mode; });
      items = all.map(function (it) { return [score(q, it.label + " " + (it.hint || "")), it]; })
        .filter(function (x) { return x[0] > 0; })
        .sort(function (a, b) { return q ? b[0] - a[0] : 0; })
        .map(function (x) { return x[1]; });
      if (!q) items = all;
      list.innerHTML = "";
      if (!items.length) { list.innerHTML = '<li class="palette-empty">Nothing matches.</li>'; return; }
      var lastGroup = null;
      items.forEach(function (it, i) {
        if (it.group !== lastGroup && !q) {
          var g = doc.createElement("li"); g.className = "palette-group"; g.textContent = it.group; g.setAttribute("role", "presentation");
          list.appendChild(g); lastGroup = it.group;
        }
        var li = doc.createElement("li");
        li.className = "palette-item"; li.id = "pi-" + i; li.setAttribute("role", "option");
        li.innerHTML = (it.sw ? '<span class="sw"></span>' : it.icon) + "<span></span>" + (it.hint ? '<span class="hint"></span>' : "");
        if (it.sw) li.firstChild.style.background = it.sw;
        li.children[1].textContent = it.label;
        if (it.hint) li.lastChild.textContent = it.hint;
        li.addEventListener("click", function () { it.run(); });
        li.addEventListener("pointermove", function () { if (sel !== i) select(i, false); });
        list.appendChild(li);
      });
      select(0, true);
    }
    function select(i, scroll) {
      sel = Math.max(0, Math.min(items.length - 1, i));
      $$(".palette-item", list).forEach(function (el) { el.setAttribute("aria-selected", el.id === "pi-" + sel ? "true" : "false"); });
      var el = doc.getElementById("pi-" + sel);
      if (el) { input.setAttribute("aria-activedescendant", el.id); if (scroll) el.scrollIntoView({ block: "nearest" }); }
    }
    function open(prefill) {
      if (dlg.open) return;
      input.value = prefill || "";
      render();
      dlg.showModal();
      input.focus();
      if (prefill) input.setSelectionRange(prefill.length, prefill.length);
    }
    function close() { if (dlg.open) dlg.close(); }

    openers.forEach(function (b) {
      b.addEventListener("click", function () { open(b.getAttribute("data-palette-open") || ""); });
    });
    input.addEventListener("input", render);
    input.addEventListener("keydown", function (e) {
      if (e.key === "ArrowDown") { e.preventDefault(); select(sel + 1, true); }
      else if (e.key === "ArrowUp") { e.preventDefault(); select(sel - 1, true); }
      else if (e.key === "Enter") { e.preventDefault(); if (items[sel]) items[sel].run(); }
    });
    dlg.addEventListener("click", function (e) { if (e.target === dlg) close(); });
    doc.addEventListener("keydown", function (e) {
      var k = e.key.toLowerCase();
      if ((e.metaKey || e.ctrlKey) && k === "k") { e.preventDefault(); dlg.open ? close() : open(); }
      else if (k === "/" && !dlg.open && !/input|textarea|select/i.test(doc.activeElement.tagName)) { e.preventDefault(); open(); }
    });
  }
})();
