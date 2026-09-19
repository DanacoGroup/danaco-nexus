'use strict';
// Klasyfikacja poleceń PowerShell: „tylko odczyt” (wykonanie od razu) albo „wymaga zgody”.
// Zasada: domyślnie zgoda. Bez niej przechodzi wyłącznie polecenie, w którym każde wywołanie
// jest na białej liście, a składnia nie pozwala uruchomić niczego innego (wywołania metod,
// operator &, przekierowania, podwyrażenia w napisach, zaciemnianie znakiem `).

const READ_ONLY_CMDLETS = new Set(
  [
    'Get-Acl', 'Get-AppxPackage', 'Get-BitLockerVolume', 'Get-ChildItem', 'Get-CimClass', 'Get-CimInstance',
    'Get-Command', 'Get-ComputerInfo', 'Get-Counter', 'Get-Culture', 'Get-Date', 'Get-Disk',
    'Get-DnsClientCache', 'Get-DnsClientServerAddress', 'Get-EventLog', 'Get-FileHash', 'Get-Help',
    'Get-HotFix', 'Get-Host', 'Get-Item', 'Get-ItemProperty', 'Get-ItemPropertyValue', 'Get-LocalGroup',
    'Get-LocalGroupMember', 'Get-LocalUser', 'Get-Location', 'Get-Member', 'Get-Module', 'Get-MpComputerStatus',
    'Get-MpThreatDetection', 'Get-NetAdapter', 'Get-NetAdapterStatistics', 'Get-NetConnectionProfile',
    'Get-NetFirewallProfile', 'Get-NetIPAddress', 'Get-NetIPConfiguration', 'Get-NetRoute',
    'Get-NetTCPConnection', 'Get-NetUDPEndpoint', 'Get-Package', 'Get-Partition', 'Get-PhysicalDisk',
    'Get-PnpDevice', 'Get-Printer', 'Get-PSDrive', 'Get-PSProvider', 'Get-Process', 'Get-ScheduledTask',
    'Get-ScheduledTaskInfo', 'Get-Service', 'Get-SmbShare', 'Get-StartApps', 'Get-StorageReliabilityCounter',
    'Get-TimeZone', 'Get-Uptime', 'Get-Variable', 'Get-Volume', 'Get-WindowsUpdateLog', 'Get-WinEvent',
    'Get-WmiObject', 'Get-WULastInstallationDate', 'ConvertFrom-Json', 'ConvertTo-Csv', 'ConvertTo-Html',
    'ConvertTo-Json', 'Format-List', 'Format-Table', 'Format-Wide', 'ForEach-Object', 'Group-Object',
    'Join-Path', 'Measure-Object', 'Out-Null', 'Out-String', 'Resolve-DnsName', 'Resolve-Path', 'Select-Object',
    'Select-String', 'Sort-Object', 'Split-Path', 'Test-Connection', 'Test-NetConnection', 'Test-Path',
    'Where-Object', 'Write-Output',
  ].map((name) => name.toLowerCase()),
);

const ALIASES = {
  ls: 'get-childitem', dir: 'get-childitem', gci: 'get-childitem', cat: 'get-content', gc: 'get-content',
  type: 'get-content', ps: 'get-process', gps: 'get-process', gsv: 'get-service', gi: 'get-item',
  gp: 'get-itemproperty', gpv: 'get-itempropertyvalue', gcim: 'get-ciminstance', gwmi: 'get-wmiobject',
  select: 'select-object', where: 'where-object', '?': 'where-object', sort: 'sort-object',
  group: 'group-object', measure: 'measure-object', foreach: 'foreach-object', '%': 'foreach-object',
  ft: 'format-table', fl: 'format-list', fw: 'format-wide', sls: 'select-string', pwd: 'get-location',
  gl: 'get-location', echo: 'write-output', write: 'write-output', gcm: 'get-command', gm: 'get-member',
  rvpa: 'resolve-path', tnc: 'test-netconnection', gdr: 'get-psdrive', gv: 'get-variable',
};

