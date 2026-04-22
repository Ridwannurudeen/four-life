/*!
 * FOUR-LIFE Certified — embeddable badge widget
 * https://four-life.gudman.xyz
 *
 * Usage:
 *   <script src="https://four-life.gudman.xyz/embed.js?token=0x..."></script>
 *
 * Attributes (optional):
 *   data-token="0x..."        explicit token address (overrides ?token= query)
 *   data-theme="dark|light"   color scheme (default: dark)
 *   data-size="sm|md|lg"      badge size (default: md)
 *   data-chain-link="true"    link pill to four.meme token page
 *   data-modal="false"        disable click-for-details modal
 *
 * Deterministic, auditable. No tracking, no external deps.
 */
(function () {
  "use strict";

  var API_BASE = "https://four-life.gudman.xyz";
  var RADAR_BASE = "https://four-life.gudman.xyz/radar";
  var FOURMEME_BASE = "https://four.meme/token";
  var POLL_MS = 60000;
  var VERSION = "four-life-embed-v1";

  // Tier style tokens (dark theme). Light theme derives from these.
  var TIERS = {
    graduated:        { label: "Graduated",        bg: "#a855f733", fg: "#d8b4fe", dot: "#c084fc", ring: "#7e22ce66" },
    graduation_watch: { label: "Graduation Watch", bg: "#00d4ff22", fg: "#67e8f9", dot: "#22d3ee", ring: "#0891b266" },
    healthy:          { label: "Healthy",          bg: "#6cff3222", fg: "#86efac", dot: "#6cff32", ring: "#16a34a66" },
    at_risk:          { label: "At Risk",          bg: "#ff494a22", fg: "#fca5a5", dot: "#ff494a", ring: "#b9141566" },
    observed:         { label: "Observed",         bg: "#ffd64122", fg: "#fde68a", dot: "#ffd641", ring: "#a1620466" },
    unknown:          { label: "Analyzing…",       bg: "#ffffff11", fg: "#ffffffaa", dot: "#ffffff66", ring: "#ffffff22" },
  };

  var SIZES = {
    sm: { h: 22, pad: "3px 8px",  fs: "10px", dot: 6,  gap: 6  },
    md: { h: 28, pad: "5px 11px", fs: "12px", dot: 8,  gap: 7  },
    lg: { h: 36, pad: "8px 16px", fs: "14px", dot: 10, gap: 9  },
  };

  // Read the <script> that loaded this file — currentScript works at parse time.
  var selfScript = document.currentScript;
  if (!selfScript) {
    // Fallback: look for any <script> whose src points at embed.js (handles async injection).
    var scripts = document.getElementsByTagName("script");
    for (var i = scripts.length - 1; i >= 0; i--) {
      if (scripts[i].src && scripts[i].src.indexOf("embed.js") !== -1) {
        selfScript = scripts[i];
        break;
      }
    }
  }

  function parseQuery(src) {
    var q = {};
    if (!src) return q;
    var i = src.indexOf("?");
    if (i === -1) return q;
    src.slice(i + 1).split("&").forEach(function (pair) {
      var eq = pair.indexOf("=");
      if (eq === -1) q[decodeURIComponent(pair)] = "";
      else q[decodeURIComponent(pair.slice(0, eq))] = decodeURIComponent(pair.slice(eq + 1));
    });
    return q;
  }

  function extractConfig(script) {
    var q = parseQuery(script && script.src);
    var token = (script && script.getAttribute("data-token")) || q.token || "";
    var theme = (script && script.getAttribute("data-theme")) || q.theme || "dark";
    var size = (script && script.getAttribute("data-size")) || q.size || "md";
    var chainLink = (script && script.getAttribute("data-chain-link")) || q.chain_link || "false";
    var modal = (script && script.getAttribute("data-modal")) || q.modal || "true";
    if (!SIZES[size]) size = "md";
    return {
      token: token,
      theme: theme === "light" ? "light" : "dark",
      size: size,
      chainLink: chainLink === "true" || chainLink === "1",
      modal: !(modal === "false" || modal === "0"),
    };
  }

  function escapeHtml(s) {
    if (s === null || s === undefined) return "";
    return String(s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function applyTheme(style, theme) {
    if (theme === "light") {
      return style
        .replace(/#ffffffaa/g, "#00000099")
        .replace(/#ffffff66/g, "#00000066")
        .replace(/#ffffff22/g, "#00000015")
        .replace(/#ffffff11/g, "#00000008");
    }
    return style;
  }

  function renderBadge(root, cfg, data) {
    var size = SIZES[cfg.size];
    var tier = (data && data.badge && data.badge.tier) || "unknown";
    var style = TIERS[tier] || TIERS.unknown;
    var label = (data && data.badge && data.badge.label) || style.label;
    // Truth-boundary: never display "Certified" when the badge was derived
    // from public-ranking heuristics — that badge is a RADAR ESTIMATE and the
    // widget must say so. Only tier_source === "certified" (full on-chain
    // measurement) earns the Certified wording.
    var source = (data && (data.tier_source || (data.badge && data.badge.tier_source))) || "certified";
    var isCertified = source === "certified";
    var brandPrefix = isCertified ? "FOUR-LIFE · " : "FOUR-LIFE · Radar · ";

    // Clear root
    while (root.firstChild) root.removeChild(root.firstChild);

    var wrap = document.createElement(cfg.chainLink && data ? "a" : "span");
    wrap.setAttribute("part", "pill");
    if (cfg.chainLink && cfg.token) {
      wrap.setAttribute("href", FOURMEME_BASE + "/" + cfg.token);
      wrap.setAttribute("target", "_blank");
      wrap.setAttribute("rel", "noopener noreferrer");
    }

    var pillStyle = [
      "display:inline-flex", "align-items:center", "gap:" + size.gap + "px",
      "height:" + size.h + "px", "padding:" + size.pad,
      "border-radius:" + (size.h) + "px",
      "font:600 " + size.fs + "/1 -apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif",
      "letter-spacing:0.04em", "text-transform:uppercase",
      "background:" + style.bg, "color:" + style.fg,
      "border:1px solid " + style.ring,
      "text-decoration:none", "cursor:" + (cfg.modal || cfg.chainLink ? "pointer" : "default"),
      "box-sizing:border-box", "user-select:none",
      "transition:transform 0.15s ease",
    ].join(";");
    wrap.setAttribute("style", applyTheme(pillStyle, cfg.theme));

    var dot = document.createElement("span");
    dot.setAttribute("style",
      "width:" + size.dot + "px;height:" + size.dot + "px;border-radius:50%;" +
      "background:" + style.dot + ";box-shadow:0 0 " + size.dot + "px " + style.dot + "66;" +
      "flex-shrink:0"
    );
    wrap.appendChild(dot);

    var txt = document.createElement("span");
    txt.textContent = brandPrefix + label;
    wrap.appendChild(txt);

    if (cfg.modal) {
      wrap.addEventListener("click", function (e) {
        if (cfg.chainLink) return;  // link handles it
        e.preventDefault();
        openModal(root.getRootNode(), cfg, data);
      });
    }

    root.appendChild(wrap);
  }

  function openModal(shadowRoot, cfg, data) {
    var host = shadowRoot.host || shadowRoot;
    var modalRoot = shadowRoot.querySelector ? shadowRoot : host.shadowRoot;
    if (!modalRoot) return;

    // Remove any existing modal
    var existing = modalRoot.querySelector("[data-role=modal]");
    if (existing) existing.parentNode.removeChild(existing);

    var overlay = document.createElement("div");
    overlay.setAttribute("data-role", "modal");
    overlay.setAttribute("style",
      "position:fixed;inset:0;z-index:2147483647;display:flex;align-items:center;justify-content:center;" +
      "background:rgba(0,0,0,0.75);backdrop-filter:blur(6px);" +
      "font:400 14px/1.5 -apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;color:#fff"
    );
    overlay.addEventListener("click", function (e) {
      if (e.target === overlay) overlay.parentNode.removeChild(overlay);
    });

    var panel = document.createElement("div");
    panel.setAttribute("style",
      "width:min(640px,92vw);max-height:86vh;overflow-y:auto;" +
      "background:#0f1012;border:1px solid #ffffff18;border-radius:16px;" +
      "padding:22px 24px;box-shadow:0 20px 60px rgba(0,0,0,0.6)"
    );

    var tier = (data && data.badge && data.badge.tier) || "unknown";
    var style = TIERS[tier] || TIERS.unknown;
    var label = (data && data.badge && data.badge.label) || style.label;
    var desc = (data && data.badge && data.badge.description) || "Analyzing token…";
    var why = (data && data.badge && data.badge.why) || [];
    var modelVersion = (data && data.model_version) || VERSION;
    var source = (data && (data.tier_source || (data.badge && data.badge.tier_source))) || "certified";
    var isCertified = source === "certified";
    var headingText = isCertified
      ? "FOUR-LIFE Certified — " + escapeHtml(label)
      : "FOUR-LIFE Radar Estimate — " + escapeHtml(label);
    var sourceNote = isCertified
      ? ""
      : "<div style='background:#ffd64122;border:1px solid #ffd64155;border-radius:8px;padding:8px 10px;font-size:11px;color:#ffd641;margin-bottom:14px'>" +
        "Heuristic estimate from public ranking data — not a Certified tier. Track this token on FOUR-LIFE for on-chain measurement." +
        "</div>";

    var header = "<div style='display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:14px'>" +
      "<div style='display:flex;align-items:center;gap:10px'>" +
        "<span style='width:10px;height:10px;border-radius:50%;background:" + style.dot + ";box-shadow:0 0 10px " + style.dot + "66'></span>" +
        "<span style='font:700 17px/1 -apple-system,Segoe UI,sans-serif;color:" + style.fg + "'>" + headingText + "</span>" +
      "</div>" +
      "<button data-role='close' style='background:transparent;border:0;color:#ffffff66;cursor:pointer;font-size:24px;line-height:1;padding:4px 8px'>×</button>" +
    "</div>";

    var descBlock = sourceNote + "<div style='color:#ffffffaa;font-size:13px;margin-bottom:18px'>" + escapeHtml(desc) + "</div>";

    var rulesHtml = "";
    if (why.length > 0) {
      rulesHtml = "<div style='font:600 10px/1 -apple-system,Segoe UI,sans-serif;color:#ffffff55;letter-spacing:0.08em;text-transform:uppercase;margin-bottom:8px'>Rule Trace</div>";
      rulesHtml += "<div style='border:1px solid #ffffff12;border-radius:10px;overflow:hidden'>";
      why.forEach(function (r, idx) {
        var bg = idx % 2 === 0 ? "#ffffff04" : "transparent";
        var pass = r.passed
          ? "<span style='color:" + TIERS.healthy.dot + "'>✓</span>"
          : "<span style='color:" + TIERS.at_risk.dot + "'>✗</span>";
        rulesHtml +=
          "<div style='display:grid;grid-template-columns:1fr 1fr auto 1fr auto;gap:12px;padding:8px 12px;font-family:ui-monospace,Menlo,monospace;font-size:11.5px;background:" + bg + "'>" +
            "<div style='color:#fff'>" + escapeHtml(r.rule) + "</div>" +
            "<div style='color:#ffffff77'>" + escapeHtml(r.metric) + "</div>" +
            "<div style='color:#ffffff55'>" + escapeHtml(r.operator) + "</div>" +
            "<div style='color:#fff'>" + escapeHtml(String(r.value)) + " <span style='color:#ffffff55'>/ " + escapeHtml(String(r.threshold)) + "</span></div>" +
            "<div>" + pass + "</div>" +
          "</div>";
      });
      rulesHtml += "</div>";
    } else {
      rulesHtml = "<div style='color:#ffffff55;font-size:12px;padding:16px;text-align:center;border:1px dashed #ffffff14;border-radius:10px'>No rule trace available yet. Retry in a moment.</div>";
    }

    var tokenShort = cfg.token ? (cfg.token.slice(0, 6) + "…" + cfg.token.slice(-4)) : "(no token)";
    var footer =
      "<div style='margin-top:20px;display:flex;flex-wrap:wrap;gap:8px;align-items:center;justify-content:space-between'>" +
        "<div style='font-family:ui-monospace,Menlo,monospace;font-size:10.5px;color:#ffffff55'>" +
          "token " + escapeHtml(tokenShort) + " · model " + escapeHtml(modelVersion) +
        "</div>" +
        "<div style='display:flex;gap:8px'>" +
          (cfg.token
            ? "<a href='" + RADAR_BASE + "?token=" + encodeURIComponent(cfg.token) + "' target='_blank' rel='noopener noreferrer' style='padding:6px 12px;border-radius:999px;font-size:11px;font-weight:600;background:#6cff32;color:#000;text-decoration:none'>Open in Radar</a>"
            : "") +
          "<a href='" + RADAR_BASE + "' target='_blank' rel='noopener noreferrer' style='padding:6px 12px;border-radius:999px;font-size:11px;font-weight:600;background:#ffffff0a;color:#fff;text-decoration:none;border:1px solid #ffffff18'>What is FOUR-LIFE?</a>" +
        "</div>" +
      "</div>";

    panel.innerHTML = header + descBlock + rulesHtml + footer;

    var close = panel.querySelector("[data-role=close]");
    if (close) close.addEventListener("click", function () { overlay.parentNode.removeChild(overlay); });

    overlay.appendChild(panel);
    modalRoot.appendChild(overlay);
  }

  function fetchBadge(token) {
    if (!token) return Promise.resolve(null);
    return fetch(API_BASE + "/api/token/" + encodeURIComponent(token) + "/badge", {
      mode: "cors",
      credentials: "omit",
      cache: "no-store",
    }).then(function (r) {
      if (!r.ok) return null;
      return r.json();
    }).catch(function () { return null; });
  }

  function mount(script) {
    var cfg = extractConfig(script);

    // Create host element right after the script tag
    var host = document.createElement("span");
    host.setAttribute("data-fl-embed", "");
    host.style.display = "inline-block";
    host.style.verticalAlign = "middle";
    script.parentNode.insertBefore(host, script.nextSibling);

    var shadow = host.attachShadow({ mode: "open" });
    var root = document.createElement("div");
    root.setAttribute("data-root", "");
    shadow.appendChild(root);

    // Initial render in "unknown" state while we fetch
    renderBadge(root, cfg, null);

    if (!cfg.token) {
      // No token at all — render final neutral state and bail.
      return { host: host, refresh: function () {}, cfg: cfg };
    }

    function tick() {
      fetchBadge(cfg.token).then(function (data) {
        renderBadge(root, cfg, data);
      });
    }

    tick();
    var interval = setInterval(tick, POLL_MS);

    return {
      host: host,
      cfg: cfg,
      refresh: tick,
      destroy: function () {
        clearInterval(interval);
        if (host.parentNode) host.parentNode.removeChild(host);
      },
    };
  }

  // Public namespace for programmatic re-render / extra embeds.
  window.FourLife = window.FourLife || {
    version: VERSION,
    instances: [],
    mount: function (opts) {
      // opts: { target: Element, token: string, theme, size, chainLink, modal }
      if (!opts || !opts.target || !opts.token) return null;
      var fakeScript = document.createElement("script");
      fakeScript.setAttribute("data-token", opts.token);
      if (opts.theme) fakeScript.setAttribute("data-theme", opts.theme);
      if (opts.size) fakeScript.setAttribute("data-size", opts.size);
      if (opts.chainLink) fakeScript.setAttribute("data-chain-link", "true");
      if (opts.modal === false) fakeScript.setAttribute("data-modal", "false");
      opts.target.appendChild(fakeScript);
      var inst = mount(fakeScript);
      window.FourLife.instances.push(inst);
      return inst;
    },
  };

  if (selfScript) {
    var inst = mount(selfScript);
    window.FourLife.instances.push(inst);
  }
})();
