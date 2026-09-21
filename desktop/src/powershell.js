'use strict';
// Uruchamianie Windows PowerShell 5.1 bez modułów natywnych:
// * runPowerShell – jednorazowe polecenie z limitem czasu (narzędzia agenta),
// * WindowHelper – stały proces pomocniczy z funkcjami user32 (aktywne okno, wklejanie).
// Wklejanie: schowek Electron + SetForegroundWindow (AttachThreadInput) + SendKeys ^v.
// Wybrane zamiast @nut-tree/robotjs, bo te wymagają kompilacji lub płatnych paczek.

const { spawn, execFile } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const readline = require('node:readline');

const POWERSHELL = path.join(process.env.SystemRoot || 'C:\\Windows', 'System32', 'WindowsPowerShell', 'v1.0', 'powershell.exe');
const MAX_OUTPUT = 60000;
const BASE_ARGS = ['-NoLogo', '-NoProfile', '-NonInteractive', '-OutputFormat', 'Text', '-ExecutionPolicy', 'Bypass'];

function encode(script) {
  return Buffer.from(script, 'utf16le').toString('base64');
}

function killTree(pid) {
  if (!pid) return;
  execFile('taskkill', ['/PID', String(pid), '/T', '/F'], { windowsHide: true }, () => {});
}

/**
 * Wykonuje skrypt PowerShell; wynik: wyjście (stdout+stderr), kod zakończenia, czas.
 * Z mergeErrors (domyślnie) błędy trafiają do wyjścia jako zwykły tekst – bez tego PowerShell
 * uruchomiony z -EncodedCommand zapisuje strumień błędów w formacie CLIXML.
 * @param {string} script
 * @param {{timeoutMs?: number, signal?: AbortSignal, env?: Record<string,string>, maxOutput?: number, mergeErrors?: boolean}} options
 */
function runPowerShell(script, options = {}) {
  const timeoutMs = options.timeoutMs || 60000;
  const maxOutput = options.maxOutput || MAX_OUTPUT;
  const prefix =
    "$ProgressPreference='SilentlyContinue'; [Console]::OutputEncoding=[Text.Encoding]::UTF8; " +
    '$OutputEncoding=[Text.Encoding]::UTF8;\n';
  const body = options.mergeErrors === false ? script : `& {\n${script}\n} 2>&1 | Out-String -Stream -Width 250
if ($LASTEXITCODE) { exit $LASTEXITCODE }`;
  return new Promise((resolve, reject) => {
    const started = Date.now();
    const child = spawn(POWERSHELL, [...BASE_ARGS, '-EncodedCommand', encode(prefix + body)], {
      windowsHide: true,
      env: { ...process.env, ...(options.env || {}) },
    });
    const chunks = [];
    let size = 0;
    let truncated = false;
    let finished = false;
    const collect = (chunk) => {
      if (size >= maxOutput * 4) {
        truncated = true;
        return;
      }
      chunks.push(chunk);
      size += chunk.length;
    };
    child.stdout.on('data', collect);
    child.stderr.on('data', collect);
    const stop = (reason) => {
      if (finished) return;
      finished = true;
      clearTimeout(timer);
      killTree(child.pid);
      reject(new Error(reason));
    };
    const timer = setTimeout(() => stop(`Polecenie przekroczyło limit czasu ${Math.round(timeoutMs / 1000)} s i zostało przerwane.`), timeoutMs);
    if (options.signal) {
      if (options.signal.aborted) stop('Polecenie anulowane.');
      options.signal.addEventListener('abort', () => stop('Polecenie anulowane.'), { once: true });
    }
    child.on('error', (error) => {
      if (finished) return;
      finished = true;
      clearTimeout(timer);
      reject(error);
    });
    child.on('close', (code) => {
      if (finished) return;
      finished = true;
      clearTimeout(timer);
      let output = cleanClixml(Buffer.concat(chunks).toString('utf8'));
      if (output.length > maxOutput) {
        output = output.slice(0, maxOutput);
        truncated = true;
      }
      resolve({ output, exitCode: code, truncated, durationMs: Date.now() - started });
    });
  });
}

/** Komunikaty błędów zapisane w CLIXML → zwykły tekst. */
function cleanClixml(text) {
  const marker = text.indexOf('#< CLIXML');
  if (marker < 0) return text;
  const errors = [...text.slice(marker).matchAll(/<S S="Error">([\s\S]*?)<\/S>/g)]
    .map((match) => match[1].replace(/_x000D__x000A_/g, '\n'))
    .join('')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&amp;/g, '&');
  return `${text.slice(0, marker)}${errors}`;
}

