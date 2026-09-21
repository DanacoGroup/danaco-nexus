import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { findModule, MODULES } from "../modules/registry";
import { breadcrumbs, chunkRanges, joinPath, parentPath, uploadToCloud, type CloudEntry } from "../modules/cloud/api";
import { CloudPage, sortEntries } from "../modules/cloud/CloudPage";
import { previewKind } from "../modules/cloud/dialogs";
import { formToInput, initialForm } from "../modules/kalendarz/EventDialog";
import type { CalendarEvent } from "../modules/kalendarz/api";
import { eventsOnDay, isoDay, layoutDay, monthGrid, rangeLabel, startOfWeek, viewRange } from "../modules/kalendarz/grid";
import { listDate, parseAddresses, replyDraft, type MailMessage } from "../modules/poczta/api";
import { KalendarzPage } from "../modules/kalendarz/KalendarzPage";
import { PocztaPage } from "../modules/poczta/PocztaPage";
import { sanitizeEmailHtml } from "../modules/poczta/sanitize";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const entry = (name: string, type: "file" | "folder", size = 0, modified = "2026-09-01T10:00:00+02:00"): CloudEntry => ({
  path: `/${name}`,
  name,
  type,
  size,
  modified,
  mime: type === "file" ? "text/plain" : null,
  etag: "e",
  fileid: 1,
  favorite: false,
  permissions: "",
  has_preview: false,
  shared_link: false,
  shared: false,
});

describe("rejestr modułów biura", () => {
  it("rejestruje Chmurę, Pocztę i Kalendarz", () => {
    expect(findModule("cloud")?.label).toBe("Chmura");
    expect(findModule("poczta")?.label).toBe("Poczta");
    expect(findModule("kalendarz")?.label).toBe("Kalendarz");
    const ids = MODULES.map((item) => item.id);
    expect(ids.indexOf("cloud")).toBeLessThan(ids.indexOf("poczta"));
  });
});

describe("Cloud – ścieżki i sortowanie", () => {
  it("składa ścieżki i okruchy", () => {
    expect(joinPath("/", "a.txt")).toBe("/a.txt");
    expect(joinPath("/Dokumenty/", "Faktura 1.pdf")).toBe("/Dokumenty/Faktura 1.pdf");
    expect(parentPath("/a/b/c.txt")).toBe("/a/b");
    expect(parentPath("/a")).toBe("/");
    expect(breadcrumbs("/Dokumenty/Umowy")).toEqual([
      { name: "Chmura", path: "/" },
      { name: "Dokumenty", path: "/Dokumenty" },
      { name: "Umowy", path: "/Dokumenty/Umowy" },
    ]);
  });

  it("sortuje foldery przed plikami, nazwy naturalnie", () => {
    const items = [entry("plik 10.txt", "file", 5), entry("plik 2.txt", "file", 50), entry("Zdjęcia", "folder"), entry("Akta", "folder")];
    expect(sortEntries(items, "name", true).map((item) => item.name)).toEqual(["Akta", "Zdjęcia", "plik 2.txt", "plik 10.txt"]);
    expect(sortEntries(items, "size", false).map((item) => item.name)).toEqual(["Zdjęcia", "Akta", "plik 2.txt", "plik 10.txt"]);
  });

  it("rozpoznaje rodzaj podglądu", () => {
    expect(previewKind({ ...entry("a.pdf", "file"), mime: "application/pdf" })).toBe("pdf");
    expect(previewKind({ ...entry("a.svg", "file"), mime: "image/svg+xml" })).toBeNull();
    expect(previewKind({ ...entry("notatka.md", "file"), mime: "application/octet-stream" })).toBe("text");
  });

  it("dzieli plik na kawałki", () => {
    expect(chunkRanges(25, 10)).toEqual([
      [0, 10],
      [10, 20],
      [20, 25],
    ]);
    expect(chunkRanges(0, 10)).toEqual([]);
  });
});

