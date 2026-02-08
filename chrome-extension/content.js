/* ===================================================================
   GTM Variable Monitor — Content script
   Runs on tagmanager.google.com pages.
   1. Detects container parameters from the URL hash
   2. Injects a fetch interceptor (MAIN world) that captures
      partialexport responses when the user clicks Export/Preview in GTM
   =================================================================== */

(function () {
  // ---- URL param detection ------------------------------------------
  function detectParams() {
    const hash = window.location.hash || "";
    const qIndex = hash.indexOf("?");
    if (qIndex < 0) return null;

    const sp = new URLSearchParams(hash.slice(qIndex + 1));
    const accountId = sp.get("accountId");
    const containerId = sp.get("containerId");
    const containerDraftId = sp.get("containerDraftId");
    const containerVersionId = sp.get("containerVersionId");

    if (!accountId || !containerId) return null;
    return { accountId, containerId, containerDraftId, containerVersionId };
  }

  const params = detectParams();
  if (params) {
    chrome.runtime.sendMessage({ type: "gtm-params-detected", params });
  }

  window.addEventListener("hashchange", () => {
    const p = detectParams();
    if (p) {
      chrome.runtime.sendMessage({ type: "gtm-params-detected", params: p });
    }
  });

  // ---- Inject fetch interceptor into the MAIN page world -----------
  // We inject a <script> tag so it runs in the page's JS context and
  // can monkey-patch the real window.fetch that GTM uses.
  const script = document.createElement("script");
  script.textContent = `(${function () {
    const _origFetch = window.fetch;
    window.fetch = function () {
      const req = arguments[0];
      const url = typeof req === "string" ? req : (req && req.url) || "";

      // Intercept partialexport responses
      if (url.includes("/partialexport")) {
        return _origFetch.apply(this, arguments).then(function (response) {
          // Clone so the original consumer still gets the body
          const clone = response.clone();
          clone.text().then(function (text) {
            try {
              // Google APIs prefix with )]\n}',\n — strip it
              const jsonStr = text.replace(/^\)\]\}',?\s*/, "");
              const parsed = JSON.parse(jsonStr);
              const exportedJson = (parsed.default || parsed).exportedContainerJson;
              if (exportedJson) {
                const containerData = JSON.parse(exportedJson);
                // Broadcast to the content script via a custom DOM event
                window.dispatchEvent(
                  new CustomEvent("__gtm_monitor_export", {
                    detail: { containerData: JSON.stringify(containerData) },
                  })
                );
              }
            } catch (e) {
              // Silently ignore parse errors
            }
          });
          return response;
        });
      }
      return _origFetch.apply(this, arguments);
    };
  }})();`;
  (document.head || document.documentElement).appendChild(script);
  script.remove();

  // ---- Listen for intercepted data from the page --------------------
  window.addEventListener("__gtm_monitor_export", function (e) {
    try {
      const containerData = JSON.parse(e.detail.containerData);
      // Store in chrome.storage so popup can access it
      chrome.storage.local.set({
        interceptedExport: containerData,
        interceptedAt: Date.now(),
      });
      // Notify popup (if open)
      chrome.runtime.sendMessage({
        type: "export-intercepted",
        timestamp: Date.now(),
      });
    } catch (err) {
      // ignore
    }
  });
})();
