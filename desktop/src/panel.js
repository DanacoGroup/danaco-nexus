'use strict';
// Wysuwany panel Nexusa: cienki języczek przy prawej krawędzi ekranu i okno panelu
// (pasek narzędzi lokalny + https://…/?widok=panel). Komunikacja z panelem wg umowy
// postMessage (nexus:context / nexus:prompt / nexus:auth → panel; nexus:ready / insert / copy ← panel).

const path = require('node:path');

const TOOLBAR_HEIGHT = 44;
const TAB_WIDTH = 10;
const TAB_HEIGHT = 120;
const SLIDE_STEPS = 7;
const SLIDE_MS = 14;
const READY_FALLBACK_MS = 4000;

class PanelController {
  /**
   * @param {object} options
   * @param {typeof import('electron')} options.electron
   * @param {import('./config').Config} options.config
   * @param {import('./powershell').WindowHelper} options.helper
   * @param {string} options.partition
   * @param {string} options.uiPreload
   * @param {string} options.panelPreload
   * @param {{info: Function, warn: Function}} options.log
   * @param {() => void} options.openMain
   * @param {() => void} options.openSettings
   * @param {(webContents: import('electron').WebContents) => void} options.guardContents
   * @param {() => boolean} options.isBusy okno zgody otwarte – panel nie chowa się po utracie fokusu
   * @param {() => boolean} options.quitting aplikacja się zamyka (zamknięcie okna nie jest chowaniem)
   * @param {() => string} options.deviceKey klucz urządzenia (tryb panelUsesDeviceKey)
   */
  constructor(options) {
    this.options = options;
    this.tab = null;
    this.window = null;
    this.toolbar = null;
    this.content = null;
    this.visible = false;
    this.pinned = false;
    this.animating = null;
    this.ready = false;
    this.outbox = [];
    this.lastExternal = null;
    this.suppressBlur = false;
    this.loadState = { state: 'nie-zaladowano' };
  }

  panelUrl() {
    return `${this.options.config.get('serverUrl')}/?widok=panel`;
  }

  // --- języczek ---

  createTab() {
    const { BrowserWindow, screen } = this.options.electron;
    const area = screen.getPrimaryDisplay().workArea;
    const offset = Math.min(0.9, Math.max(0.1, Number(this.options.config.get('tabOffset')) || 0.5));
    this.tab = new BrowserWindow({
      width: TAB_WIDTH,
      height: TAB_HEIGHT,
      x: area.x + area.width - TAB_WIDTH,
      y: Math.round(area.y + area.height * offset - TAB_HEIGHT / 2),
      frame: false,
      transparent: true,
      resizable: false,
      movable: false,
      minimizable: false,
      maximizable: false,
      skipTaskbar: true,
      focusable: false,
      alwaysOnTop: true,
      hasShadow: false,
      show: false,
      webPreferences: { preload: this.options.uiPreload, contextIsolation: true, sandbox: true },
    });
    this.tab.setAlwaysOnTop(true, 'screen-saver');
    // Przezroczysta część okna przepuszcza kliknięcia (np. do paska przewijania pod spodem);
    // ruch myszy dociera do strony, która przejmuje kliknięcia tylko nad samym języczkiem.
    this.tab.setIgnoreMouseEvents(true, { forward: true });
    this.tab.loadFile(path.join(__dirname, 'ui', 'tab.html'));
    this.tab.once('ready-to-show', () => {
      // Windows może narzucić minimalną szerokość okna – dosuwamy je do krawędzi.
      const bounds = this.tab.getBounds();
      this.tab.setBounds({ ...bounds, x: area.x + area.width - bounds.width });
      this.tab.showInactive();
    });
    return this.tab;
  }

  /** Języczek przejmuje mysz (nad uchwytem) albo ją przepuszcza. */
  setTabCapturesMouse(captures) {
    if (!this.tab || this.tab.isDestroyed()) return;
    if (captures) this.tab.setIgnoreMouseEvents(false);
    else this.tab.setIgnoreMouseEvents(true, { forward: true });
  }

  // --- okno panelu ---

