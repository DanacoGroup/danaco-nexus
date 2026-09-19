'use strict';
// Połączenie lokalnego agenta z serwerem Nexusa: WebSocket /api/pulpit/ws uwierzytelniony
// kluczem urządzenia (pierwszy komunikat), ping co 25 s, ponowne łączenie z narastającą przerwą.

const { EventEmitter } = require('node:events');
const os = require('node:os');
const WebSocket = require('ws');

const PING_MS = 25000;
const MAX_BACKOFF_MS = 60000;
const MAX_RESPONSE_BYTES = 15 * 1024 * 1024;

class AgentConnection extends EventEmitter {
  /**
   * @param {object} options
   * @param {() => string} options.serverUrl
   * @param {() => string} options.deviceKey
   * @param {(tool: string, args: object, signal: AbortSignal) => Promise<object>} options.handle
   * @param {string} options.version
   * @param {{info: Function, warn: Function}} options.log
   */
  constructor(options) {
    super();
    this.options = options;
    this.socket = null;
    this.enabled = false;
    this.attempt = 0;
    this.retryTimer = null;
    this.pingTimer = null;
    this.running = new Map();
    this.status = { state: 'wylaczony', message: 'Agent komputera jest wyłączony.' };
  }

  setStatus(state, message, extra = {}) {
    this.status = { state, message, ...extra };
    this.emit('status', this.status);
  }

  start() {
    this.enabled = true;
    this.attempt = 0;
    this.connect();
  }

  stop(message = 'Agent komputera jest wyłączony.') {
    this.enabled = false;
    clearTimeout(this.retryTimer);
    clearInterval(this.pingTimer);
    for (const controller of this.running.values()) controller.abort();
    this.running.clear();
    if (this.socket) {
      this.socket.removeAllListeners();
      this.socket.on('error', () => {});
      this.socket.terminate();
      this.socket = null;
    }
    this.setStatus('wylaczony', message);
  }

  restart() {
    this.stop();
    this.start();
  }

  connect() {
    clearTimeout(this.retryTimer);
    if (!this.enabled) return;
    const key = this.options.deviceKey();
    if (!key) {
      this.setStatus('brak-klucza', 'Komputer nie jest połączony z Nexusem – w ustawieniach wybierz „Połącz komputer”.');
      return;
    }
    const url = `${this.options.serverUrl().replace(/^http/, 'ws')}/api/pulpit/ws`;
    this.setStatus('laczenie', 'Łączenie z Nexusem…');
    const socket = new WebSocket(url, { handshakeTimeout: 15000, maxPayload: 32 * 1024 * 1024 });
    this.socket = socket;
    socket.on('open', () => {
      socket.send(
        JSON.stringify({
          type: 'auth',
          token: key,
          host: os.hostname(),
          version: this.options.version,
          platform: `${os.platform()} ${os.release()}`,
        }),
      );
    });
    socket.on('message', (raw) => this.onMessage(socket, raw));
    socket.on('error', (error) => this.options.log.warn('Agent: błąd połączenia', { message: error.message }));
    socket.on('close', (code) => this.onClose(socket, code));
  }

  onClose(socket, code) {
    if (socket !== this.socket) return;
    clearInterval(this.pingTimer);
    this.socket = null;
    for (const controller of this.running.values()) controller.abort();
    this.running.clear();
    if (!this.enabled) return;
    if (code === 4401) {
      this.setStatus('blad', 'Serwer odrzucił klucz urządzenia (cofnięty lub nieprawidłowy). Połącz komputer ponownie w ustawieniach.');
      return;
    }
    this.attempt += 1;
    const delay = code === 4409 ? 30000 : Math.min(MAX_BACKOFF_MS, 2000 * 2 ** Math.min(this.attempt - 1, 5));
    const reason = code === 4409 ? 'Ten komputer połączył się z innego okna aplikacji.' : 'Brak połączenia z Nexusem.';
    this.setStatus('rozlaczony', `${reason} Ponowna próba za ${Math.round(delay / 1000)} s.`);
    this.retryTimer = setTimeout(() => this.connect(), delay);
  }

  onMessage(socket, raw) {
    let message;
    try {
      message = JSON.parse(raw.toString('utf8'));
    } catch {
      return;
    }
    if (!message || typeof message !== 'object') return;
    if (message.type === 'ready') {
      this.attempt = 0;
      this.setStatus('polaczony', `Połączono jako „${message.device?.name || 'komputer'}”.`, { device: message.device });
      clearInterval(this.pingTimer);
      this.pingTimer = setInterval(() => {
        if (socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ type: 'ping' }));
      }, PING_MS);
      return;
    }
    if (message.type === 'error') {
      this.options.log.warn('Agent: serwer zgłosił błąd', { message: message.message });
      return;
    }
    if (message.type === 'cancel') {
      const controller = this.running.get(message.id);
      if (controller) controller.abort();
      return;
    }
    if (message.type === 'request' && typeof message.id === 'string') {
      this.runRequest(socket, message);
    }
  }

  async runRequest(socket, message) {
    const controller = new AbortController();
    this.running.set(message.id, controller);
    this.emit('request', { tool: message.tool });
    let response;
    try {
      const result = await this.options.handle(String(message.tool), message.args || {}, controller.signal);
      response = { type: 'response', id: message.id, ok: true, result };
    } catch (error) {
      response = { type: 'response', id: message.id, ok: false, error: String(error && error.message ? error.message : error) };
    } finally {
      this.running.delete(message.id);
    }
    let text = JSON.stringify(response);
    if (Buffer.byteLength(text) > MAX_RESPONSE_BYTES) {
      text = JSON.stringify({ type: 'response', id: message.id, ok: false, error: 'Wynik jest zbyt duży do przesłania (limit 15 MB).' });
    }
    if (socket.readyState === WebSocket.OPEN) socket.send(text);
  }
}

module.exports = { AgentConnection };
