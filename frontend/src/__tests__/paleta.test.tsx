// Paleta poleceń (Ctrl K): pole „Szukaj albo wpisz polecenie” pokazywało zawsze pełną listę,
// bez względu na to, co wpisano — zawężanie nie było nigdzie podpięte.

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import type { ConversationSummary } from "../api";
import type { NavEntry } from "../shell/ModuleNav";
import { Paleta } from "../shell/Paleta";
import { ChatIcon } from "../shell/icons";

afterEach(cleanup);

// jsdom nie ma `HTMLDialogElement.close()`, a paleta zamyka się nim po uruchomieniu pozycji.
const bezZamkniecia = typeof HTMLDialogElement.prototype.close !== "function";
beforeAll(() => {
  if (bezZamkniecia) {
    HTMLDialogElement.prototype.close = function (this: HTMLDialogElement) {
      this.removeAttribute("open");
    };
  }
});
afterAll(() => {
  if (bezZamkniecia) Reflect.deleteProperty(HTMLDialogElement.prototype, "close");
});

const WPISY: NavEntry[] = [
  { id: "poczta", label: "Poczta", description: "Skrzynki, wiadomości i odpowiedzi", icon: ChatIcon },
  { id: "glos", label: "Głos", description: "Rozmowa głosowa z asystentem", icon: ChatIcon },
  { id: "kalendarz", label: "Kalendarz", description: "Spotkania i terminy", icon: ChatIcon },
];
const ROZMOWY: ConversationSummary[] = [
  { id: "r1", title: "Umowa najmu lokalu", updated_at: "2026-09-20T10:00:00+02:00", active: false },
];

function otworz(onSelectEntry: (id: string) => void = () => undefined): HTMLInputElement {
  render(
    <Paleta
      entries={WPISY}
      conversations={ROZMOWY}
      onSelectEntry={onSelectEntry}
      onOpenConversation={() => undefined}
      onNewConversation={() => undefined}
      onToggleTheme={() => undefined}
      onAsk={() => undefined}
    />,
  );
  fireEvent.keyDown(window, { key: "k", ctrlKey: true });
  return screen.getByRole("combobox", { name: /Szukaj/ }) as HTMLInputElement;
}

const etykiety = () => screen.queryAllByRole("option").map((opcja) => opcja.textContent ?? "");

describe("paleta poleceń", () => {
  it("bez zapytania pokazuje wszystko, po wpisaniu — tylko pasujące pozycje", () => {
    const pole = otworz();
    // Dwa polecenia powłoki, trzy moduły i jedna rozmowa.
    expect(etykiety()).toHaveLength(6);
    fireEvent.change(pole, { target: { value: "kalend" } });
    expect(etykiety()).toEqual([expect.stringContaining("Kalendarz")]);
    fireEvent.change(pole, { target: { value: "" } });
    expect(etykiety()).toHaveLength(6);
  });

  it("nie rozróżnia wielkości liter ani polskich znaków", () => {
    const pole = otworz();
    fireEvent.change(pole, { target: { value: "GLOS" } });
    expect(etykiety()).toEqual([expect.stringContaining("Głos")]);
    fireEvent.change(pole, { target: { value: "zmien" } });
    expect(etykiety()).toEqual([expect.stringContaining("Zmień motyw")]);
    // Szuka też w opisie i w tytułach rozmów.
    fireEvent.change(pole, { target: { value: "wiadomości" } });
    expect(etykiety()).toEqual([expect.stringContaining("Poczta")]);
    fireEvent.change(pole, { target: { value: "najmu" } });
    expect(etykiety()).toEqual([expect.stringContaining("Umowa najmu lokalu")]);
  });

  it("po zawężeniu zaznacza pierwszą pozycję, a strzałki i Enter działają na zawężonej liście", () => {
    const wybrany = vi.fn();
    const pole = otworz(wybrany);
    fireEvent.keyDown(pole, { key: "ArrowDown" });
    fireEvent.keyDown(pole, { key: "ArrowDown" });
    // „rozmow” pasuje do „Nowa rozmowa” i do opisu modułu Głos.
    fireEvent.change(pole, { target: { value: "rozmów" } });
    const opcje = screen.getAllByRole("option");
    expect(opcje.map((opcja) => opcja.textContent)).toEqual([
      expect.stringContaining("Nowa rozmowa"),
      expect.stringContaining("Głos"),
    ]);
    expect(pole.getAttribute("aria-activedescendant")).toBe(opcje[0]!.id);
    expect(opcje[0]!.getAttribute("aria-selected")).toBe("true");

    fireEvent.keyDown(pole, { key: "ArrowDown" });
    expect(pole.getAttribute("aria-activedescendant")).toBe(opcje[1]!.id);
    fireEvent.keyDown(pole, { key: "Enter" });
    expect(wybrany).toHaveBeenCalledWith("glos");
  });

  it("bez dopasowań mówi, że nic nie pasuje", () => {
    const pole = otworz();
    fireEvent.change(pole, { target: { value: "xyz-nie-ma" } });
    expect(etykiety()).toHaveLength(0);
    expect(screen.getByText(/Nic nie pasuje do/)).toBeTruthy();
  });
});