/**
 * Polecenie z uprawnieniami administratora: Windows pokazuje monit UAC, wynik wraca przez
 * plik tymczasowy (procesu podniesionego nie da się odczytać ani przerwać z konta zwykłego).
 */
async function runElevated(script, options = {}) {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'nexus-admin-'));
  const outputFile = path.join(directory, 'wynik.txt');
  const quoted = (value) => `'${value.replace(/'/g, "''")}'`;
  const inner =
    "$ProgressPreference='SilentlyContinue'\n" +
    `& {\n${script}\n} 2>&1 | Out-String -Width 250 | Set-Content -LiteralPath ${quoted(outputFile)} -Encoding UTF8\n` +
    'exit $LASTEXITCODE';
  const outer =
    `$arguments = @('-NoLogo','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-EncodedCommand','${encode(inner)}')\n` +
    `$process = Start-Process -FilePath ${quoted(POWERSHELL)} -Verb RunAs -WindowStyle Hidden -Wait -PassThru -ArgumentList $arguments\n` +
    'exit $process.ExitCode';
  try {
    const result = await runPowerShell(outer, { ...options, mergeErrors: false });
    let output = '';
    try {
      output = fs.readFileSync(outputFile, 'utf8').replace(/^\uFEFF/, '');
    } catch {
      output = result.output.includes('canceled by the user') || result.output.includes('anulowana')
        ? 'Użytkownik nie zgodził się na uprawnienia administratora (monit UAC).'
        : result.output;
    }
    const maxOutput = options.maxOutput || MAX_OUTPUT;
    return { ...result, output: output.slice(0, maxOutput), truncated: output.length > maxOutput };
  } finally {
    fs.rmSync(directory, { recursive: true, force: true });
  }
}

