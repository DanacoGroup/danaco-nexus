'use strict';
// Ścieżki dla narzędzi pc_*: katalogi użytkownika, blokada plików z danymi logowania,
// dopasowanie nazw i rozpoznawanie plików tekstowych.

const path = require('node:path');

// Nazwy katalogów, które model może podać zamiast ścieżki (klucze: nazwy ścieżek Electron).
const FOLDER_ALIASES = {
  pulpit: 'desktop',
  desktop: 'desktop',
  dokumenty: 'documents',
  documents: 'documents',
  pobrane: 'downloads',
  downloads: 'downloads',
  obrazy: 'pictures',
  pictures: 'pictures',
  wideo: 'videos',
  filmy: 'videos',
  videos: 'videos',
  muzyka: 'music',
  music: 'music',
  onedrive: 'onedrive',
  'katalog domowy': 'home',
  home: 'home',
};

const DEFAULT_FOLDERS = ['desktop', 'documents', 'downloads', 'pictures', 'videos', 'music', 'onedrive'];

// Katalogi pomijane przy przeszukiwaniu (duże, systemowe albo z danymi programów).
const SKIP_DIRS = new Set([
  'node_modules', '.git', '.svn', '.hg', '$recycle.bin', 'system volume information', 'appdata', '.cache',
  '__pycache__', '.venv', 'venv', '.gradle', '.m2', '.nuget', '.vscode-server', 'windows', 'program files',
  'program files (x86)', 'programdata', '$windows.~bt', '$windows.~ws', 'windowsapps', 'recovery',
]);

const SENSITIVE_PARTS = [
  '\\.ssh\\', '\\.gnupg\\', '\\.aws\\', '\\.azure\\', '\\.kube\\', '\\.docker\\',
  '\\appdata\\local\\google\\chrome\\user data\\', '\\appdata\\local\\microsoft\\edge\\user data\\',
  '\\appdata\\local\\bravesoftware\\', '\\appdata\\roaming\\mozilla\\firefox\\profiles\\',
  '\\appdata\\roaming\\opera software\\', '\\appdata\\roaming\\microsoft\\credentials\\',
  '\\appdata\\local\\microsoft\\credentials\\', '\\appdata\\roaming\\microsoft\\protect\\',
  '\\appdata\\local\\microsoft\\vault\\', '\\windows\\system32\\config\\', '\\nexus desktop\\',
  '\\appdata\\roaming\\bitwarden\\', '\\appdata\\local\\1password\\', '\\appdata\\roaming\\keepass',
];
const SENSITIVE_NAMES = new Set([
  'id_rsa', 'id_dsa', 'id_ecdsa', 'id_ed25519', 'known_hosts', '.git-credentials', '.netrc', '_netrc',
  'wallet.dat', '.npmrc', '.pypirc', 'credentials', 'credentials.json', 'klucz-urzadzenia.bin',
]);
const SENSITIVE_EXTENSIONS = new Set(['.kdbx', '.kdb', '.pfx', '.p12', '.pem', '.key', '.ppk', '.jks', '.keystore', '.ovpn']);

const TEXT_EXTENSIONS = new Set([
  '.txt', '.md', '.csv', '.tsv', '.json', '.xml', '.html', '.htm', '.css', '.js', '.mjs', '.cjs', '.ts', '.tsx',
  '.jsx', '.py', '.ps1', '.psm1', '.bat', '.cmd', '.sh', '.log', '.ini', '.cfg', '.conf', '.yaml', '.yml', '.toml',
  '.sql', '.rtf', '.srt', '.vtt', '.java', '.kt', '.cs', '.c', '.h', '.cpp', '.hpp', '.go', '.rs', '.php', '.rb',
  '.vue', '.svelte', '.tex', '.properties', '.gradle', '.reg', '.eml', '.vcf', '.ics',
]);
const IMAGE_EXTENSIONS = new Set(['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tif', '.tiff', '.ico']);

/**
 * Czy ścieżka wskazuje dane logowania, klucze lub profile przeglądarek (zawsze zablokowane).
 * @param {string} target
 */
function isSensitivePath(target) {
  const normalized = `\\${path.win32.normalize(String(target)).toLowerCase().replace(/\//g, '\\')}\\`;
  if (SENSITIVE_PARTS.some((part) => normalized.includes(part))) return true;
  const base = path.win32.basename(String(target)).toLowerCase();
  if (SENSITIVE_NAMES.has(base)) return true;
  if (base === '.env' || base.startsWith('.env.')) return true;
  return SENSITIVE_EXTENSIONS.has(path.win32.extname(base));
}

/**
 * Katalogi do przeszukania: nazwy („Dokumenty”) albo ścieżki bezwzględne.
 * @param {string[]} folders
 * @param {Record<string, string>} known ścieżki systemowe (desktop, documents…, home, onedrive)
 * @returns {{roots: string[], errors: string[]}}
 */
function resolveFolders(folders, known) {
  const roots = [];
  const errors = [];
  const wanted = folders && folders.length ? folders : DEFAULT_FOLDERS;
  for (const raw of wanted) {
    const value = String(raw || '').trim();
    if (!value) continue;
    const alias = FOLDER_ALIASES[value.toLowerCase()];
    let resolved = alias ? known[alias] : value;
    if (!resolved) {
      if (!folders || !folders.length) continue;
      errors.push(`Nieznany katalog „${value}”.`);
      continue;
    }
    if (!path.win32.isAbsolute(resolved)) {
      errors.push(`Ścieżka „${value}” musi być bezwzględna (np. C:\\Users\\…) albo nazwą katalogu.`);
      continue;
    }
    resolved = path.win32.normalize(resolved);
    if (isSensitivePath(resolved)) {
      errors.push(`Katalog „${value}” zawiera dane poufne i jest zablokowany.`);
      continue;
    }
    if (!roots.some((root) => root.toLowerCase() === resolved.toLowerCase())) roots.push(resolved);
  }
  return { roots, errors };
}

/**
 * Funkcja dopasowania nazwy: wzorzec z * i ? (cała nazwa) albo fragment nazwy.
 * @param {string} pattern
 */
function nameMatcher(pattern) {
  const value = String(pattern || '').trim().toLocaleLowerCase('pl');
  if (!value) return () => true;
  if (/[*?]/.test(value)) {
    const source = value.replace(/[.+^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*').replace(/\?/g, '.');
    const regex = new RegExp(`^${source}$`, 'i');
    return (name) => regex.test(name.toLocaleLowerCase('pl'));
  }
  return (name) => name.toLocaleLowerCase('pl').includes(value);
}

/** Rozszerzenia z parametru narzędzia w postaci „.pdf”. */
function normalizeExtensions(extensions) {
  return new Set(
    (extensions || [])
      .map((item) => String(item).trim().toLowerCase())
      .filter(Boolean)
      .map((item) => (item.startsWith('.') ? item : `.${item}`)),
  );
}

function shouldSkipDir(name) {
  return SKIP_DIRS.has(name.toLowerCase()) || name.startsWith('.');
}

module.exports = {
  DEFAULT_FOLDERS,
  IMAGE_EXTENSIONS,
  TEXT_EXTENSIONS,
  isSensitivePath,
  nameMatcher,
  normalizeExtensions,
  resolveFolders,
  shouldSkipDir,
};