class FakeXHR {
  static sent: { method: string; url: string; size: number }[] = [];
  static failOnce = new Set<string>();
  method = "";
  url = "";
  status = 0;
  responseText = "";
  upload: { onprogress: ((event: { lengthComputable: boolean; loaded: number; total: number }) => void) | null } = { onprogress: null };
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onabort: (() => void) | null = null;
  open(method: string, url: string) {
    this.method = method;
    this.url = url;
  }
  setRequestHeader() {}
  abort() {
    this.onabort?.();
  }
  send(body: Blob) {
    queueMicrotask(() => {
      if (FakeXHR.failOnce.has(this.url)) {
        FakeXHR.failOnce.delete(this.url);
        this.onerror?.();
        return;
      }
      FakeXHR.sent.push({ method: this.method, url: this.url, size: body.size });
      this.upload.onprogress?.({ lengthComputable: true, loaded: body.size, total: body.size });
      this.status = 200;
      this.responseText = JSON.stringify({ ok: true, name: "x" });
      this.onload?.();
    });
  }
}

describe("Cloud – wgrywanie kawałkami", () => {
  it("wgrywa duży plik kawałkami, ponawia nieudany kawałek i składa plik", async () => {
    FakeXHR.sent = [];
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      if (url === "/api/cloud/przesylanie") return new Response(JSON.stringify({ upload_id: "nexus-abc" }), { status: 201 });
      if (url.endsWith("/zakoncz")) {
        const body = JSON.parse(String(init?.body));
        return new Response(JSON.stringify({ ...entry("film.mp4", "file", body.size), path: body.path }), { status: 200 });
      }
      return new Response("{}", { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("XMLHttpRequest", FakeXHR);
    vi.useFakeTimers({ toFake: ["setTimeout"] });
    FakeXHR.failOnce.add("/api/cloud/przesylanie/nexus-abc/2?path=%2Ffilm.mp4");
    const progress: number[] = [];
    const file = new File([new Uint8Array(25)], "film.mp4");
    const promise = uploadToCloud(file, "/film.mp4", { chunkSize: 10, onProgress: (value) => progress.push(value) });
    await vi.runAllTimersAsync();
    const result = await promise;
    vi.useRealTimers();
    expect(result.size).toBe(25);
    expect(FakeXHR.sent.map((item) => [item.url.split("?")[0], item.size])).toEqual([
      ["/api/cloud/przesylanie/nexus-abc/1", 10],
      ["/api/cloud/przesylanie/nexus-abc/2", 10],
      ["/api/cloud/przesylanie/nexus-abc/3", 5],
    ]);
    expect(progress.at(-1)).toBe(1);
    const finish = fetchMock.mock.calls.find(([url]) => String(url).endsWith("/zakoncz"));
    expect(JSON.parse(String(finish?.[1]?.body))).toMatchObject({ path: "/film.mp4", size: 25 });
  });

  it("mały plik wysyła jednym żądaniem", async () => {
    FakeXHR.sent = [];
    vi.stubGlobal("XMLHttpRequest", FakeXHR);
    await uploadToCloud(new File(["abc"], "a.txt"), "/Dokumenty/a.txt");
    expect(FakeXHR.sent).toEqual([{ method: "PUT", url: "/api/cloud/plik?path=%2FDokumenty%2Fa.txt", size: 3 }]);
  });
});

describe("Poczta – bezpieczny HTML", () => {
  const options = {
    showImages: false,
    cidUrl: (cid: string) => (cid === "logo@x" ? "/api/poczta/zalacznik?index=2&inline=1" : null),
    proxyUrl: (url: string) => `/api/poczta/obraz?url=${encodeURIComponent(url)}`,
  };

  it("usuwa skrypty, formularze i zdarzenia", () => {
    const { html } = sanitizeEmailHtml(
      '<p onclick="alert(1)">Hej</p><script>alert(2)</script><form action="https://zly.pl"><input name="haslo"></form><a href="javascript:alert(3)">x</a><iframe src="https://zly.pl"></iframe>',
      options,
    );
    expect(html).toContain("<p>Hej</p>");
    expect(html).not.toMatch(/script|onclick|<form|<input|javascript:|iframe/i);
  });

  it("domyślnie blokuje zdalne obrazy i tła, osadzone cid wskazuje załącznik", () => {
    const source =
      '<img src="https://tracker.example.com/p.gif"><img src="cid:logo@x"><div style="background:url(https://x.pl/t.png)">a</div><style>.a{background:url(http://x.pl/b.png)}</style>';
    const blocked = sanitizeEmailHtml(source, options);
    expect(blocked.blockedImages).toBe(3);
    expect(blocked.html).not.toContain("tracker.example.com");
    expect(blocked.html).not.toContain("x.pl");
    expect(blocked.html).toContain('src="/api/poczta/zalacznik?index=2&amp;inline=1"');
    const shown = sanitizeEmailHtml(source, { ...options, showImages: true });
    expect(shown.html).toContain(`/api/poczta/obraz?url=${encodeURIComponent("https://tracker.example.com/p.gif")}`);
  });

  it("linki otwiera w nowej karcie bez przekazywania adresu strony", () => {
    const { html } = sanitizeEmailHtml('<a href="https://booking.com/x">Rezerwacja</a>', options);
    expect(html).toContain('target="_blank"');
    expect(html).toContain('rel="noopener noreferrer nofollow"');
  });
});

describe("Poczta – odpowiedzi i adresy", () => {
  const message: MailMessage = {
    uid: 7,
    folder: "INBOX",
    subject: "Zapytanie o termin",
    from: [{ name: "Jan Kowalski", email: "jan@example.pl" }],
    to: [],
    cc: [],
    reply_to: [],
    date: "2026-09-18T10:15:00+02:00",
    message_id: "<m1@example.pl>",
    references: "",
    text: "Czy 20.09 jest wolny?\nPozdrawiam",
    html: "",
    attachments: [],
  };

  it("przygotowuje odpowiedź z cytatem i nagłówkami wątku", () => {
    const draft = replyDraft(message);
    expect(draft.to).toEqual(["Jan Kowalski <jan@example.pl>"]);
    expect(draft.subject).toBe("Re: Zapytanie o termin");
    expect(draft.in_reply_to).toBe("<m1@example.pl>");
    expect(draft.reply).toEqual({ folder: "INBOX", uid: 7 });
    expect(draft.body).toContain("> Czy 20.09 jest wolny?");
    expect(replyDraft({ ...message, subject: "RE: x" }).subject).toBe("RE: x");
  });

  it("dzieli listę adresów i formatuje datę listy", () => {
    expect(parseAddresses("a@b.pl, c@d.pl;\n e@f.pl ,")).toEqual(["a@b.pl", "c@d.pl", "e@f.pl"]);
    const now = new Date(2026, 8, 19, 12, 0);
    expect(listDate("2026-09-19T08:05:00", now)).toMatch(/08:05/);
    expect(listDate("2025-01-02T08:05:00", now)).toMatch(/2025/);
    expect(listDate(null, now)).toBe("");
  });

  it("bez konfiguracji proponuje podłączenie skrzynki w aplikacji", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) =>
        url.includes("/stan")
          ? new Response(JSON.stringify({ configured: false, address: "", accounts: [] }))
          : new Response("[]"),
      ),
    );
    render(<PocztaPage openConversation={() => undefined} openModule={() => undefined} openChat={() => undefined} />);
    await waitFor(() => expect(screen.getByText("Poczta nie jest jeszcze podłączona")).toBeTruthy());
    // Konto podaje się w module, a nie poleceniem na serwerze — inaczej każdy zalogowany
    // czyta tę samą skrzynkę.
    expect(screen.getByRole("button", { name: "Podłącz skrzynkę" })).toBeTruthy();
    expect(screen.queryByText(/sudo -u danaco-serwis/)).toBeNull();
  });

  it("chmura bez przestrzeni mówi to po ludzku, a nie czerwonym paskiem", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(JSON.stringify({ detail: "Chmura osobista nie jest skonfigurowana (brak adresu Nextcloud lub hasła aplikacji)." }), {
            status: 503,
            headers: { "Content-Type": "application/json" },
          }),
      ),
    );
    render(<CloudPage openConversation={() => undefined} openModule={() => undefined} openChat={() => undefined} />);
    await waitFor(() => expect(screen.getByText("Chmura nie jest jeszcze podłączona")).toBeTruthy());
    expect(screen.queryByText(/hasła aplikacji/)).toBeNull();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("kalendarz bez przestrzeni w chmurze mówi to po ludzku, a nie czerwonym paskiem", async () => {
    // Serwer odpowiada 503 z komunikatem dla administratora („brak adresu chmury lub hasła
    // aplikacji”). Wcześniej szedł on wprost na czerwony pasek nad pustą siatką tygodnia,
    // więc stan przed podłączeniem wyglądał na awarię aplikacji.
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(JSON.stringify({ detail: "Kalendarz nie jest skonfigurowany (brak adresu chmury lub hasła aplikacji)." }), {
            status: 503,
            headers: { "Content-Type": "application/json" },
          }),
      ),
    );
    render(<KalendarzPage openConversation={() => undefined} openModule={() => undefined} openChat={() => undefined} />);
    await waitFor(() => expect(screen.getByText("Kalendarz nie jest jeszcze podłączony")).toBeTruthy());
    expect(screen.queryByText(/hasła aplikacji/)).toBeNull();
    expect(screen.queryByRole("alert")).toBeNull();
  });
});