  createPanel() {
    const { BaseWindow, WebContentsView, screen } = this.options.electron;
    const area = screen.getPrimaryDisplay().workArea;
    const width = this.options.config.get('panelWidth');
    this.window = new BaseWindow({
      width,
      height: area.height,
      x: area.x + area.width,
      y: area.y,
      frame: false,
      show: false,
      resizable: true,
      minWidth: 340,
      maxWidth: 900,
      minimizable: false,
      maximizable: false,
      skipTaskbar: true,
      alwaysOnTop: true,
      backgroundColor: '#0D0F17',
      title: 'Nexus – panel',
    });
    this.window.setAlwaysOnTop(true, 'floating');
    this.toolbar = new WebContentsView({
      webPreferences: { preload: this.options.uiPreload, contextIsolation: true, sandbox: true },
    });
    this.content = new WebContentsView({
      webPreferences: {
        preload: this.options.panelPreload,
        partition: this.options.partition,
        contextIsolation: true,
        sandbox: true,
        nodeIntegration: false,
        spellcheck: true,
      },
    });
    this.toolbar.setBackgroundColor('#191B25');
    this.content.setBackgroundColor('#0D0F17');
    this.window.contentView.addChildView(this.toolbar);
    this.window.contentView.addChildView(this.content);
    this.layout();
    this.window.on('resize', () => {
      this.layout();
      if (!this.animating && this.visible) {
        const [currentWidth] = this.window.getSize();
        this.options.config.update({ panelWidth: currentWidth });
      }
    });
    this.window.on('blur', () => this.onBlur());
    this.window.on('close', (event) => {
      if (!this.options.quitting()) {
        event.preventDefault();
        this.hide();
      }
    });
    this.toolbar.webContents.loadFile(path.join(__dirname, 'ui', 'toolbar.html'));
    this.options.guardContents(this.content.webContents);
    const contents = this.content.webContents;
    contents.on('did-start-loading', () => {
      this.ready = false;
    });
    contents.on('did-finish-load', () => {
      this.loadState = { state: 'zaladowano', url: contents.getURL() };
      setTimeout(() => {
        if (!this.ready) this.flush(true);
      }, READY_FALLBACK_MS);
    });
    contents.on('did-fail-load', (_event, code, description, url, isMainFrame) => {
      if (isMainFrame) this.loadState = { state: 'blad', code, description, url };
    });
    contents.loadURL(this.panelUrl());
    return this.window;
  }

  layout() {
    if (!this.window) return;
    const [width, height] = this.window.getContentSize();
    this.toolbar.setBounds({ x: 0, y: 0, width, height: TOOLBAR_HEIGHT });
    this.content.setBounds({ x: 0, y: TOOLBAR_HEIGHT, width, height: Math.max(0, height - TOOLBAR_HEIGHT) });
  }

  reload() {
    if (this.content) this.content.webContents.loadURL(this.panelUrl());
  }

  onBlur() {
    if (this.pinned || this.suppressBlur || this.options.isBusy()) return;
    setTimeout(() => {
      if (this.window && !this.window.isFocused() && !this.pinned && !this.suppressBlur && !this.options.isBusy()) this.hide();
    }, 180);
  }

  /** Zapamiętuje okno pierwszoplanowe spoza Nexusa (cel „Zobacz ekran” i „Wstaw”). */
  async rememberForeground() {
    try {
      const info = await this.options.helper.foreground();
      if (info && info.pid !== process.pid && info.hwnd !== '0' && info.title !== undefined) {
        this.lastExternal = info;
      }
    } catch (error) {
      this.options.log.warn('Nie udało się odczytać aktywnego okna', { message: error.message });
    }
    return this.lastExternal;
  }

  async show() {
    if (!this.window) this.createPanel();
    await this.rememberForeground();
    const { screen } = this.options.electron;
    const display = screen.getDisplayNearestPoint(screen.getCursorScreenPoint());
    const area = display.workArea;
    const width = this.options.config.get('panelWidth');
    const target = { x: area.x + area.width - width, y: area.y, width, height: area.height };
    if (!this.visible) {
      this.window.setBounds({ ...target, x: area.x + area.width });
      this.window.show();
      await this.slide(area.x + area.width, target.x, target);
    } else {
      this.window.setBounds(target);
    }
    this.visible = true;
    this.window.focus();
    this.content.webContents.focus();
    this.notifyToolbar();
  }

  async hide() {
    if (!this.window || !this.visible) return;
    this.visible = false;
    const bounds = this.window.getBounds();
    const { screen } = this.options.electron;
    const area = screen.getDisplayMatching(bounds).workArea;
    await this.slide(bounds.x, area.x + area.width, bounds);
    this.window.hide();
    this.notifyToolbar();
  }

