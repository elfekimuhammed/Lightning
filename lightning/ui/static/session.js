(() => {
  "use strict";

  window.addEventListener("pageshow", (event) => {
    if (event.persisted) window.location.reload();
  });

  const channel = typeof BroadcastChannel === "function"
    ? new BroadcastChannel("lightning-profile")
    : null;
  const sessionMeta = document.querySelector('meta[name="lightning-session"]');
  const token = sessionMeta?.content || "";

  const announceState = () => {
    if (!channel) return;
    try {
      channel.postMessage({ type: "state" });
    } catch (_) {
      // A closed or unavailable channel does not affect the current page.
    }
  };

  if (!token) {
    if (document.readyState === "complete") {
      announceState();
    } else {
      window.addEventListener("load", announceState, { once: true });
    }
    return;
  }

  let redirecting = false;
  let healthRequest = null;
  let leaving = false;
  window.addEventListener("beforeunload", () => { leaving = true; });
  window.addEventListener("pagehide", () => { leaving = true; });

  const lockAndRedirect = () => {
    if (redirecting || leaving) return;
    redirecting = true;
    document.body.replaceChildren();
    window.location.replace("/profiles");
  };

  // Still open, but the session changed under this page (a phone lent its ledger to a PC, or got it back):
  // show this same page again in its new state instead of leaving it for the profile settings.
  const reloadHere = () => {
    if (redirecting || leaving) return;
    redirecting = true;
    window.location.replace(window.location.href);
  };

  const checkHealth = async () => {
    if (redirecting || healthRequest) return healthRequest;
    healthRequest = (async () => {
      try {
        const response = await fetch("/profiles/health", {
          method: "GET",
          cache: "no-store",
          credentials: "same-origin",
        });
        if (!response.ok) {
          lockAndRedirect();
          return;
        }
        const health = await response.json();
        if (health.locked) lockAndRedirect();
        else if (health.session !== token) reloadHere();
      } catch (error) {
        // Navigation cancels outstanding fetches in Firefox. An old document
        // must not launch a competing redirect while its successor is loading.
        if (!leaving && error.name !== "AbortError") lockAndRedirect();
      } finally {
        healthRequest = null;
      }
    })();
    return healthRequest;
  };

  const sendActivity = (() => {
    let lastSentAt = Number.NEGATIVE_INFINITY;
    return (event) => {
      if (!event.isTrusted || document.visibilityState !== "visible") return;
      const now = performance.now();
      if (now - lastSentAt < 60_000) return;
      lastSentAt = now;
      const body = new URLSearchParams({ __session: token });
      fetch("/__activity", {
        method: "POST",
        body,
        cache: "no-store",
        credentials: "same-origin",
      }).catch(() => {});
    };
  })();

  window.setInterval(checkHealth, 15_000);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") checkHealth();
  });
  window.addEventListener("keydown", sendActivity, { passive: true });
  window.addEventListener("pointerdown", sendActivity, { passive: true });

  if (channel) {
    channel.addEventListener("message", (event) => {
      if (event.data && event.data.type === "state") checkHealth();
    });
  }

  checkHealth();

  // Password advice (owner decision 2026-10-05: any length, advice only). The server never relies on it.
  const t = (text) => window.lightningT ? window.lightningT(text) : text;
  const advice = (value) => {
    if (!value) return ["", t("Any length works. Longer is safer: three or four unrelated words are hard to guess.")];
    if (value.length < 8) return ["weak", t("Weak. Short passwords can be guessed if someone copies your files.")];
    if (value.length < 14 && !/\s/.test(value.trim())) return ["fair", t("Fair. Another word or two makes it much harder to guess.")];
    return ["strong", t("Strong.")];
  };
  document.querySelectorAll("input[data-strength]").forEach((input) => {
    const note = document.getElementById(input.dataset.strength);
    if (!note) return;
    input.addEventListener("input", () => {
      const [level, text] = advice(input.value);
      note.dataset.level = level;
      note.textContent = text;
    });
  });
  document.querySelectorAll("input[data-use-suggestion]").forEach((box) => {
    const own = document.querySelectorAll("[data-own-password]");
    const sync = () => own.forEach((field) => { field.hidden = box.checked; });
    box.addEventListener("change", sync);
    sync();
  });
})();
