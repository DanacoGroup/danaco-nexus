import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";
import { defineConfig } from "vitest/config";

const DESCRIPTION =
  "Osobisty asystent AI: rozmowa i przesyłanie plików – dokumenty, zdjęcia, PDF, OCR, audio, wideo i automatyzacja.";

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      registerType: "prompt",
      injectRegister: false,
      // Ikony, po które sięga przeglądarka; warianty 1024 px są dla sklepów z aplikacjami.
      includeAssets: [
        "favicon.svg",
        "favicon.ico",
        "apple-touch-icon.png",
        "icons/icon-192.png",
        "icons/icon-512.png",
        "icons/maskable-192.png",
        "icons/maskable-512.png",
        "icons/safari-pinned-tab.svg",
        // Znaczek powiadomienia rysuje worker także bez sieci.
        "icons/badge-96.png",
        "share-target.js",
      ],
      manifest: {
        id: "/",
        name: "Danaco Nexus",
        short_name: "Nexus",
        description: DESCRIPTION,
        lang: "pl",
        dir: "ltr",
        start_url: "/czat?source=pwa",
        scope: "/",
        display: "standalone",
        display_override: ["window-controls-overlay", "standalone", "minimal-ui"],
        orientation: "any",
        background_color: "#0D0F17",
        theme_color: "#0D0F17",
        categories: ["productivity", "utilities", "business"],
        icons: [
          { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
          { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
          { src: "/icons/maskable-192.png", sizes: "192x192", type: "image/png", purpose: "maskable" },
          { src: "/icons/maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
          { src: "/favicon.svg", sizes: "any", type: "image/svg+xml", purpose: "any" },
        ],
        // Zrzuty ekranu w oknie instalacji (Android, Chrome/Edge na komputerze).
        screenshots: [
          {
            src: "/screenshots/wide.png",
            sizes: "1280x800",
            type: "image/png",
            form_factor: "wide",
            label: "Danaco Nexus – rozmowa z asystentem na komputerze",
          },
          {
            src: "/screenshots/narrow.png",
            sizes: "780x1688",
            type: "image/png",
            form_factor: "narrow",
            label: "Danaco Nexus na telefonie",
          },
        ],
        // Udostępnianie plików do Nexusa z innych aplikacji (Android, Windows).
        share_target: {
          action: "/share-target",
          method: "POST",
          enctype: "multipart/form-data",
          params: {
            title: "title",
            text: "text",
            url: "url",
            files: [
              {
                name: "files",
                accept: ["image/*", "application/pdf", "audio/*", "video/*", "text/*", "application/*"],
              },
            ],
          },
        },
        // Skróty z menu kontekstowego ikony (długie przytrzymanie na telefonie, prawy
        // przycisk na pulpicie). Android i Windows pokazują do czterech; dawaliśmy jeden,
        // więc menu instalacji było niemal puste. Kolejność od najczęstszego użycia.
        // Bez rozmowy głosowej: `/m/glos` nie jest modułem rejestru, tylko nakładką, a gdy
        // głos jest niedostępny, adres odsyła na czat — sprawdzone w przeglądarce. Skrót,
        // który czasem prowadzi gdzie indziej, jest gorszy niż brak skrótu.
        shortcuts: [
          {
            name: "Nowa rozmowa",
            short_name: "Nowa",
            url: "/czat?source=shortcut",
            icons: [{ src: "/icons/icon-192.png", sizes: "192x192", type: "image/png" }],
          },
          {
            name: "Obrazy",
            short_name: "Obrazy",
            url: "/m/obrazy?source=shortcut",
            icons: [{ src: "/icons/icon-192.png", sizes: "192x192", type: "image/png" }],
          },
          {
            name: "Pliki",
            short_name: "Pliki",
            url: "/m/pliki?source=shortcut",
            icons: [{ src: "/icons/icon-192.png", sizes: "192x192", type: "image/png" }],
          },
          {
            name: "Możliwości",
            short_name: "Możliwości",
            url: "/m/mozliwosci?source=shortcut",
            icons: [{ src: "/icons/icon-192.png", sizes: "192x192", type: "image/png" }],
          },
        ],
      },
      workbox: {
        // Lista dopuszczeń: wstępnie pobierana jest sama powłoka (kod, arkusze, kroje, znak).
        // Materiały idą z sieci i zostają w pamięci po obejrzeniu — reguły niżej.
        globPatterns: ["**/*.{js,css,html,webmanifest,woff2}", "znak/*.svg"],
        navigateFallback: "/index.html",
        // Instalatory i panel osadzany (inne nagłówki ramki) zawsze z sieci, nie z pamięci podręcznej.
        // Kanały dla wyszukiwarek też: bez tego przejście pod /sitemap.xml zwracałoby powłokę aplikacji.
        navigateFallbackDenylist: [
          /^\/api\//,
          /^\/share-target/,
          /^\/pobierz(\/|$)/,
          /[?&]widok=panel/,
          /^\/s\//,
          /^\/robots\.txt$/,
          /^\/sitemap\.xml$/,
          /^\/portal\/(atom|rss)\.xml$/,
        ],
        importScripts: ["/share-target.js"],
        cleanupOutdatedCaches: true,
        clientsClaim: true,
        runtimeCaching: [
          {
            // Plakaty, tła i zrzuty: z pamięci od razu, odświeżenie w tle. Nazwy są stałe,
            // więc „CacheFirst” podawałby treść sprzed podmiany nawet miesiąc.
            urlPattern: /\/(tla|film|kampania|ruch|screenshots)\/[^?]+\.(avif|webp|png|jpg)$/,
            handler: "StaleWhileRevalidate",
            options: {
              cacheName: "nexus-materialy-obrazy",
              expiration: { maxEntries: 80, maxAgeSeconds: 2592000 },
              cacheableResponse: { statuses: [0, 200] },
            },
          },
          {
            // Nagrania: odtwarzacz prosi o zakresy bajtów, a odpowiedzi 206 worker nie zapisze.
            urlPattern: /\/(film|kampania|ruch)\/[^?]+\.(mp4|webm|vtt)$/,
            handler: "NetworkOnly",
          },
        ],
      },
    }),
  ],
  server: { proxy: { "/api": "http://127.0.0.1:8930", "/pobierz": "http://127.0.0.1:8930" } },
  build: {
    sourcemap: false,
    chunkSizeWarningLimit: 800,
    rollupOptions: {
      output: {
        // React zmienia się rzadko, kod aplikacji przy każdym wydaniu: osobna paczka
        // zostaje w pamięci podręcznej i wydanie nie ciągnie biblioteki drugi raz.
        manualChunks: (id: string) =>
          /\/node_modules\/(react|react-dom|scheduler)\//.test(id) ? "react" : undefined,
      },
    },
  },
  test: { environment: "jsdom" },
});
