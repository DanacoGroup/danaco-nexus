// Ikony SVG w stylu aplikacji (obrys 1.75 px, currentColor, siatka 24×24).

function ikona(tresc: string, rozmiar = 18): string {
  return (
    `<svg width="${rozmiar}" height="${rozmiar}" viewBox="0 0 24 24" fill="none" stroke="currentColor" ` +
    `stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${tresc}</svg>`
  );
}

/** Znak Nexusa (litera N z kropkami, jak w favicon.svg). */
export function logo(rozmiar = 22): string {
  // Sygnet z pakietu marki (logo/pwa/android/adaptive-*.svg): gradient Aurora i łuk z punktem.
  return (
    `<svg width="${rozmiar}" height="${rozmiar}" viewBox="0 0 108 108" aria-hidden="true">` +
    '<defs><linearGradient id="nxg" x1="0" y1="0" x2="1" y2="1">' +
    '<stop offset="0" stop-color="#FF8A5B"/><stop offset="0.38" stop-color="#F2528F"/>' +
    '<stop offset="0.72" stop-color="#7B5CFF"/><stop offset="1" stop-color="#3BA7FF"/></linearGradient>' +
    '<radialGradient id="nxb" cx="0.25" cy="0.12" r="0.75">' +
    '<stop offset="0" stop-color="#FFFFFF" stop-opacity="0.24"/>' +
    '<stop offset="1" stop-color="#FFFFFF" stop-opacity="0"/></radialGradient></defs>' +
    '<rect width="108" height="108" rx="24.3" fill="url(#nxg)"/>' +
    '<rect width="108" height="108" rx="24.3" fill="url(#nxb)"/>' +
    '<path fill="#FFFFFF" fill-rule="evenodd" d="M31.5 72.9V53.1A22.5 22.5 0 0 1 76.5 53.1V72.9A5.4 5.4 0 0 1 65.7 72.9V53.1A11.7 11.7 0 0 0 42.3 53.1V72.9A5.4 5.4 0 0 1 31.5 72.9ZM48.15 53.1A5.85 5.85 0 1 0 59.85 53.1A5.85 5.85 0 1 0 48.15 53.1Z"/></svg>'
  );
}

export const IKONY = {
  zamknij: ikona('<path d="M6 6l12 12M18 6 6 18"/>'),
  odswiez: ikona('<path d="M20 11a8 8 0 1 0-2.3 5.7M20 5v6h-6"/>'),
  ustawienia: ikona(
    '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
  ),
  nowaKarta: ikona('<path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>'),
  stresc: ikona('<path d="M4 6h16M4 10h16M4 14h10M4 18h7"/>'),
  odpowiedz: ikona('<path d="M9 14 4 9l5-5"/><path d="M4 9h10.5a5.5 5.5 0 0 1 0 11H11"/>'),
  popraw: ikona('<path d="M4 20h4L19 9a2.8 2.8 0 0 0-4-4L4 16v4z"/><path d="m13.5 6.5 4 4"/>'),
  tlumacz: ikona('<path d="M4 5h8M8 3v2M5.5 5c.8 3 3 5.5 6 7M10.5 5c-.8 3.5-3 6.5-6.5 8"/><path d="m12 21 4-9 4 9M13.5 18h5"/>'),
  pytanie: ikona('<circle cx="12" cy="12" r="9"/><path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .9-1 1.6v.6M12 17h.01"/>'),
  aparat: ikona('<path d="M4 8a2 2 0 0 1 2-2h1.5l1.5-2h6l1.5 2H18a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2z"/><circle cx="12" cy="12.5" r="3.5"/>'),
  ukryj: ikona('<path d="M3 3l18 18M10.6 5.1A10 10 0 0 1 12 5c5 0 9 5 9 7a9.7 9.7 0 0 1-2.4 3.4M6.6 6.6C4.4 8 3 10.4 3 12c0 2 4 7 9 7a9.3 9.3 0 0 0 4.4-1.1M9.9 9.9a3 3 0 0 0 4.2 4.2"/>'),
  strzalka: ikona('<path d="m9 6 6 6-6 6"/>', 16),
  gwiazda: ikona('<path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1 6.2-5.5-2.9-5.5 2.9 1-6.2L3 9.6l6.2-.9z"/>', 14),
};
