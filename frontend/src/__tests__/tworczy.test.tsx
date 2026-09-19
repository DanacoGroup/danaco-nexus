import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { BeforeAfter } from "../modules/_tworczy/BeforeAfter";
import { requestJson, waitForJob, type JobState } from "../modules/_tworczy/http";
import {
  ffmpegTime,
  formatTime,
  isValidAddress,
  isVideo,
  parseTime,
  sitePrefix,
  slugify,
  stripSitePrefix,
  studioPrompt,
  worthTranslating,
  type StudioOptions,
} from "../modules/_tworczy/logic";
import { MODULES } from "../modules/registry";

describe("adresy stron", () => {
  it("tworzy adres z polskiego tytułu zgodny z walidacją serwera", () => {
    expect(slugify("Kawiarnia Pod Lipą – Łódź!")).toBe("kawiarnia-pod-lipa-lodz");
    expect(slugify("Żółć")).toBe("zolc");
    expect(slugify("!!!")).toBe("strona");
    expect(slugify("a".repeat(60))).toHaveLength(48);
    expect(isValidAddress(slugify("Pensjonat Żuraw 2026"))).toBe(true);
  });

  it("odrzuca niepoprawne adresy", () => {
    for (const bad of ["-a", "a-", "Duże", "ze spacją", "a_b", "", "a".repeat(49)]) {
      expect(isValidAddress(bad)).toBe(false);
    }
  });

  it("dokleja i ukrywa znacznik strony w wiadomości", () => {
    const text = sitePrefix("sklep") + "Dodaj cennik";
    expect(text).toBe("[Strona: sklep]\nDodaj cennik");
    expect(stripSitePrefix(text)).toBe("Dodaj cennik");
    expect(stripSitePrefix("Zwykła wiadomość")).toBe("Zwykła wiadomość");
  });
});

describe("czas nagrań", () => {
  it("formatuje i odczytuje czas", () => {
    expect(formatTime(0)).toBe("0:00");
    expect(formatTime(75.4)).toBe("1:15.4");
    expect(formatTime(3725)).toBe("1:02:05");
    expect(formatTime(59.96)).toBe("1:00");
    expect(parseTime("1:15.4")).toBeCloseTo(75.4);
    expect(parseTime("1:02:05")).toBe(3725);
    expect(parseTime("90")).toBe(90);
    expect(parseTime("1:75")).toBeNull();
    expect(parseTime("abc")).toBeNull();
  });

  it("zapisuje czas dla FFmpeg zgodnie z walidacją narzędzia", () => {
    expect(ffmpegTime(75.4)).toBe("00:01:15.4");
    expect(ffmpegTime(3725)).toBe("01:02:05");
    expect(ffmpegTime(0)).toMatch(/^\d{1,2}(:\d{2}){0,2}(\.\d+)?$/);
  });

  it("buduje polecenia Studia z zakresem i językiem", () => {
    const options: StudioOptions = { language: "pl", subtitleFormat: "vtt", format: "mp3", start: 30, end: 120, withNotes: true };
    expect(studioPrompt("trim", { ...options, format: "" }, "spotkanie.mp4")).toContain("od 00:00:30 do 00:02:00");
    expect(studioPrompt("subtitles", options, "film.mp4")).toContain("VTT");
    expect(studioPrompt("summary", options, "a.mp3")).toContain("DOCX");
    expect(studioPrompt("transcribe", { ...options, language: "auto" }, "a.mp3")).toContain("wykryj język");
    expect(isVideo("application/octet-stream", "film.MOV")).toBe(true);
    expect(isVideo("audio/mpeg", "a.mp3")).toBe(false);
  });

  it("nie tłumaczy ponownie tego samego tekstu", () => {
    expect(worthTranslating("  Dzień dobry ", "Dzień dobry")).toBe(false);
    expect(worthTranslating("Dzień dobry!", "Dzień dobry")).toBe(true);
    expect(worthTranslating("   ", "")).toBe(false);
  });
});

describe("zadania modułów", () => {
  afterEach(() => vi.restoreAllMocks());

  it("odpytuje zadanie aż do zakończenia", async () => {
    vi.useFakeTimers();
    const states: JobState[] = [
      { id: "j1", kind: "x", status: "running", progress: "50%", error: "", result: null },
      { id: "j1", kind: "x", status: "done", progress: "", error: "", result: { summary: "ok", files: [] } },
    ];
    const fetchMock = vi.fn().mockImplementation(async () => new Response(JSON.stringify(states.shift())));
    vi.stubGlobal("fetch", fetchMock);
    const progress: string[] = [];
    const promise = waitForJob("/api/obrazy", { ...states[0], progress: "" }, (state) => progress.push(state.status));
    await vi.runAllTimersAsync();
    const final = await promise;
    expect(final.status).toBe("done");
    expect(progress).toEqual(["running", "done"]);
    expect(fetchMock.mock.calls[0][0]).toBe("/api/obrazy/zadania/j1");
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("przekazuje komunikat błędu serwera", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "Strona już istnieje." }), { status: 409 })));
    await expect(requestJson("POST", "/api/strony", {})).rejects.toThrow("Strona już istnieje.");
    vi.unstubAllGlobals();
  });
});

describe("komponenty", () => {
  it("suwak przed/po reaguje na klawiaturę", () => {
    render(<BeforeAfter before="/a.png" after="/b.png" alt="Zdjęcie" />);
    const slider = screen.getByRole("slider");
    expect(slider.getAttribute("aria-valuenow")).toBe("50");
    fireEvent.keyDown(slider, { key: "ArrowRight" });
    expect(slider.getAttribute("aria-valuenow")).toBe("55");
    fireEvent.keyDown(slider, { key: "ArrowLeft" });
    fireEvent.keyDown(slider, { key: "ArrowLeft" });
    expect(slider.getAttribute("aria-valuenow")).toBe("45");
  });

  it("rejestruje moduły twórcze", () => {
    const ids = MODULES.map((item) => item.id);
    for (const id of ["strony", "obrazy", "tlumacz", "studio"]) expect(ids).toContain(id);
    expect(ids).not.toContain("_tworczy");
  });
});