// Get-Content osobno: czytanie plików jest dozwolone, ale nie plików z danymi logowania (niżej).
READ_ONLY_CMDLETS.add('get-content');

// Programy konsolowe tylko do odczytu; wartość: dozwolone argumenty (null = dowolne).
const READ_ONLY_PROGRAMS = {
  ipconfig: new Set(['/all', '/displaydns']),
  netstat: null,
  ping: null,
  tracert: null,
  pathping: null,
  nslookup: null,
  systeminfo: null,
  whoami: null,
  hostname: new Set(),
  tasklist: null,
  driverquery: null,
  getmac: null,
  powercfg: new Set([
    '/l', '/list', '/q', '/query', '/a', '/availablesleepstates', '/getactivescheme', '/requests', '/lastwake',
  ]),
};

const KEYWORDS = new Set([
  'if', 'else', 'elseif', 'switch', 'foreach', 'for', 'while', 'do', 'until', 'try', 'catch', 'finally',
  'return', 'break', 'continue', 'in', 'begin', 'process', 'end', 'param', 'exit',
]);
const DEFINITION_KEYWORDS = new Set(['function', 'filter', 'workflow', 'class', 'enum', 'trap', 'configuration']);

// Metody bez skutków ubocznych (napisy, daty, odczyt rejestru).
const SAFE_METHODS = new Set(
  [
    'ToString', 'Trim', 'TrimStart', 'TrimEnd', 'ToUpper', 'ToLower', 'ToUpperInvariant', 'ToLowerInvariant',
    'Substring', 'Split', 'Replace', 'Contains', 'StartsWith', 'EndsWith', 'IndexOf', 'LastIndexOf', 'PadLeft',
    'PadRight', 'GetType', 'Equals', 'CompareTo', 'ToShortDateString', 'ToLongDateString', 'ToShortTimeString',
    'AddDays', 'AddHours', 'AddMinutes', 'AddSeconds', 'AddMonths', 'AddYears', 'ToLocalTime', 'ToUniversalTime',
    'GetValue', 'GetValueNames', 'GetSubKeyNames', 'GetString', 'GetBytes', 'Normalize', 'Insert', 'Remove',
    'Where',
  ].map((name) => name.toLowerCase()),
);
// Remove/Insert działają na napisach i listach w pamięci; treść .Where({…}) jest sprawdzana
// jak każde inne polecenie. Metoda .ForEach('Nazwa') wywołuje dowolną metodę, więc jej tu nie ma.

const SAFE_STATIC = {
  math: null,
  datetime: new Set(['now', 'today', 'utcnow', 'parse', 'daysinmonth', 'isleapyear']),
  timespan: new Set(['fromseconds', 'fromminutes', 'fromhours', 'fromdays', 'frommilliseconds']),
  string: new Set(['join', 'isnullorempty', 'isnullorwhitespace', 'format', 'concat', 'empty']),
  environment: new Set([
    'osversion', 'machinename', 'username', 'userdomainname', 'processorcount', 'is64bitoperatingsystem',
    'tickcount', 'tickcount64', 'getfolderpath', 'getenvironmentvariable', 'getenvironmentvariables',
    'getlogicaldrives', 'systemdirectory', 'version', 'newline',
  ]),
  'io.path': new Set([
    'getfilename', 'getextension', 'getdirectoryname', 'combine', 'getfilenamewithoutextension', 'gettemppath',
    'getfullpath',
  ]),
  'io.driveinfo': new Set(['getdrives']),
  'net.dns': new Set(['gethostname', 'gethostentry', 'gethostaddresses']),
  convert: new Set(['tostring', 'toint32', 'toint64', 'todouble', 'tobase64string', 'frombase64string']),
  'text.encoding': new Set(['utf8', 'unicode', 'ascii', 'default']),
};

