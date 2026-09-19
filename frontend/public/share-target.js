// Udostępnianie do Nexusa (Web Share Target): pliki i tekst z menu „Udostępnij”
// systemu trafiają do pamięci podręcznej, a aplikacja dołącza je do nowej wiadomości.
// Skrypt jest ładowany przez service worker (importScripts) przed trasami Workboxa.

const SHARE_CACHE = "nexus-share";

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "POST" || url.pathname !== "/share-target") return;
  event.respondWith(
    (async () => {
      try {
        const form = await event.request.formData();
        const cache = await caches.open(SHARE_CACHE);
        for (const key of await cache.keys()) await cache.delete(key);
        const files = form.getAll("files").filter((item) => item instanceof File);
        let index = 0;
        for (const file of files) {
          index += 1;
          await cache.put(
            `/share-target/file/${index}`,
            new Response(file, {
              headers: {
                "Content-Type": file.type || "application/octet-stream",
                "X-File-Name": encodeURIComponent(file.name || `plik-${index}`),
              },
            }),
          );
        }
        const text = [form.get("title"), form.get("text"), form.get("url")].filter(Boolean).join("\n");
        if (text) await cache.put("/share-target/text", new Response(text));
      } catch (error) {
        console.error("Udostępnianie do Nexusa nie powiodło się", error);
      }
      return Response.redirect("/?share=1", 303);
    })(),
  );
});

// Powiadomienia Web Push o zakończonych zadaniach (treść: {title, body, url, tag}).
// Otwarta i widoczna rozmowa, której dotyczy powiadomienie, nie dostaje go ponownie.

function nexusSameOriginPath(value) {
  try {
    const url = new URL(value || "/", self.location.origin);
    return url.origin === self.location.origin ? url.pathname + url.search : "/";
  } catch {
    return "/";
  }
}

self.addEventListener("push", (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch {
    data = { body: event.data ? event.data.text() : "" };
  }
  const target = nexusSameOriginPath(data.url);
  event.waitUntil(
    (async () => {
      const windows = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
      const watching = windows.some(
        (client) => client.focused && client.visibilityState === "visible" && new URL(client.url).pathname === target,
      );
      if (watching && data.tag !== "nexus-test") return;
      await self.registration.showNotification(data.title || "Danaco Nexus", {
        body: data.body || "",
        tag: data.tag || undefined,
        icon: "/icons/icon-192.png",
        badge: "/icons/badge-96.png",
        lang: "pl",
        data: { url: target },
      });
    })(),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = nexusSameOriginPath(event.notification.data && event.notification.data.url);
  event.waitUntil(
    (async () => {
      const windows = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
      // Pełna aplikacja (nie panel osadzony w ramce rozszerzenia ani w WebView).
      const client = windows.find((item) => {
        const url = new URL(item.url);
        return item.frameType !== "nested" && url.origin === self.location.origin && !url.searchParams.has("widok");
      });
      if (client) {
        await client.focus();
        client.postMessage({ type: "nexus:open", url: target });
        return;
      }
      await self.clients.openWindow(target);
    })(),
  );
});
