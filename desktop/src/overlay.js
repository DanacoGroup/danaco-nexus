'use strict';
// Warstwy w oknie głównym: ustawienia, zgoda na polecenie i strony Nexusa (np. chmura)
// wyświetlane nad treścią okna zamiast w osobnych oknach. Naraz widoczna jest jedna warstwa;
// zgoda na polecenie ma pierwszeństwo przed pozostałymi.

const path = require('node:path');

const BAR_HEIGHT = 44;
const PRIORITY = { zgoda: 2, ustawienia: 1, strona: 1 };

class OverlayHost {
  /**
   * @param {object} options
   * @param {typeof import('electron')} options.electron
   * @param {() => import('electron').BrowserWindow} options.window okno główne (pokazane i aktywne)
   * @param {string} options.preload preload stron lokalnych
   * @param {string} options.partition sesja stron Nexusa
   * @param {(webContents: import('electron').WebContents) => void} options.guardContents
   */
  constructor(options) {
    this.options = options;
    this.current = null;
    this.onResize = () => this.layout();
  }

  get kind() {
    return this.current ? this.current.kind : null;
  }

  /** Treść bieżącej warstwy (strona lokalna albo strona Nexusa). */
  get webContents() {
    if (!this.current) return null;
    return (this.current.content || this.current.view).webContents;
  }

  localView() {
    const { WebContentsView } = this.options.electron;
    const view = new WebContentsView({
      webPreferences: { preload: this.options.preload, contextIsolation: true, sandbox: true, nodeIntegration: false },
    });
    view.setBackgroundColor('#0D0F17');
    return view;
  }

  /** Pokazuje lokalną stronę (ustawienia, zgoda) jako warstwę; zwraca jej WebContentsView. */
  openPage(kind, file) {
    if (!this.canReplace(kind)) return null;
    this.close();
    const view = this.localView();
    this.attach({ kind, view });
    view.webContents.loadFile(path.join(__dirname, 'ui', file));
    view.webContents.focus();
    return view;
  }

  /** Strona Nexusa (np. chmura) w warstwie z paskiem „Wróć do Nexusa”. */
  openUrl(url) {
    if (this.kind === 'strona' && this.current.content) {
      this.current.content.webContents.loadURL(url);
      return this.current.content;
    }
    if (!this.canReplace('strona')) return null;
    this.close();
    const { WebContentsView } = this.options.electron;
    const bar = this.localView();
    bar.setBackgroundColor('#191B25');
    const content = new WebContentsView({
      webPreferences: { partition: this.options.partition, contextIsolation: true, sandbox: true, spellcheck: true },
    });
    content.setBackgroundColor('#0D0F17');
    this.options.guardContents(content.webContents);
    this.attach({ kind: 'strona', view: bar, content });
    bar.webContents.loadFile(path.join(__dirname, 'ui', 'browser.html'));
    const title = () => {
      if (!bar.webContents.isDestroyed()) bar.webContents.send('overlay:page', { title: content.webContents.getTitle(), url: content.webContents.getURL() });
    };
    content.webContents.on('page-title-updated', title);
    content.webContents.on('did-navigate', title);
    content.webContents.on('did-navigate-in-page', title);
    bar.webContents.on('did-finish-load', title);
    content.webContents.loadURL(url);
    content.webContents.focus();
    return content;
  }

  canReplace(kind) {
    return !this.current || (PRIORITY[kind] || 0) >= (PRIORITY[this.current.kind] || 0);
  }

  attach(entry) {
    const window = this.options.window();
    this.current = { ...entry, window };
    window.contentView.addChildView(entry.view);
    if (entry.content) window.contentView.addChildView(entry.content);
    window.on('resize', this.onResize);
    this.layout();
  }

  layout() {
    if (!this.current || this.current.window.isDestroyed()) return;
    const [width, height] = this.current.window.getContentSize();
    if (this.current.content) {
      this.current.view.setBounds({ x: 0, y: 0, width, height: BAR_HEIGHT });
      this.current.content.setBounds({ x: 0, y: BAR_HEIGHT, width, height: Math.max(0, height - BAR_HEIGHT) });
    } else {
      this.current.view.setBounds({ x: 0, y: 0, width, height });
    }
  }

  /** Zamyka warstwę (tylko danego rodzaju, gdy podano ``kind``). */
  close(kind) {
    const entry = this.current;
    if (!entry || (kind && entry.kind !== kind)) return false;
    this.current = null;
    const { window } = entry;
    if (!window.isDestroyed()) {
      window.removeListener('resize', this.onResize);
      for (const view of [entry.view, entry.content]) {
        if (!view) continue;
        window.contentView.removeChildView(view);
      }
      window.webContents.focus();
    }
    for (const view of [entry.view, entry.content]) {
      if (view && !view.webContents.isDestroyed()) view.webContents.close();
    }
    return true;
  }

  /** Nawigacja w warstwie strony (pasek „Wróć”). */
  navigate(action) {
    if (this.kind !== 'strona') return;
    const contents = this.current.content.webContents;
    if (action === 'back' && contents.navigationHistory.canGoBack()) contents.navigationHistory.goBack();
    else if (action === 'reload') contents.reload();
  }

  /** Czy zdarzenie pochodzi z warstwy danego rodzaju. */
  owns(webContents, kind) {
    return Boolean(this.current && this.current.kind === kind && this.current.view.webContents === webContents);
  }
}

module.exports = { OverlayHost, BAR_HEIGHT };