/** Skrypt PowerShell zwracający JSON → obiekt JS (skrypt sam wycisza błędy poleceń). */
async function runPowerShellJson(script, options = {}) {
  const result = await runPowerShell(script, { ...options, mergeErrors: false });
  const text = result.output.trim();
  const start = text.search(/[[{]/);
  if (result.exitCode !== 0 || start < 0) {
    throw new Error(`PowerShell zakończył się błędem: ${text.slice(0, 800) || `kod ${result.exitCode}`}`);
  }
  return JSON.parse(text.slice(start));
}

const HELPER_SCRIPT = String.raw`
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
[Console]::InputEncoding = [Text.Encoding]::UTF8
Add-Type -AssemblyName System.Windows.Forms
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
using System.Text;
public static class NexusWin {
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool BringWindowToTop(IntPtr h);
  [DllImport("user32.dll")] public static extern bool IsWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr h);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int cmd);
  [DllImport("user32.dll")] public static extern bool AttachThreadInput(uint a, uint b, bool attach);
  [DllImport("kernel32.dll")] public static extern uint GetCurrentThreadId();
  public static bool Activate(IntPtr h) {
    if (!IsWindow(h)) return false;
    if (IsIconic(h)) ShowWindow(h, 9);
    uint ignored;
    uint foreground = GetWindowThreadProcessId(GetForegroundWindow(), out ignored);
    uint current = GetCurrentThreadId();
    bool attached = foreground != current && AttachThreadInput(current, foreground, true);
    BringWindowToTop(h);
    SetForegroundWindow(h);
    if (attached) AttachThreadInput(current, foreground, false);
    return GetForegroundWindow() == h;
  }
}
"@
[Console]::Out.WriteLine('{"ready":true}')
[Console]::Out.Flush()
while ($true) {
  $line = [Console]::In.ReadLine()
  if ($line -eq $null) { break }
  $id = $null
  try {
    $req = $line | ConvertFrom-Json
    $id = $req.id
    $res = $null
    switch ($req.cmd) {
      'fg' {
        $h = [NexusWin]::GetForegroundWindow()
        $sb = New-Object System.Text.StringBuilder 512
        [void][NexusWin]::GetWindowText($h, $sb, 512)
        $owner = [uint32]0
        [void][NexusWin]::GetWindowThreadProcessId($h, [ref]$owner)
        $name = ''
        try { $name = (Get-Process -Id $owner).ProcessName } catch { }
        $res = @{ hwnd = [string][int64]$h; title = $sb.ToString(); pid = [int]$owner; process = $name }
      }
      'paste' {
        $h = [IntPtr][int64]$req.hwnd
        $active = $false
        if ($h -ne [IntPtr]::Zero) { $active = [NexusWin]::Activate($h) }
        Start-Sleep -Milliseconds 150
        [System.Windows.Forms.SendKeys]::SendWait('^v')
        $res = @{ activated = $active }
      }
      'ping' { $res = @{ ok = $true } }
      default { throw "Nieznane polecenie" }
    }
    $out = @{ id = $id; ok = $true; result = $res } | ConvertTo-Json -Compress -Depth 4
  } catch {
    $out = @{ id = $id; ok = $false; error = $_.Exception.Message } | ConvertTo-Json -Compress
  }
  [Console]::Out.WriteLine($out)
  [Console]::Out.Flush()
}
`;

class WindowHelper {
  constructor(log) {
    this.log = log;
    this.child = null;
    this.pending = new Map();
    this.counter = 0;
    this.ready = null;
  }

  start() {
    if (this.child) return this.ready;
    const child = spawn(POWERSHELL, [...BASE_ARGS, '-EncodedCommand', encode(HELPER_SCRIPT)], {
      windowsHide: true,
    });
    this.child = child;
    let odrzuc = () => {};
    this.ready = new Promise((resolve, reject) => {
      odrzuc = reject;
      const lines = readline.createInterface({ input: child.stdout });
      const timer = setTimeout(() => reject(new Error('Proces pomocniczy PowerShell nie wystartował.')), 20000);
      lines.on('line', (line) => {
        let message;
        try {
          message = JSON.parse(line);
        } catch {
          return;
        }
        if (message.ready) {
          clearTimeout(timer);
          resolve();
          return;
        }
        const waiting = this.pending.get(message.id);
        if (!waiting) return;
        this.pending.delete(message.id);
        if (message.ok) waiting.resolve(message.result);
        else waiting.reject(new Error(message.error || 'Błąd procesu pomocniczego.'));
      });
    });
    this.ready.catch(() => {});
    // Bez tego nasłuchu nieudany `spawn` (brak PowerShella, zablokowane uruchamianie,
    // uruchomienie poza Windows) zgłasza zdarzenie „error” **bez słuchacza**, a Node
    // zamienia je wtedy w nieobsłużony wyjątek w procesie głównym Electrona. Reszta kodu
    // jest napisana tak, żeby brak procesu pomocniczego **przeżyć** (`this.ready.catch`
    // wyżej i `state.helper.start().catch(...)` w `main.js`) — i ten jeden nasłuch
    // decyduje o tym, czy ta odporność w ogóle zadziała.
    child.on('error', (error) => {
      this.child = null;
      this.log.warn('Proces pomocniczy PowerShell nie wystartował', { message: error.message });
      for (const waiting of this.pending.values()) waiting.reject(error);
      this.pending.clear();
      odrzuc(error);
    });
    child.stderr.on('data', (chunk) => this.log.warn('Proces pomocniczy PowerShell', { stderr: chunk.toString('utf8').slice(0, 500) }));
    child.on('exit', () => {
      this.child = null;
      for (const waiting of this.pending.values()) waiting.reject(new Error('Proces pomocniczy zakończył działanie.'));
      this.pending.clear();
    });
    return this.ready;
  }

  async request(cmd, extra = {}, timeoutMs = 5000) {
    await this.start();
    const id = String(++this.counter);
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error('Proces pomocniczy nie odpowiedział.'));
      }, timeoutMs);
      this.pending.set(id, {
        resolve: (value) => {
          clearTimeout(timer);
          resolve(value);
        },
        reject: (error) => {
          clearTimeout(timer);
          reject(error);
        },
      });
      this.child.stdin.write(`${JSON.stringify({ id, cmd, ...extra })}\n`);
    });
  }

  /** Okno pierwszoplanowe: {hwnd, title, pid, process}. */
  foreground() {
    return this.request('fg', {}, 3000);
  }

  /** Aktywuje okno i wkleja schowek (Ctrl+V). */
  paste(hwnd) {
    return this.request('paste', { hwnd: String(hwnd || '0') }, 5000);
  }

  stop() {
    if (this.child) {
      this.child.stdin.end();
      killTree(this.child.pid);
      this.child = null;
    }
  }
}

module.exports = { runPowerShell, runPowerShellJson, runElevated, WindowHelper, POWERSHELL };
