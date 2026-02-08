/* ===================================================================
   GTM Variable Monitor — MAIN world fetch interceptor
   Runs in the page's JS context (world: "MAIN" in manifest).
   Monkey-patches window.fetch to capture partialexport responses
   when the user clicks Export/Preview in GTM.
   =================================================================== */

(function () {
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
            // Google APIs prefix with )]}\',\n — strip it
            const jsonStr = text.replace(/^\)\]\}',?\s*/, "");
            const parsed = JSON.parse(jsonStr);
            const exportedJson = (parsed.default || parsed).exportedContainerJson;
            if (exportedJson) {
              const containerData = JSON.parse(exportedJson);
              // Broadcast to the ISOLATED content script via a custom DOM event
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
})();
