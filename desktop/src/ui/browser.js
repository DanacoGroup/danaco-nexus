'use strict';
// Pasek warstwy strony (np. chmura) w oknie Nexusa: powrót do aplikacji i nawigacja.

const $ = (id) => document.getElementById(id);
const act = (action) => window.nexus.invoke('overlay:action', action);

$('close').addEventListener('click', () => act('close'));
$('back').addEventListener('click', () => act('back'));
$('reload').addEventListener('click', () => act('reload'));
$('external').addEventListener('click', () => act('external'));
document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape') act('close');
});
window.nexus.on('overlay:page', (page) => {
  $('title').textContent = page.title || page.url || '';
  $('title').title = page.url || '';
});
