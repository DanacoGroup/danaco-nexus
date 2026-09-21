// Montaż filmu w Studiu: kolejność ujęć, treść polecenia dla asystenta i liczenie długości.

import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MontazPanel, montazPrompt, type Ujecie } from "../modules/studio/Montaz";
import type { FileInfo } from "../api";

function plik(nazwa: string): FileInfo {
  return { id: nazwa, name: nazwa, mime: "image/jpeg", size: 1000 } as FileInfo;
}

function ujecie(nazwa: string, napis = "", lektor = ""): Ujecie {
  return { plik: plik(nazwa), sekundy: 4, napis, lektor, ruch: "najazd" };
}

const USTAWIENIA = { tytul: "Pracownia Kowalscy", kadr: "9:16" as const, przejscie: "fade", nastroj: "korporacyjny" };

describe("polecenie montażu", () => {
  it("wymienia ujęcia w kolejności i podaje ich czas, ruch oraz napis", () => {
    const tekst = montazPrompt([ujecie("hala.jpg", "Własna hala"), ujecie("stol.jpg")], USTAWIENIA);

    expect(tekst).toContain("video_compose");
    expect(tekst.indexOf("hala.jpg")).toBeLessThan(tekst.indexOf("stol.jpg"));
    expect(tekst).toContain("1. „hala.jpg” — 4.0 s, ruch: najazd, napis: „Własna hala”");
    expect(tekst).toContain("Kadr: 9:16");
    expect(tekst).toContain("Napis otwierający: „Pracownia Kowalscy”");
  });

  it("przy wybranym nastroju każe dobrać podkład z biblioteki serwera, a nie prosić o plik", () => {
    const tekst = montazPrompt([ujecie("a.jpg")], USTAWIENIA);

    expect(tekst).toContain("asset_library");
    expect(tekst).toContain("korporacyjny");
  });

  it("zdanie lektora trafia do polecenia razem z ujęciem", () => {
    const tekst = montazPrompt([ujecie("hala.jpg", "Własna hala", "Robimy meble na wymiar.")], USTAWIENIA);

    expect(tekst).toContain("lektor czyta: „Robimy meble na wymiar.”");
  });

  it("bez nastroju mówi wprost, że film jest bez podkładu", () => {
    const tekst = montazPrompt([ujecie("a.jpg")], { ...USTAWIENIA, nastroj: "" });

    expect(tekst).toContain("bez podkładu");
    expect(tekst).not.toContain("asset_library");
  });
});

describe("panel montażu", () => {
  // Vitest działa tu bez `globals`, więc sprzątanie po renderze trzeba zlecić wprost.
  afterEach(cleanup);

  function wyswietl(ujecia: Ujecie[], onZmiana = vi.fn()) {
    render(
      <MontazPanel
        ujecia={ujecia}
        onZmiana={onZmiana}
        onDodano={vi.fn()}
        onBlad={vi.fn()}
        ustawienia={USTAWIENIA}
        onUstawienia={vi.fn()}
        onZloz={vi.fn()}
        zajete={false}
      />,
    );
    return onZmiana;
  }

  it("bez ujęć pokazuje, co z modułu wyjdzie, zamiast samego pola na plik", () => {
    wyswietl([]);

    expect(screen.getByText("Filmik promocyjny")).toBeTruthy();
    expect(screen.getByText("Rolka 9:16")).toBeTruthy();
  });

  it("liczy długość filmu z przenikaniami, a nie samą sumę ujęć", () => {
    wyswietl([ujecie("a.jpg"), ujecie("b.jpg"), ujecie("c.jpg")]);

    // 3 × 4 s minus dwa przenikania po 0,6 s ≈ 11 s.
    expect(screen.getByText(/około 11 s/)).toBeTruthy();
  });

  it("strzałka zamienia ujęcia miejscami", () => {
    const onZmiana = wyswietl([ujecie("a.jpg"), ujecie("b.jpg")]);

    fireEvent.click(screen.getByLabelText("Przesuń ujęcie 2 w górę"));

    expect(onZmiana.mock.calls[0][0].map((u: Ujecie) => u.plik.name)).toEqual(["b.jpg", "a.jpg"]);
  });

  it("usunięcie ujęcia zostawia resztę w kolejności", () => {
    const onZmiana = wyswietl([ujecie("a.jpg"), ujecie("b.jpg"), ujecie("c.jpg")]);

    fireEvent.click(screen.getByLabelText("Usuń ujęcie 2"));

    expect(onZmiana.mock.calls[0][0].map((u: Ujecie) => u.plik.name)).toEqual(["a.jpg", "c.jpg"]);
  });
});
