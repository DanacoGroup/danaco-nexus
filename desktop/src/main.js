'use strict';
// Nexus Desktop – proces główny: okno Nexusa, zasobnik, wysuwany panel, skróty,
// lokalny agent komputera (narzędzia pc_*) i tryb testu uruchomienia (--smoke-test).

const os = require('node:os');
const path = require('node:path');
const electron = require('electron');
const { Config, normalizeServerUrl } = require('./config');
const { Logger } = require('./logger');
const { WindowHelper } = require('./powershell');
const { PanelController } = require('./panel');
const { ConfirmManager } = require('./confirm');
const { PcTools } = require('./agent/tools');
const { AgentConnection } = require('./agent/connection');

const { app, BrowserWindow, Menu, Notification, Tray, globalShortcut, ipcMain, nativeImage, net, screen, session, shell } = electron;

const SMOKE = process.argv.includes('--smoke-test');
const START_HIDDEN = process.argv.includes('--ukryty');
const PARTITION = 'persist:nexus';
const ASSETS = path.join(__dirname, '..', 'assets');
const ICON = path.join(ASSETS, 'icon.png');
const UI_PRELOAD = path.join(__dirname, 'preload', 'ui.js');
const PANEL_PRELOAD = path.join(__dirname, 'preload', 'panel.js');
const ALLOWED_PERMISSIONS = new Set(['media', 'notifications', 'clipboard-sanitized-write', 'fullscreen', 'speaker-selection']);

// Test uruchomienia działa na świeżym, pustym profilu (bez kluczy i sesji użytkownika).
if (SMOKE) app.setPath('userData', require('node:fs').mkdtempSync(path.join(os.tmpdir(), 'nexus-desktop-test-')));
app.setAppUserModelId('pl.danaco.nexus.desktop');

const state = {
  quitting: false,
  config: null,
  log: null,
  helper: null,
  panel: null,
  confirm: null,
  tools: null,
  agent: null,
  tray: null,
  mainWindow: null,
  settingsWindow: null,
  trayHintShown: false,
};

// --- adresy i bezpieczeństwo treści zdalnych ---

function serverUrl() {
  return state.config.get('serverUrl');
}

/** Adres z tej samej witryny co serwer Nexusa (także poddomeny, np. chmura). */
function sameSite(url) {
  try {
    const target = new URL(url);
    const base = new URL(serverUrl());
    return target.protocol === base.protocol && (target.hostname === base.hostname || target.hostname.endsWith(`.${base.hostname}`));
  } catch {
    return false;
  }
}

function openExternal(url) {
  if (/^(https?:|mailto:)/i.test(String(url))) shell.openExternal(url);
}

function guardContents(contents) {
  contents.on('will-navigate', (event, url) => {
    if (!sameSite(url)) {
      event.preventDefault();
      openExternal(url);
    }
  });
  contents.setWindowOpenHandler(({ url }) => {
    if (sameSite(url)) {
      return {
        action: 'allow',
        overrideBrowserWindowOptions: {
          icon: ICON,
          autoHideMenuBar: true,
          backgroundColor: '#212121',
          webPreferences: { partition: PARTITION, contextIsolation: true, sandbox: true },
        },
      };
    }
    openExternal(url);
    return { action: 'deny' };
  });
}

function configureSession() {
  const nexusSession = session.fromPartition(PARTITION);
  nexusSession.setPermissionRequestHandler((contents, permission, callback, details) => {
    callback(ALLOWED_PERMISSIONS.has(permission) && sameSite(details.requestingUrl || contents.getURL()));
  });
  nexusSession.setPermissionCheckHandler((_contents, permission, origin) => ALLOWED_PERMISSIONS.has(permission) && sameSite(origin));
  return nexusSession;
}

// --- okno główne ---

function visibleBounds(saved) {
  if (!saved || !saved.width || !saved.height) return {};
  const onScreen = screen.getAllDisplays().some((display) => {
    const area = display.workArea;
    return saved.x < area.x + area.width - 80 && saved.x + saved.width > area.x + 80 && saved.y >= area.y - 10 && saved.y < area.y + area.height - 80;
  });
  return onScreen ? { x: saved.x, y: saved.y, width: saved.width, height: saved.height } : { width: saved.width, height: saved.height };
}

