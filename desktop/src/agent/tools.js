'use strict';
// Narzędzia pc_* wykonywane na komputerze użytkownika na żądanie agenta Nexusa.
// Każde narzędzie zwraca {text?, data?, images?: base64[], file?: {name, path, data}}.

const fsp = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const { classifyPowerShell } = require('./powershellPolicy');
const {
  IMAGE_EXTENSIONS,
  TEXT_EXTENSIONS,
  isSensitivePath,
  nameMatcher,
  normalizeExtensions,
  resolveFolders,
  shouldSkipDir,
} = require('./paths');
const { runElevated, runPowerShell, runPowerShellJson } = require('../powershell');

const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;
const MAX_TEXT_BYTES = 2 * 1024 * 1024;
const WALK_LIMIT_MS = 25000;
const WALK_MAX_ENTRIES = 400000;
const GB = 1024 ** 3;

function round(value, digits = 1) {
  const factor = 10 ** digits;
  return Math.round(Number(value || 0) * factor) / factor;
}

function checkAborted(signal) {
  if (signal && signal.aborted) throw new Error('Żądanie anulowane.');
}

class PcTools {
  /**
   * @param {object} deps
   * @param {import('electron')} deps.electron
   * @param {import('../config').Config} deps.config
   * @param {{ask: (request: object, signal?: AbortSignal) => Promise<boolean>}} deps.confirm
   * @param {() => Promise<{hwnd: string, title: string, process: string} | null>} deps.lastExternalWindow
   * @param {(visible: boolean) => Promise<void>} deps.hideOwnWindows
   * @param {{info: Function, warn: Function}} deps.log
   */
  constructor(deps) {
    this.deps = deps;
  }

  knownFolders() {
    const { app } = this.deps.electron;
    const get = (name) => {
      try {
        return app.getPath(name);
      } catch {
        return '';
      }
    };
    return {
      home: os.homedir(),
      desktop: get('desktop'),
      documents: get('documents'),
      downloads: get('downloads'),
      pictures: get('pictures'),
      videos: get('videos'),
      music: get('music'),
      onedrive: process.env.OneDrive || process.env.OneDriveConsumer || process.env.OneDriveCommercial || '',
    };
  }

  async handle(tool, args, signal) {
    const handlers = {
      pc_info: () => this.info(args, signal),
      pc_find_files: () => this.findFiles(args, signal),
      pc_read_file: () => this.readFile(args, signal),
      pc_powershell: () => this.powershell(args, signal),
      pc_screenshot: () => this.screenshot(args, signal),
    };
    const handler = handlers[tool];
    if (!handler) throw new Error(`Nieznane narzędzie komputera: ${tool}`);
    return handler();
  }

