'use strict';
// Test uruchomienia bez udziału użytkownika (electron . --smoke-test [--smoke-out=KATALOG]):
// tworzy wszystkie okna, sprawdza proces pomocniczy, narzędzia pc_* i okno zgody,
// zapisuje raport JSON i zrzuty okien, po czym kończy aplikację (kod 0 = sukces).

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const LOAD_TIMEOUT_MS = 25000;

function outputDir() {
  const option = process.argv.find((item) => item.startsWith('--smoke-out='));
  return option ? option.slice('--smoke-out='.length) : path.join(os.tmpdir(), 'nexus-desktop-test', 'raport');
}

function waitLoad(contents) {
  return new Promise((resolve) => {
    const timer = setTimeout(() => resolve({ state: 'limit-czasu' }), LOAD_TIMEOUT_MS);
    contents.once('did-finish-load', () => {
      clearTimeout(timer);
      resolve({ state: 'zaladowano', url: contents.getURL() });
    });
    contents.on('did-fail-load', (_event, code, description, url, isMainFrame) => {
      if (!isMainFrame) return;
      clearTimeout(timer);
      resolve({ state: 'blad-sieci', code, description, url });
    });
  });
}

async function capture(contents, file) {
  try {
    const timeout = new Promise((_, reject) => setTimeout(() => reject(new Error('limit czasu zrzutu')), 5000));
    const image = await Promise.race([contents.capturePage(), timeout]);
    fs.writeFileSync(file, image.toPNG());
    return path.basename(file);
  } catch (error) {
    return `błąd: ${error.message}`;
  }
}

async function step(report, name, action) {
  const started = Date.now();
  try {
    report.checks[name] = await action();
    report.checks[name].ms = Date.now() - started;
  } catch (error) {
    report.checks[name] = { blad: error.message };
    report.errors.push(`${name}: ${error.message}`);
  }
}

