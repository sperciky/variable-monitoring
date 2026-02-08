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

  // ---- Extract workspace name from the export dialog DOM ------------
  function getWorkspaceName() {
    try {
      const el = document.querySelector(
        "gtm-selective-export > div > div.gtm-sheet-header > div.gtm-sheet-header__title > div"
      );
      if (el) {
        const text = el.innerText.trim();
        // "Export Default Workspace" → "Default Workspace"
        return text.replace(/^Export\s+/i, "") || text;
      }
    } catch (e) { /* ignore */ }
    return null;
  }

  // ---- Extract account/container/workspace IDs from the API URL -----
  function parseExportUrl(url) {
    // .../api/accounts/218461/containers/55831269/workspaces/678/partialexport?hl=en
    // .../api/accounts/218461/containers/55831269/versions/123/partialexport?hl=en
    const m = url.match(/\/api\/accounts\/(\d+)\/containers\/(\d+)\/(workspaces|versions)\/(\d+)\/partialexport/);
    if (!m) return {};
    return {
      accountId: m[1],
      containerId: m[2],
      sourceType: m[3],   // "workspaces" or "versions"
      sourceId: m[4],
    };
  }

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
          processExportResponse(this.responseText, url, "XHR");
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
            processExportResponse(text, url, "fetch");
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
  function processExportResponse(text, requestUrl, source) {
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

    // Gather metadata
    const urlInfo = parseExportUrl(requestUrl);
    const workspaceName = getWorkspaceName();
    console.log(TAG, "URL info:", urlInfo, "Workspace name:", workspaceName);

    // Use postMessage to cross the MAIN→ISOLATED world boundary
    window.postMessage({
      type: "__gtm_monitor_export",
      containerData: JSON.stringify(containerData),
      meta: {
        accountId: urlInfo.accountId || "",
        containerId: urlInfo.containerId || "",
        sourceType: urlInfo.sourceType || "",
        sourceId: urlInfo.sourceId || "",
        workspaceName: workspaceName || "",
      },
    }, "*");
    console.log(TAG, "Posted message to ISOLATED world via postMessage");
  }
})();
