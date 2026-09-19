'use strict';
// Języczek: krótkie najechanie (bez przypadkowych muśnięć) albo kliknięcie otwiera panel.

const HOVER_DELAY_MS = 220;
const handle = document.getElementById('handle');
let timer = null;

handle.addEventListener('mouseenter', () => {
  window.nexus.invoke('tab:hover', 'capture');
  clearTimeout(timer);
  timer = setTimeout(() => window.nexus.invoke('tab:hover', 'open'), HOVER_DELAY_MS);
});
handle.addEventListener('mouseleave', () => {
  clearTimeout(timer);
  window.nexus.invoke('tab:hover', 'release');
});
handle.addEventListener('click', () => {
  clearTimeout(timer);
  window.nexus.invoke('tab:hover', 'toggle');
});
