'use strict';
// Ustawienia aplikacji (plik JSON w katalogu danych) i klucz urządzenia zaszyfrowany
// przez safeStorage (DPAPI konta Windows). Klucza nigdy nie pokazujemy w interfejsie.

const fs = require('node:fs');
const path = require('node:path');

const DEFAULTS = {
  serverUrl: 'https://danaco-nexus.pl',
  shortcut: 'Control+Space',
  screenShortcut: 'Control+Shift+Space',
  autostart: false,
  agentEnabled: true,
  allowFiles: true,
  allowScreenshots: true,
  allowPowershell: true,
  panelUsesDeviceKey: false,
  panelWidth: 440,
  tabOffset: 0.5,
  window: null,
};

const KEY_PREFIX = 'nxd_';

class Config {
  /**
   * @param {string} directory katalog danych aplikacji
   * @param {{isEncryptionAvailable: () => boolean, encryptString: (s: string) => Buffer, decryptString: (b: Buffer) => string}} safeStorage
   */
  constructor(directory, safeStorage) {
    this.directory = directory;
    this.file = path.join(directory, 'ustawienia.json');
    this.keyFile = path.join(directory, 'klucz-urzadzenia.bin');
    this.safeStorage = safeStorage;
    this.values = { ...DEFAULTS };
    this.load();
  }

  load() {
    try {
      const stored = JSON.parse(fs.readFileSync(this.file, 'utf8'));
      if (stored && typeof stored === 'object') this.values = { ...DEFAULTS, ...stored };
    } catch {
      this.values = { ...DEFAULTS };
    }
  }

  get(name) {
    return this.values[name];
  }

  /** Zapisuje zmienione pola (tylko znane klucze, z kontrolą typów). */
  update(changes) {
    for (const [key, value] of Object.entries(changes || {})) {
      if (!(key in DEFAULTS)) continue;
      const expected = DEFAULTS[key] === null ? 'object' : typeof DEFAULTS[key];
      if (value !== null && typeof value !== expected) continue;
      this.values[key] = value;
    }
    this.values.serverUrl = normalizeServerUrl(this.values.serverUrl) || DEFAULTS.serverUrl;
    this.values.panelWidth = Math.min(900, Math.max(340, Number(this.values.panelWidth) || DEFAULTS.panelWidth));
    fs.mkdirSync(this.directory, { recursive: true });
    const temporary = `${this.file}.tmp`;
    fs.writeFileSync(temporary, JSON.stringify(this.values, null, 2), 'utf8');
    fs.renameSync(temporary, this.file);
    return this.values;
  }

  hasDeviceKey() {
    return fs.existsSync(this.keyFile);
  }

  /** Klucz urządzenia albo pusty napis (brak, uszkodzony plik, inny użytkownik Windows). */
  deviceKey() {
    try {
      const data = fs.readFileSync(this.keyFile);
      const key = this.safeStorage.decryptString(data);
      return key.startsWith(KEY_PREFIX) ? key : '';
    } catch {
      return '';
    }
  }

  setDeviceKey(key) {
    const value = String(key || '').trim();
    if (!/^nxd_[A-Za-z0-9_-]{20,}$/.test(value)) {
      throw new Error('To nie jest klucz urządzenia Nexusa (powinien zaczynać się od „nxd_”).');
    }
    if (!this.safeStorage.isEncryptionAvailable()) {
      throw new Error('Szyfrowanie Windows (DPAPI) jest niedostępne – klucz nie może zostać zapisany.');
    }
    fs.mkdirSync(this.directory, { recursive: true });
    fs.writeFileSync(this.keyFile, this.safeStorage.encryptString(value), { mode: 0o600 });
  }

  clearDeviceKey() {
    fs.rmSync(this.keyFile, { force: true });
  }
}

/** Adres serwera w postaci https://host[:port] (bez ścieżki); pusty napis, gdy nieprawidłowy. */
function normalizeServerUrl(value) {
  try {
    const url = new URL(String(value || '').trim());
    if (url.protocol !== 'https:' && !(url.protocol === 'http:' && ['localhost', '127.0.0.1'].includes(url.hostname))) {
      return '';
    }
    return url.origin;
  } catch {
    return '';
  }
}

module.exports = { Config, DEFAULTS, normalizeServerUrl };
