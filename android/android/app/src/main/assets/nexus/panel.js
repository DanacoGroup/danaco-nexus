// Mostek panelu Nexusa (asystent systemowy, języczek). Panel w WebView jest oknem najwyższego poziomu,
// więc jego komunikaty do „rodzica” (window.parent === window) trafiają tutaj i są przekazywane do aplikacji.
(function () {
  "use strict";
  if (window.top !== window || window.__nexusPanelBridge) return;
  window.__nexusPanelBridge = true;
  var bridge = window.NexusPanelBridge;
  if (!bridge) return;
  var FORWARD = { "nexus:ready": true, "nexus:insert": true, "nexus:copy": true };
  window.addEventListener("message", function (event) {
    if (event.source !== window || event.origin !== location.origin) return;
    var data = event.data;
    if (!data || typeof data !== "object" || !FORWARD[data.type]) return;
    try {
      bridge.postMessage(JSON.stringify({ type: data.type, text: typeof data.text === "string" ? data.text : "" }));
    } catch (error) {
      // Mostek niedostępny – panel działa dalej bez integracji.
    }
  });
})();
