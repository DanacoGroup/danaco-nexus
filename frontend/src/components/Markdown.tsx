// Renderowanie Markdown odpowiedzi asystenta (marked + oczyszczanie DOMPurify).

import DOMPurify from "dompurify";
import { marked } from "marked";
import { useMemo } from "react";

// `breaks: true` zamienia pojedynczy znak końca wiersza na `<br>`. Tak ma być w **rozmowie**:
// użytkownik naciska Enter, żeby przejść do nowej linii, i oczekuje, że ją zobaczy.
// W **artykule** jest odwrotnie — plik źródłowy jest zawijany na ok. 95 znakach dla czytelności
// w repozytorium, a czytelnik dostawał wtedy tekst połamany w środku zdań (zmierzone na
// wydaniu 21.09.2026, wpis bloga „Dzień z Nexusem”). CommonMark traktuje pojedynczy koniec
// wiersza jako spację i tak właśnie ma wyglądać proza.
marked.setOptions({ gfm: true, breaks: true });

DOMPurify.addHook("afterSanitizeAttributes", (node) => {
  if (node.tagName === "A") {
    node.setAttribute("target", "_blank");
    node.setAttribute("rel", "noopener noreferrer");
  }
});

export function renderMarkdown(source: string, lamiWiersze = true): string {
  const html = marked.parse(source, { async: false, breaks: lamiWiersze }) as string;
  return DOMPurify.sanitize(html, { USE_PROFILES: { html: true }, FORBID_TAGS: ["style", "form", "input"] });
}

export function Markdown({ text, proza = false }: { text: string; proza?: boolean }) {
  const html = useMemo(() => renderMarkdown(text, !proza), [text, proza]);
  return <div className="markdown" dangerouslySetInnerHTML={{ __html: html }} />;
}