function createMainWindow(show) {
  const saved = state.config.get('window');
  const window = new BrowserWindow({
    width: 1280,
    height: 860,
    ...visibleBounds(saved),
    minWidth: 420,
    minHeight: 480,
    show: false,
    title: 'Nexus',
    icon: ICON,
    backgroundColor: '#212121',
    autoHideMenuBar: true,
    webPreferences: { partition: PARTITION, contextIsolation: true, sandbox: true, spellcheck: true },
  });
  window.setMenu(null);
  guardContents(window.webContents);
  let saveTimer = null;
  const remember = () => {
    clearTimeout(saveTimer);
    saveTimer = setTimeout(() => {
      if (window.isDestroyed() || window.isMinimized()) return;
      const bounds = window.getNormalBounds();
      state.config.update({ window: { ...bounds, maximized: window.isMaximized() } });
    }, 500);
  };
  window.on('resize', remember);
  window.on('move', remember);
  window.on('maximize', remember);
  window.on('unmaximize', remember);
  window.on('close', (event) => {
    if (state.quitting) return;
    event.preventDefault();
    window.hide();
    if (!state.trayHintShown && Notification.isSupported()) {
      state.trayHintShown = true;
      new Notification({ title: 'Nexus działa w tle', body: 'Panel otworzysz skrótem lub języczkiem przy prawej krawędzi ekranu. Zamknięcie: menu ikony w zasobniku.' }).show();
    }
  });
  window.once('ready-to-show', () => {
    if (saved && saved.maximized) window.maximize();
    if (show) window.show();
  });
  window.loadURL(serverUrl());
  state.mainWindow = window;
  return window;
}

function showMain() {
  if (!state.mainWindow || state.mainWindow.isDestroyed()) createMainWindow(true);
  const window = state.mainWindow;
  if (window.isMinimized()) window.restore();
  window.show();
  window.focus();
}

// --- ustawienia ---

function openSettings() {
  if (state.settingsWindow && !state.settingsWindow.isDestroyed()) {
    state.settingsWindow.show();
    state.settingsWindow.focus();
    return state.settingsWindow;
  }
  const window = new BrowserWindow({
    width: 620,
    height: 760,
    minWidth: 460,
    title: 'Nexus Desktop – ustawienia',
    icon: ICON,
    backgroundColor: '#212121',
    autoHideMenuBar: true,
    show: false,
    webPreferences: { preload: UI_PRELOAD, contextIsolation: true, sandbox: true },
  });
  window.setMenu(null);
  window.once('ready-to-show', () => window.show());
  window.loadFile(path.join(__dirname, 'ui', 'settings.html'));
  state.settingsWindow = window;
  return window;
}

function applyAutostart(enabled) {
  if (!app.isPackaged) {
    state.log.info('Autostart pominięty (aplikacja uruchomiona z kodu źródłowego).');
    return;
  }
  app.setLoginItemSettings({ openAtLogin: Boolean(enabled), path: process.execPath, args: ['--ukryty'] });
}

function registerShortcuts(values = state.config.values) {
  globalShortcut.unregisterAll();
  const errors = [];
  const bind = (accelerator, action, label) => {
    if (!accelerator) return;
    try {
      if (!globalShortcut.register(accelerator, action)) errors.push(`Skrót ${label} „${accelerator}” jest zajęty przez inny program.`);
    } catch {
      errors.push(`Skrót ${label} „${accelerator}” ma nieprawidłowy format.`);
    }
  };
  bind(values.shortcut, () => state.panel.toggle(), 'panelu');
  bind(values.screenShortcut, () => seeScreen(false), '„zobacz ekran”');
  return errors;
}

// --- klucz urządzenia z sesji okna ---

function requestJson(method, url, body) {
  return new Promise((resolve, reject) => {
    const request = net.request({ method, url, session: session.fromPartition(PARTITION), useSessionCookies: true });
    request.setHeader('Content-Type', 'application/json');
    request.setHeader('X-Nexus-Request', '1');
    const chunks = [];
    request.on('response', (response) => {
      response.on('data', (chunk) => chunks.push(chunk));
      response.on('end', () => {
        let json = null;
        try {
          json = JSON.parse(Buffer.concat(chunks).toString('utf8'));
        } catch {
          json = null;
        }
        resolve({ status: response.statusCode, json });
      });
      response.on('error', reject);
    });
    request.on('error', reject);
    if (body) request.write(JSON.stringify(body));
    request.end();
  });
}

