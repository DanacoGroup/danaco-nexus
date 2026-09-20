'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { PcTools, decodeText } = require('../src/agent/tools');

// Narzędzia pc_* działają na ścieżkach Windows (path.win32) — Nexus Desktop jest programem
// dla Windows. Na innych systemach testy dotykające plików są pomijane, nie czerwone.
const TYLKO_WINDOWS = { skip: process.platform === 'win32' ? false : 'narzędzia plikowe działają na ścieżkach Windows' };

function tools(overrides = {}) {
  const values = { allowFiles: true, allowPowershell: true, allowScreenshots: true, ...overrides };
  const asked = [];
  const instance = new PcTools({
    electron: { app: { getPath: () => '' } },
    config: { get: (name) => values[name] },
    confirm: {
      ask: async (request) => {
        asked.push(request);
        return false;
      },
    },
    log: { info() {}, warn() {} },
    lastExternalWindow: async () => null,
    hideOwnWindows: async () => {},
  });
  return { instance, asked };
}

function sandbox() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'nexus-narzedzia-'));
  fs.mkdirSync(path.join(root, 'Faktury'));
  fs.mkdirSync(path.join(root, 'node_modules'));
  fs.mkdirSync(path.join(root, '.ssh'));
  fs.writeFileSync(path.join(root, 'Faktury', 'faktura-2026-03.txt'), 'Kwota: 1 250,00 zł – Łódź');
  fs.writeFileSync(path.join(root, 'Faktury', 'faktura-2025-12.txt'), 'Kwota: 99 zł');
  fs.writeFileSync(path.join(root, 'node_modules', 'faktura-2026-pakiet.txt'), 'pomijane');
  fs.writeFileSync(path.join(root, '.ssh', 'id_rsa'), 'tajne');
  fs.writeFileSync(path.join(root, 'dane.bin'), Buffer.from([1, 0, 2, 0, 3]));
  return root;
}

test('dekodowanie tekstu: UTF-8, BOM, UTF-16LE, Windows-1250', () => {
  assert.equal(decodeText(Buffer.from('Zażółć gęślą jaźń', 'utf8')), 'Zażółć gęślą jaźń');
  assert.equal(decodeText(Buffer.concat([Buffer.from([0xef, 0xbb, 0xbf]), Buffer.from('ą', 'utf8')])), 'ą');
  assert.equal(decodeText(Buffer.concat([Buffer.from([0xff, 0xfe]), Buffer.from('Łódź', 'utf16le')])), 'Łódź');
  assert.equal(decodeText(Buffer.from([0x8c, 0xb9, 0xea, 0xf3, 0x9f, 0xbf, 0xb3, 0xe6])), 'Śąęóźżłć');
});

test('wyszukiwanie plików po nazwie i treści z pominięciem katalogów systemowych i poufnych', TYLKO_WINDOWS, async () => {
  const root = sandbox();
  const { instance } = tools();
  const byName = await instance.findFiles({ name: 'faktura-2026*', folders: [root] });
  assert.deepEqual(byName.data.files.map((file) => path.basename(file.path)), ['faktura-2026-03.txt']);
  const walked = await instance.walk({ roots: [root], content: 'łódź', name: '', extensions: new Set(['.txt']), since: NaN, limit: 10 });
  assert.deepEqual(walked.files.map((file) => path.basename(file.path)), ['faktura-2026-03.txt']);
  await assert.rejects(instance.findFiles({ name: 'x', folders: [path.join(root, '.ssh')] }), /poufne/);
  const { instance: blocked } = tools({ allowFiles: false });
  await assert.rejects(blocked.findFiles({ name: 'x', folders: [root] }), /wyłączył/);
});

test('podgląd pliku, katalogu i przesyłanie', TYLKO_WINDOWS, async () => {
  const root = sandbox();
  const { instance } = tools();
  const text = await instance.readFile({ path: path.join(root, 'Faktury', 'faktura-2026-03.txt') });
  assert.equal(text.data.type, 'tekst');
  assert.match(text.text, /Łódź/);
  const listing = await instance.readFile({ path: root });
  assert.equal(listing.data.type, 'katalog');
  assert.ok(!listing.data.entries.some((entry) => entry.name === '.ssh'));
  const binary = await instance.readFile({ path: path.join(root, 'dane.bin') });
  assert.equal(binary.data.type, 'plik binarny');
  const upload = await instance.readFile({ path: path.join(root, 'dane.bin'), upload: true });
  assert.equal(Buffer.from(upload.file.data, 'base64').length, 5);
  await assert.rejects(instance.readFile({ path: path.join(root, '.ssh', 'id_rsa') }), /poufne/);
  await assert.rejects(instance.readFile({ path: 'względna.txt' }), /pełną ścieżkę/);
});

test('PowerShell zmieniający system bez zgody nie jest wykonywany', async () => {
  const { instance, asked } = tools();
  await assert.rejects(instance.powershell({ command: 'Remove-Item C:\\nexus-test.txt', description: 'Test' }), /odrzucił/);
  assert.equal(asked.length, 1);
  assert.equal(asked[0].command, 'Remove-Item C:\\nexus-test.txt');
  await assert.rejects(instance.powershell({ command: 'Get-Date', description: 'Test', as_admin: true }), /odrzucił/);
  assert.equal(asked[1].admin, true);
  const { instance: disabled } = tools({ allowPowershell: false });
  await assert.rejects(disabled.powershell({ command: 'Get-Date', description: 'Test' }), /wyłączył/);
});