async function run({ app, state, initialize, createMainWindow, openSettings, registerShortcuts }) {
  const directory = outputDir();
  fs.mkdirSync(directory, { recursive: true });
  const report = {
    ok: false,
    electron: process.versions.electron,
    node: process.versions.node,
    chrome: process.versions.chrome,
    platform: `${os.platform()} ${os.release()}`,
    windows: {},
    checks: {},
    errors: [],
  };
  const finish = () => {
    fs.writeFileSync(path.join(directory, 'raport.json'), JSON.stringify(report, null, 2), 'utf8');
    process.stdout.write(`${JSON.stringify(report, null, 2)}\n`);
    state.quitting = true;
    app.exit(report.ok ? 0 : 1);
  };
  const guard = setTimeout(() => {
    report.errors.push('Przekroczono łączny limit czasu testu.');
    finish();
  }, 150000);
  try {
    initialize();
    const main = createMainWindow(true);
    const mainLoad = waitLoad(main.webContents);
    const tab = state.panel.createTab();
    const tabLoad = waitLoad(tab.webContents);
    state.panel.createPanel();
    const toolbarLoad = waitLoad(state.panel.toolbar.webContents);
    const panelLoad = waitLoad(state.panel.content.webContents);
    const settings = openSettings();
    const settingsLoad = waitLoad(settings.webContents);
    report.windows.glowne = { ...(await mainLoad), widoczne: main.isVisible() };
    report.windows.jezyczek = { ...(await tabLoad), granice: tab.getBounds() };
    report.windows.pasekPanelu = await toolbarLoad;
    report.windows.panel = await panelLoad;
    report.windows.ustawienia = await settingsLoad;
    report.windows.ustawienia.wOknieGlownym = main.contentView.children.includes(settings);
    await new Promise((resolve) => setTimeout(resolve, 300));
    const settingsShot = await capture(settings.webContents, path.join(directory, 'ustawienia.png'));

    await step(report, 'pokazaniePanelu', async () => {
      await state.panel.show();
      return { widoczny: state.panel.window.isVisible(), granice: state.panel.window.getBounds(), zawszeNaWierzchu: state.panel.window.isAlwaysOnTop() };
    });
    await step(report, 'oknoZgody', async () => {
      const controller = new AbortController();
      const answer = state.confirm.ask(
        { command: 'Remove-Item C:\\nexus-test -Recurse', description: 'Test okna zgody (odrzucane automatycznie).', reasons: ['Test.'], warnings: ['Rekurencyjne usuwanie plików i katalogów.'] },
        controller.signal,
      );
      const contents = state.confirm.current.contents;
      const loaded = await waitLoad(contents);
      await new Promise((resolve) => setTimeout(resolve, 400));
      const shot = await capture(contents, path.join(directory, 'okno-zgody.png'));
      const inMain = state.overlay.kind === 'zgoda';
      controller.abort();
      return {
        zaladowano: loaded.state,
        wOknieGlownym: inMain,
        odrzuconePoAnulowaniu: (await answer) === false,
        warstwaZamknieta: state.overlay.kind === null,
        zrzut: shot,
      };
    });
    await step(report, 'aktywneOkno', async () => {
      const info = await state.helper.foreground();
      return { tytul: info.title, proces: info.process, maUchwyt: info.hwnd !== '0' };
    });
    await step(report, 'skroty', () => ({ bledy: registerShortcuts() }));
    await step(report, 'pcInfo', async () => {
      const { data } = await state.tools.info({ top_processes: 3 });
      return { system: data.system, ram_gb: data.ram_gb, dyski: data.dyski.length, procesy: data.procesy_wg_pamieci.length };
    });
    await step(report, 'pcScreenshot', async () => {
      const shot = await state.tools.captureScreen(0, 1280);
      fs.writeFileSync(path.join(directory, 'zrzut-ekranu.jpg'), shot.image.toJPEG(80));
      return { szerokosc: shot.width, wysokosc: shot.height };
    });
    await step(report, 'pcFindFiles', async () => {
      const { data } = await state.tools.findFiles({ name: 'main.js', folders: [__dirname], limit: 5 });
      return { liczba: data.liczba, metoda: data.metoda };
    });
    await step(report, 'pcReadFile', async () => {
      const result = await state.tools.readFile({ path: path.join(__dirname, 'main.js'), max_chars: 500 });
      return { typ: result.data.type, znaki: result.text.length };
    });
    await step(report, 'pcPowershellOdczyt', async () => {
      const result = await state.tools.powershell({ command: 'Get-Date -Format yyyy', description: 'Test', timeout_s: 30 });
      return { wyjscie: result.text.trim(), kod: result.data.exit_code, zgoda: result.data.confirmed };
    });
    await step(report, 'agent', async () => {
      state.agent.start();
      return { ...state.agent.status };
    });
    report.windows.zrzuty = {
      glowne: await capture(main.webContents, path.join(directory, 'okno-glowne.png')),
      panel: await capture(state.panel.content.webContents, path.join(directory, 'panel.png')),
      pasekPanelu: await capture(state.panel.toolbar.webContents, path.join(directory, 'pasek-panelu.png')),
      ustawienia: settingsShot,
    };
    const local = [report.windows.jezyczek, report.windows.pasekPanelu, report.windows.ustawienia];
    report.ok =
      local.every((item) => item.state === 'zaladowano') &&
      report.checks.pokazaniePanelu.widoczny === true &&
      report.windows.ustawienia.wOknieGlownym === true &&
      report.checks.oknoZgody.wOknieGlownym === true &&
      report.checks.oknoZgody.odrzuconePoAnulowaniu === true &&
      report.checks.oknoZgody.warstwaZamknieta === true &&
      report.errors.length === 0;
  } catch (error) {
    report.errors.push(error.stack || String(error));
  }
  clearTimeout(guard);
  finish();
}

module.exports = { run };
