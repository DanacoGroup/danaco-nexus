'use strict';
// Preload strony panelu (https://…/?widok=panel). Panel działa jako strona najwyższego
// poziomu, więc jej window.parent to ona sama: komunikaty „do rodzica” odbieramy tutaj
// i przekazujemy do procesu głównego; komunikaty „od rodzica” publikujemy w tym oknie.
// Stronie nie udostępniamy żadnego API.

const { ipcRenderer } = require('electron');

const FROM_PANEL = new Set(['nexus:ready', 'nexus:insert', 'nexus:copy']);
const TO_PANEL = new Set(['nexus:auth', 'nexus:context', 'nexus:prompt']);
const MAX_TEXT = 200000;

window.addEventListener('message', (event) => {
  if (event.origin !== window.location.origin) return;
  const data = event.data;
  if (!data || typeof data !== 'object' || !FROM_PANEL.has(data.type)) return;
  ipcRenderer.send('panel:message', {
    type: data.type,
    text: typeof data.text === 'string' ? data.text.slice(0, MAX_TEXT) : '',
  });
});

ipcRenderer.on('panel:post', (_event, message) => {
  if (!message || !TO_PANEL.has(message.type)) return;
  window.postMessage(message, window.location.origin);
});
