'use strict';
// Zgoda na polecenie (warstwa w oknie Nexusa): treść wyłącznie przez textContent (polecenie i opis pochodzą od modelu).

const $ = (id) => document.getElementById(id);

async function init() {
  const details = await window.nexus.invoke('confirm:get');
  if (!details) return;
  $('description').textContent = details.description || '(asystent nie podał opisu)';
  $('command').textContent = details.command;
  for (const reason of details.reasons) {
    const item = document.createElement('li');
    item.textContent = reason;
    $('reasons').append(item);
  }
  if (details.admin) {
    $('title').textContent = 'Asystent chce wykonać polecenie jako administrator';
  }
  for (const warning of details.warnings) {
    const box = document.createElement('div');
    box.className = 'warning';
    box.textContent = `Uwaga: ${warning}`;
    $('warnings').append(box);
  }
  let left = details.timeoutSeconds;
  const tick = () => {
    $('timeout').textContent = `Bez decyzji polecenie zostanie odrzucone za ${left} s.`;
    left -= 1;
  };
  tick();
  setInterval(tick, 1000);
  // Przycisk „Wykonaj” aktywny po chwili – chroni przed przypadkowym Enterem.
  $('accept').disabled = true;
  setTimeout(() => {
    $('accept').disabled = false;
  }, 1200);
  $('reject').focus();
}

$('accept').addEventListener('click', () => window.nexus.invoke('confirm:answer', true));
$('reject').addEventListener('click', () => window.nexus.invoke('confirm:answer', false));
document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape') window.nexus.invoke('confirm:answer', false);
});

init();
