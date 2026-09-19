// Mostek aplikacji Android w oknie Nexusa (wstrzykiwany na początku dokumentu, tylko https://danaco-nexus.pl).
// Po zalogowaniu tworzy klucz urządzenia (POST /api/urzadzenia) i przekazuje go do natywnego magazynu,
// zgłasza rozpoczęte zadania (lokalne powiadomienia po ich zakończeniu) i udostępnia window.nexusAndroid.
(function () {
  "use strict";
  if (window.top !== window || window.nexusAndroid) return;
  var bridge = window.NexusAndroidBridge;
  if (!bridge) return;

  function send(message) {
    try {
      bridge.postMessage(JSON.stringify(message));
    } catch (error) {
      // Mostek niedostępny (np. strona w trakcie zamykania).
    }
  }

  var nativeFetch = window.fetch.bind(window);
  var MESSAGES = /\/api\/conversations\/([0-9a-f-]{36})\/messages$/;

  function requestUrl(input) {
    try {
      return new URL(typeof input === "string" ? input : input.url, location.href);
    } catch (error) {
      return null;
    }
  }

  // Obserwacja odpowiedzi aplikacji: logowanie (utworzenie klucza) i nowe zadania (powiadomienia).
  window.fetch = function (input, init) {
    var method = ((init && init.method) || (input && input.method) || "GET").toUpperCase();
    return nativeFetch(input, init).then(function (response) {
      try {
        var url = requestUrl(input);
        if (url && url.origin === location.origin && method === "POST") {
          if (url.pathname === "/api/auth/login" && response.ok) {
            setTimeout(hello, 300);
          }
          var match = MESSAGES.exec(url.pathname);
          if (match && response.status === 202) {
            response.clone().json().then(function (data) {
              if (data && data.run_id) send({ type: "run.started", runId: data.run_id, conversationId: match[1] });
            }).catch(function () {});
          }
        }
      } catch (error) {
        // Obserwacja nie może zakłócić działania aplikacji.
      }
      return response;
    });
  };

  function createKey(name) {
    nativeFetch("/api/auth/me", { credentials: "same-origin" })
      .then(function (me) {
        if (!me.ok) {
          send({ type: "key.nologin" });
          return null;
        }
        return nativeFetch("/api/urzadzenia", {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json", "X-Nexus-Request": "1" },
          body: JSON.stringify({ name: name, kind: "android" }),
        });
      })
      .then(function (response) {
        if (!response) return null;
        if (!response.ok) {
          send({ type: "key.error", status: response.status });
          return null;
        }
        return response.json();
      })
      .then(function (data) {
        if (data && data.token) send({ type: "key.created", token: data.token, id: data.id || "" });
      })
      .catch(function () {
        send({ type: "key.error", status: 0 });
      });
  }

  bridge.onmessage = function (event) {
    var message;
    try {
      message = JSON.parse(event.data);
    } catch (error) {
      return;
    }
    if (message && message.type === "key.request" && typeof message.name === "string") {
      createKey(message.name);
    }
  };

  function hello() {
    send({ type: "hello", path: location.pathname });
  }

  window.nexusAndroid = Object.freeze({
    platform: "android",
    /** Rozmowa głosowa w tle (usługa natywna); bez argumentu – nowa rozmowa. */
    startVoice: function (conversationId) {
      send({ type: "voice.start", conversationId: typeof conversationId === "string" ? conversationId : "" });
    },
    openSettings: function () {
      send({ type: "settings.open" });
    },
    openSms: function () {
      send({ type: "sms.open" });
    },
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", hello, { once: true });
  } else {
    hello();
  }
})();
