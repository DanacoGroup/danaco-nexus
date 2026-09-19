import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";
import { defineConfig } from "vitest/config";

const DESCRIPTION =
  "Prywatny asystent AI: rozmowa z Claude i przesyłanie plików – dokumenty, zdjęcia, PDF, OCR, audio, wideo i automatyzacja.";

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      registerType: "prompt",
      injectRegister: false,
      includeAssets: ["favicon.svg", "apple-touch-icon.png", "icons/*.png", "share-target.js"],
      manifest: {
        id: "/",
        name: "Danaco Nexus",
        short_name: "Nexus",
        description: DESCRIPTION,
        lang: "pl",
        dir: "ltr",
        start_url: "/?source=pwa",
        scope: "/",
        display: "standalone",
        display_override: ["window-controls-overlay", "standalone", "minimal-ui"],
        orientation: "any",
        background_color: "#171717",
        theme_color: "#171717",
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
        shortcuts: [
          {
            name: "Nowa rozmowa",
            short_name: "Nowa",
            url: "/?source=shortcut",
            icons: [{ src: "/icons/icon-192.png", sizes: "192x192", type: "image/png" }],
          },
        ],
      },
      workbox: {
        // Powłoka aplikacji działa offline; API, pliki i strumień zadań zawsze z sieci.
        globPatterns: ["**/*.{js,css,html,svg,png,webmanifest}"],
        globIgnores: ["screenshots/**"],
        navigateFallback: "/index.html",
        // Instalatory i panel osadzany (inne nagłówki ramki) zawsze z sieci, nie z pamięci podręcznej.
        navigateFallbackDenylist: [/^\/api\//, /^\/share-target/, /^\/pobierz(\/|$)/, /[?&]widok=panel/],
        importScripts: ["/share-target.js"],
        cleanupOutdatedCaches: true,
        clientsClaim: true,
        runtimeCaching: [],
      },
    }),
  ],
  server: { proxy: { "/api": "http://127.0.0.1:8930", "/pobierz": "http://127.0.0.1:8930" } },
  build: { sourcemap: false, chunkSizeWarningLimit: 800 },
  test: { environment: "jsdom" },
});