// Czasowniki poleceń zmieniających stan – takie słowo nawet jako argument wymaga zgody.
const CHANGING_VERBS = new Set(
  [
    'add', 'block', 'clear', 'close', 'compress', 'copy', 'disable', 'dismount', 'edit', 'enable', 'enter',
    'exit', 'expand', 'export', 'format', 'grant', 'import', 'initialize', 'install', 'invoke', 'lock', 'mount',
    'move', 'new', 'optimize', 'out', 'protect', 'publish', 'push', 'pop', 'register', 'remove', 'rename',
    'repair', 'reset', 'resize', 'restart', 'restore', 'resume', 'revoke', 'save', 'send', 'set', 'start',
    'stop', 'suspend', 'sync', 'tee', 'unblock', 'uninstall', 'unlock', 'unprotect', 'unregister', 'update',
    'use', 'wait', 'write',
  ],
);

const SENSITIVE = [
  '.ssh', 'id_rsa', 'id_ed25519', 'id_ecdsa', '.gnupg', '.kdbx', 'login data', 'web data', 'cookies',
  'credentials', 'microsoft\\protect', 'microsoft\\vault', '.pfx', '.p12', '.pem', 'wallet.dat',
  '.git-credentials', '_netrc', '.netrc', 'system32\\config', 'klucz-urzadzenia', 'get-clipboard',
];

const DANGER = [
  [/format-volume|clear-disk|initialize-disk|remove-partition|\bdiskpart\b/i, 'Operacje na dyskach i partycjach mogą usunąć dane.'],
  [/\bbcdedit\b|\bbootrec\b/i, 'Zmiana konfiguracji rozruchu systemu.'],
  [/vssadmin\s+delete|wbadmin\s+delete|disable-computerrestore/i, 'Usuwanie kopii zapasowych lub punktów przywracania.'],
  [/remove-item[^|;]*-recurse|\b(rd|rmdir)\s+\/s|\bdel\s+\/s|\bri\b[^|;]*-r/i, 'Rekurencyjne usuwanie plików i katalogów.'],
  [/\breg(\.exe)?\s+(delete|add|import)|remove-itemproperty|set-itemproperty|new-itemproperty/i, 'Zmiany w rejestrze systemu.'],
  [/set-executionpolicy|set-mppreference|add-mppreference|netsh\s+advfirewall|set-netfirewall|disable-netfirewall/i, 'Osłabienie zabezpieczeń systemu (Defender, zapora, zasady wykonywania).'],
  [/stop-computer|restart-computer|\bshutdown(\.exe)?\b/i, 'Wyłączenie lub ponowne uruchomienie komputera.'],
  [/\btakeown\b|\bicacls\b|set-acl/i, 'Zmiana właściciela lub uprawnień plików.'],
  [/remove-appxpackage|uninstall-package|\bmsiexec\b[^|;]*\/x/i, 'Odinstalowanie programów.'],
  [/invoke-webrequest|invoke-restmethod|\biwr\b|\birm\b|downloadstring|downloadfile|start-bitstransfer|\bcurl\b|\bwget\b/i, 'Pobieranie danych z internetu.'],
];

const QUOTES_SINGLE = new Set(["'", '‘', '’', '‚', '‛']);
const QUOTES_DOUBLE = new Set(['"', '“', '”', '„']);
const WORD_STOP = new Set([' ', '\t', '\r', '\n', '|', ';', '(', ')', '{', '}', '=', ',', '`', '$', '<', '>', '&']);

