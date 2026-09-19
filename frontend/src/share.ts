// Odbiór plików udostępnionych do Nexusa z innych aplikacji (patrz public/share-target.js).

const SHARE_CACHE = "nexus-share";

export interface SharedContent {
  files: File[];
  text: string;
}

/** Zwraca i usuwa treść udostępnioną do aplikacji (gdy adres zawiera ``?share=1``). */
export async function takeSharedContent(): Promise<SharedContent | null> {
  if (new URLSearchParams(window.location.search).get("share") !== "1" || !("caches" in window)) return null;
  window.history.replaceState(null, "", "/");
  const cache = await caches.open(SHARE_CACHE);
  const files: File[] = [];
  let text = "";
  for (const request of await cache.keys()) {
    const response = await cache.match(request);
    if (!response) continue;
    if (request.url.endsWith("/share-target/text")) {
      text = await response.text();
    } else {
      const name = decodeURIComponent(response.headers.get("X-File-Name") ?? "plik");
      const blob = await response.blob();
      files.push(new File([blob], name, { type: blob.type }));
    }
  }
  await caches.delete(SHARE_CACHE);
  return files.length || text ? { files, text } : null;
}
