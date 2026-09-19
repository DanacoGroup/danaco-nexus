'use strict';
// Zgoda na polecenie PowerShell zmieniające system – warstwa w oknie Nexusa: pełne polecenie,
// opis od asystenta, powody i ostrzeżenia. Domyślna odpowiedź to odmowa (także po czasie
// i po zamknięciu warstwy).

const DEFAULT_TIMEOUT_MS = 240000;

class ConfirmManager {
  /**
   * @param {object} options
   * @param {{show: () => import('electron').WebContents | null, close: (contents: import('electron').WebContents) => void}} options.host
   *   pokazuje stronę zgody w oknie Nexusa i ją zamyka
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
    const contents = this.options.host.show();
    if (!contents) {
      this.finish(item, false);
      return;
    }
    item.contents = contents;
    const contentsId = contents.id;
    this.byWebContents.set(contentsId, item);
    item.timer = setTimeout(() => this.finish(item, false), this.options.timeoutMs || DEFAULT_TIMEOUT_MS);
    contents.once('destroyed', () => {
      this.byWebContents.delete(contentsId);
      this.finish(item, false);
    });
  }

  /** Dane zgody dla strony (wywołanie z preload). */
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
    if (item.contents && !item.contents.isDestroyed()) this.options.host.close(item.contents);
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
