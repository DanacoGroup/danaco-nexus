'use strict';
// Dziennik aplikacji (plik w katalogu danych, rotacja po 2 MB). Polecenia PowerShell
// i decyzje użytkownika trafiają tu jako ślad audytowy.

const fs = require('node:fs');
const path = require('node:path');

const MAX_BYTES = 2 * 1024 * 1024;

class Logger {
  constructor(directory) {
    this.file = path.join(directory, 'logi', 'nexus-desktop.log');
    fs.mkdirSync(path.dirname(this.file), { recursive: true });
  }

  write(level, message, details) {
    const line = `${new Date().toISOString()} ${level} ${message}${details ? ` ${JSON.stringify(details)}` : ''}\n`;
    try {
      if (fs.existsSync(this.file) && fs.statSync(this.file).size > MAX_BYTES) {
        fs.renameSync(this.file, `${this.file}.1`);
      }
      fs.appendFileSync(this.file, line, 'utf8');
    } catch {
      // Dziennik nie może zatrzymać aplikacji.
    }
  }

  info(message, details) {
    this.write('INFO', message, details);
  }

  warn(message, details) {
    this.write('WARN', message, details);
  }

  error(message, details) {
    this.write('ERROR', message, details);
  }
}

module.exports = { Logger };
