/* ===================================================================
   GTM Variable Monitor — MAIN world network interceptor
   Runs in the page's JS context (world: "MAIN" in manifest).
   Intercepts both fetch() and XMLHttpRequest to capture partialexport
   responses when the user clicks Export/Preview in GTM.

   NOTE: GTM is an AngularJS app which uses XMLHttpRequest, not fetch.
   =================================================================== */

(function () {
  const TAG = "[GTM Monitor MAIN]";
  console.log(TAG, "Interceptor script loaded at", window.location.href);

  // ---- Intercept XMLHttpRequest (AngularJS uses this) ---------------
  const _origXHROpen = XMLHttpRequest.prototype.open;
  const _origXHRSend = XMLHttpRequest.prototype.send;

  XMLHttpRequest.prototype.open = function (method, url) {
    this.__gtmMonUrl = url || "";
    this.__gtmMonMethod = method || "";

    // Log all GTM API calls for debugging
    if (url && typeof url === "string" && url.includes("tagmanager.google.com/api")) {
      console.log(TAG, "GTM API call:", method, url.substring(0, 150));
    }

    return _origXHROpen.apply(this, arguments);
  };

  XMLHttpRequest.prototype.send = function () {
    const url = this.__gtmMonUrl;

    if (url.includes("/partialexport")) {
      console.log(TAG, "XHR partialexport intercepted:", this.__gtmMonMethod, url);

      this.addEventListener("load", function () {
        console.log(TAG, "XHR response status:", this.status, "length:", (this.responseText || "").length);
        try {
          processExportResponse(this.responseText, "XHR");
        } catch (e) {
          console.error(TAG, "XHR processing error:", e);
        }
      });
    }

    return _origXHRSend.apply(this, arguments);
  };

  // ---- Intercept fetch (in case GTM switches to it) -----------------
  const _origFetch = window.fetch;
  window.fetch = function () {
    const req = arguments[0];
    const url = typeof req === "string" ? req : (req && req.url) || "";

    if (url.includes("/partialexport")) {
      console.log(TAG, "fetch() partialexport intercepted:", url);

      return _origFetch.apply(this, arguments).then(function (response) {
        const clone = response.clone();
        clone.text().then(function (text) {
          console.log(TAG, "fetch response status:", response.status, "length:", text.length);
          try {
            processExportResponse(text, "fetch");
          } catch (e) {
            console.error(TAG, "fetch processing error:", e);
          }
        });
        return response;
      });
    }
    return _origFetch.apply(this, arguments);
  };

  // ---- Common response processor ------------------------------------
  function processExportResponse(text, source) {
    // Google APIs prefix with )]}',\n — strip it
    const jsonStr = text.replace(/^\)\]\}',?\s*/, "");
    console.log(TAG, "Stripped prefix, parsing JSON from", source, "first 200 chars:", jsonStr.substring(0, 200));

    const parsed = JSON.parse(jsonStr);
    console.log(TAG, "Parsed top-level keys:", Object.keys(parsed));

    const wrapper = parsed.default || parsed;
    console.log(TAG, "Wrapper keys:", Object.keys(wrapper));

    const exportedJson = wrapper.exportedContainerJson;
    if (!exportedJson) {
      console.warn(TAG, "No exportedContainerJson found in response");
      return;
    }

    console.log(TAG, "exportedContainerJson length:", exportedJson.length);
    const containerData = JSON.parse(exportedJson);
    console.log(TAG, "Parsed container data, keys:", Object.keys(containerData));

    // Use postMessage to cross the MAIN→ISOLATED world boundary
    // (CustomEvent.detail does NOT cross world boundaries)
    window.postMessage({
      type: "__gtm_monitor_export",
      containerData: JSON.stringify(containerData),
    }, "*");
    console.log(TAG, "Posted message to ISOLATED world via postMessage");
  }
})();
