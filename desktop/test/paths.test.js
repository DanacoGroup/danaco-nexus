'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { isSensitivePath, nameMatcher, normalizeExtensions, resolveFolders, shouldSkipDir } = require('../src/agent/paths');

const KNOWN = {
  home: 'C:\\Users\\Jan',
  desktop: 'C:\\Users\\Jan\\OneDrive\\Pulpit',
  documents: 'C:\\Users\\Jan\\Documents',
  downloads: 'C:\\Users\\Jan\\Downloads',
  pictures: 'C:\\Users\\Jan\\Pictures',
  videos: 'C:\\Users\\Jan\\Videos',
  music: 'C:\\Users\\Jan\\Music',
  onedrive: '',
};

test('pliki z danymi logowania są zablokowane', () => {
  for (const blocked of [
    'C:\\Users\\Jan\\.ssh\\id_rsa',
    'C:/Users/Jan/.ssh/config',
    'C:\\Users\\Jan\\AppData\\Local\\Google\\Chrome\\User Data\\Default\\Login Data',
    'C:\\Users\\Jan\\Documents\\hasla.kdbx',
    'C:\\Users\\Jan\\certyfikat.PFX',
    'D:\\projekt\\.env',
    'D:\\projekt\\.env.production',
    'C:\\Users\\Jan\\AppData\\Roaming\\Nexus Desktop\\klucz-urzadzenia.bin',
    'C:\\Windows\\System32\\config\\SAM',
  ]) {
    assert.equal(isSensitivePath(blocked), true, blocked);
  }
  for (const allowed of ['C:\\Users\\Jan\\Documents\\umowa.pdf', 'D:\\Zdjęcia\\wakacje.jpg', 'C:\\Users\\Jan\\envy.txt']) {
    assert.equal(isSensitivePath(allowed), false, allowed);
  }
});

test('katalogi po nazwie i ścieżce', () => {
  const all = resolveFolders([], KNOWN);
  assert.deepEqual(all.errors, []);
  assert.ok(all.roots.includes('C:\\Users\\Jan\\OneDrive\\Pulpit'));
  assert.equal(all.roots.length, 6);
  const picked = resolveFolders(['Dokumenty', 'D:\\Faktury', 'względna', 'C:\\Users\\Jan\\.ssh', 'Nieznany'], KNOWN);
  assert.deepEqual(picked.roots, ['C:\\Users\\Jan\\Documents', 'D:\\Faktury']);
  assert.equal(picked.errors.length, 3);
});

test('dopasowanie nazw i rozszerzeń', () => {
  assert.equal(nameMatcher('faktura*2026*.pdf')('Faktura_03_2026_Łódź.PDF'), true);
  assert.equal(nameMatcher('faktura*2026*.pdf')('faktura_2025.pdf'), false);
  assert.equal(nameMatcher('ŁÓDŹ')('raport-łódź.docx'), true);
  assert.equal(nameMatcher('')('cokolwiek'), true);
  assert.equal(nameMatcher('a?c')('abc'), true);
  assert.deepEqual([...normalizeExtensions(['PDF', '.docx', ' '])], ['.pdf', '.docx']);
  assert.equal(shouldSkipDir('node_modules'), true);
  assert.equal(shouldSkipDir('AppData'), true);
  assert.equal(shouldSkipDir('Faktury'), false);
});
