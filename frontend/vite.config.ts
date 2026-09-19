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
      includeAssets: ["favicon.svg", "apple-touch-icon.png", "icons/*.png"],
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
        navigateFallback: "/index.html",
        navigateFallbackDenylist: [/^\/api\//],
        cleanupOutdatedCaches: true,
        clientsClaim: true,
        runtimeCaching: [],
      },
    }),
  ],
  server: { proxy: { "/api": "http://127.0.0.1:8930" } },
  build: { sourcemap: false, chunkSizeWarningLimit: 800 },
  test: { environment: "jsdom" },
});
