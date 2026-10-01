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
        if (health.locked || health.session !== token) lockAndRedirect();
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
})();
