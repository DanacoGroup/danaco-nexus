'use strict';
// Okno zgody na polecenie PowerShell zmieniające system: pełne polecenie, opis od asystenta,
// powody i ostrzeżenia. Domyślna odpowiedź to odmowa (także po czasie i po zamknięciu okna).

const path = require('node:path');

const DEFAULT_TIMEOUT_MS = 240000;

class ConfirmManager {
  /**
   * @param {object} options
   * @param {typeof import('electron')} options.electron
   * @param {string} options.preload
   * @param {string} options.icon
   * @param {number} [options.timeoutMs]
   */
  constructor(options) {
    this.options = options;
    this.queue = [];
    this.current = null;
    this.byWebContents = new Map();
  }

  /** Czeka na decyzję użytkownika; true tylko po kliknięciu „Wykonaj”. */
  ask(request, signal) {
    return new Promise((resolve) => {
      const item = { request, signal, resolve, done: false };
      if (signal) {
        if (signal.aborted) return resolve(false);
        signal.addEventListener('abort', () => this.finish(item, false), { once: true });
      }
      this.queue.push(item);
      this.next();
    });
  }

  next() {
    if (this.current || !this.queue.length) return;
    const item = this.queue.shift();
    if (item.done) return this.next();
    this.current = item;
    const { BrowserWindow } = this.options.electron;
    const window = new BrowserWindow({
      width: 680,
      height: 560,
      minWidth: 480,
      minHeight: 400,
      show: false,
      alwaysOnTop: true,
      minimizable: false,
      maximizable: false,
      title: 'Nexus – zatwierdź polecenie',
      icon: this.options.icon,
      backgroundColor: '#212121',
      autoHideMenuBar: true,
      webPreferences: { preload: this.options.preload, contextIsolation: true, sandbox: true, nodeIntegration: false },
    });
    item.window = window;
    const contentsId = window.webContents.id;
    this.byWebContents.set(contentsId, item);
    item.timer = setTimeout(() => this.finish(item, false), this.options.timeoutMs || DEFAULT_TIMEOUT_MS);
    window.on('closed', () => {
      this.byWebContents.delete(contentsId);
      this.finish(item, false);
    });
    window.once('ready-to-show', () => {
      window.show();
      window.focus();
      window.flashFrame(true);
    });
    window.loadFile(path.join(__dirname, 'ui', 'confirm.html'));
  }

  /** Dane okna zgody dla strony (wywołanie z preload). */
  details(webContentsId) {
    const item = this.byWebContents.get(webContentsId);
    if (!item) return null;
    const { command, description, reasons, warnings, admin } = item.request;
    return {
      command,
      admin: Boolean(admin),
      description,
      reasons: reasons || [],
      warnings: warnings || [],
      timeoutSeconds: Math.round((this.options.timeoutMs || DEFAULT_TIMEOUT_MS) / 1000),
    };
  }

  answer(webContentsId, accepted) {
    const item = this.byWebContents.get(webContentsId);
    if (item) this.finish(item, accepted === true);
  }

  finish(item, accepted) {
    if (item.done) return;
    item.done = true;
    clearTimeout(item.timer);
    item.resolve(accepted);
    if (item.window && !item.window.isDestroyed()) item.window.destroy();
    if (this.current === item) {
      this.current = null;
      this.next();
    }
  }

  get busy() {
    return Boolean(this.current);
  }
}

module.exports = { ConfirmManager };