function tokenize(source) {
  const tokens = [];
  const flags = new Set();
  const src = source;
  let i = 0;
  let start = 0;
  const push = (t, v, extra = {}) => tokens.push({ t, v, pos: start, ...extra });
  while (i < src.length) {
    start = i;
    const c = src[i];
    const next = src[i + 1];
    if (c === ' ' || c === '\t' || c === '\r') {
      i += 1;
    } else if (c === '\n') {
      push('op', ';');
      i += 1;
    } else if (c === '<' && next === '#') {
      const end = src.indexOf('#>', i + 2);
      i = end < 0 ? src.length : end + 2;
    } else if (c === '#') {
      while (i < src.length && src[i] !== '\n') i += 1;
    } else if (c === '@' && (QUOTES_SINGLE.has(next) || QUOTES_DOUBLE.has(next))) {
      flags.add('herestring');
      return { tokens, flags };
    } else if (QUOTES_SINGLE.has(c)) {
      let value = '';
      i += 1;
      while (i < src.length) {
        if (QUOTES_SINGLE.has(src[i])) {
          if (QUOTES_SINGLE.has(src[i + 1])) {
            value += "'";
            i += 2;
            continue;
          }
          break;
        }
        value += src[i];
        i += 1;
      }
      i += 1;
      push('str', value, { callNext: src[i] === '.' });
    } else if (QUOTES_DOUBLE.has(c)) {
      let value = '';
      i += 1;
      while (i < src.length && !QUOTES_DOUBLE.has(src[i])) {
        if (src[i] === '`') {
          value += src[i + 1] || '';
          i += 2;
          continue;
        }
        if (src[i] === '$' && src[i + 1] === '(') flags.add('subexpression');
        value += src[i];
        i += 1;
      }
      i += 1;
      push('str', value);
    } else if (c === '`') {
      flags.add('backtick');
      i += 2;
    } else if (c === '$') {
      if (next === '(') {
        push('op', '$(');
        i += 2;
        continue;
      }
      let name = '$';
      i += 1;
      if (src[i] === '{') {
        const end = src.indexOf('}', i);
        name += src.slice(i, end < 0 ? src.length : end + 1);
        i = end < 0 ? src.length : end + 1;
      } else {
        while (i < src.length && /[\w:?^$]/.test(src[i])) {
          name += src[i];
          i += 1;
        }
      }
      while (src[i] === '.' && /[A-Za-z_]/.test(src[i + 1] || '')) {
        name += '.';
        i += 1;
        while (i < src.length && /\w/.test(src[i])) {
          name += src[i];
          i += 1;
        }
      }
      push('var', name, { callNext: src[i] === '(' });
    } else if (c === '@' && (next === '(' || next === '{')) {
      push('op', `@${next}`);
      i += 2;
    } else if (c === '[') {
      let depth = 0;
      let j = i;
      for (; j < src.length; j += 1) {
        if (src[j] === '[') depth += 1;
        if (src[j] === ']') {
          depth -= 1;
          if (depth === 0) break;
        }
      }
      push('type', src.slice(i + 1, j).trim());
      i = j + 1;
    } else if (c === ':' && next === ':') {
      push('op', '::');
      i += 2;
    } else if ((c === '|' || c === '&') && next === c) {
      push('op', c + c);
      i += 2;
    } else if ('|;(){},'.includes(c)) {
      push('op', c);
      i += 1;
    } else if (c === '&') {
      push('op', '&');
      i += 1;
    } else if (c === '=') {
      push('op', '=');
      i += 1;
    } else if (c === '>' || c === '<') {
      // Dozwolone jedynie wyciszenie: 2>&1, >$null, 2>$null, *>$null.
      const rest = src.slice(i);
      const harmless = /^>\s*\$null\b/i.exec(rest) || /^>&1/.exec(rest);
      if (c === '>' && harmless) {
        if (tokens.length && /^[12*]$/.test(tokens[tokens.length - 1].v)) tokens.pop();
        i += harmless[0].length;
      } else {
        flags.add('redirect');
        i += 1;
      }
    } else {
      let word = '';
      while (i < src.length && !WORD_STOP.has(src[i]) && !QUOTES_SINGLE.has(src[i]) && !QUOTES_DOUBLE.has(src[i])) {
        if (src[i] === '[' && word) break;
        // Operatory przypisania złożonego (+=, -=…) kończą słowo.
        if ('+-*/%'.includes(src[i]) && src[i + 1] === '=' && word) break;
        word += src[i];
        i += 1;
      }
      if (!word) {
        word = src[i];
        i += 1;
      }
      if (/^[+\-*/%]$/.test(word) && src[i] === '=') {
        push('op', '=');
        i += 1;
        continue;
      }
      push('word', word, { callNext: src[i] === '(' });
    }
  }
  return { tokens, flags };
}