async function connectFromSession() {
  const name = `Nexus Desktop (${os.hostname()})`.slice(0, 100);
  let response;
  try {
    response = await requestJson('POST', `${serverUrl()}/api/urzadzenia`, { name, kind: 'desktop' });
  } catch (error) {
    return { ok: false, message: `Brak połączenia z Nexusem: ${error.message}` };
  }
  if (response.status === 401 || response.status === 403) {
    showMain();
    return { ok: false, message: 'Najpierw zaloguj się w oknie Nexusa (otwarte obok), potem kliknij „Połącz komputer” ponownie.' };
  }
  if (response.status !== 201 || !response.json || !response.json.token) {
    return { ok: false, message: `Serwer nie utworzył klucza (kod ${response.status}).` };
  }
  state.config.setDeviceKey(response.json.token);
  state.log.info('Utworzono klucz urządzenia z sesji okna', { name });
  restartAgent();
  return { ok: true, message: `Komputer połączony z Nexusem jako „${name}”.` };
}

// --- agent komputera ---

function restartAgent() {
  if (state.config.get('agentEnabled')) state.agent.restart();
  else state.agent.stop();
}

function updateTray() {
  if (!state.tray) return;
  const status = state.agent.status;
  const menu = Menu.buildFromTemplate([
    { label: 'Otwórz Nexusa', click: showMain },
    { label: `Panel boczny (${state.config.get('shortcut') || 'bez skrótu'})`, click: () => state.panel.toggle() },
    { label: 'Zobacz ekran w panelu', click: () => seeScreen(false) },
    { type: 'separator' },
    { label: `Agent komputera: ${status.message}`, enabled: false },
    { label: 'Ustawienia…', click: openSettings },
    {
      label: 'Uruchamiaj z Windows',
      type: 'checkbox',
      checked: Boolean(state.config.get('autostart')),
      click: (item) => {
        state.config.update({ autostart: item.checked });
        applyAutostart(item.checked);
      },
    },
    { type: 'separator' },
    {
      label: 'Zakończ',
      click: () => {
        state.quitting = true;
        app.quit();
      },
    },
  ]);
  state.tray.setContextMenu(menu);
  state.tray.setToolTip(`Nexus – ${status.message}`);
}

async function seeScreen(whole) {
  try {
    await state.panel.seeScreen(state.tools, whole);
  } catch (error) {
    state.log.warn('Zobacz ekran: błąd', { message: error.message });
    if (Notification.isSupported()) new Notification({ title: 'Nexus', body: `Nie udało się wykonać zrzutu: ${error.message}` }).show();
  }
}

// --- IPC ---

function fromLocalPage(event) {
  return event.senderFrame && event.senderFrame.url.startsWith('file://');
}

function registerIpc() {
  ipcMain.on('panel:message', (event, message) => {
    if (state.panel.content && event.sender === state.panel.content.webContents) state.panel.onPanelMessage(message);
  });
  const handle = (channel, handler) =>
    ipcMain.handle(channel, (event, ...args) => {
      if (!fromLocalPage(event)) throw new Error('Niedozwolone źródło żądania.');
      return handler(event, ...args);
    });
  handle('tab:hover', (_event, mode) => {
    if (mode === 'capture' || mode === 'release') return state.panel.setTabCapturesMouse(mode === 'capture');
    return mode === 'toggle' ? state.panel.toggle() : state.panel.show();
  });
  handle('panel:action', async (_event, action) => {
    const actions = {
      'see-window': () => seeScreen(false),
      'see-screen': () => seeScreen(true),
      pin: () => state.panel.setPinned(!state.panel.pinned),
      main: () => showMain(),
      reload: () => state.panel.reload(),
      settings: () => openSettings(),
      hide: () => state.panel.hide(),
    };
    if (actions[action]) await actions[action]();
  });
  handle('confirm:get', (event) => state.confirm.details(event.sender.id));
  handle('confirm:answer', (event, accepted) => state.confirm.answer(event.sender.id, accepted === true));
  handle('settings:get', () => {
    const { window: _window, ...values } = state.config.values;
    return { version: app.getVersion(), values, hasDeviceKey: state.config.hasDeviceKey(), agentStatus: state.agent.status };
  });
  handle('settings:save', (_event, changes) => saveSettings(changes || {}));
  handle('device:connect', () => connectFromSession());
  handle('device:set-key', (_event, key) => {
    state.config.setDeviceKey(key);
    restartAgent();
    return { ok: true, message: 'Klucz zapisany – łączenie z Nexusem.' };
  });
  handle('device:clear', () => {
    state.config.clearDeviceKey();
    restartAgent();
    return { ok: true, message: 'Klucz usunięty z tego komputera. Cofnij go także na stronie „Urządzenia” w Nexusie.' };
  });
}

