// Test skryptów wstrzykiwanych do WebView (assets/nexus/most.js i panel.js) w Node, bez zależności:
// atrapa window/document/fetch i mostka WebMessageListener. Uruchomienie: node android/scripts/test-mostek.mjs
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const assets = join(dirname(fileURLToPath(import.meta.url)), "..", "android", "app", "src", "main", "assets", "nexus");
const ORIGIN = "https://danaco-nexus.pl";
const RUN = "11111111-2222-3333-4444-555555555555";
const CONVERSATION = "66666666-7777-8888-9999-000000000000";
const TOKEN = "nxd_" + "k".repeat(43);

function environment({ loggedIn = true } = {}) {
  const sent = [];
  const requests = [];
  const listeners = {};
  const bridge = { postMessage: (text) => sent.push(JSON.parse(text)), onmessage: null };
  const response = (status, body) => ({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
    clone() {
      return response(status, body);
    },
  });
  const fetch = async (input, init = {}) => {
    const url = typeof input === "string" ? input : input.url;
    requests.push({ url, init });
    if (url === "/api/auth/me") return loggedIn ? response(200, { username: "admin" }) : response(401, {});
    if (url === "/api/urzadzenia") return response(201, { id: "d1", token: TOKEN });
    if (url.endsWith("/messages")) return response(202, { run_id: RUN });
    if (url === "/api/auth/login") return response(200, { username: "admin" });
    return response(404, {});
  };
  const window = {
    location: { href: ORIGIN + "/c/" + CONVERSATION, origin: ORIGIN, pathname: "/c/" + CONVERSATION },
    fetch,
    URL,
    addEventListener: (type, handler) => (listeners[type] = handler),
  };
  window.top = window;
  window.window = window;
  const document = { readyState: "complete", addEventListener() {} };
  const context = vm.createContext({ window, document, location: window.location, URL, JSON, setTimeout, Object });
  return { context, window, bridge, sent, requests, listeners };
}

const flush = () => new Promise((resolve) => setTimeout(resolve, 20));

// --- most.js: klucz urządzenia, zadania, API window.nexusAndroid ---------------------------
{
  const env = environment();
  env.window.NexusAndroidBridge = env.bridge;
  vm.runInContext(readFileSync(join(assets, "most.js"), "utf8"), env.context);
  assert.deepEqual(env.sent[0], { type: "hello", path: "/c/" + CONVERSATION });

  env.bridge.onmessage({ data: JSON.stringify({ type: "key.request", name: "Android – Pixel" }) });
  await flush();
  const create = env.requests.find((request) => request.url === "/api/urzadzenia");
  assert.equal(create.init.method, "POST");
  assert.equal(create.init.headers["X-Nexus-Request"], "1");
  assert.deepEqual(JSON.parse(create.init.body), { name: "Android – Pixel", kind: "android" });
  assert.deepEqual(env.sent.at(-1), { type: "key.created", token: TOKEN, id: "d1" });

  await env.window.fetch(`/api/conversations/${CONVERSATION}/messages`, { method: "POST" });
  await flush();
  assert.deepEqual(env.sent.at(-1), { type: "run.started", runId: RUN, conversationId: CONVERSATION });

  env.window.nexusAndroid.startVoice(CONVERSATION);
  assert.deepEqual(env.sent.at(-1), { type: "voice.start", conversationId: CONVERSATION });
  assert.ok(Object.isFrozen(env.window.nexusAndroid));

  const before = env.sent.length;
  await env.window.fetch("/api/auth/login", { method: "POST" });
  await new Promise((resolve) => setTimeout(resolve, 400));
  assert.equal(env.sent.at(-1).type, "hello", "po zalogowaniu mostek zgłasza się ponownie");
  assert.ok(env.sent.length > before);
}

// --- most.js bez zalogowania: brak klucza ------------------------------------------------
{
  const env = environment({ loggedIn: false });
  env.window.NexusAndroidBridge = env.bridge;
  vm.runInContext(readFileSync(join(assets, "most.js"), "utf8"), env.context);
  env.bridge.onmessage({ data: JSON.stringify({ type: "key.request", name: "Android" }) });
  await flush();
  assert.deepEqual(env.sent.at(-1), { type: "key.nologin" });
  assert.equal(env.requests.filter((request) => request.url === "/api/urzadzenia").length, 0);
}

// --- most.js bez mostka natywnego nie zmienia strony -------------------------------------
{
  const env = environment();
  const original = env.window.fetch;
  vm.runInContext(readFileSync(join(assets, "most.js"), "utf8"), env.context);
  assert.equal(env.window.fetch, original);
  assert.equal(env.window.nexusAndroid, undefined);
}

// --- panel.js: przekazywanie nexus:ready / insert / copy --------------------------------
{
  const env = environment();
  env.window.NexusPanelBridge = env.bridge;
  vm.runInContext(readFileSync(join(assets, "panel.js"), "utf8"), env.context);
  const message = env.listeners.message;
  message({ source: env.window, origin: ORIGIN, data: { type: "nexus:ready" } });
  message({ source: env.window, origin: ORIGIN, data: { type: "nexus:insert", text: "Dziękujemy za opinię!" } });
  message({ source: env.window, origin: ORIGIN, data: { type: "nexus:auth", token: TOKEN } });
  message({ source: {}, origin: ORIGIN, data: { type: "nexus:copy", text: "obce okno" } });
  message({ source: env.window, origin: "https://obca.pl", data: { type: "nexus:copy", text: "obce źródło" } });
  assert.deepEqual(env.sent, [
    { type: "nexus:ready", text: "" },
    { type: "nexus:insert", text: "Dziękujemy za opinię!" },
  ]);
}

console.log("Skrypty mostka: wszystkie testy przeszły.");