  async info(args, signal) {
    const count = Math.min(60, Math.max(1, Number(args.top_processes) || 15));
    const script = `
$ErrorActionPreference = 'SilentlyContinue'
$o = Get-CimInstance Win32_OperatingSystem
$c = Get-CimInstance Win32_Processor | Select-Object -First 1
$d = @(Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3" | ForEach-Object { [pscustomobject]@{ dysk = $_.DeviceID; etykieta = $_.VolumeName; rozmiar = [double]$_.Size; wolne = [double]$_.FreeSpace } })
$p = @(Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First ${count} | ForEach-Object { [pscustomobject]@{ nazwa = $_.ProcessName; id = $_.Id; pamiec = [double]$_.WorkingSet64; cpu_s = [math]::Round([double]$_.CPU, 1) } })
$s = @(Get-CimInstance Win32_StartupCommand | Select-Object -First 40 | ForEach-Object { [pscustomobject]@{ nazwa = $_.Name; polecenie = $_.Command; miejsce = $_.Location } })
[pscustomobject]@{
  system = "$($o.Caption) $($o.Version) (kompilacja $($o.BuildNumber))"
  start_systemu = if ($o.LastBootUpTime) { $o.LastBootUpTime.ToString('s') } else { '' }
  procesor = $c.Name
  obciazenie_cpu = $c.LoadPercentage
  pamiec_wirtualna_wolna_kb = [double]$o.FreeVirtualMemory
  pamiec_wirtualna_kb = [double]$o.TotalVirtualMemorySize
  dyski = $d
  procesy = $p
  autostart = $s
} | ConvertTo-Json -Depth 4 -Compress`;
    const details = await runPowerShellJson(script, { timeoutMs: 60000, signal });
    const total = os.totalmem();
    const free = os.freemem();
    const disks = (details.dyski || []).map((disk) => ({
      dysk: disk.dysk,
      etykieta: disk.etykieta || '',
      rozmiar_gb: round(disk.rozmiar / GB),
      wolne_gb: round(disk.wolne / GB),
      wolne_proc: disk.rozmiar ? round((disk.wolne / disk.rozmiar) * 100, 0) : null,
    }));
    const processes = (details.procesy || []).map((item) => ({
      nazwa: item.nazwa,
      id: item.id,
      pamiec_mb: round(item.pamiec / 1024 ** 2, 0),
      cpu_s: item.cpu_s,
    }));
    const data = {
      komputer: os.hostname(),
      uzytkownik: os.userInfo().username,
      system: details.system,
      procesor: details.procesor || os.cpus()[0]?.model,
      rdzenie_logiczne: os.cpus().length,
      obciazenie_cpu_proc: details.obciazenie_cpu,
      ram_gb: round(total / GB),
      ram_wolne_gb: round(free / GB),
      ram_zajete_proc: round(((total - free) / total) * 100, 0),
      pamiec_zadeklarowana_proc: details.pamiec_wirtualna_kb
        ? round(((details.pamiec_wirtualna_kb - details.pamiec_wirtualna_wolna_kb) / details.pamiec_wirtualna_kb) * 100, 0)
        : null,
      czas_pracy_h: round(os.uptime() / 3600),
      start_systemu: details.start_systemu,
      dyski: disks,
      procesy_wg_pamieci: processes,
      programy_autostartu: details.autostart || [],
    };
    return { data };
  }

  async findFiles(args, signal) {
    if (!this.deps.config.get('allowFiles')) throw new Error('Użytkownik wyłączył dostęp agenta do plików.');
    const { roots, errors } = resolveFolders(args.folders || [], this.knownFolders());
    if (!roots.length) throw new Error(errors.join(' ') || 'Brak katalogów do przeszukania.');
    const limit = Math.min(500, Math.max(1, Number(args.limit) || 50));
    const extensions = normalizeExtensions(args.extensions);
    const since = args.modified_after ? Date.parse(`${args.modified_after}T00:00:00`) : NaN;
    const content = String(args.content || '').trim();
    let method = 'przeszukanie katalogów';
    let files = null;
    const notes = [...errors];
    if (content) {
      try {
        files = await this.searchIndex({ roots, content, name: args.name, extensions, since, limit, signal });
        method = 'indeks wyszukiwania Windows';
        if (!files.length) {
          files = null;
          notes.push('Indeks Windows nic nie znalazł – przeszukano pliki tekstowe bezpośrednio.');
        }
      } catch (error) {
        notes.push(`Indeks wyszukiwania Windows niedostępny (${error.message.slice(0, 160)}).`);
      }
    }
    let partial = false;
    if (files === null) {
      const walked = await this.walk({ roots, content, name: args.name, extensions, since, limit, signal });
      files = walked.files;
      partial = walked.partial;
      if (content) method = 'przeszukanie treści plików tekstowych';
    }
    files = files.filter((file) => !isSensitivePath(file.path)).slice(0, limit);
    if (partial) notes.push('Przeszukiwanie przerwano po limicie czasu – wyniki mogą być niepełne.');
    return { data: { katalogi: roots, metoda: method, liczba: files.length, files, uwagi: notes } };
  }