function saveSettings(changes) {
  const previous = { ...state.config.values };
  const next = { ...changes };
  if ('serverUrl' in next) {
    const normalized = normalizeServerUrl(next.serverUrl);
    if (!normalized) return { ok: false, message: 'Adres Nexusa musi zaczynać się od https://.' };
    next.serverUrl = normalized;
  }
  const errors = registerShortcuts({ ...previous, ...next });
  if (errors.length) {
    registerShortcuts(previous);
    return { ok: false, message: errors.join(' ') };
  }
  const values = state.config.update(next);
  if (values.autostart !== previous.autostart) applyAutostart(values.autostart);
  if (values.serverUrl !== previous.serverUrl) {
    if (state.mainWindow && !state.mainWindow.isDestroyed()) state.mainWindow.loadURL(values.serverUrl);
    state.panel.reload();
  }
  if (values.serverUrl !== previous.serverUrl || values.agentEnabled !== previous.agentEnabled) restartAgent();
  updateTray();
  return { ok: true, message: 'Zapisano.' };
}

// --- start ---

function initialize() {
  state.config = new Config(app.getPath('userData'), electron.safeStorage);
  state.log = new Logger(app.getPath('userData'));
  state.log.info('Start Nexus Desktop', { version: app.getVersion(), electron: process.versions.electron, smoke: SMOKE });
  state.helper = new WindowHelper(state.log);
  state.helper.start().catch((error) => state.log.warn('Proces pomocniczy', { message: error.message }));
  configureSession();
  state.confirm = new ConfirmManager({ electron, preload: UI_PRELOAD, icon: ICON });
  state.panel = new PanelController({
    electron,
    config: state.config,
    helper: state.helper,
    partition: PARTITION,
    uiPreload: UI_PRELOAD,
    panelPreload: PANEL_PRELOAD,
    log: state.log,
    openMain: showMain,
    openSettings,
    guardContents,
    isBusy: () => state.confirm.busy,
    quitting: () => state.quitting,
    deviceKey: () => state.config.deviceKey(),
  });
  state.tools = new PcTools({
    electron,
    config: state.config,
    confirm: state.confirm,
    log: state.log,
    lastExternalWindow: () => state.panel.rememberForeground(),
    hideOwnWindows: (hidden) => state.panel.setHiddenForCapture(hidden),
  });
  state.agent = new AgentConnection({
    serverUrl,
    deviceKey: () => state.config.deviceKey(),
    handle: (tool, args, signal) => state.tools.handle(tool, args, signal),
    version: app.getVersion(),
    log: state.log,
  });
  state.agent.on('status', (status) => {
    updateTray();
    if (state.settingsWindow && !state.settingsWindow.isDestroyed()) state.settingsWindow.webContents.send('agent:status', status);
  });
  registerIpc();
}

function start() {
  initialize();
  state.tray = new Tray(nativeImage.createFromPath(path.join(ASSETS, 'tray.png')));
  state.tray.on('click', showMain);
  updateTray();
  state.panel.createTab();
  createMainWindow(!START_HIDDEN);
  const errors = registerShortcuts();
  if (errors.length && Notification.isSupported()) new Notification({ title: 'Nexus', body: errors.join(' ') }).show();
  if (state.config.get('agentEnabled')) state.agent.start();
  if (!state.config.hasDeviceKey() && !START_HIDDEN) setTimeout(openSettings, 1500);
}

app.on('before-quit', () => {
  state.quitting = true;
});
app.on('will-quit', () => {
  globalShortcut.unregisterAll();
  if (state.agent) state.agent.stop();
  if (state.helper) state.helper.stop();
});
app.on('window-all-closed', () => {
  // Aplikacja zostaje w zasobniku.
});

if (SMOKE) {
  app.whenReady().then(() => require('./smoke').run({ app, state, initialize, createMainWindow, openSettings, registerShortcuts }));
} else if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on('second-instance', showMain);
  app.whenReady().then(start);
}