const event = (summary: string, start: string, end: string, allDay = false): CalendarEvent => ({
  id: `personal/${summary}.ics`,
  uid: summary,
  etag: '"1"',
  calendar: "personal",
  calendar_name: "Osobiste",
  color: "#00679e",
  writable: true,
  summary,
  location: "",
  description: "",
  start,
  end,
  all_day: allDay,
  recurring: false,
  recurrence_id: null,
});

describe("Kalendarz – siatka i układ", () => {
  it("liczy tydzień od poniedziałku i siatkę miesiąca", () => {
    expect(isoDay(startOfWeek(new Date(2026, 8, 20)))).toBe("2026-09-14");
    expect(isoDay(startOfWeek(new Date(2026, 8, 21)))).toBe("2026-09-21");
    const grid = monthGrid(2026, 8);
    expect(grid).toHaveLength(42);
    expect(isoDay(grid[0])).toBe("2026-08-31");
    const [from, to] = viewRange("tydzien", new Date(2026, 8, 23));
    expect([isoDay(from), isoDay(to)]).toEqual(["2026-09-21", "2026-09-28"]);
    expect(rangeLabel("miesiac", new Date(2026, 8, 5))).toBe("Wrzesień 2026");
  });

  it("przypisuje wydarzenia do dni (koniec wyłączny, całodniowe najpierw)", () => {
    const events = [
      event("Spotkanie", "2026-09-21T10:00", "2026-09-21T11:00"),
      event("Urlop", "2026-09-21", "2026-09-23", true),
      event("Nocka", "2026-09-21T23:00", "2026-09-22T01:00"),
    ];
    expect(eventsOnDay(events, new Date(2026, 8, 21)).map((item) => item.summary)).toEqual(["Urlop", "Spotkanie", "Nocka"]);
    expect(eventsOnDay(events, new Date(2026, 8, 22)).map((item) => item.summary)).toEqual(["Urlop", "Nocka"]);
    expect(eventsOnDay(events, new Date(2026, 8, 23))).toEqual([]);
  });

  it("nakładające się wydarzenia stoją obok siebie", () => {
    const layout = layoutDay(
      [
        event("A", "2026-09-21T10:00", "2026-09-21T11:00"),
        event("B", "2026-09-21T10:30", "2026-09-21T12:00"),
        event("C", "2026-09-21T11:00", "2026-09-21T11:30"),
        event("D", "2026-09-21T14:00", "2026-09-21T15:00"),
      ],
      new Date(2026, 8, 21),
    );
    const byName = Object.fromEntries(layout.map((item) => [item.event.summary, item]));
    expect([byName.A.column, byName.B.column, byName.C.column]).toEqual([0, 1, 0]);
    expect(byName.A.columns).toBe(2);
    expect(byName.D).toMatchObject({ column: 0, columns: 1, top: 14 * 60, bottom: 15 * 60 });
  });

  it("formularz wydarzenia: całodniowe z wyłącznym końcem, godzinowe w czasie lokalnym", () => {
    const allDay = initialForm(event("Urlop", "2026-09-24", "2026-09-26", true), null);
    expect([allDay.startDate, allDay.endDate, allDay.allDay]).toEqual(["2026-09-24", "2026-09-25", true]);
    expect(formToInput(allDay)).toMatchObject({ start: "2026-09-24", end: "2026-09-26", all_day: true });
    const fresh = initialForm(null, { day: new Date(2026, 8, 22), hour: 14 });
    expect(formToInput({ ...fresh, summary: " Dentysta " })).toMatchObject({
      summary: "Dentysta",
      start: "2026-09-22T14:00",
      end: "2026-09-22T15:00",
      all_day: false,
    });
  });
});
