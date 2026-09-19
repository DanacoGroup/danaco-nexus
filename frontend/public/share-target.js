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