  toggle() {
    return this.visible ? this.hide() : this.show();
  }

  slide(fromX, toX, bounds) {
    return new Promise((resolve) => {
      clearInterval(this.animating);
      let step = 0;
      this.animating = setInterval(() => {
        step += 1;
        const progress = 1 - (1 - step / SLIDE_STEPS) ** 3;
        const x = Math.round(fromX + (toX - fromX) * progress);
        if (this.window && !this.window.isDestroyed()) this.window.setBounds({ ...bounds, x });
        if (step >= SLIDE_STEPS) {
          clearInterval(this.animating);
          this.animating = null;
          resolve();
        }
      }, SLIDE_MS);
    });
  }

  setPinned(pinned) {
    this.pinned = Boolean(pinned);
    this.notifyToolbar();
  }

  notifyToolbar() {
    if (this.toolbar && !this.toolbar.webContents.isDestroyed()) {
      this.toolbar.webContents.send('panel:state', { pinned: this.pinned, visible: this.visible });
    }
  }

  /** Chowa okna Nexusa na czas zrzutu całego ekranu. */
  async setHiddenForCapture(hidden) {
    if (!this.window || !this.visible) return;
    this.suppressBlur = hidden;
    this.window.setOpacity(hidden ? 0 : 1);
    if (this.tab) this.tab.setOpacity(hidden ? 0 : 1);
    await new Promise((resolve) => setTimeout(resolve, hidden ? 120 : 0));
  }

  // --- umowa postMessage ---

  post(message) {
    this.outbox.push(message);
    this.flush(false);
  }

  flush(force) {
    if (!this.content || (!this.ready && !force)) return;
    const contents = this.content.webContents;
    while (this.outbox.length) contents.send('panel:post', this.outbox.shift());
  }

  /** Komunikat ze strony panelu (przez preload). */
  onPanelMessage(message) {
    if (!message || typeof message !== 'object') return;
    if (message.type === 'nexus:ready') {
      this.ready = true;
      const key = this.options.config.get('panelUsesDeviceKey') ? this.options.deviceKey() : '';
      if (key) this.outbox.unshift({ type: 'nexus:auth', token: key });
      this.flush(false);
    } else if (message.type === 'nexus:copy') {
      this.options.electron.clipboard.writeText(String(message.text || ''));
    } else if (message.type === 'nexus:insert') {
      this.insert(String(message.text || ''));
    }
  }

  /** „Wstaw”: schowek + wklejenie w oknie aktywnym przed otwarciem panelu. */
  async insert(text) {
    const { clipboard, Notification } = this.options.electron;
    clipboard.writeText(text);
    const target = this.lastExternal;
    if (!target || !target.hwnd || target.hwnd === '0') {
      if (Notification.isSupported()) {
        new Notification({ title: 'Nexus', body: 'Skopiowano odpowiedź do schowka – wklej ją Ctrl+V.' }).show();
      }
      return;
    }
    if (!this.pinned) await this.hide();
    try {
      await this.options.helper.paste(target.hwnd);
      this.options.log.info('Wstawiono tekst', { window: target.title, process: target.process });
    } catch (error) {
      this.options.log.warn('Wklejanie nie powiodło się', { message: error.message });
      if (Notification.isSupported()) {
        new Notification({ title: 'Nexus', body: 'Nie udało się wkleić – tekst jest w schowku (Ctrl+V).' }).show();
      }
    }
  }

  /** „Zobacz ekran”: zrzut okna aktywnego (albo ekranu) → nexus:context. */
  async seeScreen(capture, whole) {
    if (!this.visible) await this.show();
    const shot = whole ? await capture.captureScreen(0, 1600) : await capture.captureWindow(1600);
    const title = shot.title || 'Ekran';
    this.post({
      type: 'nexus:context',
      context: {
        kind: 'screen',
        title,
        url: '',
        text: shot.process ? `Okno programu ${shot.process}: „${title}”` : title,
        image: `data:image/jpeg;base64,${shot.image.toJPEG(82).toString('base64')}`,
      },
    });
    return shot;
  }

  destroy() {
    clearInterval(this.animating);
    if (this.tab && !this.tab.isDestroyed()) this.tab.destroy();
    if (this.window && !this.window.isDestroyed()) this.window.destroy();
  }
}

module.exports = { PanelController, TOOLBAR_HEIGHT };
