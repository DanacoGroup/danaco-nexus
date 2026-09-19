// Podświetlanie składni (highlight.js – rdzeń z wybranymi językami, bez pełnego pakietu).

import hljs from "highlight.js/lib/core";
import bash from "highlight.js/lib/languages/bash";
import c from "highlight.js/lib/languages/c";
import cpp from "highlight.js/lib/languages/cpp";
import csharp from "highlight.js/lib/languages/csharp";
import css from "highlight.js/lib/languages/css";
import diff from "highlight.js/lib/languages/diff";
import dockerfile from "highlight.js/lib/languages/dockerfile";
import go from "highlight.js/lib/languages/go";
import ini from "highlight.js/lib/languages/ini";
import java from "highlight.js/lib/languages/java";
import javascript from "highlight.js/lib/languages/javascript";
import json from "highlight.js/lib/languages/json";
import kotlin from "highlight.js/lib/languages/kotlin";
import markdown from "highlight.js/lib/languages/markdown";
import php from "highlight.js/lib/languages/php";
import powershell from "highlight.js/lib/languages/powershell";
import python from "highlight.js/lib/languages/python";
import rust from "highlight.js/lib/languages/rust";
import scss from "highlight.js/lib/languages/scss";
import sql from "highlight.js/lib/languages/sql";
import typescript from "highlight.js/lib/languages/typescript";
import xml from "highlight.js/lib/languages/xml";
import yaml from "highlight.js/lib/languages/yaml";

const LANGUAGES = {
  bash,
  c,
  cpp,
  csharp,
  css,
  diff,
  dockerfile,
  go,
  ini,
  java,
  javascript,
  json,
  kotlin,
  markdown,
  php,
  powershell,
  python,
  rust,
  scss,
  sql,
  typescript,
  xml,
  yaml,
};
for (const [name, definition] of Object.entries(LANGUAGES)) hljs.registerLanguage(name, definition);

const EXTENSIONS: Record<string, string> = {
  sh: "bash",
  bash: "bash",
  zsh: "bash",
  c: "c",
  h: "c",
  cpp: "cpp",
  cc: "cpp",
  hpp: "cpp",
  cs: "csharp",
  css: "css",
  diff: "diff",
  patch: "diff",
  go: "go",
  ini: "ini",
  cfg: "ini",
  toml: "ini",
  env: "ini",
  java: "java",
  js: "javascript",
  mjs: "javascript",
  cjs: "javascript",
  jsx: "javascript",
  json: "json",
  kt: "kotlin",
  kts: "kotlin",
  md: "markdown",
  php: "php",
  ps1: "powershell",
  psm1: "powershell",
  py: "python",
  rs: "rust",
  scss: "scss",
  sql: "sql",
  ts: "typescript",
  tsx: "typescript",
  html: "xml",
  htm: "xml",
  xml: "xml",
  svg: "xml",
  vue: "xml",
  yml: "yaml",
  yaml: "yaml",
};
const FILE_NAMES: Record<string, string> = { dockerfile: "dockerfile", makefile: "bash", ".env": "ini" };
// Większe pliki pokazujemy bez podświetlania (płynność przewijania na telefonie).
const MAX_HIGHLIGHT = 300_000;

export function languageFor(path: string): string | null {
  const name = path.split("/").pop()?.toLowerCase() ?? "";
  if (FILE_NAMES[name]) return FILE_NAMES[name];
  const dot = name.lastIndexOf(".");
  return dot >= 0 ? (EXTENSIONS[name.slice(dot + 1)] ?? null) : null;
}

function escapeHtml(text: string): string {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

/** Kod jako bezpieczny HTML (znaczniki tylko od highlight.js, treść zawsze zakodowana). */
export function highlightCode(text: string, path: string): { html: string; language: string | null } {
  const language = languageFor(path);
  if (!language || text.length > MAX_HIGHLIGHT) return { html: escapeHtml(text), language: null };
  try {
    return { html: hljs.highlight(text, { language, ignoreIllegals: true }).value, language };
  } catch {
    return { html: escapeHtml(text), language: null };
  }
}
