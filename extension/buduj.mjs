// Budowa rozszerzenia: katalog rozpakowany + paczka ZIP.
//
//   node buduj.mjs [katalog-wyjściowy]
//
// Domyślnie: <repozytorium>/.tmp/rozszerzenie/out/ (nexus-rozszerzenie/ i nexus-rozszerzenie.zip).
// Wersja pochodzi z manifest.json, ikony z frontend/public/icons.

import { build } from "esbuild";
import { copyFileSync, mkdirSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync } from "node:fs";
import { dirname, join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import zlib from "node:zlib";

const KATALOG = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(KATALOG, "..");
const WYJSCIE = resolve(process.argv[2] ?? process.env.NEXUS_ROZSZERZENIE_OUT ?? join(REPO, ".tmp", "rozszerzenie", "out"));
const NAZWA = "nexus-rozszerzenie";
const CEL = join(WYJSCIE, NAZWA);

const manifest = JSON.parse(readFileSync(join(KATALOG, "manifest.json"), "utf8"));
if (!/^\d+(\.\d+){0,3}$/.test(manifest.version)) throw new Error(`Nieprawidłowa wersja w manifest.json: ${manifest.version}`);

rmSync(CEL, { recursive: true, force: true });
mkdirSync(join(CEL, "ikony"), { recursive: true });

await build({
  entryPoints: {
    tlo: join(KATALOG, "src/tlo.ts"),
    tresc: join(KATALOG, "src/tresc/index.ts"),
    panel: join(KATALOG, "src/panel/panel.ts"),
    opcje: join(KATALOG, "src/opcje/opcje.ts"),
  },
  outdir: CEL,
  bundle: true,
  format: "iife",
  target: ["chrome116"],
  charset: "utf8",
  legalComments: "none",
  minify: false,
  logLevel: "warning",
});

copyFileSync(join(KATALOG, "manifest.json"), join(CEL, "manifest.json"));
copyFileSync(join(KATALOG, "src/panel/panel.html"), join(CEL, "panel.html"));
copyFileSync(join(KATALOG, "src/opcje/opcje.html"), join(CEL, "opcje.html"));
copyFileSync(join(KATALOG, "src/styl.css"), join(CEL, "styl.css"));
const IKONY = join(REPO, "frontend/public/icons");
copyFileSync(join(IKONY, "favicon-32.png"), join(CEL, "ikony/nexus-32.png"));
copyFileSync(join(IKONY, "icon-192.png"), join(CEL, "ikony/nexus-192.png"));

// ---------- ZIP (deflate, bez zewnętrznych zależności) ----------

const TABELA_CRC = Array.from({ length: 256 }, (_, n) => {
  let c = n;
  for (let k = 0; k < 8; k += 1) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
  return c >>> 0;
});

function crc32(bufor) {
  if (typeof zlib.crc32 === "function") return zlib.crc32(bufor) >>> 0;
  let c = 0xffffffff;
  for (const bajt of bufor) c = TABELA_CRC[(c ^ bajt) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

function pliki(katalog) {
  return readdirSync(katalog)
    .sort()
    .flatMap((nazwa) => {
      const sciezka = join(katalog, nazwa);
      return statSync(sciezka).isDirectory() ? pliki(sciezka) : [sciezka];
    });
}

function zip(katalog, plikZip) {
  const lokalne = [];
  const centralne = [];
  let przesuniecie = 0;
  // Stała data (1.01.2026) – powtarzalna paczka dla tej samej treści.
  const czasDos = 0;
  const dataDos = ((2026 - 1980) << 9) | (1 << 5) | 1;
  for (const sciezka of pliki(katalog)) {
    const nazwa = Buffer.from(relative(katalog, sciezka).split(sep).join("/"), "utf8");
    const dane = readFileSync(sciezka);
    const skompresowane = zlib.deflateRawSync(dane, { level: 9 });
    const suma = crc32(dane);
    const naglowek = Buffer.alloc(30);
    naglowek.writeUInt32LE(0x04034b50, 0);
    naglowek.writeUInt16LE(20, 4);
    naglowek.writeUInt16LE(0x0800, 6); // nazwy w UTF-8
    naglowek.writeUInt16LE(8, 8);
    naglowek.writeUInt16LE(czasDos, 10);
    naglowek.writeUInt16LE(dataDos, 12);
    naglowek.writeUInt32LE(suma, 14);
    naglowek.writeUInt32LE(skompresowane.length, 18);
    naglowek.writeUInt32LE(dane.length, 22);
    naglowek.writeUInt16LE(nazwa.length, 26);
    naglowek.writeUInt16LE(0, 28);
    lokalne.push(naglowek, nazwa, skompresowane);
    const wpis = Buffer.alloc(46);
    wpis.writeUInt32LE(0x02014b50, 0);
    wpis.writeUInt16LE(20, 4);
    wpis.writeUInt16LE(20, 6);
    wpis.writeUInt16LE(0x0800, 8);
    wpis.writeUInt16LE(8, 10);
    wpis.writeUInt16LE(czasDos, 12);
    wpis.writeUInt16LE(dataDos, 14);
    wpis.writeUInt32LE(suma, 16);
    wpis.writeUInt32LE(skompresowane.length, 20);
    wpis.writeUInt32LE(dane.length, 24);
    wpis.writeUInt16LE(nazwa.length, 28);
    wpis.writeUInt32LE(przesuniecie, 42);
    centralne.push(wpis, nazwa);
    przesuniecie += naglowek.length + nazwa.length + skompresowane.length;
  }
  const katalogCentralny = Buffer.concat(centralne);
  const koniec = Buffer.alloc(22);
  const liczba = centralne.length / 2;
  koniec.writeUInt32LE(0x06054b50, 0);
  koniec.writeUInt16LE(liczba, 8);
  koniec.writeUInt16LE(liczba, 10);
  koniec.writeUInt32LE(katalogCentralny.length, 12);
  koniec.writeUInt32LE(przesuniecie, 16);
  writeFileSync(plikZip, Buffer.concat([...lokalne, katalogCentralny, koniec]));
  return liczba;
}

const plikZip = join(WYJSCIE, `${NAZWA}.zip`);
const liczba = zip(CEL, plikZip);
console.log(`Rozszerzenie ${manifest.version}: ${CEL}`);
console.log(`Paczka: ${plikZip} (${liczba} plików, ${statSync(plikZip).size} B)`);
