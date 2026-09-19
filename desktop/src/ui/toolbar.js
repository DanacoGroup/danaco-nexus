'use strict';
// Pasek narzędzi panelu: akcje wykonuje proces główny (kanał panel:action).

const pin = document.querySelector('[data-action="pin"]');

for (const button of document.querySelectorAll('[data-action]')) {
  button.addEventListener('click', async () => {
    const action = button.dataset.action;
    button.disabled = true;
    try {
      await window.nexus.invoke('panel:action', action);
    } finally {
      button.disabled = false;
    }
  });
}

window.nexus.on('panel:state', (state) => {
  pin.setAttribute('aria-pressed', state.pinned ? 'true' : 'false');
});

document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape') window.nexus.invoke('panel:action', 'hide');
});