  async searchIndex({ roots, content, name, extensions, since, limit, signal }) {
    const clean = (value) => String(value || '').replace(/['"%\\[\]]/g, ' ').trim();
    const scopes = roots.map((root) => `SCOPE='file:${root.replace(/'/g, '').replace(/\\/g, '/')}'`).join(' OR ');
    const conditions = [`(${scopes})`, `CONTAINS(*, '"${clean(content)}"')`];
    if (name && clean(name)) {
      const pattern = clean(name).replace(/\*/g, '%').replace(/\?/g, '_');
      conditions.push(`System.FileName LIKE '${/[%_]/.test(pattern) ? pattern : `%${pattern}%`}'`);
    }
    if (extensions.size) {
      conditions.push(`System.FileExtension IN (${[...extensions].map((ext) => `'${clean(ext)}'`).join(',')})`);
    }
    if (!Number.isNaN(since)) conditions.push(`System.DateModified >= '${new Date(since).toISOString().slice(0, 10)}'`);
    const sql = `SELECT TOP ${limit} System.ItemPathDisplay, System.Size, System.DateModified FROM SYSTEMINDEX WHERE ${conditions.join(' AND ')} ORDER BY System.DateModified DESC`;
    const script = `
$sql = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($env:NEXUS_SQL))
$connection = New-Object -ComObject ADODB.Connection
$connection.Open("Provider=Search.CollatorDSO;Extended Properties='Application=Windows';")
$records = New-Object -ComObject ADODB.Recordset
$records.Open($sql, $connection)
$found = New-Object System.Collections.ArrayList
while (-not $records.EOF) {
  $modified = $records.Fields.Item('System.DateModified').Value
  [void]$found.Add([pscustomobject]@{ path = $records.Fields.Item('System.ItemPathDisplay').Value; size = [double]$records.Fields.Item('System.Size').Value; modified = if ($modified) { ([datetime]$modified).ToString('s') } else { '' } })
  $records.MoveNext()
}
$records.Close(); $connection.Close()
ConvertTo-Json -InputObject @($found) -Compress`;
    const result = await runPowerShellJson(script, {
      timeoutMs: 45000,
      signal,
      env: { NEXUS_SQL: Buffer.from(sql, 'utf8').toString('base64') },
    });
    return (Array.isArray(result) ? result : [result]).filter((item) => item && item.path);
  }

  async walk({ roots, content, name, extensions, since, limit, signal }) {
    const matches = nameMatcher(name);
    const needle = content.toLocaleLowerCase('pl');
    const started = Date.now();
    const files = [];
    const queue = [...roots];
    const visited = new Set();
    let entries = 0;
    let partial = false;
    while (queue.length && files.length < limit) {
      checkAborted(signal);
      if (Date.now() - started > WALK_LIMIT_MS || entries > WALK_MAX_ENTRIES) {
        partial = true;
        break;
      }
      const directory = queue.shift();
      // Katalogi mogą się pokrywać (np. Pulpit wewnątrz OneDrive).
      const key = directory.toLowerCase();
      if (visited.has(key)) continue;
      visited.add(key);
      let listing;
      try {
        listing = await fsp.readdir(directory, { withFileTypes: true });
      } catch {
        continue;
      }
      for (const entry of listing) {
        entries += 1;
        const full = path.join(directory, entry.name);
        if (entry.isDirectory()) {
          if (!shouldSkipDir(entry.name) && !isSensitivePath(full)) queue.push(full);
          continue;
        }
        if (!entry.isFile()) continue;
        if (!matches(entry.name)) continue;
        const extension = path.extname(entry.name).toLowerCase();
        if (extensions.size && !extensions.has(extension)) continue;
        if (isSensitivePath(full)) continue;
        let stat;
        try {
          stat = await fsp.stat(full);
        } catch {
          continue;
        }
        if (!Number.isNaN(since) && stat.mtimeMs < since) continue;
        if (needle) {
          if (!TEXT_EXTENSIONS.has(extension) || stat.size > MAX_TEXT_BYTES) continue;
          try {
            const text = (await fsp.readFile(full, 'utf8')).toLocaleLowerCase('pl');
            if (!text.includes(needle)) continue;
          } catch {
            continue;
          }
        }
        files.push({ path: full, size: stat.size, modified: new Date(stat.mtimeMs).toISOString().slice(0, 19) });
        if (files.length >= limit) break;
      }
    }
    return { files, partial };
  }

  async readFile(args, signal) {
    if (!this.deps.config.get('allowFiles')) throw new Error('Użytkownik wyłączył dostęp agenta do plików.');
    const target = String(args.path || '').trim();
    if (!path.win32.isAbsolute(target)) throw new Error('Podaj pełną ścieżkę (np. C:\\Users\\…\\plik.txt).');
    const full = path.win32.normalize(target);
    if (isSensitivePath(full)) throw new Error('Ten plik lub katalog zawiera dane poufne (klucze, hasła, profile przeglądarek) i jest zablokowany.');
    let stat;
    try {
      stat = await fsp.stat(full);
    } catch {
      throw new Error(`Nie znaleziono: ${full}`);
    }
    checkAborted(signal);
    const meta = { path: full, size: stat.size, modified: new Date(stat.mtimeMs).toISOString().slice(0, 19) };
    if (stat.isDirectory()) {
      const listing = await fsp.readdir(full, { withFileTypes: true });
      const entries = [];
      for (const entry of listing.slice(0, 500)) {
        const child = path.join(full, entry.name);
        if (isSensitivePath(child)) continue;
        let size = null;
        let modified = '';
        try {
          const info = await fsp.stat(child);
          size = entry.isDirectory() ? null : info.size;
          modified = new Date(info.mtimeMs).toISOString().slice(0, 19);
        } catch {
          // Pozycja bez dostępu – pokazujemy samą nazwę.
        }
        entries.push({ name: entry.name, type: entry.isDirectory() ? 'katalog' : 'plik', size, modified });
      }
      entries.sort((a, b) => (a.type === b.type ? a.name.localeCompare(b.name, 'pl') : a.type === 'katalog' ? -1 : 1));
      return { data: { ...meta, type: 'katalog', entries, total: listing.length } };
    }
    const extension = path.extname(full).toLowerCase();
    if (args.upload) {
      if (stat.size > MAX_UPLOAD_BYTES) throw new Error('Plik jest większy niż 10 MB – przesyłanie przez Nexus Desktop jest ograniczone.');
      const data = await fsp.readFile(full);
      return { data: { ...meta, uploaded: true }, file: { name: path.basename(full), path: full, data: data.toString('base64') } };
    }
    if (IMAGE_EXTENSIONS.has(extension)) {
      const { nativeImage } = this.deps.electron;
      const image = nativeImage.createFromPath(full);
      if (!image.isEmpty()) {
        const size = image.getSize();
        const scaled = Math.max(size.width, size.height) > 1600 ? image.resize(size.width >= size.height ? { width: 1600 } : { height: 1600 }) : image;
        return { data: { ...meta, type: 'obraz', width: size.width, height: size.height }, images: [scaled.toJPEG(82).toString('base64')] };
      }
    }
    const maxChars = Math.min(100000, Math.max(500, Number(args.max_chars) || 20000));
    const handle = await fsp.open(full, 'r');
    let buffer;
    try {
      const length = Math.min(stat.size, maxChars * 4);
      buffer = Buffer.alloc(length);
      await handle.read(buffer, 0, length, 0);
    } finally {
      await handle.close();
    }
    if (!TEXT_EXTENSIONS.has(extension) && buffer.subarray(0, 8192).includes(0)) {
      return {
        data: { ...meta, type: 'plik binarny' },
        text: 'Plik nie jest tekstowy. Aby odczytać jego treść (PDF, DOCX, XLSX…), wywołaj pc_read_file z upload=true i użyj narzędzi serwera (extract_text, OCR).',
      };
    }
    const text = decodeText(buffer);
    const cut = text.length > maxChars || stat.size > buffer.length;
    return { data: { ...meta, type: 'tekst', truncated: cut }, text: text.slice(0, maxChars) };
  }

  async powershell(args, signal) {
    const { config, confirm, log } = this.deps;
    if (!config.get('allowPowershell')) throw new Error('Użytkownik wyłączył wykonywanie poleceń PowerShell przez agenta.');
    const command = String(args.command || '');
    const description = String(args.description || '').slice(0, 500);
    const timeoutMs = Math.min(600, Math.max(5, Number(args.timeout_s) || 60)) * 1000;
    const classification = classifyPowerShell(command);
    const admin = args.as_admin === true;
    const reasons = admin ? ['Uprawnienia administratora – Windows dodatkowo zapyta o zgodę (UAC).', ...classification.reasons] : classification.reasons;
    let confirmed = false;
    if (!classification.readOnly || admin) {
      log.info('PowerShell: prośba o zgodę', { command, description, admin, reasons });
      const accepted = await confirm.ask({ command, description, admin, reasons, warnings: classification.warnings }, signal);
      log.info(`PowerShell: ${accepted ? 'zatwierdzone' : 'odrzucone'} przez użytkownika`, { command });
      if (!accepted) throw new Error('Użytkownik odrzucił wykonanie polecenia (albo nie odpowiedział na czas). Nie ponawiaj bez pytania.');
      confirmed = true;
    } else {
      log.info('PowerShell: tylko odczyt – wykonanie bez pytania', { command });
    }
    checkAborted(signal);
    const result = admin ? await runElevated(command, { timeoutMs, signal }) : await runPowerShell(command, { timeoutMs, signal });
    log.info('PowerShell: zakończone', { exitCode: result.exitCode, ms: result.durationMs });
    return {
      text: result.output || '(brak wyjścia)',
      data: {
        exit_code: result.exitCode,
        confirmed,
        read_only: classification.readOnly,
        admin,
        duration_ms: result.durationMs,
        truncated: result.truncated,
      },
    };
  }

  async screenshot(args, signal) {
    const { config, electron } = this.deps;
    if (!config.get('allowScreenshots')) throw new Error('Użytkownik wyłączył zrzuty ekranu dla agenta.');
    checkAborted(signal);
    const shot = args.target === 'active_window' ? await this.captureWindow() : await this.captureScreen(Number(args.display) || 0);
    if (electron.Notification.isSupported()) {
      new electron.Notification({ title: 'Nexus', body: 'Asystent wykonał zrzut ekranu na potrzeby zadania.', silent: true }).show();
    }
    return { data: { title: shot.title, width: shot.width, height: shot.height }, images: [shot.image.toJPEG(80).toString('base64')] };
  }

  /** Zrzut okna aktywnego przed Nexusem; w razie braku – ekran. */
  async captureWindow(maxSide = 1920) {
    const { desktopCapturer } = this.deps.electron;
    const target = await this.deps.lastExternalWindow();
    if (target && target.hwnd && target.hwnd !== '0') {
      const sources = await desktopCapturer.getSources({ types: ['window'], thumbnailSize: { width: maxSide, height: maxSide }, fetchWindowIcons: false });
      const source = sources.find((item) => item.id.startsWith(`window:${target.hwnd}:`)) || sources.find((item) => item.name === target.title);
      if (source && !source.thumbnail.isEmpty()) {
        const size = source.thumbnail.getSize();
        return { image: source.thumbnail, title: target.title || source.name, process: target.process || '', width: size.width, height: size.height };
      }
    }
    return this.captureScreen(0, maxSide);
  }

  async captureScreen(displayIndex = 0, maxSide = 1920) {
    const { desktopCapturer, screen } = this.deps.electron;
    const displays = screen.getAllDisplays();
    const primary = screen.getPrimaryDisplay();
    const display = displays[displayIndex] || primary;
    const scale = display.scaleFactor || 1;
    const width = Math.round(display.size.width * scale);
    const height = Math.round(display.size.height * scale);
    const ratio = Math.min(1, maxSide / Math.max(width, height));
    await this.deps.hideOwnWindows(true);
    try {
      const sources = await desktopCapturer.getSources({ types: ['screen'], thumbnailSize: { width: Math.round(width * ratio), height: Math.round(height * ratio) } });
      const source = sources.find((item) => String(item.display_id) === String(display.id)) || sources[0];
      if (!source || source.thumbnail.isEmpty()) throw new Error('Nie udało się wykonać zrzutu ekranu.');
      const size = source.thumbnail.getSize();
      return { image: source.thumbnail, title: `Ekran ${displays.indexOf(display) + 1}`, process: '', width: size.width, height: size.height };
    } finally {
      await this.deps.hideOwnWindows(false);
    }
  }
}

/** Tekst z bufora: UTF-8 (z BOM), UTF-16LE (BOM) albo Windows-1250. */
function decodeText(buffer) {
  if (buffer[0] === 0xff && buffer[1] === 0xfe) return new TextDecoder('utf-16le').decode(buffer.subarray(2));
  const start = buffer[0] === 0xef && buffer[1] === 0xbb && buffer[2] === 0xbf ? 3 : 0;
  try {
    return new TextDecoder('utf-8', { fatal: true }).decode(buffer.subarray(start));
  } catch {
    // Obcięty ostatni znak wielobajtowy albo inne kodowanie.
  }
  const lenient = new TextDecoder('utf-8').decode(buffer.subarray(start));
  const broken = (lenient.match(/\uFFFD/g) || []).length;
  if (broken <= 2) return lenient;
  try {
    return new TextDecoder('windows-1250').decode(buffer);
  } catch {
    return buffer.toString('latin1');
  }
}

module.exports = { PcTools, decodeText };
