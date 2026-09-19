'use strict';
// Ustawienia Nexus Desktop. Klucz urządzenia nigdy nie wraca do tej strony.

const $ = (id) => document.getElementById(id);
const TOGGLES = ['agentEnabled', 'allowFiles', 'allowScreenshots', 'allowPowershell', 'autostart', 'panelUsesDeviceKey'];
const TEXTS = ['shortcut', 'screenShortcut', 'serverUrl'];

function say(element, text, kind) {
  element.textContent = text || '';
  element.className = `message ${kind || ''}`;
}

function showStatus(status) {
  const element = $('agent-status');
  element.dataset.state = status.state;
  element.textContent = status.message;
}

async function load() {
  const settings = await window.nexus.invoke('settings:get');
  $('version').textContent = `Wersja ${settings.version}`;
  for (const name of TOGGLES) $(name).checked = Boolean(settings.values[name]);
  for (const name of TEXTS) $(name).value = settings.values[name] || '';
  $('key-state').textContent = settings.hasDeviceKey
    ? 'Ten komputer ma zapisany klucz urządzenia.'
    : 'Ten komputer nie ma jeszcze klucza urządzenia.';
  showStatus(settings.agentStatus);
}

async function run(button, target, action) {
  button.disabled = true;
  say(target, 'Chwileczkę…');
  try {
    const result = await action();
    say(target, result.message, result.ok ? 'ok' : 'error');
  } catch (error) {
    say(target, error.message, 'error');
  } finally {
    button.disabled = false;
    await load();
  }
}

$('connect').addEventListener('click', () => run($('connect'), $('device-message'), () => window.nexus.invoke('device:connect')));
$('disconnect').addEventListener('click', () => run($('disconnect'), $('device-message'), () => window.nexus.invoke('device:clear')));
$('save-key').addEventListener('click', () =>
  run($('save-key'), $('device-message'), async () => {
    const result = await window.nexus.invoke('device:set-key', $('manual-key').value);
    $('manual-key').value = '';
    return result;
  }),
);
$('save').addEventListener('click', () =>
  run($('save'), $('save-message'), () => {
    const values = {};
    for (const name of TOGGLES) values[name] = $(name).checked;
    for (const name of TEXTS) values[name] = $(name).value.trim();
    return window.nexus.invoke('settings:save', values);
  }),
);
window.nexus.on('agent:status', showStatus);
$('close').addEventListener('click', () => window.nexus.invoke('overlay:action', 'close'));
document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape' && !event.target.closest('input')) window.nexus.invoke('overlay:action', 'close');
});

load();
