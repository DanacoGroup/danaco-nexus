// Bezpieczne wyświetlanie treści HTML e-maili: DOMPurify (osobna instancja), bez zdalnych obrazów domyślnie.
//
// Zdalne obrazy (śledzące piksele) są domyślnie blokowane; po zgodzie użytkownika ładuje je
// Nexus (pośrednik /api/poczta/obraz), więc nadawca nie poznaje adresu IP ani chwili otwarcia.
// Obrazy osadzone (cid:) wskazują załączniki wiadomości.

import createDOMPurify from "dompurify";

export interface SanitizeOptions {
  showImages: boolean;
  /** Adres załącznika dla obrazu `cid:…` (null – brak takiego załącznika). */
  cidUrl: (contentId: string) => string | null;
  /** Adres pośrednika dla zdalnego obrazu. */
  proxyUrl: (url: string) => string;
}

export interface SanitizedEmail {
  html: string;
  blockedImages: number;
}

const FORBID_TAGS = ["form", "input", "button", "textarea", "select", "option", "iframe", "frame", "object", "embed", "link", "meta", "base", "svg", "math"];
const REMOTE = /^https?:\/\//i;
const CSS_URL = /url\(\s*(['"]?)(.*?)\1\s*\)/gi;

function cleanStyle(style: string, counter: { blocked: number }): string {
  // Obrazy z CSS nie przechodzą przez pośrednika – zdalne adresy są zawsze usuwane.
  return style.replace(CSS_URL, (match, _quote: string, url: string) => {
    if (url.startsWith("data:image/")) return match;
    counter.blocked += 1;
    return "none";
  });
}

export function sanitizeEmailHtml(html: string, options: SanitizeOptions): SanitizedEmail {
  const purifier = createDOMPurify(window);
  const counter = { blocked: 0 };
  purifier.addHook("afterSanitizeAttributes", (node) => {
    const element = node as Element;
    if (element.tagName === "A") {
      const href = element.getAttribute("href") ?? "";
      if (href.startsWith("#")) element.removeAttribute("href");
      element.setAttribute("target", "_blank");
      element.setAttribute("rel", "noopener noreferrer nofollow");
    }
    if (element.tagName === "IMG") {
      element.removeAttribute("srcset");
      const src = (element.getAttribute("src") ?? "").trim();
      if (src.toLowerCase().startsWith("cid:")) {
        const url = options.cidUrl(src.slice(4).replace(/^<|>$/g, ""));
        if (url) element.setAttribute("src", url);
        else element.removeAttribute("src");
      } else if (REMOTE.test(src)) {
        if (options.showImages) {
          element.setAttribute("src", options.proxyUrl(src));
        } else {
          counter.blocked += 1;
          element.removeAttribute("src");
          element.setAttribute("data-nexus-blocked", "1");
          if (!element.getAttribute("alt")) element.setAttribute("alt", "");
        }
      } else if (!src.startsWith("data:image/")) {
        element.removeAttribute("src");
      }
    }
    if (element.hasAttribute("background")) {
      counter.blocked += 1;
      element.removeAttribute("background");
    }
    const style = element.getAttribute("style");
    if (style && /url\(/i.test(style)) element.setAttribute("style", cleanStyle(style, counter));
  });
  purifier.addHook("uponSanitizeElement", (node, data) => {
    if (data.tagName === "style" && node.textContent && /url\(/i.test(node.textContent)) {
      node.textContent = cleanStyle(node.textContent, counter);
    }
  });
  const clean = purifier.sanitize(html, {
    FORBID_TAGS,
    FORBID_ATTR: ["srcset", "formaction", "ping"],
    ADD_TAGS: ["style"],
    WHOLE_DOCUMENT: false,
    FORCE_BODY: true,
  });
  return { html: String(clean), blockedImages: counter.blocked };
}

/** Styl bazowy treści e-maila w izolowanym drzewie (Shadow DOM). */
export const EMAIL_BASE_STYLE = `
:host { all: initial; display: block; contain: content; }
.nexus-mail { background: #ffffff; color: #111113; font: 14px/1.55 "Segoe UI", system-ui, -apple-system, Arial, sans-serif;
  padding: 16px; overflow-wrap: anywhere; overflow-x: auto; border-radius: 12px; }
.nexus-mail img { max-width: 100%; height: auto; }
.nexus-mail img[data-nexus-blocked] { display: inline-block; min-width: 24px; min-height: 16px; background: #f1f1f3;
  outline: 1px dashed #c4c4cc; }
.nexus-mail table { max-width: 100%; }
.nexus-mail a { color: #4f46e5; }
.nexus-mail blockquote { margin: 0 0 0 8px; padding-left: 10px; border-left: 3px solid #d4d4d8; color: #52525b; }
.nexus-mail pre { white-space: pre-wrap; }
`;