const STATEMENT_START = new Set([';', '|', '||', '&&', '(', '{', '$(', '@(', '@{', '=']);
const STATEMENT_END = new Set([';', '|', '||', '&&', ')', '}']);

function normalizeType(name) {
  return name.toLowerCase().replace(/^system\./, '');
}

function commandName(word) {
  const lower = word.toLowerCase();
  if (ALIASES[lower]) return ALIASES[lower];
  return lower.replace(/\.exe$/, '');
}

/**
 * Klasyfikuje polecenie PowerShell.
 * @param {string} command
 * @returns {{readOnly: boolean, reasons: string[], warnings: string[], commands: string[]}}
 */
function classifyPowerShell(command) {
  const reasons = [];
  const warnings = [];
  const commands = [];
  const text = String(command || '');
  if (!text.trim()) return { readOnly: false, reasons: ['Puste polecenie.'], warnings, commands };
  if (text.length > 8000) reasons.push('Polecenie jest zbyt długie do automatycznej oceny.');
  for (const [pattern, message] of DANGER) {
    if (pattern.test(text)) warnings.push(message);
  }
  const lower = text.toLowerCase();
  const sensitive = SENSITIVE.find((item) => lower.includes(item));
  if (sensitive) reasons.push(`Polecenie dotyczy danych poufnych („${sensitive}”).`);

  const { tokens, flags } = tokenize(text);
  if (flags.has('herestring')) reasons.push('Napisy wielowierszowe (here-string) wymagają zgody.');
  if (flags.has('subexpression')) reasons.push('Podwyrażenie $( ) wewnątrz napisu.');
  if (flags.has('backtick')) reasons.push('Znak ` (możliwe zaciemnienie polecenia).');
  if (flags.has('redirect')) reasons.push('Przekierowanie wyjścia do pliku (> lub <).');

  let expectCommand = true;
  for (let index = 0; index < tokens.length; index += 1) {
    const token = tokens[index];
    const nextToken = tokens[index + 1];
    const previous = tokens[index - 1];
    if (token.t === 'op') {
      if (token.v === '&') reasons.push('Operator wywołania & uruchamia dowolny program lub blok.');
      if (token.v === '=') {
        const target = previous;
        const beforeTarget = tokens[index - 2];
        const simpleVariable = target && target.t === 'var' && !target.v.slice(1).includes('.');
        const hashKey = target && target.t === 'word' && !(beforeTarget && beforeTarget.v === '::');
        const quotedKey = target && target.t === 'str';
        if (!simpleVariable && !hashKey && !quotedKey) {
          reasons.push('Przypisanie do właściwości obiektu lub składowej statycznej zmienia stan.');
        }
      }
      if (token.v === '::') {
        const typeToken = previous && previous.t === 'type' ? normalizeType(previous.v) : '';
        const member = nextToken && nextToken.t === 'word' ? nextToken.v.toLowerCase() : '';
        const allowed = Object.prototype.hasOwnProperty.call(SAFE_STATIC, typeToken) ? SAFE_STATIC[typeToken] : undefined;
        if (allowed === undefined || (allowed !== null && !allowed.has(member.split('.')[0]))) {
          reasons.push(`Wywołanie .NET [${previous ? previous.v : '?'}]::${member || '?'}.`);
        }
        if (nextToken && nextToken.t === 'word') index += 1;
        const memberCall = nextToken && nextToken.v.includes('.') && nextToken.callNext;
        if (memberCall) checkMethod(nextToken.v.split('.').pop(), reasons);
        expectCommand = false;
        continue;
      }
      if (STATEMENT_START.has(token.v)) expectCommand = true;
      else expectCommand = false;
      continue;
    }
    if (token.t === 'var') {
      if (token.callNext) checkMethod(token.v.split('.').pop(), reasons);
      expectCommand = false;
      continue;
    }
    if (token.t === 'str') {
      if (token.callNext && nextToken && nextToken.t === 'word' && nextToken.callNext) {
        checkMethod(nextToken.v.replace(/^\./, ''), reasons);
        index += 1;
      }
      expectCommand = false;
      continue;
    }
    if (token.t === 'type') {
      expectCommand = false;
      continue;
    }
    // Słowo.
    const word = token.v;
    const attached = token.pos > 0 && !/\s/.test(text[token.pos - 1]);
    const memberOf = previous && (previous.t !== 'op' || previous.v === ')' || previous.v === '}');
    if (word.startsWith('.') && word.length > 1 && attached && memberOf) {
      if (token.callNext) checkMethod(word.slice(1).split('.').pop(), reasons);
      expectCommand = false;
      continue;
    }
    if (expectCommand) {
      expectCommand = false;
      if (word === '.') {
        reasons.push('Uruchamianie skryptu kropką (dot-sourcing).');
        continue;
      }
      if (nextToken && nextToken.t === 'op' && nextToken.v === '=') continue;
      if (word.startsWith('-') || word === '!' || /^[\d.]+([kmgtp]b)?$/i.test(word)) continue;
      const lowerWord = word.toLowerCase();
      if (DEFINITION_KEYWORDS.has(lowerWord)) {
        reasons.push(`Definicja „${word}” wymaga zgody.`);
        continue;
      }
      if (KEYWORDS.has(lowerWord) && !(lowerWord === 'foreach' && previous && previous.v === '|')) {
        if (lowerWord === 'in' || lowerWord === 'return' || lowerWord === 'exit') expectCommand = true;
        continue;
      }
      const name = commandName(word);
      if (READ_ONLY_CMDLETS.has(name)) {
        commands.push(name);
        if (name === 'foreach-object' && invokesMember(tokens, index + 1)) {
          reasons.push('ForEach-Object z nazwą metody może wywołać dowolną metodę obiektów.');
        }
        continue;
      }
      if (Object.prototype.hasOwnProperty.call(READ_ONLY_PROGRAMS, name)) {
        commands.push(name);
        const allowedArgs = READ_ONLY_PROGRAMS[name];
        if (allowedArgs !== null) {
          for (let j = index + 1; j < tokens.length; j += 1) {
            const arg = tokens[j];
            if (arg.t === 'op' && STATEMENT_END.has(arg.v)) break;
            if (!allowedArgs.has(String(arg.v).toLowerCase())) {
              reasons.push(`Program ${name} z argumentem „${arg.v}” może zmieniać system.`);
              break;
            }
          }
        }
        continue;
      }
      reasons.push(`Polecenie „${word}” nie jest na liście poleceń tylko do odczytu.`);
      continue;
    }
    const verbNoun = /^([A-Za-z]+)-([A-Za-z][\w]*)$/.exec(word);
    if (verbNoun && CHANGING_VERBS.has(verbNoun[1].toLowerCase()) && !READ_ONLY_CMDLETS.has(word.toLowerCase())) {
      reasons.push(`Nazwa polecenia zmieniającego stan w argumentach („${word}”).`);
    }
  }
  const unique = [...new Set(reasons)];
  return { readOnly: unique.length === 0, reasons: unique, warnings: [...new Set(warnings)], commands: [...new Set(commands)] };
}

// ForEach-Object -MemberName X albo ForEach-Object X (bez bloku { }) wywołuje metodę X.
function invokesMember(tokens, from) {
  for (let j = from; j < tokens.length; j += 1) {
    const arg = tokens[j];
    if (arg.t === 'op' && (STATEMENT_END.has(arg.v) || arg.v === '{')) return false;
    if (arg.t === 'str') return true;
    if (arg.t === 'word') {
      const lowerArg = arg.v.toLowerCase();
      if (!lowerArg.startsWith('-')) return true;
      if (lowerArg.length > 2 && 'membername'.startsWith(lowerArg.slice(1))) return true;
      if (lowerArg === '-m') return true;
    }
  }
  return false;
}

function checkMethod(name, reasons) {
  if (!SAFE_METHODS.has(String(name).toLowerCase())) {
    reasons.push(`Wywołanie metody .${name}() może zmieniać stan.`);
  }
}

module.exports = { classifyPowerShell, tokenize, READ_ONLY_CMDLETS, READ_ONLY_PROGRAMS };
